import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pboc_branches import listing,navigation,remove_mirrors
from pboc_http import Client,BudgetReached
import requests

class BranchTests(unittest.TestCase):
    def test_legacy_table_listing_and_href_pagination(self):
        soup=BeautifulSoup('<table><tr><td><a istitle="true" title="完整标题" href="/notice/index.html">截断标题</a></td><td>2024-01-02</td></tr></table><a href="/list/123-2.html">下一页</a>','lxml')
        rows,next_url=listing(soup,'https://beijing.pbc.gov.cn/list/index.html')
        self.assertEqual(rows[0]['day'],'2024-01-02');self.assertEqual(rows[0]['title'],'完整标题')
        self.assertEqual(next_url,'https://beijing.pbc.gov.cn/list/123-2.html')
    def test_discovery_distinguishes_directory_and_notice(self):
        soup=BeautifulSoup('<a href="/disclosure/">政务公开</a><a href="/punishments/index.html">行政处罚</a><a istitle="true" href="/notice/">行政处罚公示表</a><a href="https://evil.example/">行政处罚</a>','lxml')
        directories,nav=navigation(soup,'https://beijing.pbc.gov.cn/','beijing.pbc.gov.cn')
        self.assertEqual(directories,['https://beijing.pbc.gov.cn/punishments/index.html']);self.assertEqual(len(nav),1)
    def test_all_hosts_redirects_and_process_clients_share_rate_clock(self):
        now=[1000.0];starts=[]
        def sleep(delay):now[0]+=delay
        def download(url,**kwargs):
            starts.append(now[0]);self.assertFalse(kwargs['allow_redirects'])
            return Mock(status_code=200,content=b'ok')
        with tempfile.TemporaryDirectory() as directory,patch('pboc_http.time.time',side_effect=lambda:now[0]),patch('pboc_http.time.sleep',side_effect=sleep):
            a=Client();b=Client();a.clock=b.clock=Path(directory)/'clock.json'
            a.session.get=download;b.session.get=download
            a.get('https://beijing.pbc.gov.cn/');b.get('https://shanghai.pbc.gov.cn/');a.get('https://www.pbc.gov.cn/a.pdf')
        self.assertEqual(starts,[1000.0,1060.0,1120.0])
    def test_403_is_not_retried_in_same_batch(self):
        client=Client();response=Mock(status_code=403);response.raise_for_status.side_effect=requests.HTTPError('403',response=response)
        client.session.get=Mock(return_value=response)
        with patch.object(client,'_gate'):
            with self.assertRaises(requests.HTTPError):client.get('https://beijing.pbc.gov.cn/')
        self.assertEqual(client.session.get.call_count,1)
    def test_budget_stops_before_network(self):
        client=Client(max_requests=0);client.session.get=Mock()
        with self.assertRaises(BudgetReached):client.get('https://beijing.pbc.gov.cn/')
        client.session.get.assert_not_called()
    def test_frequency_cannot_be_lower_than_one_minute(self):
        with self.assertRaises(ValueError):Client(1)

    def test_mirrored_decisions_are_not_counted_twice(self):
        row={'文号':'京罚〔2024〕1号','被处罚单位（公司）':'甲银行','被处罚单位（分行）':'','处罚对象':'机构','违法违规事实':'违规','处罚决定':'罚款1万元','处罚金额':'10000','处罚书url':'https://beijing.pbc.gov.cn/a'}
        mirror=dict(row,处罚书url='https://beijing.pbc.gov.cn/b')
        self.assertEqual(remove_mirrors([mirror],[row],mirror['处罚书url']),[])
        mirror['处罚金额']='20000'
        with self.assertRaises(ValueError):remove_mirrors([mirror],[row],mirror['处罚书url'])

    def test_same_number_from_different_authorities_is_not_a_mirror(self):
        row={'文号':'银罚〔2024〕1号','被处罚单位（公司）':'甲银行','被处罚单位（分行）':'','处罚对象':'机构','处罚机关':'中国人民银行北京市分行','违法违规事实':'违规','处罚决定':'罚款1万元','处罚金额':'10000','处罚书url':'https://beijing.pbc.gov.cn/a'}
        other=dict(row,处罚机关='中国人民银行天津市分行',处罚书url='https://tianjin.pbc.gov.cn/a')
        self.assertEqual(remove_mirrors([other],[row],other['处罚书url']),[other])
