import csv,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import pboc_validate_complete as validator
class CompleteHistoryTests(unittest.TestCase):
    def setup_files(self,root,pending=False):
        (root/'seeds').mkdir();(root/'config').mkdir()
        (root/'config/pboc_branches.json').write_text(json.dumps({'expectedBranchCount':1,'branches':[{'name':'北京市分行','home':'https://beijing.pbc.gov.cn/','status':'verified','directories':['https://beijing.pbc.gov.cn/list/']}]}))
        (root/'seeds/pboc_crawl_state.json').write_text(json.dumps({'queue':[{}] if pending else [],'failures':{},'done':{'https://beijing.pbc.gov.cn/a':{'rows':1}},'coverage':{'北京市分行':{'historyComplete':True,'parsedNotices':1}}}))
        rows=[{'source_key':'a'*64,'seed_row_number':'1','文号':'京罚2024-1','被处罚单位（公司）':'甲银行','被处罚单位（分行）':'','处罚对象':'机构','处罚机关':'中国人民银行北京市分行','发布时间':'2024-01-01','处罚书url':'https://beijing.pbc.gov.cn/a'}]
        with (root/'seeds/pboc_penalties.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    def test_pending_history_cannot_be_marked_complete(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.setup_files(root,True)
            with patch.object(validator,'ROOT',root):manifest,issues=validator.validate()
            self.assertIsNone(manifest);self.assertTrue(any('pending' in issue for issue in issues))
    def test_complete_snapshot_has_checksum_and_per_branch_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.setup_files(root)
            with patch.object(validator,'ROOT',root):manifest,issues=validator.validate()
            self.assertEqual(issues,[]);self.assertEqual(manifest['rows'],1);self.assertEqual(manifest['branches'][0]['rows'],1);self.assertEqual(len(manifest['seedSha256']),64)
    def test_missing_official_branch_blocks_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);self.setup_files(root)
            path=root/'config/pboc_branches.json';data=json.loads(path.read_text());data['expectedBranchCount']=36;path.write_text(json.dumps(data))
            with patch.object(validator,'ROOT',root):manifest,issues=validator.validate()
            self.assertIsNone(manifest);self.assertTrue(any('branch count' in issue for issue in issues))
