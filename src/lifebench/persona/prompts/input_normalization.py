"""Prompt for extracting facts from arbitrary source records."""

import json
from typing import Any

from ..internal_models import STANDARD_PERSONA_KEYS

PROMPT_VERSION = "persona-input-normalization-v1"


def build_input_normalization_prompt(source: Any, as_of_date: str) -> str:
    source_text = source if isinstance(source, str) else json.dumps(source, ensure_ascii=False, indent=2)
    allowed = [key for key in STANDARD_PERSONA_KEYS if key != "relation"]
    return f"""
将任意格式的一条人物参考信息规范化为稀疏事实，不要生成或补全画像。
数据基准日期：{as_of_date}。

只输出以下 JSON 对象：
{{
  "explicit_facts": {{}},
  "soft_clues": {{}},
  "source_description": "",
  "conflicts": [],
  "unmapped_information": []
}}

规则：
- explicit_facts 只能使用这些顶层字段：{json.dumps(allowed, ensure_ascii=False)}。
- age 必须是整数；salary 必须是数值；birth 必须规范为 YYYY-MM-DD。
- home_address/workplace/birth_place 使用地址对象；body 使用 height/weight/BMI 对象；personality 使用 mbti/traits 对象；hobbies、favorite_foods、memory_date、aim 使用数组。
- 只把输入明确陈述的内容放入 explicit_facts，不得猜测缺失的年龄、性别、职业、收入、家庭或人格。
- 地址尽量规范为 province/city/district/street_name/street_number 的部分对象；没有的信息不要编造。
- 简介中的稳定但不够精确的信息放入 soft_clues，例如职业方向、兴趣方向、性格线索和生活方式线索。
- 六个描述字段不要作为锁定事实；原始描述合并保存在 source_description，后续阶段会重写。
- 区分当前事实、愿望、过去经历、临时地点和否定表达。例如“去北京出差”不是居住在北京。
- 输入内部有无法同时成立的明确事实时写入 conflicts，每项包含 path、values、message；不要自行选择。
- 有价值但无法映射的内容放入 unmapped_information。
- 不输出 Markdown、解释或额外字段。

原始输入：
{source_text}
""".strip()
