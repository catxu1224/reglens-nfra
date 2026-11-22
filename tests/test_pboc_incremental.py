import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from pboc_incremental import extract

class PbocTests(unittest.TestCase):
    def test_continued_tables_keep_header_and_original_extra_fields(self):
        rows=extract([[['序号','当事人名称','行政处罚\n决定书文号','违法行为类型','行政处罚内容','作出行政处罚决定机关名称','作出行政处罚决定日期','公示期限','备注'],['1','甲银行','银罚1号','违规','罚款5万元','中国人民银行','2024年1月1日','三年','说明']], [['2','张某','银罚2号','违规','罚款1万元','中国人民银行','2024年1月1日','三年','']]])
        self.assertEqual(len(rows),2)
        self.assertEqual(rows[1]['decision_no'],'银罚2号')
        self.assertEqual(rows[0]['remarks'],'说明')
        self.assertEqual(rows[0]['decision_authority'],'中国人民银行')
        self.assertNotIn('legal_basis',rows[0])
