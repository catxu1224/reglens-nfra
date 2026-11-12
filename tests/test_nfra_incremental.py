import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from nfra_incremental import amount_yuan, classify, raw_for


def source(doc_id, party, decision, facts="虚列费用", row_no="1"):
    return {
        "doc_id": doc_id,
        "source_row_no": row_no,
        "party_name": party,
        "penalty_text": decision,
        "violation_text": facts,
        "decision_no": "",
        "legal_basis": "",
        "decision_authority": "江苏金融监管局",
        "publishing_source": "江苏",
        "published_date": "2026-11-12",
        "notice_url": f"https://www.nfra.gov.cn/cn/view/pages/ItemDetail.html?docId={doc_id}",
    }


class IncrementalClassificationTests(unittest.TestCase):
    def test_separates_institution_and_person_fines(self):
        entry = source("1", "苏州东吴财产保险股份有限公司及相关责任人员",
                       "对苏州东吴财产保险股份有限公司罚款10万元。对吴烨茜给予警告，并罚款7万元。")
        rows = classify(entry, [raw_for(entry)], 0, [("苏州东吴财产保险股份有限公司", "")])
        self.assertEqual([(kind, row["处罚金额"]) for kind, row in rows],
                         [("institution", "100000"), ("person", "70000")])
        self.assertEqual(rows[1][1]["被处罚个人"], "吴烨茜")

    def test_links_insurance_agent_to_company_in_same_notice(self):
        entry = source("2", "陈珍（时任泰康人寿营口中心支公司保险代理人）",
                       "警告并处1000元罚款", "通过垫付保费引诱投保人签订保险合同")
        rows = classify(entry, [raw_for(entry)], 0,
                        [("泰康人寿保险有限责任公司", "辽宁营口中心支公司")])
        result = rows[0][1]
        self.assertEqual(result["被处罚单位（公司）"], "泰康人寿保险有限责任公司")
        self.assertEqual(result["被处罚个人"], "陈珍")
        self.assertEqual(result["合规风险点"], "保险销售与消费者权益保护")

    def test_former_employee_is_personal_penalty(self):
        entry = source("3", "原交通银行股份有限公司员工仇征",
                       "对仇征给予禁止从事银行业工作5年的行政处罚", "利用职务便利收受贿赂")
        rows = classify(entry, [raw_for(entry)], 0, [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["处罚对象"], "个人")
        self.assertEqual(rows[0][1]["被处罚单位（公司）"], "交通银行股份有限公司")
        self.assertEqual(rows[0][1]["处罚类型"], "禁止从业")

    def test_aggregate_fine(self):
        self.assertEqual(amount_yuan("对甲罚款5万元；对乙罚款共计3万元"), "80000")


if __name__ == "__main__":
    unittest.main()
