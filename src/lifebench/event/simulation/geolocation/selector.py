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

DISTANCE_CUTOFF_MULTIPLIER = {
    "meal": 0.35, "fitness": 0.55, "shopping": 0.80,
    "medical": 1.0, "leisure": 1.20, "other": 1.0,
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
                 epr_profile: Optional[EPRProfile] = None):
        self.seed = str(seed)
        self.novelty_level = (
            novelty_level if novelty_level in {"none", "low", "medium", "high"}
            else "medium"
        )
        self.epr_profile = epr_profile or EPRProfile()
        self.current_date = ""
        self.decision_trace = []

    def rank(self, intent: StopIntent, candidates: List[LocationCandidate], previous: Optional[LocationCandidate]) -> List[Tuple[LocationCandidate, float]]:
        eligible = [item for item in candidates if city_matches(intent.city, item.city)]
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

        approved_ids = set(intent.historical_candidate_ids)
        return_pool = [
            item for item in eligible
            if intent.epr_applicable
            and item.source == "trajectory_history"
            and item.location_id in approved_ids
        ]
        explore_pool = [item for item in eligible if item not in return_pool]
        exploration_probability = self._exploration_probability(intent)
        if not return_pool:
            decision = "explore_first_visit" if not approved_ids else "explore_no_valid_history"
            selected_pool = explore_pool
            exploration_probability = 1.0
        elif not explore_pool:
            decision = "return_no_new_candidate"
            selected_pool = return_pool
            exploration_probability = 0.0
        elif rng.random() < exploration_probability:
            decision = "explore"
            selected_pool = explore_pool
        else:
            decision = "return"
            selected_pool = return_pool

        if decision.startswith("return"):
            weighted = [
                (candidate, self._return_weight(intent, candidate))
                for candidate in selected_pool
            ]
        else:
            weighted = [
                (candidate, self._exploration_weight(intent, candidate, previous))
                for candidate in selected_pool
            ]
        ordered = self._weighted_order(weighted, rng)
        self._record(intent, decision, exploration_probability, return_pool, ordered)
        return ordered

    def _exploration_probability(self, intent: StopIntent) -> float:
        profile = self.epr_profile
        distinct = max(1, profile.distinct_location_count)
        category = EPR_ACTIVITY_RHO_MULTIPLIER.get(intent.activity_type, 1.0)
        novelty = {"none": 0.45, "low": 0.72, "medium": 1.0, "high": 1.45}[
            self.novelty_level
        ]
        probability = profile.rho * category * distinct ** (-profile.gamma) * novelty
        return max(0.02, min(0.95, probability))

    def _return_weight(self, intent: StopIntent, candidate: LocationCandidate) -> float:
        visits = max(1, int(candidate.raw.get("visit_count", 0) or 0))
        frequency = visits ** self.epr_profile.return_exponent
        recency = self._recency_weight(candidate.raw.get("last_seen_date"))
        time_match = self._time_match_weight(intent, candidate)
        semantic = 1.25 if candidate.category == intent.activity_type else 1.0
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
        attraction = 1.0 / math.log(candidate.map_rank + 2.0)
        semantic = 1.35 if candidate.category == intent.activity_type else 0.80
        return max(1e-9, distance_kernel * attraction * semantic)

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

    @staticmethod
    def _weighted_order(weighted: List[Tuple[LocationCandidate, float]],
                        rng: random.Random) -> List[Tuple[LocationCandidate, float]]:
        raced = []
        for candidate, weight in weighted:
            safe_weight = max(1e-9, float(weight))
            race = -math.log(max(1e-12, rng.random())) / safe_weight
            raced.append((candidate, race))
        raced.sort(key=lambda item: (item[1], item[0].location_id))
        return [(candidate, 1.0 / max(1e-9, race)) for candidate, race in raced]

    def _record(self, intent: StopIntent, decision: str, probability: float,
                return_pool: List[LocationCandidate],
                ordered: List[object]) -> None:
        candidates = []
        for item in ordered:
            candidate = item[0] if isinstance(item, tuple) else item
            candidates.append(candidate.location_id)
        self.decision_trace.append({
            "stop_id": intent.stop_id,
            "selection_policy": intent.selection_policy,
            "epr_applicable": bool(intent.epr_applicable),
            "requested_historical_candidate_ids": list(intent.historical_candidate_ids),
            "valid_return_candidate_ids": [item.location_id for item in return_pool],
            "decision": decision,
            "exploration_probability": round(float(probability), 4),
            "ranked_candidate_ids": candidates,
        })

    def _rng(self, stop_id: str) -> random.Random:
        digest = hashlib.sha256((self.seed + "|" + stop_id).encode("utf-8")).hexdigest()[:16]
        return random.Random(int(digest, 16))
