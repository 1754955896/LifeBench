# -*- coding: utf-8 -*-
"""构造 thought 阶段的精简结构化输入，不用规则理解生活语义。"""
import copy
import json
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.lifebench.event.simulation.state import LongTermMemory
from .variation import (
    build_day_variation_context, build_mobility_day_budget,
    build_recent_behavior_summary,
)
from .location_inspiration import build_location_inspiration_context
from .activity_recommendation import build_activity_recommendation


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _first(mapping: Dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _normalize_holiday(value: Any) -> Any:
    """规范输入数据的空节日哨兵；这是格式归一化，不推断节日语义。"""
    value = str(value or "").strip()
    return "" if value.lower() in {
        "", "无", "否", "none", "null", "false", "非节假日",
    } else value


_SHORT_MEMORY_BUCKETS = ("recent", "periodic", "similar")


def _normalize_short_memory(value: Any) -> Dict[str, Any]:
    """把短期记忆统一成面向 LLM 的分桶结构。

    - 剥离 event_id / source / retrieved_ids / bootstrap 等记账字段，只保留语义字段；
    - 兼容旧扁平结构（recent_events + source），迁移为 recent/periodic/similar 三桶。
    """
    value = _dict(value)
    if "recent" not in value and "recent_events" in value:
        flat = value.get("recent_events")
        flat = flat if isinstance(flat, list) else []
        source_to_bucket = {"recent": "recent", "fuzzy": "recent", "periodic": "periodic", "similar": "similar"}
        bucketed: Dict[str, Any] = {"recent": [], "periodic": [], "similar": []}
        for item in flat:
            if not isinstance(item, dict):
                continue
            bucketed[source_to_bucket.get(item.get("source"), "recent")].append(item)
        value = bucketed
    normalized: Dict[str, Any] = {}
    for bucket in _SHORT_MEMORY_BUCKETS:
        records = value.get(bucket)
        records = records if isinstance(records, list) else []
        cleaned = []
        for item in records:
            if not isinstance(item, dict):
                continue
            cleaned.append({
                "date": str(item.get("date") or ""),
                "topic": str(item.get("topic") or ""),
                "events": str(item.get("events") or ""),
                "thought": str(item.get("thought") or ""),
                "confidence": item.get("confidence", 1.0),
            })
        normalized[bucket] = cleaned
    return normalized


def _date_environment(plan: Dict[str, Any], date: str) -> Dict[str, Any]:
    attributes = _dict(plan.get("date_attribute"))
    result = {
        "date": date,
        "weather": str(_first(attributes, "weather", "天气", default="")),
        "weekday": str(_first(attributes, "week", "星期", default="")),
    }
    holiday = _normalize_holiday(_first(attributes, "holiday", "节日", default=""))
    if holiday:
        result["holiday"] = holiday
    return result


def _previous_thought(mind, date: str) -> Dict[str, Any]:
    content = str(getattr(mind, "thought", "") or "")
    try:
        source_date: Optional[str] = (
            datetime.strptime(date, "%Y-%m-%d") - timedelta(days=1)
        ).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        source_date = None
    return {
        "source_date": source_date if content else None,
        "content": content,
        "available": bool(content),
    }


def build_subjective_context(mind, plan: Any, date: str) -> Dict[str, Any]:
    """分离记忆与上日更新；个人状态和需求语义由 reflection LLM 提供。"""
    plan_data = copy.deepcopy(plan) if isinstance(plan, dict) else {"raw": _text(plan)}
    long_memory = LongTermMemory.from_string(str(getattr(mind, "long_memory", "") or ""))
    long_memory_data = long_memory.to_dict()

    short_context = _normalize_short_memory(getattr(mind, "short_memory_context", None))

    previous_update = copy.deepcopy(_dict(getattr(mind, "next_day_context", None)))
    behavior_history = getattr(mind, "behavior_history", None)
    recent_behavior_summary = build_recent_behavior_summary(behavior_history)
    config = _dict(getattr(mind, "config", {}))
    trajectory_config = _dict(config.get("trajectory_assignment"))
    simulation_seed = trajectory_config.get("seed", 0)
    day_variation_context = build_day_variation_context(
        history=behavior_history,
        plan=plan_data,
        date=date,
        instance_id=getattr(mind, "instance_id", 0),
        simulation_seed=simulation_seed,
        distribution_config=_dict(
            trajectory_config.get("mobility_distribution_targets")
        ),
    )
    mobility_day_profile = build_mobility_day_budget(day_variation_context, plan_data)
    location_inspiration_context = build_location_inspiration_context(
        location_data=getattr(mind, "persona_location_data", None)
        or getattr(mind, "persona_address_data", None),
        trajectory_history=getattr(mind, "trajectory_location_history", None),
        mobility_profile=mobility_day_profile,
        date=date,
        instance_id=getattr(mind, "instance_id", 0),
        seed=simulation_seed,
        config=_dict(trajectory_config.get("location_opportunity_pool")),
    )
    activity_recommendation = build_activity_recommendation(
        day_variation=day_variation_context,
        recent_behavior_summary=recent_behavior_summary,
        mobility_day_profile=mobility_day_profile,
        location_inspiration_context=location_inspiration_context,
        persona=getattr(mind, "persona", None),
        plan=plan_data,
        date=date,
        instance_id=getattr(mind, "instance_id", 0),
        seed=simulation_seed,
    )
    state_and_needs = str(previous_update.get("state_and_needs") or "")
    # 兼容刚生成的旧 checkpoint；仅拼接旧字段，不再对文本做规则判断。
    if not state_and_needs:
        state_and_needs = "；".join(
            value for value in (
                str(previous_update.get("state") or "").strip(),
                str(previous_update.get("needs") or "").strip(),
            ) if value
        )
    return {
        "schema_version": "subjective_context_v7",
        "date": date,
        "persona": copy.deepcopy(getattr(mind, "persona", {})),
        "plan": plan_data,
        "long_memory": long_memory_data,
        "short_memory_context": copy.deepcopy(short_context),
        "previous_thought": _previous_thought(mind, date),
        "state_and_needs": state_and_needs,
        "environment": _date_environment(plan_data, date),
        "recent_behavior_summary": recent_behavior_summary,
        "day_variation_context": day_variation_context,
        "mobility_day_profile": mobility_day_profile,
        # Internal compatibility alias while trajectory modules migrate to the V2 name.
        "mobility_day_budget": mobility_day_profile,
        "location_inspiration_context": location_inspiration_context,
        "activity_recommendation": activity_recommendation,
        "bootstrap": {"is_cold_start": not bool(previous_update)},
    }
