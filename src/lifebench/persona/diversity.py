"""Run seeding, directives and dependency-light persona diversity metrics."""

import hashlib
import secrets
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, Optional, Set

from .eval.metrics import flatten_relation_groups, get_social_circle


DIVERSITY_LEVELS = frozenset({"low", "medium", "high"})


def create_run_seed(seed: Optional[int]) -> int:
    return int(seed) if seed is not None else secrets.randbits(63)


def stage_seed(run_seed: int, source_index: int, variant_index: int, stage: str) -> int:
    payload = "%s:%s:%s:%s" % (run_seed, source_index, variant_index, stage)
    return int(hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16], 16)


def diversity_directive(level: str) -> str:
    if level not in DIVERSITY_LEVELS:
        raise ValueError("diversity 必须是 low、medium 或 high")
    if level == "high":
        return "高差异：在不修改锁定事实的前提下，让未提供的年龄阶段、性别、教育、家庭、职业细节、经济状况、人格、兴趣组合和社交结构尽可能形成独特且一致的人生方案。"
    if level == "medium":
        return "中差异：保持输入事实，重点改变未锁定的职业路径、家庭阶段、人格、兴趣组合和社交结构。"
    return "低差异：保持主体人生结构，仅改变未锁定的次要细节、兴趣组合、表达和联系人。"


def minimum_distance(level: str) -> float:
    return {"low": 0.12, "medium": 0.28, "high": 0.42}[level]


def _value(data: Dict[str, Any], path: str) -> Any:
    current: Any = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _set_distance(left: Any, right: Any) -> float:
    left_set = {str(item).strip() for item in (left or []) if str(item).strip()}
    right_set = {str(item).strip() for item in (right or []) if str(item).strip()}
    if not left_set and not right_set:
        return 0.0
    return 1.0 - len(left_set & right_set) / len(left_set | right_set)


def _text_distance(left: Any, right: Any) -> float:
    left_text, right_text = str(left or "").strip(), str(right or "").strip()
    if not left_text and not right_text:
        return 0.0
    return 1.0 - SequenceMatcher(None, left_text, right_text).ratio()


def persona_distance(left: Dict[str, Any], right: Dict[str, Any], locked_fields: Optional[Iterable[str]] = None) -> float:
    locked: Set[str] = set(locked_fields or [])
    scores = []
    categorical = (
        "gender", "education", "job", "occupation", "family", "belief",
        "personality.mbti",
    )
    for path in categorical:
        if path.split(".")[0] not in locked:
            scores.append(0.0 if _value(left, path) == _value(right, path) else 1.0)
    if "age" not in locked and "birth" not in locked:
        left_age, right_age = left.get("age"), right.get("age")
        if isinstance(left_age, int) and isinstance(right_age, int):
            scores.append(min(abs(left_age - right_age) / 20.0, 1.0))
    for path in ("hobbies", "favorite_foods", "aim"):
        if path not in locked:
            scores.append(_set_distance(left.get(path), right.get(path)))
    scores.append(_text_distance(left.get("experience_desc"), right.get("experience_desc")))
    left_circles = [get_social_circle(item) for item in flatten_relation_groups(left.get("relation", []))]
    right_circles = [get_social_circle(item) for item in flatten_relation_groups(right.get("relation", []))]
    scores.append(_set_distance(left_circles, right_circles))
    return sum(scores) / len(scores) if scores else 0.0
