"""One persisted rate gate for every PBOC host, retry and redirect."""
import fcntl,json,time
from pathlib import Path
import requests

class BudgetReached(Exception):pass

class Client:
    def __init__(self,interval=60,max_requests=None,max_seconds=None):
        if interval<60:raise ValueError('PBOC requests must be at least 60 seconds apart')
        self.interval=interval;self.max_requests=max_requests;self.count=0
        self.deadline=time.monotonic()+max_seconds if max_seconds else None
        self.session=requests.Session();self.session.headers.update({'User-Agent':'Mozilla/5.0','Accept':'text/html,application/pdf,*/*'})
        self.clock=Path(__file__).resolve().parents[1]/'work/pboc/request-clock.json'
    def _gate(self):
        if self.max_requests is not None and self.count>=self.max_requests:raise BudgetReached('request budget reached')
        self.clock.parent.mkdir(parents=True,exist_ok=True)
        with self.clock.open('a+') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX);handle.seek(0)
            raw=handle.read()
            try:
                if raw:last=float(json.loads(raw)['last'])
                else:
                    state=Path(__file__).resolve().parents[1]/'seeds/pboc_crawl_state.json'
                    last=float(json.loads(state.read_text()).get('requestClock',0)) if state.exists() else 0
            except (ValueError,KeyError):last=time.time()
            delay=max(0,last+self.interval-time.time())
            if self.deadline and time.monotonic()+delay>=self.deadline:raise BudgetReached('time budget reached')
            time.sleep(delay);handle.seek(0);handle.truncate();json.dump({'last':time.time()},handle);handle.flush()
        self.count+=1
    def get(self,url):
        from urllib.parse import urljoin,urlparse
        for attempt in range(3):
            try:
                current=url
                for redirect in range(6):
                    parsed=urlparse(current)
                    if parsed.scheme not in ('http','https') or not (parsed.hostname=='pbc.gov.cn' or (parsed.hostname or '').endswith('.pbc.gov.cn')):raise ValueError('Non-PBOC URL rejected: '+current)
                    self._gate()
                    response=self.session.get(current,timeout=40,allow_redirects=False)
                    if response.status_code in (301,302,303,307,308):
                        current=urljoin(current,response.headers['Location']);continue
                    response.raise_for_status();return response.content
                raise ValueError('Too many redirects')
            except requests.RequestException as error:
                if getattr(error.response,'status_code',None) in (403,429):
                    # Stop this batch instead of repeatedly probing a blocked host.
                    raise
                if attempt==2:raise
        raise RuntimeError('Request failed')
    def html(self,url):
        from bs4 import BeautifulSoup
        return BeautifulSoup(self.get(url),'lxml')
