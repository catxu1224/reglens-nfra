import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import nfra_site


class RequestRateTests(unittest.TestCase):
    def test_primary_mirror_retry_and_attachment_share_one_minute_limit(self):
        now = [100.0]
        starts = []
        def sleep(seconds):
            now[0] += seconds
        def download(url, **kwargs):
            starts.append(now[0])
            if len(starts) <= 2:
                return Mock(status_code=403)
            return Mock(status_code=200, json=lambda: {'rptCode': 200, 'data': {'ok': True}})
        with patch.object(nfra_site, 'next_request', 0.0), \
             patch.object(nfra_site.time, 'monotonic', side_effect=lambda: now[0]), \
             patch.object(nfra_site.time, 'sleep', side_effect=sleep), \
             patch.object(nfra_site.http, 'get', side_effect=download):
            self.assertEqual(nfra_site.get('/detail'), {'ok': True})
            nfra_site.request('https://www.nfra.gov.cn/notice.doc', timeout=30)
        self.assertEqual(len(starts), 4)
        self.assertTrue(all(b-a >= 60 for a,b in zip(starts, starts[1:])))
