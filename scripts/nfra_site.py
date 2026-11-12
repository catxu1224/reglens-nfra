from pathlib import Path
import threading
import requests, json, re, time, random
from bs4 import BeautifulSoup
from urllib.parse import urljoin

base="https://www.nfra.gov.cn"
api_bases=[base,"https://big5.nfra.gov.cn"]
http=requests.Session()
http.headers.update({
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
    "Accept":"application/json, text/plain, */*",
    "Referer":"https://www.nfra.gov.cn/cn/view/pages/ItemList.html?itemId=931",
})
root=Path(__file__).resolve().parent.parent
cache=root/"work"/"nfra_details"
cache.mkdir(parents=True,exist_ok=True)
aliases={
"source_row_no":r"^序号$", "party_name":r"当事人|被处罚|被罚", "decision_no":r"决定书文号|处罚文号",
"violation_text":r"违法|违规|案由", "legal_basis":r"依据", "penalty_text":r"处罚内容|处罚结果|处罚决定$",
"decision_authority":r"决定机关|处罚机关", "decision_date":r"决定时间|决定日期|处罚日期"}
rate_lock=threading.Lock()
next_request=0.0
def get(path, **params):
    global next_request
    for attempt in range(3):
        try:
            with rate_lock:
                time.sleep(max(0,next_request-time.monotonic()))
                next_request=time.monotonic()+0.35
            response=None
            for api_base in api_bases:
                request_headers={"Referer":f"{api_base}/cn/view/pages/ItemList.html?itemId=931"}
                if "SelectByDocId" in path and params.get("docId"):
                    request_headers["Referer"]=f"{api_base}/cn/view/pages/ItemDetail.html?docId={params['docId']}"
                candidate=http.get(api_base+path,params=params,headers=request_headers,timeout=25)
                response=candidate
                if candidate.status_code not in (403,429):
                    break
            if response.status_code in (403,429):
                if attempt == 2:
                    response.raise_for_status()
                delay=min(30,10*(2**attempt))+random.uniform(0,2)
                with rate_lock:
                    next_request=max(next_request,time.monotonic()+delay)
                continue
            response.raise_for_status()
            result=response.json()
            if result.get("rptCode")==200 and result.get("data") is not None:
                return result["data"]
            raise ValueError(str(result)[:180])
        except (requests.RequestException,ValueError):
            if attempt==2: raise
            time.sleep(min(8,2**attempt)+random.uniform(0,1))
def listing(cutoff, upper=None):
    notices={}
    # 4113: 总局机关，4115: 派出机构旧目录，4293: 派出机构新目录。
    # 新公告仍会出现在 4115；2026-11-05 至 11-12 有 16 篇仅在此目录。
    for item in (4113,4115,4293):
        page=1
        previous=None
        while True:
            rows=get("/cbircweb/DocInfo/SelectDocByItemIdAndChild",itemId=item,pageSize=20,pageIndex=page)["rows"]
            ids=tuple(r["docId"] for r in rows)
            if ids and ids==previous: raise RuntimeError(f"Repeated page {item}/{page}")
            previous=ids
            for r in rows:
                day=r["publishDate"][:10]
                if day>=cutoff and (upper is None or day<upper): notices.setdefault(str(r["docId"]),(item,r))
            if not rows or max(r["publishDate"][:10] for r in rows)<cutoff: break
            page+=1
        print(item,page,len(notices),flush=True)
    return notices
def label(text):
    text=re.sub(r"\s+","",text)
    return next((k for k,p in aliases.items() if re.search(p,text)),None)
def grid(table):
    spans={}
    for i,tr in enumerate(table.find_all("tr")):
        if tr.find_parent("table") is not table: continue
        j=0
        for td in tr.find_all(["td","th"],recursive=False):
            while (i,j) in spans: j+=1
            value=td.get_text(" ",strip=True)
            width=int(td.get("colspan",1) or 1)
            for a in range(min(int(td.get("rowspan",1) or 1),100)):
                for b in range(min(width,100)): spans[i+a,j+b]=value
            j+=width
        yield [spans.get((i,k),"") for k in range(max((col for row,col in spans if row==i),default=-1)+1)]
def parse(docid, entry, refresh):
    item,r=entry
    path=cache/(docid+".json")
    if refresh or not path.exists():
        d=get("/cbircweb/DocInfo/SelectByDocId",docId=docid)
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d,ensure_ascii=False),encoding="utf-8")
        tmp.replace(path)
    else: d=json.loads(path.read_text(encoding="utf-8"))
    soup=BeautifulSoup(d.get("docClob") or "","lxml")
    rows=[]
    for table in soup.find_all("table"):
        cols=None
        vertical={}
        for cells in grid(table):
            labels=[label(c) if len(c)<35 else None for c in cells]
            if "party_name" in labels and ("penalty_text" in labels or "violation_text" in labels):
                cols=labels
                continue
            if cols and len(cells)==len(cols):
                row={k:v for k,v in zip(cols,cells) if k and v}
                if row.get("party_name") and (row.get("penalty_text") or row.get("violation_text")):
                    rows.append(row)
            elif labels and labels[0] and len(cells)>1:
                vertical[labels[0]]=cells[-1]
        if vertical.get("party_name") and vertical.get("penalty_text"): rows.append(vertical)
    links=set()
    for a in soup.select("a[href]"):
        href=a["href"]
        if re.search(r"\.(pdf|docx?|xlsx?|zip)(\?|$)",href,re.I): links.add(urljoin(base,href))
    for k in ("docFileUrl","pdfFileUrl"):
        if r.get(k): links.add(urljoin(base,r[k]))
    if not rows: return [],{"doc_id":docid,"title":r.get("docSubtitle"),"attachments":sorted(links)}
    common=dict(doc_id=docid,notice_title=BeautifulSoup(r.get("docSubtitle") or d.get("docTitle") or "","lxml").get_text(" ",strip=True),
                published_date=r["publishDate"][:10],publishing_source=d.get("docSource") or "",
                notice_url=f"{base}/cn/view/pages/ItemDetail.html?docId={docid}",attachment_urls=json.dumps(sorted(links),ensure_ascii=False))
    for row in rows:
        row.update(common)
        m=re.fullmatch(r"\s*(\d{4})\s*[-年/.]\s*(\d{1,2})\s*[-月/.]\s*(\d{1,2})日?\s*",row.get("decision_date",""))
        if m: row["decision_date"]="-".join([m[1],m[2].zfill(2),m[3].zfill(2)])
    return rows,None
