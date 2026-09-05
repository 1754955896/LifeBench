# -*- coding: utf-8 -*-
"""跨日行为摘要与当日变化设定。

这里只统计结构化事件和轨迹，不用关键词或自然语言规则理解活动语义。
当日设定是给 LLM 的软约束，用于打破连续多天的同质日程，而不是强制新增事件。
"""
from __future__ import annotations

import hashlib
import random
from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Mapping, Sequence


_HISTORY_LIMIT = 30


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _time_minutes(value: Any) -> int:
    try:
        hour, minute = str(value).split(":", 1)
        return int(hour) * 60 + int(minute)
    except (TypeError, ValueError):
        return 0


def _stable_rng(instance_id: Any, date: str) -> random.Random:
    raw = f"day-variation-v1|{instance_id}|{date}".encode("utf-8")
    seed = int(hashlib.sha256(raw).hexdigest()[:16], 16)
    return random.Random(seed)


def _weighted_choice(rng: random.Random, weights: Mapping[str, float]) -> str:
    positive = [(key, max(0.0, float(weight))) for key, weight in weights.items()]
    total = sum(weight for _, weight in positive)
    if total <= 0:
        return next(iter(weights))
    point = rng.random() * total
    cumulative = 0.0
    for key, weight in positive:
        cumulative += weight
        if point <= cumulative:
            return key
    return positive[-1][0]


def _window_summary(records: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not records:
        return {
            "days": 0,
            "average_unique_stops": 0.0,
            "average_travel_legs": 0.0,
            "average_travel_minutes": 0.0,
            "low_mobility_days": 0,
            "evening_out_days": 0,
            "social_days": 0,
            "exercise_days": 0,
            "exploratory_days": 0,
            "new_location_count": 0,
            "dominant_mobility_signature": "",
            "dominant_signature_days": 0,
        }
    count = len(records)
    signatures = Counter(str(item.get("mobility_signature") or "") for item in records)
    signatures.pop("", None)
    dominant, dominant_days = signatures.most_common(1)[0] if signatures else ("", 0)
    return {
        "days": count,
        "average_unique_stops": round(
            sum(_number(item.get("unique_stop_count")) for item in records) / count, 2
        ),
        "average_travel_legs": round(
            sum(_number(item.get("travel_leg_count")) for item in records) / count, 2
        ),
        "average_travel_minutes": round(
            sum(_number(item.get("travel_minutes")) for item in records) / count, 2
        ),
        "low_mobility_days": sum(bool(item.get("low_mobility")) for item in records),
        "evening_out_days": sum(bool(item.get("evening_out")) for item in records),
        "social_days": sum(bool(item.get("social_day")) for item in records),
        "exercise_days": sum(bool(item.get("exercise_day")) for item in records),
        "exploratory_days": sum(_number(item.get("new_location_count")) > 0 for item in records),
        "new_location_count": int(sum(_number(item.get("new_location_count")) for item in records)),
        "dominant_mobility_signature": dominant,
        "dominant_signature_days": dominant_days,
    }


def build_recent_behavior_summary(history: Any) -> Dict[str, Any]:
    """把跨日行为记录压缩为供生成器使用的近7/30天统计。"""
    records = [dict(item) for item in _list(history) if isinstance(item, dict)]
    records = records[-_HISTORY_LIMIT:]
    return {
        "schema_version": "recent_behavior_summary_v1",
        "last_7d": _window_summary(records[-7:]),
        "last_30d": _window_summary(records),
        "recent_day_types": [str(item.get("actual_day_type") or "") for item in records[-7:]],
        "recent_mobility_signatures": [
            str(item.get("mobility_signature") or "") for item in records[-7:]
        ],
    }


_WEEKDAY_ARCHETYPES = {
    "low_mobility": 0.14,
    "routine_commute": 0.28,
    "commute_with_errand": 0.25,
    "evening_activity": 0.18,
    "social_or_leisure": 0.10,
    "exploratory": 0.05,
}

_WEEKEND_ARCHETYPES = {
    "home_recovery": 0.18,
    "local_leisure": 0.27,
    "social_activity": 0.24,
    "exercise_outing": 0.16,
    "exploratory": 0.10,
    "long_distance": 0.05,
}

_ARCHETYPE_SETTINGS = {
    "low_mobility": ("low", "none", "0-1", "medium", "high"),
    "routine_commute": ("low", "low", "0-1", "low", "medium"),
    "commute_with_errand": ("medium", "low", "1-2", "medium", "medium"),
    "evening_activity": ("medium", "low", "1-2", "medium", "low"),
    "social_or_leisure": ("medium", "medium", "1-2", "medium", "low"),
    "exploratory": ("high", "high", "1-2", "low", "medium"),
    "home_recovery": ("low", "none", "0-1", "medium", "high"),
    "local_leisure": ("medium", "low", "1-2", "medium", "medium"),
    "social_activity": ("medium", "medium", "1-2", "medium", "low"),
    "exercise_outing": ("medium", "low", "1-2", "low", "medium"),
    "long_distance": ("high", "high", "1-2", "low", "low"),
}


def build_day_variation_context(
    *, history: Any, plan: Any, date: str, instance_id: Any = 0,
) -> Dict[str, Any]:
    """按日期和近期分布生成可复现的当日软约束。"""
    summary = build_recent_behavior_summary(history)
    recent = summary["last_7d"]
    try:
        is_weekend = datetime.strptime(date, "%Y-%m-%d").weekday() >= 5
    except (TypeError, ValueError):
        is_weekend = False
    plan_data = _dict(plan)
    date_attributes = _dict(plan_data.get("date_attribute"))
    holiday = str(
        date_attributes.get("holiday") or date_attributes.get("节日") or ""
    ).strip()
    has_holiday = holiday.lower() not in {
        "", "无", "否", "none", "null", "false", "非节假日",
    }
    if has_holiday:
        is_weekend = True
    weights = dict(_WEEKEND_ARCHETYPES if is_weekend else _WEEKDAY_ARCHETYPES)

    days = int(recent.get("days", 0) or 0)
    if days >= 3:
        repeated = int(recent.get("dominant_signature_days", 0) or 0)
        average_stops = _number(recent.get("average_unique_stops"))
        if repeated >= 3 or average_stops <= 2.2:
            for key in ("routine_commute", "low_mobility", "home_recovery"):
                if key in weights:
                    weights[key] *= 0.55
            for key in (
                "commute_with_errand", "evening_activity", "social_or_leisure",
                "local_leisure", "social_activity", "exploratory",
            ):
                if key in weights:
                    weights[key] *= 1.35
        if int(recent.get("evening_out_days", 0) or 0) == 0:
            for key in ("evening_activity", "social_or_leisure", "social_activity"):
                if key in weights:
                    weights[key] *= 1.45
        if int(recent.get("exercise_days", 0) or 0) == 0 and "exercise_outing" in weights:
            weights["exercise_outing"] *= 1.35
        if int(recent.get("new_location_count", 0) or 0) >= 5:
            if "exploratory" in weights:
                weights["exploratory"] *= 0.45
            if "long_distance" in weights:
                weights["long_distance"] *= 0.65

    required_event_count = len(_list(plan_data.get("events")))
    if required_event_count >= 6:
        for key in ("exploratory", "long_distance", "social_activity", "social_or_leisure"):
            if key in weights:
                weights[key] *= 0.70

    rng = _stable_rng(instance_id, date)
    day_type = _weighted_choice(rng, weights)
    mobility, novelty, extra_budget, mundane_density, schedule_slack = _ARCHETYPE_SETTINGS[day_type]
    return {
        "schema_version": "day_variation_v1",
        "day_type": day_type,
        "mobility_level": mobility,
        "novelty_level": novelty,
        "formal_extra_activity_budget": extra_budget,
        "mundane_detail_density": mundane_density,
        "schedule_slack": schedule_slack,
        "principles": {
            "required_events_remain_mandatory": True,
            "allow_unstructured_time": True,
            "avoid_single_theme_day": True,
            "mundane_details_do_not_require_new_stops": True,
            "soft_constraint": "若与必选事件、实际反馈、体力或时空可行性冲突，可以自然降级，不为满足类型强行出行。",
        },
    }


def _actual_day_type(
    unique_stop_count: int, travel_leg_count: int, travel_distance_km: float,
    evening_out: bool, new_location_count: int,
) -> str:
    if travel_distance_km >= 80:
        return "long_distance"
    if unique_stop_count <= 1 or travel_leg_count == 0:
        return "home_or_single_anchor"
    if evening_out:
        return "evening_out"
    if new_location_count > 0:
        return "exploratory_or_new_stop"
    if unique_stop_count <= 2 and travel_leg_count <= 2:
        return "routine_two_anchor"
    return "multi_stop"


def build_daily_behavior_record(
    *, date: str, location_records: Any, reflection: Any, history: Any,
    day_variation_context: Any = None,
) -> Dict[str, Any]:
    """从最终结构化行程和反思指标生成一天的行为记录。"""
    records = _dict(location_records)
    stops = [item for item in _list(records.get("stops")) if isinstance(item, dict)]
    legs = [item for item in _list(records.get("legs")) if isinstance(item, dict)]
    segments = [item for item in _list(records.get("event_segments")) if isinstance(item, dict)]
    stop_by_id = {str(item.get("stop_id") or ""): item for item in stops}

    location_ids: List[str] = []
    for stop in stops:
        location_id = str(stop.get("location_id") or stop.get("stop_id") or "")
        if location_id and location_id not in location_ids:
            location_ids.append(location_id)
    seen_ids = {
        str(location_id)
        for item in _list(history) if isinstance(item, dict)
        for location_id in _list(item.get("location_ids"))
        if location_id
    }
    novel_ids = []
    for stop in stops:
        location_id = str(stop.get("location_id") or stop.get("stop_id") or "")
        source = str(stop.get("source") or "")
        if location_id and location_id not in seen_ids and source != "persona_catalog":
            novel_ids.append(location_id)

    signature_parts: List[str] = []
    evening_out = False
    for segment in segments:
        if str(segment.get("kind") or "") != "activity":
            continue
        stop_id = str(segment.get("stop_id") or "")
        stop = stop_by_id.get(stop_id, {})
        category = str(stop.get("activity_type") or stop.get("category") or stop_id or "unknown")
        if not signature_parts or signature_parts[-1] != category:
            signature_parts.append(category)
        if _time_minutes(segment.get("end_time")) > 18 * 60 and category != "home":
            evening_out = True

    metrics = _dict(_dict(reflection).get("activity_metrics"))
    travel_minutes = int(round(sum(_number(item.get("duration_minutes")) for item in legs)))
    travel_distance = round(sum(_number(item.get("distance_km")) for item in legs), 2)
    unique_stop_count = len(location_ids)
    travel_leg_count = len(legs)
    new_location_count = len(set(novel_ids))
    variation = _dict(day_variation_context)
    return {
        "schema_version": "daily_behavior_record_v1",
        "date": date,
        "planned_day_type": str(variation.get("day_type") or ""),
        "actual_day_type": _actual_day_type(
            unique_stop_count, travel_leg_count, travel_distance,
            evening_out, new_location_count,
        ),
        "activity_segment_count": sum(
            str(item.get("kind") or "") == "activity" for item in segments
        ),
        "travel_leg_count": travel_leg_count,
        "unique_stop_count": unique_stop_count,
        "travel_minutes": travel_minutes,
        "travel_distance_km": travel_distance,
        "location_ids": location_ids,
        "new_location_count": new_location_count,
        "mobility_signature": ">".join(signature_parts),
        "low_mobility": unique_stop_count <= 2,
        "evening_out": evening_out,
        "social_day": _number(metrics.get("social_minutes")) > 0,
        "exercise_day": _number(metrics.get("exercise_minutes")) > 0,
    }


def append_daily_behavior_record(history: Any, record: Dict[str, Any]) -> List[Dict[str, Any]]:
    """按日期覆盖并保留最近30天，支持失败重试和 checkpoint 恢复。"""
    records = [dict(item) for item in _list(history) if isinstance(item, dict)]
    records = [item for item in records if str(item.get("date") or "") != record.get("date")]
    records.append(dict(record))
    records.sort(key=lambda item: str(item.get("date") or ""))
    return records[-_HISTORY_LIMIT:]
