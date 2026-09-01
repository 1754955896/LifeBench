"""Field-level repair prompt."""

import json
from typing import Any, Dict, List

from .common import render_common_rules

PROMPT_VERSION = "persona-repair-v2"


def build_repair_prompt(data: Dict[str, Any], violations: List[Dict[str, Any]], allowed_paths: List[str], as_of_date: str) -> str:
    return f"""
只修复指定 JSON 路径上的人物数据错误。
{render_common_rules(as_of_date)}
输出格式必须为 {{"repairs":[{{"path":"/...","value":任意JSON值,"reason":"RULE-ID"}}]}}。

要求：
- path 必须来自允许路径；不得修改其他字段。
- 不输出整份画像。
- 修复值必须解决对应错误且不引入新的时间或关系矛盾。

允许路径：
{json.dumps(allowed_paths, ensure_ascii=False, indent=2)}

错误：
{json.dumps(violations, ensure_ascii=False, indent=2)}

相关数据：
{json.dumps(data, ensure_ascii=False, indent=2)}
""".strip()
