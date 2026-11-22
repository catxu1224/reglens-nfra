#!/usr/bin/env python3
"""Resumable, budgeted PBOC branch discovery, backfill and daily refresh."""
import argparse,csv,hashlib,json,re,time
from collections import deque
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urljoin,urlparse,urlunparse
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from pboc_http import Client,BudgetReached
from pboc_incremental import extract,grid,tables,raw_for,classify,build_row,is_person_subject,load_seed,save_seed,BUSINESS
ROOT=Path(__file__).resolve().parents[1];REGISTRY=ROOT/'config/pboc_branches.json';STATE=ROOT/'seeds/pboc_crawl_state.json';SEED=ROOT/'seeds/pboc_penalties.csv';AUDIT=ROOT/'seeds/pboc_notice_fields.json';CACHE=ROOT/'work/pboc/branches'
START='2024-01-01'

def canonical(url):
    p=urlparse(url);return urlunparse(('https',p.netloc.lower(),p.path or '/',p.params,p.query,''))

def atomic(path,value):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

def listing(soup,url):
    rows=[]
    for a in soup.select('a[istitle="true"]'):
        container=a.find_parent('li') or a.find_parent('tr') or a.parent
        match=re.search(r'(20\d{2})[-年/.](\d{1,2})[-月/.](\d{1,2})',container.get_text(' ',strip=True))
        if not match:raise ValueError('Missing publication date: '+a.get_text())
        day=f'{match[1]}-{int(match[2]):02}-{int(match[3]):02}'
        rows.append({'url':canonical(urljoin(url,a['href'])),'day':day,'title':a.get('title') or a.get_text(strip=True)})
    if not rows:raise ValueError('No notice links; directory requires review: '+url)
    next_url=None
    for a in soup.select('a'):
        if a.get('title')=='下一页' or a.get_text(strip=True)=='下一页':
            target=a.get('tagname') or a.get('href')
            if target and not target.startswith('['):next_url=canonical(urljoin(url,target));break
    return rows,next_url

def navigation(soup,url,host):
    penalties=set();navigation=set()
    for a in soup.select('a[href]'):
        text=a.get_text(' ',strip=True) or a.get('title','');href=canonical(urljoin(url,a['href']))
        if urlparse(href).hostname!=host:continue
        if '行政处罚' in text and len(text)<=24 and a.get('istitle')!='true' and not any(word in text for word in ('决定书','裁量','办法','程序','规定')):
            penalties.add(href)
        elif any(word in text for word in ('政务公开','政府信息公开','行政执法')) and not any(word in text for word in ('指南','申请')):navigation.add(href)
    return sorted(penalties),sorted(navigation)

def identity(row):
    number=re.sub(r'\s+','',row.get('文号','')).translate(str.maketrans('〔〕【】','[][]'))
    party=row.get('被处罚个人') if row.get('处罚对象')=='个人' else row.get('被处罚单位（公司）','')+row.get('被处罚单位（分行）','')
    return (number,re.sub(r'\s+','',party or ''),row.get('处罚对象')) if number and party else None

def remove_mirrors(rows,existing,url):
    index={identity(row):row for row in existing if identity(row) and row['处罚书url']!=url}
    output=[]
    for row in rows:
        prior=index.get(identity(row))
        if prior:
            for field in ('违法违规事实','处罚决定','处罚金额'):
                if re.sub(r'\s+','',prior[field])!=re.sub(r'\s+','',row[field]):
                    raise ValueError('Conflicting duplicate decision/party requires review: '+row['文号'])
        else:output.append(row)
    return output

def parse_notice(client,task,old):
    url=task['url'];cached=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
    if task.get('refresh'):cached=CACHE/(hashlib.sha256((url+':'+datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()).encode()).hexdigest()+'.html')
    if cached.exists():body=cached.read_bytes()
    else:
        body=client.get(url);cached.write_bytes(body)
    soup=BeautifulSoup(body,'lxml');content=soup.select_one('#zoom') or soup.select_one('.TRS_Editor') or soup
    source=extract(grid(t) for t in content.find_all('table'))
    if not source:
        groups={}
        for a in content.select('a[href]'):
            link=canonical(urljoin(url,a['href']));suffix=Path(urlparse(link).path).suffix.lower()
            if suffix in ('.doc','.docx','.wps','.rtf','.pdf','.xls','.xlsx'):groups.setdefault(Path(urlparse(link).path).stem,[]).append(link)
        for variants in groups.values():
            extracted=[];errors=[]
            for link in sorted(set(variants),key=lambda u:{'.docx':0,'.doc':1,'.wps':2,'.rtf':3,'.xlsx':4,'.xls':5,'.pdf':6}[Path(urlparse(u).path).suffix.lower()]):
                try:
                    suffix=Path(urlparse(link).path).suffix.lower();version=link+(':'+datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat() if task.get('refresh') else '')
                    file=CACHE/(hashlib.sha256(version.encode()).hexdigest()+suffix)
                    if not file.exists():file.write_bytes(client.get(link))
                    extracted=extract(tables(file.read_bytes(),suffix))
                    if extracted:break
                except BudgetReached:raise
                except Exception as error:
                    if getattr(getattr(error,'response',None),'status_code',None) in (403,429):raise
                    errors.append(str(error))
            if not extracted:raise ValueError('Unparsed attachment '+str(variants)+str(errors))
            source.extend(extracted)
    if not source:raise ValueError('No readable penalty table; scanned image/PDF may need OCR')
    for row in source:row.update(doc_id=url,notice_url=url,published_date=task['day'],publishing_source=task['branch'])
    group=[raw_for(row) for row in source];known=[]
    for i,raw in enumerate(group):
        if not is_person_subject(raw['被处罚单位（公司）']):
            built=build_row(raw,group,i);known.append((built['被处罚单位（公司）'],built['被处罚单位（分行）']))
    rows=[];keys=set()
    for i,row in enumerate(source):
        for kind,built in classify(row,group,i,known):
            built['机关']=built['处罚机关']=row.get('decision_authority') or '中国人民银行'+task['branch']
            identity=row.get('decision_no') or str(i+1)
            key=hashlib.sha256(f'PBOC:{url}:{identity}:{row["party_name"]}:{kind}'.encode()).hexdigest()
            if key in keys:raise ValueError('Duplicate penalty identity')
            keys.add(key);previous=old.get(key)
            built['update_time']=previous['update_time'] if previous and all(previous[k]==built[k] for k in BUSINESS if k!='update_time') else datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
            rows.append(dict(source_key=key,seed_row_number=previous['seed_row_number'] if previous else '0',**built))
    return rows,[dict(notice_title=task['title'],branch=task['branch'],**row) for row in source]

def main():
    import fcntl
    lock_path=ROOT/'work/pboc/branch-worker.lock';lock_path.parent.mkdir(parents=True,exist_ok=True)
    worker_lock=lock_path.open('a+')
    try:fcntl.flock(worker_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another branch worker is already running')
    parser=argparse.ArgumentParser();parser.add_argument('--max-requests',type=int,default=300);parser.add_argument('--max-minutes',type=int,default=320);parser.add_argument('--retry-failed',action='store_true');parser.add_argument('--refresh-days',type=int,default=7);args=parser.parse_args()
    registry=json.loads(REGISTRY.read_text());state=json.loads(STATE.read_text()) if STATE.exists() else {'queue':[],'done':{},'listed':{},'failures':{},'discovery_seen':{}}
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat();queue=deque(sorted(state['queue'],key=lambda task:0 if task['kind']=='discover' and task.get('depth',0)>0 else 1));queued={(t['kind'],t['url']) for t in queue}
    def enqueue(task,front=False):
        key=(task['kind'],task['url'])
        if key not in queued:
            (queue.appendleft if front else queue.append)(task);queued.add(key)
    for branch in registry['branches']:
        if branch['directories']:
            for directory in branch['directories']:
                if state['listed'].get(directory)!=today:enqueue({'kind':'list','url':directory,'branch':branch['name'],'home':branch['home'],'daily':directory in state['listed']})
        elif not any(t['branch']==branch['name'] for t in queue):enqueue({'kind':'discover','url':branch['home'],'branch':branch['name'],'home':branch['home'],'depth':0})
    if args.retry_failed:
        for value in state['failures'].values():enqueue(value['task'])
    client=Client(60,args.max_requests,args.max_minutes*60);CACHE.mkdir(parents=True,exist_ok=True);seed=load_seed(SEED);audits=json.loads(AUDIT.read_text());by_key={r['source_key']:r for r in seed}
    def checkpoint():
        state['coverage']={b['name']:{'directoryStatus':b['status'],'directories':b['directories'],'parsedNotices':sum(v['branch']==b['name'] for v in state['done'].values()),'pendingTasks':sum(t['branch']==b['name'] for t in queue),'failedTasks':sum(v['task']['branch']==b['name'] for v in state['failures'].values()),'historyComplete':b['status']=='verified' and not any(t['branch']==b['name'] for t in queue) and not any(v['task']['branch']==b['name'] for v in state['failures'].values())} for b in registry['branches']}
        state['queue']=list(queue);state['updated_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
        atomic(STATE,state);atomic(REGISTRY,registry)
    completed=0
    while queue:
        task=queue.popleft();queued.discard((task['kind'],task['url']));url=task['url']
        try:
            if task['kind']=='discover':
                page=CACHE/(hashlib.sha256(('discovery:'+url).encode()).hexdigest()+'.html')
                if not page.exists():page.write_bytes(client.get(url))
                soup=BeautifulSoup(page.read_bytes(),'lxml');branch=next(b for b in registry['branches'] if b['home']==task['home']);penalties,nav=navigation(soup,url,urlparse(branch['home']).hostname)
                penalties=[link for link in penalties if link not in state['failures']]
                state['discovery_seen'][url]=True
                if penalties:
                    branch['directories']=sorted(set(branch['directories'])|set(penalties));branch['status']='discovered'
                    queue=deque(t for t in queue if not(t['kind']=='discover' and t['home']==task['home']))
                    queued={(t['kind'],t['url']) for t in queue}
                    state['failures']={u:v for u,v in state['failures'].items() if not(v['task']['kind']=='discover' and v['task']['home']==task['home'])}
                    for directory in penalties:enqueue(dict(kind='list',url=directory,branch=task['branch'],home=task['home'],daily=False),front=True)
                elif task['depth']<2:
                    added=0
                    for link in nav[:6]:
                        if link not in state['discovery_seen']:enqueue(dict(task,url=link,depth=task['depth']+1),front=True);added+=1
                    if not added:raise ValueError('No punishment directory found; manual review required')
                else:raise ValueError('Discovery depth exhausted; manual review required')
            elif task['kind']=='list':
                page=CACHE/(hashlib.sha256(('listing:'+today+':'+url).encode()).hexdigest()+'.html')
                if not page.exists():page.write_bytes(client.get(url))
                rows,next_url=listing(BeautifulSoup(page.read_bytes(),'lxml'),url);new=False
                for entry in rows:
                    if START<=entry['day']<=today:
                        refresh=entry['day']>=(datetime.fromisoformat(today)-timedelta(days=args.refresh_days)).date().isoformat()
                        if entry['url'] not in state['done'] or refresh:
                            enqueue(dict(entry,kind='notice',branch=task['branch'],home=task['home'],refresh=refresh));new=True
                state['listed'][url]=today
                if next_url and max(r['day'] for r in rows)>=START and (not task.get('daily') or new):enqueue(dict(task,url=next_url))
                for branch in registry['branches']:
                    if branch['home']==task['home']:branch['status']='verified'
            else:
                rows,raw=parse_notice(client,task,by_key)
                rows=remove_mirrors(rows,seed,url)
                seed=[r for r in seed if r['处罚书url']!=url]+rows;seed.sort(key=lambda r:(r['发布时间'],r['source_key']),reverse=True)
                number=max([0]+[int(r['seed_row_number']) for r in seed])
                for row in seed:
                    if row['seed_row_number']=='0':number+=1;row['seed_row_number']=str(number)
                if len({r['source_key'] for r in seed})!=len(seed):raise ValueError('Duplicate seed key')
                audits=[r for r in audits if r['notice_url']!=url]+raw
                save_seed(SEED,seed);atomic(AUDIT,audits);by_key={r['source_key']:r for r in seed}
                state['done'][url]={'branch':task['branch'],'date':task['day'],'rows':len(rows)};completed+=1
            state['failures'].pop(url,None)
            print(json.dumps({'kind':task['kind'],'url':url,'requests':client.count,'remaining':len(queue),'seedRows':len(seed)},ensure_ascii=False),flush=True)
        except BudgetReached:
            queue.appendleft(task);checkpoint();print('Paused at request/time budget; checkpoint saved',flush=True);break
        except Exception as error:
            state['failures'][url]={'task':task,'error':str(error),'last_attempt':today};print('FAILED '+url+': '+str(error),flush=True)
            checkpoint()
            if getattr(getattr(error,'response',None),'status_code',None) in (403,429):print('Website blocked this batch; stopping without retry storm',flush=True);break
        checkpoint()
    checkpoint()
    print(json.dumps({'completedThisBatch':completed,'seedRows':len(seed),'pending':len(queue),'failures':len(state['failures']),'verifiedBranches':sum(b['status']=='verified' for b in registry['branches']),'totalBranches':len(registry['branches'])},ensure_ascii=False),flush=True)
    if state['failures']:
        raise SystemExit(2)
if __name__=='__main__':main()
