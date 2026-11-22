#!/usr/bin/env python3
"""Emit a complete-history manifest only after every branch passes coverage checks."""
import csv,hashlib,json
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo
from pboc_branches import identity,atomic
ROOT=Path(__file__).resolve().parents[1]

def validate():
    state=json.loads((ROOT/'seeds/pboc_crawl_state.json').read_text())
    catalog=json.loads((ROOT/'config/pboc_branches.json').read_text());registry=catalog['branches']
    issues=[]
    if len(registry)!=catalog.get("expectedBranchCount",36):issues.append("Official branch count does not match expected scope")
    if state['queue']:issues.append(f"{len(state['queue'])} pending tasks")
    if state['failures']:issues.append(f"{len(state['failures'])} unresolved failures")
    for branch in registry:
        progress=state.get('coverage',{}).get(branch['name'],{})
        if branch['status']!='verified' or not progress.get('historyComplete') or not progress.get('parsedNotices',0):
            issues.append('Incomplete branch: '+branch['name'])
    if issues:return None,issues
    path=ROOT/'seeds/pboc_penalties.csv'
    with path.open(encoding='utf-8-sig',newline='') as handle:rows=list(csv.DictReader(handle))
    for field in ('source_key','seed_row_number'):
        if len({r[field] for r in rows})!=len(rows):issues.append('Duplicate '+field)
    identities=Counter(identity(row) for row in rows if identity(row))
    if any(count>1 for count in identities.values()):issues.append('Duplicate authority/decision/party')
    today=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    if any(not '2024-01-01'<=row['发布时间']<=today for row in rows):issues.append('Publication date out of range')
    allowed={urlparse(b['home']).hostname for b in registry}|{'www.pbc.gov.cn'}
    if any(urlparse(row['处罚书url']).hostname not in allowed for row in rows):issues.append('Unregistered source host')
    for url,value in state['done'].items():
        if value['rows'] and not any(r['处罚书url']==url for r in rows):issues.append('Parsed notice absent from seed: '+url)
    if issues:return None,issues
    counts=Counter(urlparse(row['处罚书url']).hostname for row in rows)
    manifest={'status':'complete','periodStart':'2024-01-01','checkedThrough':today,'rows':len(rows),'totalBranches':len(registry),'seedSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'branches':[{'name':b['name'],'directories':b['directories'],'rows':counts[urlparse(b['home']).hostname]} for b in registry]}
    return manifest,[]

def main():
    manifest,issues=validate();path=ROOT/'seeds/pboc_complete_history.json'
    if manifest:
        atomic(path,manifest);print(json.dumps(manifest,ensure_ascii=False))
    else:
        path.unlink(missing_ok=True)
        print(json.dumps({'status':'incomplete','reasons':issues},ensure_ascii=False))
        state=json.loads((ROOT/'seeds/pboc_crawl_state.json').read_text())
        if not state['queue']:raise SystemExit(2)
if __name__=='__main__':main()
