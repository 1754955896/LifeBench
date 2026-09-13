# -*- coding: utf-8 -*-
"""Small structured bridge between subjective and objective generation.

The surrounding narrative remains free-form.  Only the explicit named JSON
control lines are parsed; no keyword/NLP inference is used.
"""
import json
from typing import Any, Dict, List


def extract_named_json(text: Any, name: str) -> Dict[str, Any]:
    marker = "%s=" % name
    value = str(text or "")
    start = value.rfind(marker)
    if start < 0:
        return {}
    start = value.find("{", start + len(marker))
    if start < 0:
        return {}
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(value)):
        char = value[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(value[start:index + 1])
                except (TypeError, ValueError, json.JSONDecodeError):
                    return {}
                return parsed if isinstance(parsed, dict) else {}
    return {}


def validate_optional_activity_contract(
    plan: Any, result: Any, preferred_count: int = 0,
) -> Dict[str, Any]:
    plan_data = plan if isinstance(plan, dict) else {}
    result_data = result if isinstance(result, dict) else {}
    planned = [
        row for row in plan_data.get("activities", []) if isinstance(row, dict)
    ]
    realized = [
        row for row in result_data.get("activities", []) if isinstance(row, dict)
    ]
    planned_ids = [str(row.get("activity_id") or "") for row in planned]
    result_by_id = {
        str(row.get("activity_id") or ""): row for row in realized
        if str(row.get("activity_id") or "")
    }
    issues: List[str] = []
    if preferred_count > 0 and len(planned) < preferred_count:
        issues.append("主观自主活动少于当日软目标")
    if len(set(planned_ids)) != len(planned_ids) or any(not item for item in planned_ids):
        issues.append("主观自主活动ID缺失或重复")
    missing = [item for item in planned_ids if item not in result_by_id]
    if missing:
        issues.append("客观阶段未报告自主活动结果: %s" % ",".join(missing))
    allowed = {"completed", "modified", "cancelled"}
    for activity_id, row in result_by_id.items():
        status = str(row.get("status") or "")
        if status not in allowed:
            issues.append("自主活动%s状态非法" % activity_id)
        if status == "cancelled" and not str(row.get("cancel_reason") or "").strip():
            issues.append("自主活动%s取消但没有原因" % activity_id)
    return {
        "preferred_count": max(0, int(preferred_count or 0)),
        "planned_count": len(planned),
        "reported_count": len(realized),
        "completed_or_modified_count": sum(
            str(row.get("status") or "") in {"completed", "modified"}
            for row in realized
        ),
        "issues": issues,
    }
