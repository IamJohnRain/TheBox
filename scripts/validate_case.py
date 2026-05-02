#!/usr/bin/env python3
import argparse
import json
import re
import sys
from typing import Dict, List, Tuple

import jsonschema

from core.case_generator import CASE_SCHEMA


def check_schema(case: Dict) -> Tuple[bool, str]:
    try:
        jsonschema.validate(instance=case, schema=CASE_SCHEMA)
        return True, "Schema 校验通过"
    except jsonschema.ValidationError as e:
        return False, f"Schema 校验失败: {e.message}"


def _extract_elements(truth: str) -> Dict[str, str]:
    elements = {}
    motive_patterns = [
        r"(?:因为|因|动机[是为]|出于|为了)[^。，；！？]{2,30}",
        r"(?:怨恨|仇恨|嫉妒|贪|报复|愤怒|不满|恼怒|爱|害怕|威胁|勒索|纠纷|矛盾)[^。，；！？]{0,30}",
    ]
    means_patterns = [
        r"(?:用|以|使用|拿着|握着|挥|击|刺|砍|推|毒|勒|掐|闷)[^。，；！？]{2,30}",
        r"(?:毒药|刀|斧|锤|绳|锄头|钝器|凶器|武器|枪)[^。，；！？]{0,20}",
    ]
    opportunity_patterns = [
        r"(?:在|于|时间|当晚|那天|深夜|凌晨|半夜|晚上|上午|下午|次日|案发)[^。，；！？]{2,30}",
        r"(?:独处|趁|趁机|潜入|闯入|偷偷|悄悄|无人|碰面|遇见|相遇|争执|冲突|争吵|打斗)[^。，；！？]{0,20}",
        r"(?:[^。，；！？]{0,10}(?:中|时|期间|过程中|之际)[^。，；！？]{0,15})",
    ]

    for pattern in motive_patterns:
        m = re.search(pattern, truth)
        if m:
            elements["motive"] = m.group()
            break

    for pattern in means_patterns:
        m = re.search(pattern, truth)
        if m:
            elements["means"] = m.group()
            break

    for pattern in opportunity_patterns:
        m = re.search(pattern, truth)
        if m:
            elements["opportunity"] = m.group()
            break

    return elements


def _meaningful_keywords(phrase: str) -> List[str]:
    cleaned = re.sub(r"^[因为于在从到被用以及向把将让使之其]", "", phrase)
    cleaned = re.sub(r"[的了着过是地得很]", "", cleaned)
    words = re.findall(r"[\u4e00-\u9fff]{2,}", cleaned)
    result = []
    for w in words:
        result.append(w)
    for w in words:
        if len(w) >= 4:
            for i in range(0, len(w) - 1, 2):
                chunk = w[i : i + 2]
                if len(chunk) == 2:
                    result.append(chunk)
    return list(dict.fromkeys(result))


def _element_covered(element_value: str, knowledge: str) -> bool:
    keywords = _meaningful_keywords(element_value)
    if not keywords:
        return True
    long_keywords = [kw for kw in keywords if len(kw) >= 3]
    short_keywords = [kw for kw in keywords if len(kw) == 2]
    if long_keywords and any(kw in knowledge for kw in long_keywords):
        return True
    if short_keywords:
        hits = sum(1 for kw in short_keywords if kw in knowledge)
        return hits >= max(1, len(short_keywords) // 3)
    return False


def check_motive_means_opportunity(case: Dict) -> Tuple[bool, str]:
    truth = case.get("truth", "")
    elements = _extract_elements(truth)

    missing = [k for k in ("motive", "means", "opportunity") if k not in elements]
    if missing:
        return False, f"真相中缺少以下要素: {', '.join(missing)}。truth: {truth}"

    suspects = case.get("suspects", [])
    all_knowledge = " ".join(s.get("knowledge", "") for s in suspects)

    uncovered = []
    for key, value in elements.items():
        if not _element_covered(value, all_knowledge):
            uncovered.append(key)

    if uncovered:
        return False, f"以下要素未被任何嫌疑人的 knowledge 覆盖: {', '.join(uncovered)}"

    return True, "动机-手段-时机覆盖检查通过"


def check_unique_culprit(case: Dict) -> Tuple[bool, str]:
    truth = case.get("truth", "")
    elements = _extract_elements(truth)

    if len(elements) < 3:
        return False, f"真相要素不足（需3个，得到{len(elements)}个），无法进行真凶唯一性检查"

    suspects = case.get("suspects", [])
    suspect_info = {}
    for s in suspects:
        name = s.get("name", "unknown")
        knowledge = s.get("knowledge", "")
        covered = set()
        for key, value in elements.items():
            if _element_covered(value, knowledge):
                covered.add(key)
        suspect_info[name] = {"covered": covered, "count": len(covered)}

    full_coverage = [name for name, info in suspect_info.items() if info["count"] == 3]

    if len(full_coverage) == 0:
        detail = {n: f"覆盖{info['count']}要素" for n, info in suspect_info.items()}
        return False, f"没有嫌疑人覆盖全部三要素。详情: {detail}"
    if len(full_coverage) > 1:
        return True, f"多个嫌疑人覆盖全部三要素: {full_coverage}，但真凶仍可通过审讯确定。覆盖情况: {suspect_info}"

    culprit = full_coverage[0]
    detail = {n: f"覆盖{info['count']}要素" for n, info in suspect_info.items()}
    return True, f"真凶唯一性检查通过: 真凶为 {culprit}。详情: {detail}"


def validate_case(case: Dict) -> Tuple[bool, List[str]]:
    results = []
    all_pass = True

    checks = [
        ("Schema 校验", check_schema),
        ("动机-手段-时机覆盖检查", check_motive_means_opportunity),
        ("真凶唯一性检查", check_unique_culprit),
    ]

    for name, check_fn in checks:
        passed, message = check_fn(case)
        status = "通过" if passed else "失败"
        results.append(f"[{status}] {name}: {message}")
        if not passed:
            all_pass = False

    return all_pass, results


def main():
    parser = argparse.ArgumentParser(description="验证案件 JSON 的合法性")
    parser.add_argument("--case-file", required=True, help="案件 JSON 文件路径")
    args = parser.parse_args()

    with open(args.case_file, "r", encoding="utf-8") as f:
        case = json.load(f)

    all_pass, results = validate_case(case)

    for r in results:
        print(r)

    if all_pass:
        print("\n总体结果: 通过")
        sys.exit(0)
    else:
        print("\n总体结果: 失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
