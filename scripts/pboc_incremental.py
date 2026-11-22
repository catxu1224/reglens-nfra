#!/usr/bin/env python3
"""PBOC headquarters notices: HTML/attachment tables to common penalty seed."""
import argparse, csv, hashlib, json, re, time
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from nfra_site import grid
from nfra_attachments import tables
from nfra_incremental import HEADERS, BUSINESS, classify, raw_for, load_seed, save_seed
from restructure_penalties import build_row, is_person_subject
ROOT=Path(__file__).resolve().parents[1]
DIRECTORY='https://www.pbc.gov.cn/zhengwugongkai/4081330/4081344/4081407/4081705/'
OUTPUT=ROOT/'seeds/pboc_penalties.csv'
CACHE=ROOT/'work/pboc'
LABELS={'序号':'source_row_no','当事人名称':'party_name','企业名称':'party_name','被处罚当事人名称':'party_name','被处罚人名称':'party_name','被处罚单位名称':'party_name','被处罚人姓名':'party_name','姓名':'party_name','单位名称':'party_name','主要违法违规事实':'violation_text','违法行为':'violation_text','行政处罚决定':'penalty_text','处罚内容':'penalty_text','处罚决定':'penalty_text','行政处罚机关名称':'decision_authority','作出行政处罚决定的机关名称':'decision_authority','行政处罚决定日期':'decision_date','作出行政处罚决定的日期':'decision_date','行政处罚决定书文号':'decision_no','违法行为类型':'violation_text','行政处罚内容':'penalty_text','作出行政处罚决定机关名称':'decision_authority','作出行政处罚决定日期':'decision_date','公示期限':'disclosure_period','备注':'remarks','处罚依据':'legal_basis'}

def normalize_label(value):
    return LABELS.get(re.sub(r'\s+','',value or ''))

def extract(matrices):
    result=[]; columns=None
    for matrix in matrices:
        vertical={}
        for cells in matrix:
            cells=[re.sub(r'\s+','',str(x) if x is not None else '') for x in cells]
            labels=[normalize_label(x) for x in cells]
            if 'party_name' in labels and 'penalty_text' in labels:
                columns=labels;continue
            if columns and len(cells)==len(columns):
                row={key:value for key,value in zip(columns,cells) if key and value}
                if row.get('party_name') and row.get('penalty_text'):result.append(row)
            elif labels and labels[0] and len(cells)>1:
                vertical[labels[0]]=cells[-1]
        if vertical.get('party_name') and vertical.get('penalty_text'):result.append(vertical)
    return result

from pboc_http import Client

def notices(client,since,until):
    pending=[urljoin(DIRECTORY,'index.html')];seen=set();found={}
    while pending:
        url=pending.pop(0)
        if url in seen:continue
        seen.add(url);soup=client.html(url)
        listing=soup.select('a[istitle="true"]')
        if not listing:raise ValueError('No notice links on '+url)
        days=[]
        for a in listing:
            li=a.find_parent('li') or a.find_parent('tr');match=re.search(r'\d{4}-\d{2}-\d{2}',li.get_text())
            if not match:raise ValueError('Missing publication date')
            day=match[0];days.append(day)
            if since<=day<until:found[urljoin(url,a['href'])]=(day,a.get_text(strip=True))
        for a in [a for a in soup.select('a') if a.get('title')=='下一页' or a.get_text(strip=True)=='下一页']:
            target=a.get('tagname') or a.get('href')
            if target and max(days)>=since:pending.append(urljoin(url,target))
        print('listing',len(seen),'notices',len(found),flush=True)
    return found

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--since',default='2024-01-01');parser.add_argument('--until',default=None);parser.add_argument('--interval',type=float,default=60);parser.add_argument('--dry-run',action='store_true');args=parser.parse_args()
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date()
    from datetime import timedelta
    until=args.until or (today+timedelta(days=1)).isoformat()
    if not '2024-01-01'<=args.since<until:raise ValueError('Invalid date range')
    client=Client(args.interval);CACHE.mkdir(parents=True,exist_ok=True)
    found=notices(client,args.since,until)
    if not found:
        print(json.dumps({'notices':0,'changed':0,'since':args.since,'until':until}));return
    old=load_seed(OUTPUT);by_key={r['source_key']:r for r in old};generated=[];audit=[];issues=[]
    for url,(day,title) in found.items():
        try:
            path=CACHE/(hashlib.sha256(url.encode()).hexdigest()+'.html')
            # Always refresh network data; cached bodies remain available for audit.
            body=client.get(url);path.write_bytes(body);soup=BeautifulSoup(body,'lxml',from_encoding='utf-8')
            content=soup.select_one('#zoom') or soup.select_one('.TRS_Editor') or soup
            source=extract(grid(t) for t in content.find_all('table'))
            if not source:
                links={urljoin(url,a['href']) for a in content.select('a[href]') if re.search(r'\.(?:docx?|pdf)(?:\?|$)',a['href'],re.I)}
                groups={}
                for link in sorted(links):groups.setdefault(Path(urlparse(link).path).stem,[]).append(link)
                for variants in groups.values():
                    extracted=[];errors=[]
                    for link in sorted(variants,key=lambda u:{'.docx':0,'.doc':1,'.pdf':2}.get(Path(urlparse(u).path).suffix.lower(),9)):
                        try:
                            extracted=extract(tables(client.get(link),Path(urlparse(link).path).suffix.lower()))
                            if extracted:break
                        except Exception as e:
                            if getattr(getattr(e,'response',None),'status_code',None) in (403,429):raise
                            errors.append(str(e))
                    if not extracted:raise ValueError('Attachment unreadable: '+str(variants)+str(errors))
                    source.extend(extracted)
            if not source:raise ValueError('No penalty rows')
            for row in source:row.update(doc_id=url,notice_url=url,published_date=day,publishing_source='中国人民银行')
            group=[raw_for(row) for row in source];known=[]
            for i,raw in enumerate(group):
                if not is_person_subject(raw['被处罚单位（公司）']):
                    built=build_row(raw,group,i);known.append((built['被处罚单位（公司）'],built['被处罚单位（分行）']))
            keys=set()
            for i,row in enumerate(source):
                identity=row.get('decision_no') or str(i+1)
                for kind,built in classify(row,group,i,known):
                    built['机关']=row.get('decision_authority') or '中国人民银行'
                    built['处罚机关']=built['机关']
                    key=hashlib.sha256(f'PBOC:{url}:{identity}:{row["party_name"]}:{kind}'.encode()).hexdigest()
                    if key in keys:raise ValueError('Duplicate business identity')
                    keys.add(key)
                    previous=by_key.get(key);built['update_time']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
                    if previous and all(previous[k]==built[k] for k in BUSINESS if k!='update_time'):built['update_time']=previous['update_time']
                    generated.append(dict(source_key=key,seed_row_number=previous['seed_row_number'] if previous else '0',**built))
                audit.append(dict(notice_title=title,**row))
            print(day,title,len(source),flush=True)
        except Exception as e:
            issues.append(f'{url}: {e}')
            if getattr(getattr(e,'response',None),'status_code',None) in (403,429):break
    if issues:
        (CACHE/'issues.json').write_text(json.dumps(issues,ensure_ascii=False,indent=2));raise RuntimeError('; '.join(issues))
    merged=[r for r in old if r['处罚书url'] not in found]+generated
    merged.sort(key=lambda r:(r['发布时间'],r['source_key']),reverse=True)
    counter=max([0]+[int(r['seed_row_number']) for r in old])
    for row in merged:
        if row['seed_row_number']=='0':counter+=1;row['seed_row_number']=str(counter)
    if len({r['source_key'] for r in merged})!=len(merged):raise ValueError('Duplicate source key')
    print(json.dumps({'notices':len(found),'generatedRows':len(generated),'seedRows':len(merged)},ensure_ascii=False))
    if not args.dry_run:
        save_seed(OUTPUT,merged)
        # Preserve fields absent from the shared dashboard schema.
        old_audit=ROOT/'seeds/pboc_notice_fields.json'
        previous=json.loads(old_audit.read_text()) if old_audit.exists() else []
        old_audit.write_text(json.dumps([r for r in previous if r['notice_url'] not in found]+audit,ensure_ascii=False,indent=2)+'\n')
if __name__=='__main__':main()
