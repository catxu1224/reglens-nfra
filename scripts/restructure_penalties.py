#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按最新字段要求重构处罚 CSV，并识别机构/个人责任人。"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from enrich_penalties import (
    clean,
    institution_type,
    multi_match,
    province,
    punishment_types,
    split_subject,
    trim_branch_role,
    RISK_RULES,
    CAUSE_RULES,
)


HEADERS = [
    "被处罚单位（公司）", "被处罚单位（分行）", "被处罚个人", "机构类型", "文号", "地区", "机关",
    "违法违规事实", "处罚决定", "处罚对象", "处罚依据", "处罚金额", "发布时间",
    "合规风险点", "处罚类型", "处罚案由", "处罚机关", "处罚书url", "update_time",
]
INSTITUTION_HINT = re.compile(
    r"银行|保险|证券|信托|财务|金融|资产管理|资产投资|融资租赁|消费金融|汽车金融|基金|期货|保险经纪|保险代理|保险公估|公司"
)
SHORT_NAME_MAP = {
    "交通银行": "交通银行股份有限公司", "广发银行": "广发银行股份有限公司", "建设银行": "中国建设银行股份有限公司",
    "工商银行": "中国工商银行股份有限公司", "农业银行": "中国农业银行股份有限公司", "农行": "中国农业银行股份有限公司",
    "中国银行": "中国银行股份有限公司", "邮储银行": "中国邮政储蓄银行股份有限公司", "中信银行": "中信银行股份有限公司",
    "民生银行": "中国民生银行股份有限公司", "平安银行": "平安银行股份有限公司", "光大银行": "中国光大银行股份有限公司",
    "兴业银行": "兴业银行股份有限公司", "华夏银行": "华夏银行股份有限公司", "招商银行": "招商银行股份有限公司",
    "浦发银行": "上海浦东发展银行股份有限公司", "渤海银行": "渤海银行股份有限公司", "北京银行": "北京银行股份有限公司",
    "宁波银行": "宁波银行股份有限公司", "台州银行": "台州银行股份有限公司", "天津银行": "天津银行股份有限公司",
    "长安银行": "长安银行股份有限公司", "徽商银行": "徽商银行股份有限公司", "中原银行": "中原银行股份有限公司",
    "贵州银行": "贵州银行股份有限公司", "湖北银行": "湖北银行股份有限公司", "友利银行": "友利银行（中国）有限公司",
    "东亚银行": "东亚银行（中国）有限公司",
}

# 总局直接处罚法人总部、且处罚文本没有省市线索时，按公开登记/公司披露的注册地补齐省份。
# 该表只用于“地区”字段，不改变被处罚单位名称。
HQ_REGISTRATION_PROVINCES = {
    "浦银理财有限责任公司": "上海市", "太平资产管理有限公司": "上海市", "太平洋资产管理有限责任公司": "上海市",
    "交银保险资产管理有限公司": "上海市", "交银理财有限责任公司": "上海市", "交银金融资产投资有限公司": "上海市",
    "民生通惠资产管理有限公司": "上海市", "陆家嘴国际信托有限公司": "上海市", "中国太平洋财产保险股份有限公司": "上海市",
    "中国太平洋人寿保险股份有限公司": "上海市", "天安人寿保险股份有限公司": "上海市", "天安财产保险股份有限公司": "上海市",
    "大地财产保险": "上海市", "中国大地财产保险股份有限公司": "上海市", "众安在线财产保险股份有限公司": "上海市",
    "永诚保险资产管理有限公司": "浙江省", "渤银理财有限责任公司": "天津市", "渤海银行股份有限公司": "天津市",
    "恒丰银行股份有限公司": "山东省", "兴业银行股份有限公司": "福建省", "南安农村商业银行股份有限公司": "福建省",
    "平安银行股份有限公司": "广东省", "华夏久盈资产管理有限责任公司": "广东省", "广发银行股份有限公司": "广东省",
    "广银理财有限责任公司": "广东省", "易安财产保险股份有限公司": "广东省", "复星联合健康保险股份有限公司": "广东省",
    "平安理财有限责任公司": "广东省", "招银理财有限责任公司": "广东省", "平安健康保险股份有限公司": "广东省",
    "平安财产保险股份有限公司": "广东省", "华安财产保险股份有限公司": "广东省", "华保鑫诺保险销售有限公司": "北京市",
    "国元农业保险股份有限公司": "安徽省", "浙商银行股份有限公司": "浙江省", "泰康在线财产保险股份有限公司": "湖北省",
    "渝农商金融租赁有限责任公司": "重庆市", "昆仑金融租赁有限责任公司": "重庆市",
    "中华联合财产保险股份有限公司": "北京市", "中华联合财险": "北京市", "安心财产保险有限责任公司": "江苏省",
    "恒大人寿保险有限公司": "重庆市", "车车保险": "北京市",
    "中国人寿再保险有限责任公司": "北京市", "新华人寿保险股份有限公司": "北京市", "招商银行股份有限公司": "广东省",
    "国寿投资保险资产管理有限公司": "北京市", "太平财产保险有限公司": "北京市", "中信银行股份有限公司": "北京市",
    "交通银行股份有限公司": "上海市", "中国建设银行股份有限公司": "北京市", "中国工商银行股份有限公司": "北京市",
    "幸福人寿保险股份有限公司": "北京市", "中国银河资产管理有限责任公司": "北京市", "中国太平保险集团有限责任公司": "北京市",
    "泰康人寿保险有限责任公司": "北京市", "阳光保险集团股份有限公司": "北京市", "中国人寿财产保险股份有限公司": "北京市",
    "中国人民财产保险股份有限公司": "北京市", "中国人民人寿保险股份有限公司": "北京市", "中国民生银行股份有限公司": "北京市",
    "中国农业银行股份有限公司": "北京市", "中国银行股份有限公司": "北京市", "中国邮政储蓄银行股份有限公司": "北京市",
    "中国进出口银行股份有限公司": "北京市", "中国光大银行股份有限公司": "北京市", "华夏银行股份有限公司": "北京市",
    "中信百信银行股份有限公司": "北京市", "华夏理财有限责任公司": "北京市", "信银理财有限责任公司": "上海市",
    "建信金融资产投资有限公司": "北京市", "工银金融资产投资有限公司": "北京市", "中再资产管理股份有限公司": "北京市",
    "中国信达资产管理股份有限公司": "北京市", "华夏人寿保险股份有限公司": "北京市", "中国农业发展银行股份有限公司": "北京市",
    "中银理财有限责任公司": "北京市", "建信理财有限责任公司": "北京市",
    "农业发展银行": "北京市", "工商银行": "北京市",
}

BRANCH_LOCATION_PROVINCES = {
    "宁县": "甘肃省", "西峰": "甘肃省", "叶城": "新疆维吾尔自治区", "图木舒克": "新疆维吾尔自治区", "南安": "福建省",
}


def is_person_subject(subject: str) -> bool:
    s = clean(subject)
    if not s or s in {"姓名或名称个人姓名", "个人姓名"}:
        return True
    if "及相关责任" in s or "相关责任人员" in s:
        return False
    if s.startswith("当事人") and any(x in s for x in ("时任", "时为", "任职", "代为履职")):
        return True
    # “姓名（单位及职务）”和“姓名[时任单位及职务]”是个人责任人格式。
    bracket = re.search(r"[（(\[【〔]", s)
    if bracket:
        prefix = clean(s[:bracket.start()])
        # 括号前是姓名时，不再限定必须是汉字姓名；覆盖英文姓名、点号姓名等。
        if prefix and not INSTITUTION_HINT.search(prefix):
            return True
        if any(x in s[bracket.start():] for x in ("时任", "任职", "代为履职")) and not prefix.startswith(("一、", "二、", "三、")):
            return True
    if any(x in s for x in ("时任", "时为", "任职", "代为履职")) and not INSTITUTION_HINT.search(re.split(r"[（(\[【，,]", s, 1)[0]):
        return True
    return not bool(INSTITUTION_HINT.search(s))


def nearest_institution(rows: List[Dict[str, str]], index: int) -> Optional[Tuple[str, str]]:
    for i in range(index - 1, -1, -1):
        candidate = clean(rows[i].get("被处罚单位（公司）", ""))
        if candidate and not is_person_subject(candidate):
            return split_subject(candidate)
    return None


def extract_parenthetical_unit(person: str) -> Tuple[str, str]:
    """从时任、任职或括号内容中提取单位，支持截断和时间段格式。"""
    marker = re.search(r"(?:时任|时为|代为履职|任职于?)\s*", person)
    text = person[marker.end():] if marker else ""
    if not text:
        m = re.search(r"[（(\[【〔]\s*(.*)$", person)
        text = m.group(1) if m else ""
    if not text:
        return "", ""
    if re.match(r"^\d{4}年", text):
        text = re.sub(r"^.*?(?:代为履职|任职|任)\s*", "", text, count=1)
    text = trim_branch_role(clean(text))
    text = re.split(r"[】\]〕]", text, 1)[0]
    text = re.split(r"[，,；;]", text, 1)[0]
    if not INSTITUTION_HINT.search(text):
        return "", ""
    short = re.match(r"^(.*?(?:银行|保险|信托|财务公司|汽车金融公司))(.*)$", text)
    if short and not re.search(r"(?:股份有限公司|有限责任公司|有限公司)", text):
        company = formalize_company(short.group(1))
        rest = trim_branch_role(short.group(2))
        return company, rest if "分行" in rest or "支行" in rest or "分公司" in rest or "中心支公司" in rest else ""
    company, branch = split_subject(text)
    if company and company != "公司":
        return formalize_company(company), branch
    return formalize_company(company), branch


def formalize_company(company: str) -> str:
    value = clean(company)
    for short, full in sorted(SHORT_NAME_MAP.items(), key=lambda x: len(x[0]), reverse=True):
        if value == short:
            return full
    if value.endswith("农村商业银行"):
        return value + "股份有限公司"
    if value.endswith("银行") and "股份有限公司" not in value and "有限公司" not in value:
        return value + "股份有限公司"
    return value


def registration_province(company: str, branch: str) -> str:
    """按具体分支地名优先，其次按法人注册地补省份。"""
    location_text = clean(company) + clean(branch)
    for key, value in BRANCH_LOCATION_PROVINCES.items():
        if key in location_text:
            return value
    normalized = clean(company).replace(" ", "")
    for key, value in sorted(HQ_REGISTRATION_PROVINCES.items(), key=lambda item: len(item[0]), reverse=True):
        if key in normalized:
            return value
    return "未识别"


def normalize_regulator(value: str) -> str:
    """统一监管机关称谓，兼容总局、省级局、地市分局及历史银保监会名称。"""
    text = clean(value)
    if not text:
        return ""
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"国家国家金融监督管理总局", "国家金融监督管理总局", text)
    text = re.sub(r"(?:20\d{2}年\d{1,2}月\d{1,2}日?)$", "", text)
    text = re.sub(r"（根据金融监管总局授权实施）$", "", text)
    text = re.sub(r"金融监管总局$", "", text) if text.endswith("监管分局金融监管总局") else text

    # 历史称谓统一到现行国家金融监督管理总局体系。
    text = text.replace("中国银行保险监督管理委员会", "国家金融监督管理总局")
    text = text.replace("中国银保监会", "国家金融监督管理总局")
    text = text.replace("原国家金融监督管理总局", "国家金融监督管理总局")
    text = text.replace("原国家金融监管总局", "国家金融监督管理总局")
    text = text.replace("国家金融监管总局", "国家金融监督管理总局")

    if text in {"金融监管总局", "国家金融监督管理总局", "国家金融监督管理总局局"}:
        return "国家金融监督管理总局"

    # 清理“金融监管局/分局”及 OCR 造成的“监分管局”等变体。
    text = text.replace("金融监分管局", "金融监管分局")
    text = text.replace("金融监管管理总局", "金融监督管理总局")
    if "国家金融监督管理总局" in text:
        suffix = text.split("国家金融监督管理总局", 1)[1]
    else:
        suffix = text
    suffix = suffix.replace("金融监管分局", "监管分局")
    suffix = suffix.replace("金融监管局", "监管局")
    suffix = suffix.replace("银保监分局", "监管分局")
    suffix = suffix.replace("银保监局", "监管局")
    suffix = suffix.replace("监管分局监管分局", "监管分局")
    suffix = suffix.replace("监管局监管局", "监管局")
    if suffix in {"", "局"}:
        return "国家金融监督管理总局"
    if suffix.endswith("监管分局"):
        return "国家金融监督管理总局" + suffix
    if suffix.endswith("监管局"):
        return "国家金融监督管理总局" + suffix
    # “云南金融监管”等缺少“局”的省级简称。
    if suffix.endswith("金融监管"):
        return "国家金融监督管理总局" + suffix[:-4] + "监管局"
    if suffix.endswith("监管"):
        return "国家金融监督管理总局" + suffix[:-2] + "监管局"
    # 处罚决定、金额等误落入机关列的值无法安全推断机关，置空待后续回溯原文。
    return ""


def regulator_from_region(region: str) -> str:
    """原始机关缺失时，用已识别的省级地区补成省级监管局称谓。"""
    value = clean(region)
    if not value or value == "未识别":
        return "国家金融监督管理总局"
    short = value.replace("维吾尔自治区", "").replace("壮族自治区", "").replace("回族自治区", "")
    short = short.replace("自治区", "").replace("省", "").replace("市", "")
    return "国家金融监督管理总局" + short + "监管局"


def numbered_items(text: str) -> List[str]:
    marks = list(re.finditer(r"([一二三四五六七八九十]+)、", text))
    if len(marks) < 2 or marks[0].start() > 2:
        return [text]
    items = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        part = clean(text[mark.end():end])
        if part:
            items.append(part)
    return items or [text]


def split_person_decision(decision: str) -> Tuple[str, str, str]:
    """返回机构处罚、个人处罚和个人姓名文本。"""
    parts = [p.strip() for p in re.split(r"(?=对)", decision) if p.strip()]
    institution_parts: List[str] = []
    person_parts: List[str] = []
    names: List[str] = []
    action = r"(?=给予|予以|警告|罚款|禁止|没收|责令|终身)"
    for part in parts:
        if not part.startswith("对"):
            institution_parts.append(part)
            continue
        core = part[1:]
        name_match = re.search(r"([\u4e00-\u9fffA-Za-z·]{2,30}(?:、[\u4e00-\u9fffA-Za-z·]{2,30})*)" + action, core)
        is_person = bool(name_match) and not re.search(r"银行|保险|证券|信托|财务|金融|公司|机构", name_match.group(1))
        if "责任人" in core or "责任人员" in core or "时任" in core:
            is_person = True
        if is_person:
            person_parts.append(part)
            if name_match:
                names.append(name_match.group(1))
        else:
            institution_parts.append(part)
    return "；".join(institution_parts), "；".join(person_parts), "、".join(dict.fromkeys(names))


def expand_source_rows(row: Dict[str, str]) -> List[Dict[str, str]]:
    subject = clean(row.get("被处罚单位（公司）", ""))
    decision = clean(row.get("处罚决定", ""))
    subjects = numbered_items(subject)
    decisions = numbered_items(decision)
    if len(subjects) > 1:
        result = []
        for i, item in enumerate(subjects):
            copy = dict(row)
            copy["__subject"] = item
            copy["__decision"] = decisions[i] if i < len(decisions) else decision
            result.append(copy)
        return result
    row = dict(row)
    row["__subject"] = subject
    row["__decision"] = decision
    # 一条机构处罚同时写有个人责任人时，拆成机构行和个人行。
    if not is_person_subject(subject) and ("及相关责任" in subject or "责任人" in decision or "责任人员" in decision or "对时任" in decision):
        institution_decision, person_decision, names = split_person_decision(decision)
        if names and person_decision:
            company, branch = split_subject(subject)
            row["__decision"] = institution_decision or decision
            person_row = dict(row)
            person_row["__subject"] = names
            person_row["__decision"] = person_decision
            person_row["__force_person"] = "1"
            person_row["__person"] = names
            person_row["__unit"] = (formalize_company(company), branch)
            return [row, person_row]
    return [row]


def amount_from_decision(decision: str) -> str:
    amounts = re.findall(
        r"(?:人民币|罚款|处以|并处罚款|罚款人民币)[^0-9]{0,15}"
        r"([0-9][0-9,]*(?:\.\d+)?)\s*(万)?\s*元", decision
    )
    if not amounts:
        return ""
    total = sum(float(v.replace(",", "")) * (10000 if wan else 1) for v, wan in amounts)
    return str(int(total)) if total.is_integer() else str(total)


def build_row(row: Dict[str, str], rows: List[Dict[str, str]], index: int) -> Dict[str, str]:
    raw_subject = clean(row.get("__subject", row.get("被处罚单位（公司）", "")))
    person = ""
    if row.get("__force_person"):
        object_type = "个人"
        person = row.get("__person", raw_subject)
        company, branch = row.get("__unit", ("", ""))
    elif is_person_subject(raw_subject):
        object_type = "个人"
        person = raw_subject
        # 括号中明确写出的“时任某机构……”优先级高于上一条记录，
        # 只有没有明确单位时，才按用户要求向前遍历寻找最近机构。
        unit = extract_parenthetical_unit(raw_subject)
        if not unit[0]:
            unit = nearest_institution(rows, index) or ("", "")
        company, branch = unit
    else:
        object_type = "机构"
        company, branch = split_subject(raw_subject)

    facts = clean(row.get("违法违规事实", ""))
    decision = clean(row.get("__decision", row.get("处罚决定", "")))
    authority_raw = clean(row.get("处罚机关") or row.get("机关") or "")
    authority = normalize_regulator(authority_raw)
    evidence = facts + " " + decision
    region_value = province(authority_raw + " " + branch + " " + company)
    if region_value == "未识别":
        region_value = registration_province(formalize_company(company), branch)
    normalized_authority = authority or regulator_from_region(region_value)
    row_out = {h: "" for h in HEADERS}
    row_out.update({
        "被处罚单位（公司）": formalize_company(company) or "未识别",
        "被处罚单位（分行）": branch,
        "被处罚个人": person,
        "机构类型": institution_type(company or person),
        "文号": row.get("文号", ""),
        "地区": region_value,
        "机关": normalize_regulator(row.get("机关") or authority_raw) or normalized_authority,
        "违法违规事实": facts,
        "处罚决定": decision,
        "处罚对象": object_type,
        "处罚依据": row.get("处罚依据", ""),
        "处罚金额": row.get("处罚金额") or amount_from_decision(decision),
        "发布时间": row.get("发布时间", ""),
        "合规风险点": multi_match(evidence, RISK_RULES) or "未识别",
        "处罚类型": punishment_types(decision),
        "处罚案由": multi_match(facts, CAUSE_RULES) or ("违法事实未披露" if not facts else "其他"),
        "处罚机关": normalized_authority,
        "处罚书url": row.get("处罚书url", ""),
        "update_time": row.get("update_time", ""),
    })
    return row_out


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", default="data/监管处罚信息_2024至今.csv")
    ap.add_argument("output", nargs="?", default="data/监管处罚信息_2024至今_新字段_v9.csv")
    args = ap.parse_args()
    with Path(args.input).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    output_rows = []
    for i, row in enumerate(rows):
        for expanded in expand_source_rows(row):
            output_rows.append(build_row(expanded, rows, i))
    with Path(args.output).open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(output_rows)
    print(f"已输出 {len(output_rows)} 条：{Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
