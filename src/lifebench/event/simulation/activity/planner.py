# -*- coding: utf-8 -*-
"""在地点查询前规范化活动意图并压缩不必要的独立出行。

本模块刻意保持轻量：V1 的自然语言活动仍由 LLM 生成，程序只处理可稳定
判断的空间层级、来源、重复购物与必要事件覆盖，不试图理解全部生活语义。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List

from ..geolocation.models import StopIntent


MERGEABLE_ERRANDS = {"shopping"}
LOCAL_LOOP_TERMS = (
    "晨跑", "夜跑", "慢跑", "跑步", "散步", "遛狗", "健走", "绕小区",
    "骑行一圈", "环线骑行", "社区骑行",
)
GENERIC_LOOP_NAMES = {
    "晨跑", "夜跑", "慢跑", "跑步", "散步", "遛狗", "健走",
    "骑行", "骑行一圈", "环线骑行", "社区骑行",
}
PLAUSIBLE_ACTIVITY_TYPES = {"fitness", "leisure", "meal", "shopping", "other"}


@dataclass
class ActivityPlanResult:
    intents: List[StopIntent]
    dropped: List[Dict[str, str]] = field(default_factory=list)
    warnings: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "intents": [intent.to_dict() for intent in self.intents],
            "dropped": list(self.dropped),
            "warnings": list(self.warnings),
        }


def _normalize(intent: StopIntent, order: int) -> StopIntent:
    intent.order = order
    intent.provenance = intent.provenance if intent.provenance in {"plan", "memory", "inferred"} else "inferred"
    intent.flexibility = intent.flexibility if intent.flexibility in {"fixed", "movable", "optional"} else "movable"
    if intent.provenance == "plan":
        intent.required = True
    if intent.required:
        intent.flexibility = "fixed" if intent.flexibility == "optional" else intent.flexibility
    text = " ".join((intent.event_ref, intent.explicit_name, intent.keyword, intent.poi_type))
    # 意图 LLM 偶尔会把“晨跑”这种活动标签误填成 POI 名称。
    # 泛化环线名不是显式目的地，不应阻断附近搜索和本地环线兜底。
    if intent.explicit_name.strip() in GENERIC_LOOP_NAMES and not intent.explicit_location:
        intent.explicit_name = ""
    explicit_destination = bool(intent.explicit_name or intent.explicit_location)
    if (
        any(term in text for term in LOCAL_LOOP_TERMS)
        and not explicit_destination
        and not any(term in text for term in ("去公园", "到公园", "前往公园"))
    ):
        intent.mobility_pattern = "local_loop"
        intent.spatial_scope = "neighborhood"
        intent.query_type = "around"
        intent.anchor_role = intent.anchor_role or "home"
        intent.keyword = intent.keyword or "公园 健身步道"
        intent.poi_type = intent.poi_type or "公园|体育休闲服务"
        intent.maximum_travel_minutes = min(intent.maximum_travel_minutes or 15, 15)
        intent.preferred_radius_m = min(intent.preferred_radius_m or 1200, 1500)
        intent.allow_plausible_location = True
        if not intent.target_duration_minutes:
            intent.target_duration_minutes = _duration_minutes(intent.start_time, intent.end_time) or 30
    elif intent.activity_type not in {"home", "work", "education"} and intent.mobility_pattern == "micro":
        intent.spatial_scope = intent.spatial_scope if intent.spatial_scope in {"room", "building", "compound"} else "compound"
        intent.query_type = "micro"
        # 不再强制 micro 默认锚到 home：发生在上一停留点内部/附近的 micro（如
        # 商场内买咖啡）应锚到上一站。空 anchor_role 由 candidate_provider 的
        # `anchor or previous` 链自然解析。
        intent.maximum_travel_minutes = min(intent.maximum_travel_minutes or 15, 15)
    elif not intent.spatial_scope:
        intent.spatial_scope = "city"
    if (
        intent.activity_type in PLAUSIBLE_ACTIVITY_TYPES
        and intent.spatial_scope in {"building", "compound", "neighborhood"}
        and not explicit_destination
    ):
        intent.allow_plausible_location = True
    return intent


def _duration_minutes(start: str, end: str) -> int:
    try:
        left = datetime.strptime(start, "%H:%M")
        right = datetime.strptime(end, "%H:%M")
    except (TypeError, ValueError):
        return 0
    value = int((right - left).total_seconds() / 60)
    return value if value >= 0 else value + 24 * 60


def plan_activity_intents(intents: Iterable[StopIntent]) -> ActivityPlanResult:
    """规范化意图，并删除可安全合并的低置信度重复跑腿。

    只自动删除 ``optional + inferred`` 的重复购物。计划事件、历史待办、固定
    活动以及其他类型活动全部保留，避免启发式规则改变核心日程。
    """
    normalized = [_normalize(intent, index) for index, intent in enumerate(intents)]
    result: List[StopIntent] = []
    dropped: List[Dict[str, str]] = []
    seen_mergeable: Dict[str, StopIntent] = {}
    for intent in normalized:
        prior = seen_mergeable.get(intent.activity_type)
        can_drop = (
            intent.activity_type in MERGEABLE_ERRANDS
            and intent.provenance == "inferred"
            and not intent.required
            and intent.flexibility == "optional"
            and prior is not None
        )
        if can_drop:
            dropped.append({
                "activity_id": intent.stop_id,
                "merged_into": prior.stop_id,
                "reason": "可选推断购物已合并到当天较早的同类活动，避免独立重复往返",
            })
            continue
        result.append(intent)
        if intent.activity_type in MERGEABLE_ERRANDS:
            seen_mergeable[intent.activity_type] = intent

    for order, intent in enumerate(result):
        intent.order = order
    return ActivityPlanResult(intents=result, dropped=dropped)
