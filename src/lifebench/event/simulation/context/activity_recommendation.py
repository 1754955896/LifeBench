# -*- coding: utf-8 -*-
"""为主观思考生成「泛化指导 + 具体活动推荐」的移动参考层。

这里只基于结构化信号（近期行为摘要、当日变化设定、移动预算、地点灵感）打分，
不用关键词或自然语言规则理解活动语义；带可复现随机，输出是软参考而非必做清单。
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Mapping, Sequence

from .variation import _dict, _list, _number


# ---------------------------------------------------------------------------
# 活动目录：8 类 × 若干具体活动。label 是通用语义（不含具体人名/地点），
# 具体人物与地点的绑定由 location_inspiration_context 完成。
# 字段说明：
#   category      活动类别（用于日形态匹配与地点绑定）
#   novelty       routine / novel（是否属新尝试）
#   distance_tier 0=home 1=local 2=urban 3=long
#   location_kind home/anchor/familiar/citywide/social（绑哪个地点池）
#   social / is_exercise / indoor / evening  打分用结构化特征位
# ---------------------------------------------------------------------------
_ACTIVITY_CATALOG: List[Dict[str, Any]] = [
    # social 社交
    {"label": "约熟人聚餐或喝咖啡", "category": "social", "novelty": "routine", "distance_tier": 2, "location_kind": "social", "social": True, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "约朋友逛街或看电影", "category": "social", "novelty": "routine", "distance_tier": 2, "location_kind": "social", "social": True, "is_exercise": False, "indoor": False, "evening": True},
    {"label": "和朋友玩桌游或聚会", "category": "social", "novelty": "routine", "distance_tier": 2, "location_kind": "social", "social": True, "is_exercise": False, "indoor": False, "evening": True},
    {"label": "约运动搭子一起跑步或打球", "category": "social", "novelty": "routine", "distance_tier": 2, "location_kind": "social", "social": True, "is_exercise": True, "indoor": False, "evening": True},
    {"label": "拜访亲友或去对方家做客", "category": "social", "novelty": "routine", "distance_tier": 2, "location_kind": "social", "social": True, "is_exercise": False, "indoor": False, "evening": True},

    # exercise 运动
    {"label": "去公园慢跑或快走", "category": "exercise", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": True, "indoor": False, "evening": False},
    {"label": "去健身房或游泳馆锻炼", "category": "exercise", "novelty": "routine", "distance_tier": 2, "location_kind": "familiar", "social": False, "is_exercise": True, "indoor": True, "evening": False},
    {"label": "骑行或户外徒步", "category": "exercise", "novelty": "routine", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": True, "indoor": False, "evening": False},
    {"label": "在家做拉伸、瑜伽或核心训练", "category": "exercise", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": True, "indoor": True, "evening": False},
    {"label": "尝试一项新的运动", "category": "exercise", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": True, "indoor": False, "evening": False},

    # leisure_out 外出休闲
    {"label": "去商场逛街或探店", "category": "leisure_out", "novelty": "routine", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "去书店或咖啡店坐坐", "category": "leisure_out", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "去公园散步或放空", "category": "leisure_out", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "看电影或演出", "category": "leisure_out", "novelty": "routine", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": True, "evening": True},
    {"label": "逛博物馆或看展览", "category": "leisure_out", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": True, "evening": False},

    # leisure_home 居家休闲
    {"label": "在家看剧、电影或综艺", "category": "leisure_home", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "在家做饭或烘焙", "category": "leisure_home", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "在家打游戏", "category": "leisure_home", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "在家读书或听播客", "category": "leisure_home", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "在家整理房间或收拾物品", "category": "leisure_home", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},

    # errand 生活办事/采购
    {"label": "采购日用品或食材", "category": "errand", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "取快递、退换货或送修", "category": "errand", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "理发、美容或按摩", "category": "errand", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "办理生活业务或缴费", "category": "errand", "novelty": "routine", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": True, "evening": False},

    # meal 餐饮
    {"label": "尝试一家新餐厅", "category": "meal", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "自己做一顿与平时不同的饭", "category": "meal", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "点外卖换换口味", "category": "meal", "novelty": "routine", "distance_tier": 0, "location_kind": "home", "social": False, "is_exercise": False, "indoor": True, "evening": False},

    # culture 文化
    {"label": "看一场展览", "category": "culture", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "逛科技馆或博物馆", "category": "culture", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": True, "evening": False},
    {"label": "听一场讲座或沙龙", "category": "culture", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": True, "evening": False},

    # explore 探索新地点
    {"label": "去一个没去过的商圈或街区", "category": "explore", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "打卡一个新公园或景点", "category": "explore", "novelty": "novel", "distance_tier": 2, "location_kind": "citywide", "social": False, "is_exercise": False, "indoor": False, "evening": False},
    {"label": "尝试一项新爱好", "category": "explore", "novelty": "novel", "distance_tier": 1, "location_kind": "familiar", "social": False, "is_exercise": False, "indoor": True, "evening": False},
]


# 日形态 -> 命中该形态主题的活动类别集合（用于风格加分）
_DAY_TYPE_CATEGORY_MAP: Dict[str, set] = {
    "low_mobility": {"leisure_home"},
    "home_recovery": {"leisure_home"},
    "routine_commute": {"leisure_home", "errand"},
    "commute_with_errand": {"errand", "meal", "leisure_home"},
    "evening_activity": {"exercise", "leisure_out", "meal", "social"},
    "social_or_leisure": {"social", "leisure_out", "meal"},
    "social_activity": {"social", "leisure_out"},
    "local_leisure": {"leisure_out", "meal", "errand"},
    "exercise_outing": {"exercise"},
    "exploratory": {"explore", "culture", "meal"},
    "citywide_leisure": {"leisure_out", "culture", "meal", "explore"},
    "long_distance": {"explore", "culture", "leisure_out"},
}

# 活动类别 -> 首选地点池
_CATEGORY_POOL: Dict[str, str] = {
    "social": "social",
    "exercise": "familiar",
    "leisure_out": "citywide",
    "leisure_home": "home",
    "errand": "familiar",
    "meal": "familiar",
    "culture": "citywide",
    "explore": "citywide",
}

# 地点池检索优先级（首选池失败时依次降级）
_POOL_PRIORITY: Dict[str, Sequence[str]] = {
    "social": ("social_options", "citywide_options", "familiar_options"),
    "familiar": ("familiar_options", "citywide_options"),
    "citywide": ("citywide_options", "familiar_options"),
    "home": (),
}

# 活动类别 -> 可兼容的地点 category（location_inspiration 的 _compact 输出）
_COMPATIBLE_LOCATION_CATEGORIES: Dict[str, set] = {
    "social": {"social", "leisure", "meal"},
    "exercise": {"fitness", "leisure", "other"},
    "leisure_out": {"leisure", "shopping", "culture", "meal"},
    "leisure_home": set(),
    "errand": {"shopping", "other"},
    "meal": {"meal", "leisure"},
    "culture": {"culture", "leisure"},
    "explore": {"leisure", "culture", "shopping", "meal"},
}

# 距离层级 -> 代表性单程距离（用于判断是否落在目的地距离带内）
_TIER_KM: Dict[int, float] = {0: 0.0, 1: 1.5, 2: 8.0, 3: 25.0}


def _rng(seed: Any, instance_id: Any, date: str) -> random.Random:
    raw = "activity-recommendation-v1|%s|%s|%s" % (seed, instance_id, date)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return random.Random(int(digest, 16))


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _bind_location(candidate: Dict[str, Any], location_context: Dict[str, Any]) -> Dict[str, Any] | None:
    """按 location_kind 从地点灵感里挑同类别 POI，附 location_id + name。

    只绑定类别兼容的 POI；找不到兼容 POI 时返回 None（留语义），
    不降级绑定到任意 POI，避免「采购日用品 → 咖啡店」这类错配。
    """
    location_kind = str(candidate.get("location_kind") or "")
    compatible = _COMPATIBLE_LOCATION_CATEGORIES.get(str(candidate.get("category") or ""), set())
    if not compatible:
        return None
    for pool_key in _POOL_PRIORITY.get(location_kind, ()):
        options = _list(location_context.get(pool_key))
        if not options:
            continue
        matched = [
            row for row in options
            if isinstance(row, dict) and str(row.get("category") or "") in compatible
        ]
        if not matched:
            continue
        pick = matched[0]
        if pick.get("location_id"):
            return {"location_id": str(pick.get("location_id")), "name": str(pick.get("name") or "")}
    return None


def _build_guidance(
    day_variation: Dict[str, Any], recent: Dict[str, Any], rng: random.Random,
) -> List[Dict[str, Any]]:
    """Layer 1：方向性指导，结构化信号触发，带可复现抖动。"""
    day_type = str(day_variation.get("day_type") or "")
    days = int(recent.get("days", 0) or 0)
    social_days = int(recent.get("social_days", 0) or 0)
    exercise_days = int(recent.get("exercise_days", 0) or 0)
    evening_out_days = int(recent.get("evening_out_days", 0) or 0)
    low_mobility_days = int(recent.get("low_mobility_days", 0) or 0)
    new_location_count = int(recent.get("new_location_count", 0) or 0)
    average_stops = _number(recent.get("average_unique_stops"))

    merged: Dict[str, Dict[str, Any]] = {}

    def add(direction: str, strength: float, text: str) -> None:
        strength = _clamp(strength + rng.uniform(-0.1, 0.1))
        if direction not in merged or merged[direction]["strength"] < strength:
            merged[direction] = {"direction": direction, "strength": round(strength, 2), "text": text}

    _DAY_TYPE_DIRECTION = {
        "home_recovery": ("stay_home_recover", 0.7, "今日形态倾向宅家或低强度恢复"),
        "low_mobility": ("stay_home_recover", 0.7, "今日形态倾向宅家或低强度恢复"),
        "routine_commute": ("keep_routine", 0.6, "今日以常规通勤和稳定日常为主"),
        "commute_with_errand": ("errand_life", 0.55, "今日可在通勤链上顺路处理生活事务"),
        "evening_activity": ("increase_outing", 0.6, "今日可在晚间安排一项完整的外出活动"),
        "social_or_leisure": ("reach_out_social", 0.6, "今日可联系熟人安排社交或休闲"),
        "social_activity": ("reach_out_social", 0.65, "今日可安排半日社交或共同娱乐"),
        "local_leisure": ("increase_outing", 0.55, "今日可在社区或邻近城区安排轻松外出"),
        "exercise_outing": ("exercise", 0.6, "今日可根据体力安排一次运动或恢复训练"),
        "exploratory": ("explore_new", 0.65, "今日可尝试一种新活动或新地点类型"),
        "citywide_leisure": ("explore_new", 0.6, "今日若空闲允许可安排跨城区休闲活动"),
        "long_distance": ("explore_new", 0.55, "今日若动机时间充分可安排远距离出行"),
    }
    day_direction = _DAY_TYPE_DIRECTION.get(day_type)
    if day_direction:
        add(*day_direction)

    if days >= 1 and social_days < 1:
        add("reach_out_social", 0.6, "近7天几乎没有社交，可主动联系熟人")
    if days >= 1 and exercise_days == 0:
        add("exercise", 0.5, "近7天没有运动日，可安排一次轻量运动")
    if days >= 1 and evening_out_days == 0:
        add("increase_outing", 0.45, "近7天无晚间外出，可在有意愿时增加一次晚间活动")
    if days >= 1 and (low_mobility_days >= max(2, days // 2) or (days >= 3 and average_stops <= 2.2)):
        add("increase_outing", 0.55, "近期移动偏少，可增加一次外出或顺路活动")
    if days >= 1 and social_days >= 4:
        add("stay_home_recover", 0.5, "近期社交较密，可留出独处或居家时间")
    if days >= 1 and new_location_count >= 5:
        add("keep_routine", 0.5, "近期探索较多，可回到熟悉地点和普通生活")

    if not merged:
        add("keep_routine", 0.4, "近期分布平稳，维持日常节奏即可")

    return sorted(merged.values(), key=lambda item: item["strength"], reverse=True)[:4]


def _score_candidates(
    candidates: Sequence[Dict[str, Any]], day_variation: Dict[str, Any],
    recent: Dict[str, Any], mobility_profile: Dict[str, Any],
    location_context: Dict[str, Any], plan: Any, rng: random.Random,
) -> List[Dict[str, Any]]:
    """Layer 2：逐候选打分（基础 0.5 + 信号修正 + 抖动），输出带分、带理由。"""
    day_type = str(day_variation.get("day_type") or "")
    novelty_level = str(day_variation.get("novelty_level") or "medium")
    day_type_categories = _DAY_TYPE_CATEGORY_MAP.get(day_type, set())

    social_days = int(recent.get("social_days", 0) or 0)
    exercise_days = int(recent.get("exercise_days", 0) or 0)
    evening_out_days = int(recent.get("evening_out_days", 0) or 0)
    low_mobility_days = int(recent.get("low_mobility_days", 0) or 0)
    new_location_count = int(recent.get("new_location_count", 0) or 0)
    dominant_signature_days = int(recent.get("dominant_signature_days", 0) or 0)

    destination_band = mobility_profile.get("destination_distance_band_km")
    if not isinstance(destination_band, (list, tuple)) or len(destination_band) < 2:
        destination_band = [0.0, 30.0]
    band_low, band_high = float(destination_band[0]), float(destination_band[1])
    exploration_budget = int(mobility_profile.get("exploration_budget", 1) or 0)
    independent_trip_probability = _number(mobility_profile.get("independent_trip_probability"))

    required_count = len(_list(_dict(plan).get("events")))

    scored: List[Dict[str, Any]] = []
    for candidate in candidates:
        category = str(candidate.get("category") or "")
        novelty = str(candidate.get("novelty") or "routine")
        tier = int(candidate.get("distance_tier", 0) or 0)
        is_social = bool(candidate.get("social"))
        is_exercise = bool(candidate.get("is_exercise"))
        indoor = bool(candidate.get("indoor"))
        evening = bool(candidate.get("evening"))

        score = 0.5
        reasons: List[str] = []

        # 风格
        if category in day_type_categories:
            score += 0.2
            reasons.append("匹配今日形态 %s" % day_type)
        if novelty_level in {"medium", "high"} and novelty == "novel":
            score += 0.15
            reasons.append("今日倾向新颖尝试")
        elif novelty_level in {"low", "none"} and novelty == "routine":
            score += 0.15
        elif novelty_level in {"low", "none"} and novelty == "novel":
            score -= 0.15
        if day_type in {"home_recovery", "low_mobility"} and not indoor:
            score -= 0.2
            reasons.append("今日倾向宅家")

        # 历史
        if social_days < 1 and is_social:
            score += 0.25
            reasons.append("近7天社交偏少")
        if exercise_days == 0 and is_exercise:
            score += 0.2
            reasons.append("近7天无运动")
        if evening_out_days == 0 and evening:
            score += 0.15
            reasons.append("近7天无晚间外出")
        if dominant_signature_days >= 3 and tier > 0:
            score += 0.2
            reasons.append("近期移动链重复")
        if new_location_count >= 5 and novelty == "novel":
            score -= 0.2
            reasons.append("近期探索偏多")

        # 需求（结构化代理）
        if social_days >= 4 and is_social:
            score -= 0.15
            reasons.append("近期社交过密")
        if low_mobility_days >= 2 and indoor:
            score += 0.1

        # 移动预算
        if tier > 0 and band_low <= _TIER_KM.get(tier, 0.0) <= band_high:
            score += 0.1
        if exploration_budget == 0 and novelty == "novel":
            score -= 0.25
            reasons.append("今日探索预算为零")
        if independent_trip_probability < 0.1 and tier >= 2:
            score -= 0.1
        if required_count >= 6 and tier >= 2:
            score -= 0.1
            reasons.append("必选事件较多")

        # 地点绑定
        location = _bind_location(candidate, location_context)
        if location:
            score += 0.15

        raw_score = score + rng.uniform(-0.08, 0.08)
        scored.append({
            "activity": str(candidate.get("label") or ""),
            "category": category,
            "novelty": novelty,
            "distance_tier": tier,
            "location": location,
            "raw_score": raw_score,
            "reasons": reasons[:4],
        })

    # 相对归一化到 [0,1]，避免多种信号叠加后全部顶到 1.0 而失去区分度。
    if scored:
        raw_values = [item["raw_score"] for item in scored]
        raw_min, raw_max = min(raw_values), max(raw_values)
        spread = raw_max - raw_min
        for item in scored:
            normalized = 0.5 if spread < 1e-9 else (item["raw_score"] - raw_min) / spread
            item["score"] = round(_clamp(normalized), 3)
            item.pop("raw_score", None)

    scored.sort(key=lambda item: item["score"], reverse=True)

    # 多样性：top-4 里同一类别最多 2 条，避免某个信号（如社交缺位）让推荐全是同类。
    picked: List[Dict[str, Any]] = []
    category_count: Dict[str, int] = {}
    for item in scored:
        category = item["category"]
        if category_count.get(category, 0) >= 2:
            continue
        picked.append(item)
        category_count[category] = category_count.get(category, 0) + 1
        if len(picked) >= 4:
            break
    return picked


def build_activity_recommendation(
    *, day_variation: Any, recent_behavior_summary: Any, mobility_day_profile: Any,
    location_inspiration_context: Any, persona: Any = None, plan: Any = None,
    date: str, instance_id: Any = 0, seed: Any = 0,
) -> Dict[str, Any]:
    """生成「泛化指导 + 具体活动推荐」两级软参考，确定性可复现。"""
    variation = _dict(day_variation)
    recent = _dict(_dict(recent_behavior_summary).get("last_7d"))
    mobility_profile = _dict(mobility_day_profile)
    location_context = _dict(location_inspiration_context)
    rng = _rng(seed, instance_id, date)

    guidance = _build_guidance(variation, recent, rng)
    recommendations = _score_candidates(
        _ACTIVITY_CATALOG, variation, recent, mobility_profile,
        location_context, plan, rng,
    )

    return {
        "guidance": guidance,
        "recommendations": recommendations,
    }
