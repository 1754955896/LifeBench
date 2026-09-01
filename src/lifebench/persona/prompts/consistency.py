"""Final persona consistency review prompt: traits + social circle naming."""

import json
from typing import Any, Dict, List, Optional

from .common import render_common_rules

PROMPT_VERSION = "persona-consistency-v1"

# 抽象价值观/价值取向词，不适合作为可观察的行为特质（提示词与确定性校验共用）。
ABSTRACT_TRAIT_MARKERS = (
    "权力", "仁慈", "成就", "安全", "传统", "博爱", "刺激", "享乐", "从众",
    "普适", "自我导向", "社会责任", "家庭导向", "导向", "价值", "取向",
)


def build_persona_consistency_prompt(
    profile: Dict[str, Any],
    relation_groups: List[Dict[str, Any]],
    as_of_date: str,
    soft_clues: Optional[Dict[str, Any]] = None,
) -> str:
    soft_clues = soft_clues or {}
    return f"""
你是画像最终一致性审查员。在画像定稿前修复两类语义问题：性格特质是否具体且自洽、社交圈名称是否与其内容/兴趣一致。
{render_common_rules(as_of_date)}

只输出一个 JSON 对象：
{{
  "traits": ["<2～4 个具体行为特质>"],
  "circle_renames": [{{"group_index": <整数>, "social_circle": "<修正后的圈名>"}}]
}}

任务一：重写 personality.traits。
- traits 必须是 2～4 个稳定、可观察、能互相区分的行为特质，例如「自律」「好胜」「对新事物好奇」「恋旧」「健谈」。
- 禁止使用抽象价值观/价值取向词，例如「权力」「仁慈」「成就」「安全」「传统」「博爱」「刺激」「享乐」「从众」「社会责任导向」「家庭导向」等。
- traits 之间不得自相矛盾（例如「权力」与「仁慈/社会责任」互斥），也不得与画像里的性格描述、生活方式、工作方式冲突。
- 依据画像已有的性格描述、兴趣爱好和软线索重写，保持人物性格连贯，而不是凭空更换性格。

任务二：修正 social_circle 名称与其内容的冲突。
- relation_groups 是关系圈列表，group_index 是其在列表中的下标（从 0 开始）。
- 若某圈的 social_circle 名称与该圈成员的 relation_description 或人物兴趣爱好明显不符（例如圈名是「科普读书会」但内容与描述是「硬科幻书友会」），则在该 group_index 下给出修正后的 social_circle。
- 只列出需要改名的圈；其余圈不要写入 circle_renames。工作、家庭、合租、学校等锚点圈若名称与内容一致，不要改动。
- 修正后的圈名要具体、稳定，并与该组成员的共同经历和兴趣一致。

人物画像（不含 relation）：
{json.dumps(profile, ensure_ascii=False, indent=2)}

关系圈：
{json.dumps(relation_groups, ensure_ascii=False, indent=2)}

软线索：
{json.dumps(soft_clues, ensure_ascii=False, indent=2)}
""".strip()
