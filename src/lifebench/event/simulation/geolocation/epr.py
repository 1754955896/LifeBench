# -*- coding: utf-8 -*-
"""个体化 exploration-preferential-return 参数。

参数只从结构化跨日轨迹统计和地点注册表估计，不解析自然语言。短历史时使用
保守先验，历史增加后逐渐吸收人物自己的探索率、重复度和移动尺度。
"""
from dataclasses import asdict, dataclass
from typing import Any, Dict


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _clamp(low: float, high: float, value: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class EPRProfile:
    rho: float = 0.60
    gamma: float = 0.22
    return_exponent: float = 1.0
    distance_beta: float = 1.45
    distance_offset_km: float = 0.20
    distance_cutoff_km: float = 30.0
    characteristic_trip_km: float = 5.0
    distinct_location_count: int = 0
    return_eligible_count: int = 0
    observed_days: int = 0
    count_scope: str = "blended"
    global_count_weight: float = 0.35

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_personal_epr_profile(
    behavior_history: Any, location_history: Any, calibration: Any = None,
) -> EPRProfile:
    settings = calibration if isinstance(calibration, dict) else {}
    records = [item for item in (behavior_history or []) if isinstance(item, dict)][-30:]
    locations = [item for item in (location_history or []) if isinstance(item, dict)]
    days = len(records)
    total_stops = sum(_number(item.get("unique_stop_count")) for item in records)
    new_locations = sum(_number(item.get("new_location_count")) for item in records)
    observed_exploration = new_locations / max(1.0, total_stops)

    signatures = [str(item.get("mobility_signature") or "") for item in records]
    dominant_count = max((signatures.count(item) for item in set(signatures) if item), default=0)
    repeat_ratio = dominant_count / max(1, days)

    # 配置值是人群先验而不是硬覆盖。随着个人历史增加，最多按
    # personalization_weight 吸收个人观测，避免所有人物退化成同一套 EPR 参数。
    personalization_weight = _clamp(
        0.0, 1.0, _number(settings.get("personalization_weight", 0.70)),
    )
    observation_weight = min(
        personalization_weight,
        days / 30.0 * personalization_weight,
    )
    prior_rho = _clamp(0.10, 0.90, _number(settings.get("rho", 0.60)))
    prior_gamma = _clamp(0.05, 0.80, _number(settings.get("gamma", 0.22)))
    prior_return_exponent = _clamp(
        0.50, 1.80, _number(settings.get("return_exponent", 1.0)),
    )
    prior_beta = _clamp(
        0.80, 2.50, _number(settings.get("distance_beta", 1.45)),
    )
    prior_cutoff = _clamp(
        5.0, 150.0, _number(settings.get("distance_cutoff_km", 30.0)),
    )
    count_scope = str(settings.get("epr_count_scope") or "blended").strip().lower()
    if count_scope not in {"global", "context", "blended"}:
        count_scope = "blended"
    global_count_weight = _clamp(
        0.0, 1.0, _number(settings.get("epr_global_count_weight", 0.35)),
    )

    empirical_rho = _clamp(0.20, 0.90, 0.30 + observed_exploration * 1.80)
    empirical_gamma = _clamp(0.12, 0.60, 0.18 + repeat_ratio * 0.36)
    empirical_return_exponent = _clamp(0.70, 1.20, 0.75 + repeat_ratio * 0.35)
    empirical_beta = _clamp(1.20, 1.90, 1.30 + repeat_ratio * 0.40)

    rho = prior_rho * (1.0 - observation_weight) + empirical_rho * observation_weight
    gamma = prior_gamma * (1.0 - observation_weight) + empirical_gamma * observation_weight
    return_exponent = (
        prior_return_exponent * (1.0 - observation_weight)
        + empirical_return_exponent * observation_weight
    )

    total_legs = sum(_number(item.get("travel_leg_count")) for item in records)
    total_distance = sum(_number(item.get("travel_distance_km")) for item in records)
    characteristic = total_distance / total_legs if total_legs else 5.0
    characteristic = _clamp(0.8, 40.0, characteristic)
    cutoff_multiplier = _clamp(
        1.5, 6.0, _number(settings.get("distance_cutoff_multiplier", 3.0)),
    )
    empirical_cutoff = _clamp(8.0, 120.0, characteristic * cutoff_multiplier)
    cutoff = prior_cutoff * (1.0 - observation_weight) + empirical_cutoff * observation_weight
    beta = prior_beta * (1.0 - observation_weight) + empirical_beta * observation_weight

    distinct_ids = {
        str(item.get("location_id") or item.get("id") or "")
        for item in locations
        if str(item.get("location_id") or item.get("id") or "")
    }
    eligible_ids = {
        str(item.get("location_id") or item.get("id") or "")
        for item in locations
        if str(item.get("location_id") or item.get("id") or "")
        and item.get("return_eligible", True)
        and str(item.get("location_tier") or "") not in {"temporary", "episodic"}
    }
    return EPRProfile(
        rho=round(rho, 4),
        gamma=round(gamma, 4),
        return_exponent=round(return_exponent, 4),
        distance_beta=round(beta, 4),
        distance_cutoff_km=round(cutoff, 3),
        characteristic_trip_km=round(characteristic, 3),
        distinct_location_count=len(distinct_ids),
        return_eligible_count=len(eligible_ids),
        observed_days=days,
        count_scope=count_scope,
        global_count_weight=round(global_count_weight, 4),
    )
