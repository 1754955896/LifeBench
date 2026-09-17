# -*- coding: utf-8 -*-
"""跨日行为摘要与当日变化设定。

这里只统计结构化事件和轨迹，不用关键词或自然语言规则理解活动语义。
当日设定是给 LLM 的软约束，用于打破连续多天的同质日程，而不是强制新增事件。
"""
from __future__ import annotations

import hashlib
import math
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


def _stable_rng(instance_id: Any, date: str, simulation_seed: Any = 0) -> random.Random:
    raw = f"day-variation-v2|{simulation_seed}|{instance_id}|{date}".encode("utf-8")
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
            "average_distance_km": 0.0,
            "average_radius_gyration_km": 0.0,
            "urban_activity_days": 0,
            "long_distance_days": 0,
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
        "average_distance_km": round(
            sum(
                _number(item.get("travel_distance_km") or item.get("route_distance_km"))
                for item in records
            ) / count, 2
        ),
        "average_radius_gyration_km": round(
            sum(_number(item.get("radius_gyration_km")) for item in records) / count, 2
        ),
        "urban_activity_days": sum(
            30 <= _number(item.get("travel_distance_km") or item.get("route_distance_km")) < 80
            for item in records
        ),
        "long_distance_days": sum(
            _number(item.get("travel_distance_km") or item.get("route_distance_km")) >= 80
            for item in records
        ),
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
    "low_mobility": 0.18,
    "routine_commute": 0.31,
    "commute_with_errand": 0.22,
    "evening_activity": 0.14,
    "social_or_leisure": 0.08,
    "exploratory": 0.04,
    "citywide_leisure": 0.03,
}

_WEEKEND_ARCHETYPES = {
    "home_recovery": 0.23,
    "local_leisure": 0.24,
    "social_activity": 0.17,
    "exercise_outing": 0.12,
    "exploratory": 0.08,
    "citywide_leisure": 0.09,
    "long_distance": 0.07,
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
    "citywide_leisure": ("high", "medium", "1-3", "low", "medium"),
}


# daily distance, macro stops, destination distance, maximum single trip,
# radius of gyration and the prior chance that one leg exceeds 15 km.
_MOBILITY_ARCHETYPE_PROFILES = {
    "low_mobility": ([0, 10], [1, 3], [0, 4], [0, 2], [0, 3], 0.01),
    "home_recovery": ([0, 8], [1, 3], [0, 3], [0, 2], [0, 2.5], 0.01),
    "local_leisure": ([5, 20], [2, 4], [1, 8], [2, 5], [1, 5], 0.02),
    "routine_commute": ([8, 25], [2, 3], [2, 12], [2, 8], [2, 7], 0.02),
    "commute_with_errand": ([12, 35], [3, 5], [2, 15], [4, 10], [3, 9], 0.04),
    "evening_activity": ([15, 40], [3, 5], [3, 18], [5, 15], [4, 10], 0.06),
    "social_or_leisure": ([15, 50], [3, 5], [3, 20], [5, 18], [4, 11], 0.08),
    "social_activity": ([15, 50], [3, 5], [3, 20], [5, 18], [4, 11], 0.08),
    "exercise_outing": ([5, 30], [2, 4], [1, 12], [2, 10], [2, 7], 0.03),
    "exploratory": ([15, 50], [3, 5], [3, 22], [6, 20], [4, 12], 0.10),
    "citywide_leisure": ([30, 80], [3, 5], [5, 25], [10, 25], [8, 12], 0.14),
    "long_distance": ([60, 180], [3, 5], [10, 80], [15, 80], [10, 40], 0.22),
}


_ACTIVITY_STIMULI = {
    "low_mobility": ["保留居家休息和附近短活动，不为丰富度专程远行"],
    "home_recovery": ["以恢复、家务和低强度生活为主，允许完全不外出"],
    "local_leisure": ["可在社区或邻近城区安排公园、餐饮、采购或轻松活动"],
    "routine_commute": ["维持主要通勤骨架，只安排自然的用餐和自由时间"],
    "commute_with_errand": ["可沿通勤链增加一次采购、维修、理发或生活办事"],
    "evening_activity": ["可在下班后安排一项完整的运动、餐饮或娱乐活动"],
    "social_or_leisure": ["可联系已有关系中的熟人，安排聚餐或休闲活动"],
    "social_activity": ["可联系已有关系中的熟人，安排半日社交或共同娱乐"],
    "exercise_outing": ["可根据体力安排户外、场馆运动或恢复训练"],
    "exploratory": ["可改变一种活动或地点，在当天完成一次有动机的新尝试"],
    "citywide_leisure": ["若空闲允许，可去同城其他城区安排景点、商场、餐饮或娱乐组成的活动链"],
    "long_distance": ["只有动机和时间充分时才安排远郊、跨区或更远目的地"],
}


_EXTRA_ACTIVITY_TYPES = {
    "low_mobility": "none_or_micro",
    "home_recovery": "recovery_or_home",
    "routine_commute": "none_or_local",
    "commute_with_errand": "life_service",
    "evening_activity": "leisure_or_exercise",
    "social_or_leisure": "social_or_leisure",
    "social_activity": "social",
    "local_leisure": "local_leisure",
    "exercise_outing": "exercise",
    "exploratory": "novel_experience",
    "citywide_leisure": "citywide_leisure",
    "long_distance": "long_distance_leisure",
}


def _sample_extra_activity_target(
    day_type: str, budget: str, seed_key: str,
) -> tuple[int, str, bool, str]:
    """Turn a vague range into one reproducible daily soft target.

    Active archetypes already won a probabilistic day-type draw, so their
    target starts at one.  Low/recovery/routine days retain a genuine chance of
    no formal extra activity.  The target may still be downgraded by the LLM
    when required events or feasibility conflict.
    """
    try:
        low_text, high_text = str(budget).split("-", 1)
        low, high = max(0, int(low_text)), max(0, int(high_text))
    except (TypeError, ValueError):
        low, high = 0, 1
    if high < low:
        low, high = high, low
    rng = random.Random(int(hashlib.sha256(
        (seed_key + "|extra-activity-target").encode("utf-8")
    ).hexdigest()[:16], 16))
    passive_probability = {
        "low_mobility": 0.08,
        "home_recovery": 0.06,
        "routine_commute": 0.18,
    }.get(day_type)
    if passive_probability is not None:
        count = 1 if high >= 1 and rng.random() < passive_probability else 0
    else:
        count = max(1, low) if high >= 1 else 0
        if high > count and rng.random() < 0.15:
            count += 1
        if high > count and rng.random() < 0.03:
            count += 1
    count = min(high, count)
    mobility_role = (
        "urban_optional" if day_type in {
            "social_or_leisure", "social_activity", "exploratory",
            "citywide_leisure", "long_distance",
        }
        else "local_chain" if day_type == "commute_with_errand"
        else "local_optional"
    )
    return (
        count,
        _EXTRA_ACTIVITY_TYPES.get(day_type, "general_life"),
        bool(count),
        mobility_role,
    )


def build_day_variation_context(
    *, history: Any, plan: Any, date: str, instance_id: Any = 0,
    simulation_seed: Any = 0, distribution_config: Any = None,
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
    configured = _dict(distribution_config).get(
        "weekend_archetype_weights" if is_weekend else "weekday_archetype_weights",
        {},
    )
    if isinstance(configured, dict):
        for key, value in configured.items():
            if key not in weights:
                continue
            try:
                weights[key] = max(0.0, float(value))
            except (TypeError, ValueError):
                continue

    days = int(recent.get("days", 0) or 0)
    if days == 0:
        # 冷启动使用人群先验。降低而不禁止尾部日型，否则短分片中几乎
        # 永远不会出现跨城区/长距离日，总体分布会被人为截断。
        if "citywide_leisure" in weights:
            weights["citywide_leisure"] *= 0.65
        if "long_distance" in weights:
            weights["long_distance"] *= 0.45
        if "exploratory" in weights:
            weights["exploratory"] *= 0.75
        for key in (
            "routine_commute", "commute_with_errand", "low_mobility",
            "home_recovery", "local_leisure",
        ):
            if key in weights:
                weights[key] *= 1.25
    if days >= 3:
        repeated = int(recent.get("dominant_signature_days", 0) or 0)
        average_stops = _number(recent.get("average_unique_stops"))
        if repeated >= 3 or average_stops <= 2.2:
            for key in ("routine_commute", "low_mobility", "home_recovery"):
                if key in weights:
                    weights[key] *= 0.80
            for key in (
                "commute_with_errand", "evening_activity", "social_or_leisure",
                "local_leisure", "social_activity", "exploratory", "citywide_leisure",
            ):
                if key in weights:
                    weights[key] *= 1.15
        if int(recent.get("evening_out_days", 0) or 0) == 0:
            for key in ("evening_activity", "social_or_leisure", "social_activity"):
                if key in weights:
                    weights[key] *= 1.20
        if int(recent.get("exercise_days", 0) or 0) == 0 and "exercise_outing" in weights:
            weights["exercise_outing"] *= 1.20
        if int(recent.get("new_location_count", 0) or 0) >= 5:
            if "exploratory" in weights:
                weights["exploratory"] *= 0.45
            if "long_distance" in weights:
                weights["long_distance"] *= 0.65
        if int(recent.get("urban_activity_days", 0) or 0) == 0 and "citywide_leisure" in weights:
            weights["citywide_leisure"] *= 1.20
        if int(recent.get("long_distance_days", 0) or 0) > 0 and "long_distance" in weights:
            weights["long_distance"] *= 0.55

    required_event_count = len(_list(plan_data.get("events")))
    if required_event_count >= 6:
        for key in (
            "exploratory", "long_distance", "social_activity", "social_or_leisure",
            "citywide_leisure", "evening_activity",
        ):
            if key in weights:
                weights[key] *= 0.70

    rng = _stable_rng(instance_id, date, simulation_seed)
    day_type = _weighted_choice(rng, weights)
    mobility, novelty, extra_budget, mundane_density, schedule_slack = _ARCHETYPE_SETTINGS[day_type]
    seed_key = "day-variation-v2|%s|%s|%s" % (
        simulation_seed, instance_id, date,
    )
    (
        preferred_extra_activity_count,
        preferred_extra_activity_type,
        prefer_independent_topic,
        preferred_mobility_role,
    ) = _sample_extra_activity_target(day_type, extra_budget, seed_key)
    history_signals = []
    if days == 0:
        history_signals.append("暂无近期结构化移动历史，今日使用人群先验与可复现随机抽样")
    else:
        if int(recent.get("dominant_signature_days", 0) or 0) >= 3:
            history_signals.append("近期同一移动链连续出现，可温和提高第三地点或顺路活动概率")
        if _number(recent.get("average_unique_stops")) <= 2.2:
            history_signals.append("近期日均宏观地点较少，空闲且状态允许时可考虑多一个自然停留点")
        if int(recent.get("evening_out_days", 0) or 0) == 0:
            history_signals.append("近七日无晚间外出，仅在人物有意愿时增加晚间活动可能")
        if int(recent.get("urban_activity_days", 0) or 0) == 0:
            history_signals.append("近期无30–80公里城市活动日，休息日可温和增加跨城区活动概率")
        if int(recent.get("long_distance_days", 0) or 0) > 0:
            history_signals.append("近期已有长距离日，不需要为尾部分布连续安排远行")
    return {
        "schema_version": "day_variation_v2",
        "seed_key": seed_key,
        "day_type": day_type,
        "day_archetype": day_type,
        "mobility_level": mobility,
        "novelty_level": novelty,
        "formal_extra_activity_budget": extra_budget,
        "preferred_extra_activity_count": preferred_extra_activity_count,
        "preferred_extra_activity_type": preferred_extra_activity_type,
        "prefer_independent_topic": prefer_independent_topic,
        "preferred_mobility_role": preferred_mobility_role,
        "mundane_detail_density": mundane_density,
        "schedule_slack": schedule_slack,
        "history_signals": history_signals[:4],
        "base_distribution_source": "config" if configured else "builtin",
        "principles": {
            "required_events_remain_mandatory": True,
            "allow_unstructured_time": True,
            "avoid_single_theme_day": True,
            "mundane_details_do_not_require_new_stops": True,
            "soft_constraint": "若与必选事件、实际反馈、体力或时空可行性冲突，可以自然降级，不为满足类型强行出行。",
        },
    }


def build_mobility_day_budget(day_variation: Any, plan: Any) -> Dict[str, Any]:
    """Build the V2 day profile; targets are soft and never remove required events."""
    variation = _dict(day_variation)
    level = str(variation.get("mobility_level") or "medium")
    day_type = str(variation.get("day_type") or "")
    profile = _MOBILITY_ARCHETYPE_PROFILES.get(
        day_type, _MOBILITY_ARCHETYPE_PROFILES["routine_commute"]
    )
    distance_band, stops, destination_band, max_trip_band, gyration_band, long_probability = profile
    stop_min, stop_max = stops
    trip_min, trip_max = {
        "low": (0, 4), "medium": (2, 8), "high": (4, 10),
    }.get(level, (2, 8))
    explore_min, explore_max = (
        (0, 1) if level == "low" else ((1, 3) if level == "high" else (0, 2))
    )
    required = len(_list(_dict(plan).get("events")))
    trip_max = max(trip_max, min(12, required + 2))
    # 区间控制总体分布，区间内的可复现随机目标避免所有同类日都落在同一值。
    target_rng = random.Random(int(hashlib.sha256(
        (str(variation.get("seed_key") or "") + "|mobility-targets").encode("utf-8")
    ).hexdigest()[:16], 16))
    distance_fraction = (target_rng.random() + target_rng.random()) / 2.0
    sampled_distance = round(
        float(distance_band[0]) + (float(distance_band[1]) - float(distance_band[0])) * distance_fraction,
        1,
    )
    sampled_stops = target_rng.randint(int(stop_min), int(stop_max))
    independent_probability = {
        "low_mobility": 0.05, "home_recovery": 0.03, "routine_commute": 0.08,
        "commute_with_errand": 0.15, "evening_activity": 0.28,
        "social_or_leisure": 0.30, "social_activity": 0.30,
        "local_leisure": 0.18, "exercise_outing": 0.18,
        "exploratory": 0.35, "citywide_leisure": 0.45, "long_distance": 0.55,
    }.get(day_type, 0.15)
    preferred_windows = (
        ["weekday_evening"] if day_type in {"evening_activity", "social_or_leisure"}
        else ["weekend_daytime", "weekend_evening"] if day_type in {
            "social_activity", "local_leisure", "exercise_outing", "exploratory", "citywide_leisure",
        } else []
    )
    return {
        "schema_version": "mobility_day_profile_v2",
        "seed_key": str(variation.get("seed_key") or ""),
        "day_type": day_type,
        "day_archetype": day_type,
        "mobility_level": level,
        "novelty_level": str(variation.get("novelty_level") or "medium"),
        "soft_constraint": True,
        "default_application": "attempt_unless_required_plan_or_feasibility_conflicts",
        "daily_distance_band_km": list(distance_band),
        "sampled_daily_distance_target_km": sampled_distance,
        "destination_distance_band_km": list(destination_band),
        "max_single_trip_band_km": list(max_trip_band),
        "target_radius_gyration_km": list(gyration_band),
        "macro_stop_range": [stop_min, stop_max],
        "sampled_macro_stop_target": sampled_stops,
        "trip_count_range": [trip_min, trip_max],
        "unique_macro_location_range": [stop_min, stop_max],
        "activity_radius_km": float(max(destination_band)),
        "exploration_budget": explore_max,
        "exploration_stop_range": [explore_min, explore_max],
        "long_trip_probability": long_probability,
        "independent_trip_probability": independent_probability,
        "preferred_outing_windows": preferred_windows,
        "distance_band_prior": {
            "local": 0.80 if level == "low" else (0.38 if level == "high" else 0.55),
            "urban": 0.18 if level == "low" else (0.48 if level == "high" else 0.39),
            "long": 0.02 if level == "low" else (0.14 if level == "high" else 0.06),
        },
        "activity_stimuli": list(_ACTIVITY_STIMULI.get(day_type, [])),
        "history_signals": list(variation.get("history_signals", [])),
        "activity_chain_prior": (
            ["H-X-Y-Z-H", "H-X-Y-H"] if day_type == "citywide_leisure"
            else ["H-W-X-H", "H-W-H"] if day_type in {
                "routine_commute", "commute_with_errand", "evening_activity"
            } else ["H-X-H", "H-X-Y-H"]
        ),
        "allow_intercity": "only_when_required_or_narratively_justified",
        "budget_source": "recent_history_plan_day_variation",
        "instruction": "先保留必选事件；默认尝试落实软画像。若冲突，由LLM调整弹性活动并记录降级原因。",
    }


# mobility_day_profile 中与 day_variation_context 重复、或纯记账对 LLM 无用的字段。
# 只用于主观/客观模板打印的精简视图；程序化消费者（地点灵感、分配器）仍用完整结构。
_MOBILITY_PROFILE_LEAN_DROP = {
    "schema_version", "seed_key", "day_type", "day_archetype",
    "mobility_level", "novelty_level", "history_signals",
    "soft_constraint", "default_application", "budget_source", "instruction",
}


def lean_mobility_day_profile(profile: Any) -> Dict[str, Any]:
    """返回去掉重复/记账字段后的移动画像，供 LLM 模板打印，避免与 day_variation_context 重复。"""
    return {
        key: value
        for key, value in _dict(profile).items()
        if key not in _MOBILITY_PROFILE_LEAN_DROP
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
        if location_id and location_id not in seen_ids and source not in {
            "persona_catalog", "persona_familiar",
        }:
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
    distance_band_counts = {"local": 0, "urban": 0, "long": 0}
    for leg in legs:
        distance = _number(leg.get("distance_km"))
        bucket = "local" if distance < 3 else ("urban" if distance < 15 else "long")
        distance_band_counts[bucket] += 1
    dwell_by_stop: Dict[str, float] = {}
    for segment in segments:
        if str(segment.get("kind") or "") != "activity":
            continue
        stop_id = str(segment.get("stop_id") or "")
        duration = max(0, _time_minutes(segment.get("end_time")) - _time_minutes(segment.get("start_time")))
        if stop_id:
            dwell_by_stop[stop_id] = dwell_by_stop.get(stop_id, 0.0) + duration
    weighted_points = []
    for stop in stops:
        try:
            longitude = float(stop.get("longitude"))
            latitude = float(stop.get("latitude"))
        except (TypeError, ValueError):
            continue
        weight = max(1.0, dwell_by_stop.get(str(stop.get("stop_id") or ""), 1.0))
        weighted_points.append((longitude, latitude, weight))
    radius_gyration = 0.0
    if weighted_points:
        total_weight = sum(point[2] for point in weighted_points)
        center_lon = sum(point[0] * point[2] for point in weighted_points) / total_weight
        center_lat = sum(point[1] * point[2] for point in weighted_points) / total_weight
        latitude_km = 110.574
        longitude_km = 111.320 * math.cos(math.radians(center_lat))
        squared = sum(
            point[2] * (
                ((point[0] - center_lon) * longitude_km) ** 2
                + ((point[1] - center_lat) * latitude_km) ** 2
            )
            for point in weighted_points
        ) / total_weight
        radius_gyration = round(math.sqrt(max(0.0, squared)), 2)
    unique_stop_count = len(location_ids)
    travel_leg_count = len(legs)
    new_location_count = len(set(novel_ids))
    variation = _dict(day_variation_context)
    return {
        "schema_version": "daily_behavior_record_v2",
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
        "route_distance_km": travel_distance,
        "radius_gyration_km": radius_gyration,
        "macro_stop_count": unique_stop_count,
        "long_stay_location_count": sum(value >= 60 for value in dwell_by_stop.values()),
        "distance_band_counts": distance_band_counts,
        "location_ids": location_ids,
        "new_location_count": new_location_count,
        "return_location_count": max(0, unique_stop_count - new_location_count),
        "mobility_signature": ">".join(signature_parts),
        "low_mobility": travel_distance <= 10.0,
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
