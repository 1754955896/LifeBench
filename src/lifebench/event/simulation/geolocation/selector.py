# -*- coding: utf-8 -*-
"""确定性的 EPR-lite + 重力模型候选排序。"""
import hashlib
import datetime as dt
import math
import random
from typing import List, Optional, Tuple

from .catalog import city_matches
from .epr import EPRProfile
from .models import LocationCandidate, StopIntent


EPR_ACTIVITY_RHO_MULTIPLIER = {
    "meal": 0.85, "fitness": 0.65, "shopping": 0.80,
    "medical": 0.45, "leisure": 1.15, "other": 1.0,
}

EPR_ACTIVITY_BOUNDS = {
    "meal": (0.08, 0.45), "fitness": (0.06, 0.40),
    "shopping": (0.10, 0.50), "leisure": (0.12, 0.60),
    "medical": (0.03, 0.25), "other": (0.06, 0.50),
}

DISTANCE_CUTOFF_MULTIPLIER = {
    "meal": 0.35, "fitness": 0.55, "shopping": 0.80,
    "medical": 1.0, "leisure": 1.20, "other": 1.0,
}

SEMANTIC_WEIGHT = {
    "return": {
        "match": 1.25, "compatible": 1.05, "unknown": 0.90,
        "conflict": 0.25,
    },
    "explore": {
        "match": 1.35, "compatible": 1.00, "unknown": 0.75,
        "conflict": 0.10,
    },
}


def haversine_km(first: str, second: str) -> float:
    try:
        lon1, lat1 = (float(value) for value in first.split(","))
        lon2, lat2 = (float(value) for value in second.split(","))
    except (TypeError, ValueError):
        return 0.0
    radius = 6371.0088
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    value = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(max(0.0, 1 - value)))


class GravitySelector:
    def __init__(self, seed: str = "0", novelty_level: str = "medium",
                 epr_profile: Optional[EPRProfile] = None,
                 selection_temperature: float = 0.75,
                 preference_boost: float = 1.5,
                 repetition_fatigue_step: float = 0.10,
                 repetition_fatigue_cap: float = 0.30):
        self.seed = str(seed)
        self.novelty_level = (
            novelty_level if novelty_level in {"none", "low", "medium", "high"}
            else "medium"
        )
        self.epr_profile = epr_profile or EPRProfile()
        self.selection_temperature = max(0.25, min(2.0, float(selection_temperature)))
        self.preference_boost = max(0.0, min(4.0, float(preference_boost)))
        self.repetition_fatigue_step = max(
            0.0, min(0.50, float(repetition_fatigue_step))
        )
        self.repetition_fatigue_cap = max(
            0.0, min(1.0, float(repetition_fatigue_cap))
        )
        self.current_date = ""
        self.decision_trace = []

    def rank(self, intent: StopIntent, candidates: List[LocationCandidate], previous: Optional[LocationCandidate]) -> List[Tuple[LocationCandidate, float]]:
        eligible = [item for item in candidates if city_matches(intent.city, item.city)]
        if intent.selection_policy in {"gravity", "random"}:
            non_conflicting = [
                item for item in eligible
                if self._semantic_status(intent, item) != "conflict"
            ]
            # 地图类别明确冲突时优先剔除；全部候选都冲突时保留原池，
            # 让后续重组/兜底有机会处理，而不是把活动直接变成无地点。
            if non_conflicting:
                eligible = non_conflicting
        rng = self._rng(intent.stop_id)
        if intent.selection_policy == "best_match":
            ordered = sorted(enumerate(eligible), key=lambda pair: (
                pair[1].map_rank, pair[0], pair[1].location_id,
            ))
            self._record(intent, "best_match", 0.0, [], [item for _, item in ordered])
            return [(item, 1.0 / (index + 1.0)) for index, (_, item) in enumerate(ordered)]
        if intent.selection_policy == "random":
            # 被动但未具名的地点从合格候选中确定性随机抽取；不看前一地点距离。
            ordered = list(eligible)
            rng.shuffle(ordered)
            self._record(intent, "random", 0.0, [], ordered)
            return [(item, 1.0 / (index + 1.0)) for index, item in enumerate(ordered)]
        if intent.reuse_location_id or intent.reuse_policy == "must_return":
            ordered = sorted(eligible, key=lambda item: (item.map_rank, item.location_id))
            self._record(intent, "explicit_return", 0.0, ordered, ordered)
            return [(item, 1.0 / (index + 1.0)) for index, item in enumerate(ordered)]

        preferred_ids = set(intent.preferred_candidate_ids)
        return_pool = [
            item for item in eligible
            if intent.epr_applicable
            and (
                bool(item.raw.get("epr_return_candidate", False))
                or (
                    item.source == "trajectory_history"
                    and item.location_id in set(intent.historical_candidate_ids)
                )
            )
        ]
        explore_pool = [item for item in eligible if item not in return_pool]
        preferred_pool = [
            item for item in eligible if item.location_id in preferred_ids
        ]
        exploration_probability, probability_factors = self._exploration_probability(
            intent, return_pool,
        )
        random_draw = rng.random() if return_pool and explore_pool else None
        if not return_pool:
            decision = (
                "explore_no_valid_history"
                if intent.historical_candidate_ids else "explore_first_visit"
            )
            selected_pool = explore_pool
            exploration_probability = 1.0
        elif not explore_pool:
            decision = "return_no_new_candidate"
            selected_pool = return_pool
            exploration_probability = 0.0
        elif random_draw < exploration_probability:
            decision = "explore"
            selected_pool = explore_pool
        else:
            decision = "return"
            selected_pool = return_pool

        strength = max(0.0, min(1.0, float(intent.preference_strength)))
        preferred_multiplier = 1.0 + self.preference_boost * strength
        weighted = []
        for candidate in selected_pool:
            if decision.startswith("return"):
                weight = self._return_weight(intent, candidate)
            else:
                weight = self._exploration_weight(intent, candidate, previous)
            if candidate in preferred_pool:
                weight *= preferred_multiplier
            weighted.append((candidate, weight))
        ordered = self._weighted_order(weighted, rng)
        self._record(
            intent, decision, exploration_probability, return_pool, ordered,
            random_draw=random_draw, probability_factors=probability_factors,
            preferred_pool=preferred_pool,
            preference_boost=preferred_multiplier if preferred_pool else 1.0,
        )
        return ordered

    def _exploration_probability(
        self, intent: StopIntent, return_pool: List[LocationCandidate],
    ) -> Tuple[float, dict]:
        profile = self.epr_profile
        global_distinct = max(1, int(profile.return_eligible_count or 0))
        context_distinct = max(1, len(return_pool))
        if profile.count_scope == "global":
            distinct = float(global_distinct)
        elif profile.count_scope == "context":
            distinct = float(context_distinct)
        else:
            global_weight = max(0.0, min(1.0, profile.global_count_weight))
            distinct = (
                global_distinct ** global_weight
                * context_distinct ** (1.0 - global_weight)
            )
        category = EPR_ACTIVITY_RHO_MULTIPLIER.get(intent.activity_type, 1.0)
        novelty = {"none": 0.50, "low": 0.75, "medium": 1.0, "high": 1.25}[
            self.novelty_level
        ]
        fatigue = self._repetition_fatigue(return_pool)
        probability = profile.rho * category * distinct ** (-profile.gamma) * novelty * fatigue
        low, high = EPR_ACTIVITY_BOUNDS.get(intent.activity_type, (0.06, 0.65))
        result = max(low, min(high, probability))
        return result, {
            "return_eligible_count": profile.return_eligible_count,
            "global_distinct_count": global_distinct,
            "context_distinct_count": context_distinct,
            "effective_distinct_count": round(distinct, 4),
            "count_scope": profile.count_scope,
            "global_count_weight": round(profile.global_count_weight, 4),
            "activity_multiplier": category,
            "novelty_multiplier": novelty,
            "repetition_fatigue_multiplier": fatigue,
            "bounds": [low, high],
        }

    def _repetition_fatigue(self, candidates: List[LocationCandidate]) -> float:
        """连续数日复访提高探索概率；只读取结构化访问日期。"""
        try:
            current = dt.datetime.strptime(self.current_date, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return 1.0
        recent_days = set()
        for candidate in candidates:
            for value in candidate.raw.get("recent_visit_dates", []) or []:
                try:
                    delta = (current - dt.datetime.strptime(str(value), "%Y-%m-%d").date()).days
                except (TypeError, ValueError):
                    continue
                if 1 <= delta <= 3:
                    recent_days.add(delta)
        consecutive = 0
        while consecutive + 1 in recent_days:
            consecutive += 1
        return 1.0 + min(
            self.repetition_fatigue_cap,
            consecutive * self.repetition_fatigue_step,
        )

    def _return_weight(self, intent: StopIntent, candidate: LocationCandidate) -> float:
        visits = max(1, int(candidate.raw.get("visit_count", 0) or 0))
        frequency = visits ** self.epr_profile.return_exponent
        recency = self._recency_weight(candidate.raw.get("last_seen_date"))
        time_match = self._time_match_weight(intent, candidate)
        semantic = SEMANTIC_WEIGHT["return"][self._semantic_status(intent, candidate)]
        return max(1e-9, frequency * recency * time_match * semantic)

    def _exploration_weight(self, intent: StopIntent, candidate: LocationCandidate,
                            previous: Optional[LocationCandidate]) -> float:
        distance = haversine_km(previous.coordinates, candidate.coordinates) if previous else 0.0
        profile = self.epr_profile
        cutoff = profile.distance_cutoff_km * DISTANCE_CUTOFF_MULTIPLIER.get(
            intent.activity_type, 1.0
        )
        cutoff = max(1.0, cutoff)
        # 截断幂律：短距离占主导，同时保留随个人移动尺度变化的中长距离尾部。
        distance_kernel = (
            (distance + profile.distance_offset_km) ** (-profile.distance_beta)
            * math.exp(-distance / cutoff)
        )
        if intent.target_distance_km > 0:
            target = max(0.2, intent.target_distance_km)
            distance_kernel *= math.exp(-abs(math.log((distance + 0.2) / target)))
        if intent.distance_band_km and len(intent.distance_band_km) >= 2:
            low, high = intent.distance_band_km[:2]
            if distance < low:
                band_fit = math.exp(-(low - distance) / max(0.8, low + 0.5))
            elif distance > high:
                band_fit = math.exp(-(distance - high) / max(1.0, high * 0.45))
            else:
                band_fit = 1.35
            sensitivity = {"high": 1.6, "medium": 1.0, "low": 0.55}.get(
                intent.distance_sensitivity, 1.0,
            )
            distance_kernel *= band_fit ** sensitivity
        attraction = 1.0 / math.log(candidate.map_rank + 2.0)
        semantic = SEMANTIC_WEIGHT["explore"][self._semantic_status(intent, candidate)]
        return max(1e-9, distance_kernel * attraction * semantic)

    @staticmethod
    def _semantic_status(intent: StopIntent, candidate: LocationCandidate) -> str:
        declared = str(candidate.raw.get("semantic_status") or "").strip()
        if declared in {"match", "compatible", "unknown", "conflict"}:
            return declared
        if intent.activity_type == "other" or candidate.category == "other":
            return "unknown"
        if candidate.category == intent.activity_type:
            return "match"
        compatible = {
            frozenset(("fitness", "leisure")),
            frozenset(("shopping", "meal")),
        }
        if frozenset((intent.activity_type, candidate.category)) in compatible:
            return "compatible"
        return "conflict"

    def _preference_weight(
        self, intent: StopIntent, candidate: LocationCandidate,
        previous: Optional[LocationCandidate],
    ) -> float:
        if (
            candidate.source == "trajectory_history"
            and candidate.location_id in set(intent.historical_candidate_ids)
        ):
            base = self._return_weight(intent, candidate)
        else:
            base = self._exploration_weight(intent, candidate, previous)
        return base * (1.0 + self.preference_boost * max(
            0.0, min(1.0, float(intent.preference_strength))
        ))

    def _recency_weight(self, last_seen_date: object) -> float:
        try:
            current = dt.datetime.strptime(self.current_date, "%Y-%m-%d")
            previous = dt.datetime.strptime(str(last_seen_date), "%Y-%m-%d")
            days = max(0, (current - previous).days)
        except (TypeError, ValueError):
            return 1.0
        return 1.0 + 0.35 * math.exp(-days / 14.0)

    def _time_match_weight(self, intent: StopIntent,
                           candidate: LocationCandidate) -> float:
        bucket = self._time_bucket(self.current_date, intent.start_time)
        count = int((candidate.raw.get("visit_time_buckets") or {}).get(bucket, 0) or 0)
        return 1.0 + math.log1p(count) * 0.18

    @staticmethod
    def _time_bucket(date: str, time: str) -> str:
        try:
            day_kind = "weekend" if dt.datetime.strptime(date, "%Y-%m-%d").weekday() >= 5 else "weekday"
        except (TypeError, ValueError):
            day_kind = "weekday"
        try:
            hour = int(str(time).split(":", 1)[0])
        except (TypeError, ValueError):
            hour = 12
        period = "morning" if hour < 11 else "noon" if hour < 14 else "afternoon" if hour < 18 else "evening"
        return "%s_%s" % (day_kind, period)

    def _weighted_order(self, weighted: List[Tuple[LocationCandidate, float]],
                        rng: random.Random) -> List[Tuple[LocationCandidate, float]]:
        raced = []
        for candidate, weight in weighted:
            safe_weight = max(1e-9, float(weight))
            effective_weight = safe_weight ** (1.0 / self.selection_temperature)
            race = -math.log(max(1e-12, rng.random())) / effective_weight
            raced.append((candidate, race, effective_weight))
        raced.sort(key=lambda item: (item[1], item[0].location_id))
        # 排序仍然是可复现的加权随机顺序，但返回给路线分配器的是稳定的
        # 基础权重，而不是随机 race 的倒数，避免路线评分被随机噪声支配。
        return [(candidate, weight) for candidate, _, weight in raced]

    def _record(self, intent: StopIntent, decision: str, probability: float,
                return_pool: List[LocationCandidate],
                ordered: List[object], random_draw: Optional[float] = None,
                probability_factors: Optional[dict] = None,
                preferred_pool: Optional[List[LocationCandidate]] = None,
                preference_probability: float = 0.0,
                preference_draw: Optional[float] = None,
                preference_boost: float = 1.0) -> None:
        candidates = []
        for item in ordered:
            candidate = item[0] if isinstance(item, tuple) else item
            candidates.append(candidate.location_id)
        self.decision_trace.append({
            "stop_id": intent.stop_id,
            "selection_policy": intent.selection_policy,
            "epr_applicable": bool(intent.epr_applicable),
            "requested_historical_candidate_ids": list(intent.historical_candidate_ids),
            "requested_preferred_candidate_ids": list(intent.preferred_candidate_ids),
            "valid_return_candidate_ids": [item.location_id for item in return_pool],
            "valid_preferred_candidate_ids": [
                item.location_id for item in (preferred_pool or [])
            ],
            "decision": decision,
            "exploration_probability": round(float(probability), 4),
            "random_draw": None if random_draw is None else round(float(random_draw), 4),
            "probability_factors": probability_factors or {},
            "preference_probability": round(float(preference_probability), 4),
            "preference_draw": (
                None if preference_draw is None else round(float(preference_draw), 4)
            ),
            "preference_boost": round(float(preference_boost), 4),
            "selection_temperature": round(self.selection_temperature, 4),
            "distance_tier": intent.distance_tier,
            "distance_band_km": list(intent.distance_band_km),
            "ranked_candidate_ids": candidates,
            "candidate_semantics": {
                candidate.location_id: self._semantic_status(intent, candidate)
                for candidate in (
                    item[0] if isinstance(item, tuple) else item for item in ordered
                )
            },
        })

    def _rng(self, stop_id: str) -> random.Random:
        digest = hashlib.sha256((self.seed + "|" + self.current_date + "|" + stop_id).encode("utf-8")).hexdigest()[:16]
        return random.Random(int(digest, 16))
