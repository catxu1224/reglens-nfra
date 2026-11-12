#!/usr/bin/env python3
"""Import newly published NFRA notices into the versioned incremental seed."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
from enrich_penalties import institution_type, multi_match, punishment_types, RISK_RULES, CAUSE_RULES
from restructure_penalties import build_row, clean, formalize_company, is_person_subject
import nfra_site

BUSINESS = [
    "被处罚单位（公司）", "被处罚单位（分行）", "被处罚个人", "机构类型", "机构大类",
    "文号", "地区", "机关", "违法违规事实", "处罚决定", "处罚对象", "处罚依据",
    "处罚金额", "发布时间", "合规风险点", "处罚类型", "处罚案由", "处罚机关",
    "处罚书url", "update_time",
]
HEADERS = ["source_key", "seed_row_number", *BUSINESS]
OUTPUT = ROOT / "seeds" / "nfra_penalties_incremental.csv"
BASELINE = ROOT / "seeds" / "nfra_penalties.csv"
NOTICE_DATE_START = "2026-11-05"
PERSON_ACTION = re.compile(r"给予|予以|分别|警告|罚款|处以|禁止|终身|没收|责令|取消")
INSTITUTION_TARGET = re.compile(r"公司|银行|联社|信用社|支行|分行|机构|该行|该联社|财务|信托")


def doc_id(row: dict[str, str]) -> str:
    return parse_qs(urlparse(row["处罚书url"]).query).get("docId", [""])[0]


def amount_yuan(decision: str) -> str:
    """Sum separately stated fines, without counting a number twice."""
    expressions = [
        r"(?:罚款|处以|并处|处罚|合计)\s*(?:共计|合计)?\s*(?:人民币)?\s*([\d,]+(?:\.\d+)?)\s*(亿|万|千)?\s*元",
        r"([\d,]+(?:\.\d+)?)\s*(亿|万|千)?\s*元\s*罚款",
    ]
    spans: dict[tuple[int, int], float] = {}
    for pattern in expressions:
        for match in re.finditer(pattern, decision):
            value = float(match.group(1).replace(",", "")) * {"亿": 1e8, "万": 1e4, "千": 1e3, None: 1}[match.group(2)]
            if any(not (match.end() <= start or match.start() >= end) for start, end in spans):
                continue
            spans[(match.start(), match.end())] = value
    total = sum(spans.values(), 0.0)
    return str(int(total)) if total.is_integer() and spans else (str(total) if spans else "")


def decision_parts(text: str) -> tuple[str, str, str]:
    institution: list[str] = []
    persons: list[str] = []
    names: list[str] = []
    for part in re.split(r"(?=对\s*)", text):
        part = clean(part)
        if not part:
            continue
        if not part.startswith("对"):
            institution.append(part)
            continue
        target = PERSON_ACTION.split(part[1:], maxsplit=1)[0].strip(" ：:，,。；; ")
        target = re.sub(r"^(?:相关)?责任人员?\s*", "", target)
        if INSTITUTION_TARGET.search(target):
            institution.append(part)
        else:
            persons.append(part)
            name = re.sub(r"(?:分别|合计|共计)$", "", target).strip()
            if name and name not in {"其", "该", "相关责任人"}:
                names.append(name)
    return "；".join(institution), "；".join(persons), "、".join(dict.fromkeys(names))


def raw_for(source: dict[str, str]) -> dict[str, str]:
    return {
        "被处罚单位（公司）": source.get("party_name", ""),
        "文号": source.get("decision_no", ""),
        "违法违规事实": source.get("violation_text", ""),
        "处罚决定": source.get("penalty_text", ""),
        "处罚依据": source.get("legal_basis", ""),
        "处罚机关": source.get("decision_authority", ""),
        "机关": source.get("decision_authority", "") or source.get("publishing_source", ""),
        "发布时间": source["published_date"],
        "处罚书url": source["notice_url"],
    }


def canonical_company(subject: str, known: list[tuple[str, str]]) -> tuple[str, str]:
    prefix = re.sub(r"\s+", "", subject)
    for company, branch in known:
        short = re.sub(r"(股份有限公司|有限责任公司|有限公司|保险)", "", company)
        aliases = ("国寿财险",) if company.startswith("中国人寿财产保险") else ()
        for candidate in (company[:4], short[:4], company.replace("中国", "")[:4], *aliases):
            if len(candidate) >= 3 and candidate in prefix:
                local_branch = re.search(r"(?:人寿|财险|银行)([^（）()]{2,30}?)(?:保险代理人|客户经理|副总经理|总经理|行长)", subject)
                return company, clean(local_branch.group(1)) if local_branch else (branch if branch and branch in subject else "")
    return known[0] if len(known) == 1 else ("", "")


def classify(source: dict[str, str], group: list[dict[str, str]], index: int,
             known: list[tuple[str, str]]) -> list[tuple[str, dict[str, str]]]:
    raw = raw_for(source)
    subject = raw["被处罚单位（公司）"]
    institution_text, person_text, names = decision_parts(raw["处罚决定"])
    combined = bool(
        institution_text and person_text and names and not is_person_subject(subject)
    )
    components: list[tuple[str, dict[str, str]]] = []
    former_employee = re.match(r"^原(.+?公司)员工([^\s，,。；;]+)$", subject)
    if former_employee:
        person_raw = dict(raw)
        person_raw.update({
            "__force_person": "1", "__subject": former_employee.group(2),
            "__person": former_employee.group(2), "__unit": (former_employee.group(1), ""),
        })
        components.append(("person", build_row(person_raw, group, index)))
    elif not combined or institution_text:
        institution_raw = dict(raw)
        if combined:
            institution_raw["处罚决定"] = institution_text
        built = build_row(institution_raw, group, index)
        components.append(("institution" if built["处罚对象"] == "机构" else "person", built))
    if combined and person_text and names:
        person_raw = dict(raw)
        person_raw.update({
            "__force_person": "1", "__subject": names, "__person": names,
            "__decision": person_text,
        })
        company = components[0][1]["被处罚单位（公司）"] if components else ""
        branch = components[0][1]["被处罚单位（分行）"] if components else ""
        if not company or company == "未识别":
            company, branch = canonical_company(subject, known)
        person_raw["__unit"] = (company, branch)
        built = build_row(person_raw, group, index)
        components.append(("person", built))
    if combined and person_text and not names:
        raise ValueError(f"Could not extract person from {source['doc_id']} row {source.get('source_row_no')}")
    for _, row in components:
        if row["处罚对象"] == "个人":
            name = re.split(r"[（(\[【]", row["被处罚个人"], maxsplit=1)[0].strip()
            name = re.sub(r"^原.*?员工", "", name)
            if name:
                row["被处罚个人"] = name
            needs_link = row["被处罚单位（公司）"] == "未识别" or (
                row["被处罚单位（公司）"] not in {c for c, _ in known}
                and (not row["被处罚单位（公司）"].endswith(("公司", "联社")) or row["被处罚单位（公司）"].startswith("国寿财险"))
            )
            if needs_link:
                company, branch = canonical_company(subject, known)
                if company:
                    row["被处罚单位（公司）"] = company
                    row["被处罚单位（分行）"] = branch
        row["被处罚单位（公司）"] = re.sub(r"、分支机构$", "", row["被处罚单位（公司）"])
        company = row["被处罚单位（公司）"]
        row["机构类型"] = institution_type(company if company != "未识别" else subject)
        row["机构大类"] = "保险" if row["机构类型"] == "保险业金融机构" else (
            "银行" if "银行" in row["机构类型"] or row["机构类型"] == "农村信用联社" else "其他"
        )
        row["处罚金额"] = amount_yuan(row["处罚决定"])
        row["处罚类型"] = punishment_types(row["处罚决定"])
        if row["合规风险点"] == "未识别":
            row["合规风险点"] = multi_match(row["违法违规事实"] + " " + row["处罚决定"], RISK_RULES) or "未识别"
        if row["处罚案由"] in ("未识别", "其他") and row["违法违规事实"]:
            row["处罚案由"] = multi_match(row["违法违规事实"], CAUSE_RULES) or "其他"
        if row["处罚案由"] == "其他":
            for label, pattern in (
                ("财务会计资料不真实", r"虚列费用|财务数据不真实|财务数据不准确"),
                ("未按规定办理行政许可、备案或报告", r"未经.*(?:批准|审批).*?(?:分支机构|营业场所)|未经批准设立分支机构"),
                ("保险销售或中介业务违规", r"垫付保费|引诱投保人|保费回扣|保险代理"),
                ("数据质量管理不到位", r"客户信息不真实|客户信息不完整"),
                ("贷前调查不尽职", r"贷款审查不审慎"),
                ("支付结算或银行卡业务违规", r"承兑汇票|票据业务"),
                ("个人任职或履职责任", r"利用职务便利收受贿赂"),
            ):
                if re.search(pattern, row["违法违规事实"]):
                    row["处罚案由"] = label
                    break
        if source["doc_id"] == "1278360":
            row["地区"] = {
                "民生人寿保险股份有限公司": "北京市",
                "中国人民保险集团股份有限公司": "北京市",
            }.get(company, row["地区"])
        row["处罚书url"] = source["notice_url"]
    return components


def load_seed(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != HEADERS:
            raise ValueError(f"Unexpected seed header: {path}")
        return list(reader)


def save_seed(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since", default=None, help="Inclusive publication date, YYYY-MM-DD")
    parser.add_argument("--until", default=None, help="Exclusive publication date, YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    since = args.since or max(date.fromisoformat(NOTICE_DATE_START), today - timedelta(days=30)).isoformat()
    until = args.until or (today + timedelta(days=1)).isoformat()
    if not (NOTICE_DATE_START <= since < until):
        raise ValueError("Invalid backfill range")
    existing = load_seed(OUTPUT)
    baseline = load_seed(BASELINE)
    baseline_keys = {r["source_key"] for r in baseline}
    notices = nfra_site.listing(since, until)
    if not notices:
        raise RuntimeError(f"No official notices in {since}..{until}; verify the site before treating this as complete")
    generated: list[dict[str, str]] = []
    issues: list[str] = []
    source_count = 0
    for notice_id, entry in notices.items():
        try:
            source_rows, issue = nfra_site.parse(notice_id, entry, True)
            if issue:
                raise ValueError(json.dumps(issue, ensure_ascii=False))
            if not source_rows:
                raise ValueError("No penalty rows")
            source_count += len(source_rows)
            group = [raw_for(row) for row in source_rows]
            known = []
            for i, raw in enumerate(group):
                if not is_person_subject(raw["被处罚单位（公司）"]):
                    parsed = build_row(raw, group, i)
                    company = parsed["被处罚单位（公司）"]
                    if company != "未识别":
                        known.append((company, parsed["被处罚单位（分行）"]))
            for index, source in enumerate(source_rows):
                for component, row in classify(source, group, index, known):
                    key = hashlib.sha256(
                        f"NFRA:{notice_id}:{source.get('source_row_no') or index + 1}:{component}".encode()
                    ).hexdigest()
                    generated.append({"source_key": key, "seed_row_number": "0", **row})
        except Exception as error:
            issues.append(f"{notice_id}: {error}")
            if "403" in str(error) or "429" in str(error) or len(issues) >= 5:
                break
    if issues:
        raise RuntimeError("Unresolved official notices: " + "; ".join(issues))
    new_keys = [r["source_key"] for r in generated]
    if len(new_keys) != len(set(new_keys)) or any(key in baseline_keys for key in new_keys):
        raise RuntimeError("Duplicate source key")
    touched = set(notices)
    merged = [r for r in existing if doc_id(r) not in touched]
    old_by_key = {r["source_key"]: r for r in existing}
    clock = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    for row in generated:
        old = old_by_key.get(row["source_key"])
        row["update_time"] = old["update_time"] if old and all(
            old.get(k, "") == row.get(k, "") for k in BUSINESS if k != "update_time"
        ) else clock
        merged.append(row)
    merged.sort(key=lambda r: (r["发布时间"], r["处罚书url"], r["source_key"]), reverse=True)
    next_number = max([len(baseline), *(int(r["seed_row_number"]) for r in existing)])
    for row in merged:
        old = old_by_key.get(row["source_key"])
        if old:
            row["seed_row_number"] = old["seed_row_number"]
        else:
            next_number += 1
            row["seed_row_number"] = str(next_number)
    if any(r["发布时间"] < NOTICE_DATE_START for r in merged):
        raise RuntimeError("Incremental seed contains a record before the baseline cutoff")
    changed = sum(
        r["source_key"] not in old_by_key or any(
            old_by_key[r["source_key"]].get(k, "") != r.get(k, "") for k in BUSINESS
        ) for r in generated
    )
    deleted = len([r for r in existing if doc_id(r) in touched and r["source_key"] not in new_keys])
    counts = {field: Counter(r[field] for r in generated).get("未识别", 0)
              for field in ("被处罚单位（公司）", "机构类型", "地区", "合规风险点", "处罚类型")}
    print(json.dumps({"notices": len(notices), "sourceRows": source_count, "generatedRows": len(generated),
                      "seedRows": len(merged), "changed": changed, "deleted": deleted,
                      "unknown": counts}, ensure_ascii=False))
    if not args.dry_run:
        save_seed(OUTPUT, merged)


if __name__ == "__main__":
    main()
