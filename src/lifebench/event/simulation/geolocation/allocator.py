# -*- coding: utf-8 -*-
"""按停留顺序联合选择地点、交通方式与通行时间。"""
import datetime as dt
import hashlib
import math
from typing import Any, Dict, List, Optional, Tuple

from .candidate_provider import CandidateProvider
from .catalog import LocationCatalog, city_matches
from .epr import EPRProfile
from .mode import ModePlanner, RouteChoice
from .models import (
    LocationCandidate, PlausibleLocationSpec, ResolvedStop, StopIntent,
    TrajectoryAssignment, TravelLeg,
)
from .selector import GravitySelector


DEFAULT_MAX_LEG_MINUTES = {
    "meal": 20, "shopping": 45, "fitness": 45, "medical": 60,
    "leisure": 60, "education": 60, "work": 90, "home": 90, "other": 45,
}

SCOPE_MAX_DISTANCE_M = {
    "room": 30, "building": 100, "compound": 300,
    "neighborhood": 1500, "district": 8000, "city": 15000,
}


def offset_coordinates(coordinates: str, distance_m: int, salt: str) -> str:
    """相对锚点按稳定方向偏移，用于未核验叙事地点的估算坐标。"""
    try:
        lon, lat = (float(value) for value in coordinates.split(","))
    except (TypeError, ValueError):
        return coordinates
    digest = hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8]
    bearing = int(digest, 16) / float(0xFFFFFFFF) * 2 * math.pi
    north_m = math.cos(bearing) * distance_m
    east_m = math.sin(bearing) * distance_m
    lat += north_m / 110570.0
    lon += east_m / max(1.0, 111320.0 * math.cos(math.radians(lat)))
    return "%.6f,%.6f" % (lon, lat)


class TrajectoryAllocator:
    def __init__(self, maptools: Any, persona_addresses: Any, persona: Any,
                 seed: str = "0", candidate_limit: int = 12, route_top_k: int = 4,
                 novelty_level: str = "medium", mobility_level: str = "medium",
                 epr_profile: Optional[EPRProfile] = None):
        self.catalog = LocationCatalog(persona_addresses)
        self.provider = CandidateProvider(maptools, self.catalog, candidate_limit)
        self.selector = GravitySelector(
            seed, novelty_level=novelty_level, epr_profile=epr_profile,
        )
        self.novelty_level = self.selector.novelty_level
        self.mobility_level = (
            mobility_level if mobility_level in {"low", "medium", "high"}
            else "medium"
        )
        self.mode_planner = ModePlanner(maptools, persona)
        self.route_top_k = max(1, route_top_k)

    def allocate(self, intents: List[StopIntent], date: str = "",
                 plausible_fallbacks: Optional[Dict[str, PlausibleLocationSpec]] = None,
                 budget_aware: bool = True) -> TrajectoryAssignment:
        assignment = TrajectoryAssignment(date=date)
        self.selector.current_date = date
        self.selector.decision_trace = []
        plausible_fallbacks = plausible_fallbacks or {}
        previous_candidate = None  # type: Optional[LocationCandidate]
        previous_intent = None  # type: Optional[StopIntent]
        route_queries = 0

        for intent in sorted(intents, key=lambda item: item.order):
            if (
                intent.reuse_location_id
                and self.catalog.by_location_id(intent.reuse_location_id) is None
            ):
                assignment.violations.append({
                    "code": "reuse_location_unresolved", "stop_id": intent.stop_id,
                    "reuse_location_id": intent.reuse_location_id,
                    "message": "LLM指定的历史location_id不在动态地点注册表中",
                })
                # 禁止非法 ID 静默降级为上一地点、住宅或新的地图候选。
                continue
            pool = self.provider.get(intent, previous_candidate)
            ranked = self.selector.rank(intent, pool, previous_candidate)
            candidate, route, over_budget = self._choose(
                intent, previous_intent, previous_candidate, ranked,
                budget_aware=budget_aware,
            )
            route_queries += min(len(ranked), self.route_top_k) if previous_candidate else 0
            degraded = False
            fallback_spec = plausible_fallbacks.get(intent.stop_id)
            if (
                fallback_spec and previous_candidate
                and intent.selection_policy == "gravity"
                and (candidate is None or over_budget)
            ):
                candidate, route = self._plausible_candidate(intent, previous_candidate, fallback_spec)
                degraded = True
                over_budget = False
                assignment.violations.append({
                    "code": "plausible_location_fallback", "stop_id": intent.stop_id,
                    "message": "真实地点和重规划仍不可行，使用有来源标记的叙事地点",
                    "reason": fallback_spec.generation_reason,
                })
            if budget_aware and over_budget and previous_candidate and intent.reuse_policy != "must_return":
                # 不再把语义不同的活动静默改成“在当前地点完成”。保留最短的真实
                # 候选并暴露预算告警，供后续 LLM 重排、合并或替换地点。
                degraded = True
                assignment.violations.append({
                    "code": "travel_replan_required", "stop_id": intent.stop_id,
                    "message": "候选地点超过通行预算，需要调整活动时间、顺序或地点",
                })
            if candidate is None:
                # 候选为空时优先取目标城市的画像锚点，其次住宅，最后才借用上一地点；
                # 跨城借用上一地点会触发 city_mismatch，这里明确优先同城锚点。
                candidate = (
                    self.catalog.anchor(
                        intent.anchor_role or intent.activity_type, intent.city,
                    )
                    or self.catalog.anchor("home")
                    or previous_candidate
                )
                degraded = True
                assignment.violations.append({
                    "code": "location_fallback", "stop_id": intent.stop_id,
                    "message": "没有可用候选地点，退回目标城市锚点或住宅锚点",
                })
            if candidate is None:
                assignment.violations.append({
                    "code": "location_unresolved", "stop_id": intent.stop_id,
                    "message": "没有可用候选地点且不存在住宅锚点",
                })
                continue

            if intent.city and candidate.city and not city_matches(intent.city, candidate.city):
                degraded = True
                assignment.violations.append({
                    "code": "city_mismatch", "stop_id": intent.stop_id,
                    "expected_city": intent.city, "actual_city": candidate.city,
                    "message": "地点不在活动指定城市，禁止以出发地附近坐标代替跨城目的地",
                })

            stop = self._resolved(intent, candidate, degraded)
            if previous_candidate and assignment.stops:
                route = route or self.mode_planner.route(previous_candidate, candidate, intent)
                if budget_aware:
                    budget = self._budget(previous_intent, intent)
                    feasible = route.leg_type == "local_loop" or route.duration_minutes <= budget
                    if over_budget or not feasible:
                        assignment.violations.append({
                            "code": "travel_budget_exceeded", "stop_id": intent.stop_id,
                            "duration_minutes": route.duration_minutes, "budget_minutes": budget,
                        })
                else:
                    # 预算分析交由后续一轮 LLM 完成，这里只记录真实通行时长。
                    feasible = True
                departure, arrival = self._leg_times(
                    previous_intent, intent, route.duration_minutes, route.leg_type,
                )
                assignment.legs.append(TravelLeg(
                    leg_id="leg_%03d" % (len(assignment.legs)),
                    origin_stop_id=assignment.stops[-1].stop_id,
                    destination_stop_id=stop.stop_id,
                    origin_name=assignment.stops[-1].name,
                    destination_name=stop.name,
                    mode=route.mode,
                    duration_minutes=route.duration_minutes,
                    distance_km=round(route.distance_km, 2),
                    departure_time=departure,
                    arrival_time=arrival,
                    source=route.source,
                    feasible=feasible,
                    confidence=route.confidence,
                    leg_type=route.leg_type,
                    narrative_route=route.narrative_route,
                    map_verified=route.map_verified,
                ))
            assignment.stops.append(stop)
            previous_candidate = candidate
            previous_intent = intent

        severe = any(item["code"] in {
            "location_unresolved", "location_fallback",
            "reuse_location_unresolved", "city_mismatch",
        }
                     for item in assignment.violations)
        assignment.feasible = not severe and all(leg.feasible for leg in assignment.legs)
        assignment.diagnostics = {
            "allocator": "personalized_epr_truncated_powerlaw_v2",
            "budget_aware": bool(budget_aware),
            "novelty_level": self.novelty_level,
            "mobility_level": self.mobility_level,
            "epr_profile": self.selector.epr_profile.to_dict(),
            "epr_decisions": list(self.selector.decision_trace),
            "stop_count": len(assignment.stops),
            "leg_count": len(assignment.legs),
            "map_or_heuristic_route_evaluations": route_queries,
            "degraded_stop_count": sum(1 for stop in assignment.stops if stop.degraded),
            "low_confidence_stop_count": sum(1 for stop in assignment.stops if stop.confidence < 0.8),
            "plausible_stop_count": sum(1 for stop in assignment.stops if stop.source == "llm_plausible"),
            "local_loop_count": sum(1 for leg in assignment.legs if leg.leg_type == "local_loop"),
            "selection_policy_counts": {
                policy: sum(1 for intent in intents if intent.selection_policy == policy)
                for policy in ("gravity", "best_match", "random")
            },
        }
        return assignment

    def _plausible_candidate(self, intent: StopIntent, previous: LocationCandidate,
                             spec: PlausibleLocationSpec) -> Tuple[LocationCandidate, RouteChoice]:
        is_loop = spec.location_kind == "local_loop" or intent.mobility_pattern == "local_loop"
        scope_limit = SCOPE_MAX_DISTANCE_M.get(intent.spatial_scope, 1500)
        requested = spec.estimated_distance_m or intent.preferred_radius_m or min(600, scope_limit)
        distance_m = max(0, min(int(requested), scope_limit))
        coordinates = previous.coordinates if is_loop else offset_coordinates(
            previous.coordinates, max(80, distance_m), intent.stop_id,
        )
        digest = hashlib.sha1((previous.location_id + "|" + intent.stop_id).encode("utf-8")).hexdigest()[:12]
        candidate = LocationCandidate(
            location_id="plausible_" + digest,
            name=spec.name,
            address=spec.narrative_address or (previous.address + "附近"),
            coordinates=coordinates,
            province=previous.province,
            city=previous.city,
            district=previous.district,
            adcode=previous.adcode,
            category=intent.activity_type,
            role="local_loop" if is_loop else "plausible_destination",
            source="llm_plausible",
            anchor_id=previous.location_id,
            distance_m=float(distance_m),
            raw={
                "spatial_scope": intent.spatial_scope,
                "generation_reason": spec.generation_reason,
                "map_verified": False,
            },
            confidence=max(0.2, min(float(spec.confidence), 0.65)),
            map_verified=False,
        )
        mode = spec.mode if spec.mode in {"walking", "bicycling", "running"} else "walking"
        if is_loop:
            mode = "running" if intent.activity_type == "fitness" and mode == "walking" else mode
            duration = spec.estimated_travel_minutes or intent.target_duration_minutes or 30
            duration = max(10, min(int(duration), 180))
            speeds = {"walking": 4.2, "running": 8.0, "bicycling": 14.0}
            distance_km = intent.target_distance_km or duration / 60.0 * speeds[mode]
            route = RouteChoice(
                mode, duration, round(max(0.5, distance_km), 2), "llm_plausible",
                leg_type="local_loop", narrative_route=spec.narrative_route,
                confidence=candidate.confidence, map_verified=False,
            )
        else:
            speeds = {"walking": 4.5, "bicycling": 12.0, "running": 8.0}
            duration = spec.estimated_travel_minutes or max(
                2, int(round(distance_m / 1000.0 / speeds[mode] * 60)),
            )
            route = RouteChoice(
                mode, duration, round(distance_m / 1000.0, 2), "llm_plausible",
                narrative_route=spec.narrative_route,
                confidence=candidate.confidence, map_verified=False,
            )
        return candidate, route

    @staticmethod
    def _offset_coordinates(coordinates: str, distance_m: int, salt: str) -> str:
        return offset_coordinates(coordinates, distance_m, salt)

    def _choose(self, intent: StopIntent, previous_intent: Optional[StopIntent],
                previous: Optional[LocationCandidate],
                ranked: List[Tuple[LocationCandidate, float]],
                budget_aware: bool = True) -> Tuple[Optional[LocationCandidate], Optional[RouteChoice], bool]:
        if not ranked:
            return None, None, False
        if previous is None:
            return ranked[0][0], None, False
        if not budget_aware:
            # 不做预算分析：直接取排序第一候选并记录真实通行时长，判断交给 LLM。
            candidate = ranked[0][0]
            route = self.mode_planner.route(previous, candidate, intent)
            return candidate, route, False
        budget = self._budget(previous_intent, intent)
        if intent.selection_policy in {"best_match", "random"}:
            candidate = ranked[0][0]
            route = self.mode_planner.route(previous, candidate, intent)
            # 被动/指定地点的地址决定权高于距离：超预算只触发时间重排，
            # 不得换成离上一地点更近但语义错误的POI。
            return candidate, route, route.duration_minutes > budget
        evaluated = []
        for candidate, gravity_score in ranked[:self.route_top_k]:
            route = self.mode_planner.route(previous, candidate, intent)
            route_score = gravity_score / (1.0 + route.duration_minutes / float(max(1, budget)))
            evaluated.append((candidate, route, route_score))
        feasible = [item for item in evaluated if item[1].duration_minutes <= budget]
        if feasible:
            selected = max(feasible, key=lambda item: item[2])
            return selected[0], selected[1], False
        selected = min(evaluated, key=lambda item: (item[1].duration_minutes, -item[2]))
        return selected[0], selected[1], True

    def _budget(self, previous: Optional[StopIntent], current: StopIntent) -> int:
        default = current.maximum_travel_minutes or DEFAULT_MAX_LEG_MINUTES.get(current.activity_type, 45)
        intercity = bool(
            previous and previous.city and current.city
            and not city_matches(previous.city, current.city)
        )
        if intercity:
            # 跨城出差/返乡不是日常通勤，不能套用住宅—公司的通勤上限。
            default = current.maximum_travel_minutes or 360
        elif current.activity_type in {"work", "home"}:
            target = self.mode_planner.commute_target()
            if target:
                default = max(10, int(round(target * 1.2 + 5)))
        elif current.selection_policy == "gravity" and not current.maximum_travel_minutes:
            default = max(5, int(round(default * {
                "low": 0.80, "medium": 1.0, "high": 1.50,
            }[self.mobility_level])))
        gap = self._time_gap(previous.end_time if previous else "", current.start_time)
        return min(default, gap) if gap is not None and gap > 0 else default

    @staticmethod
    def _resolved(intent: StopIntent, candidate: LocationCandidate, degraded: bool) -> ResolvedStop:
        return ResolvedStop(
            stop_id=intent.stop_id, event_ref=intent.event_ref,
            activity_type=intent.activity_type, location_id=candidate.location_id,
            name=candidate.name, address=candidate.address,
            coordinates=candidate.coordinates, city=candidate.city,
            category=candidate.category, source=candidate.source,
            degraded=degraded, original_order=intent.order,
            parent_event_id=intent.parent_event_id,
            required=intent.required,
            provenance=intent.provenance,
            flexibility=intent.flexibility,
            spatial_scope=intent.spatial_scope,
            confidence=candidate.confidence,
            map_verified=candidate.map_verified,
        )

    @staticmethod
    def _time_gap(first: str, second: str) -> Optional[int]:
        try:
            start = dt.datetime.strptime(first, "%H:%M")
            end = dt.datetime.strptime(second, "%H:%M")
        except (TypeError, ValueError):
            return None
        minutes = int((end - start).total_seconds() / 60)
        return minutes if minutes >= 0 else minutes + 24 * 60

    @staticmethod
    def _leg_times(previous: Optional[StopIntent], current: StopIntent, minutes: int,
                   leg_type: str = "transfer") -> Tuple[str, str]:
        try:
            if leg_type == "local_loop" and current.start_time:
                departure = dt.datetime.strptime(current.start_time, "%H:%M")
                if current.end_time:
                    arrival = dt.datetime.strptime(current.end_time, "%H:%M")
                else:
                    arrival = departure + dt.timedelta(minutes=minutes)
                return departure.strftime("%H:%M"), arrival.strftime("%H:%M")
            if current.start_time:
                arrival = dt.datetime.strptime(current.start_time, "%H:%M")
                departure = arrival - dt.timedelta(minutes=minutes)
                return departure.strftime("%H:%M"), arrival.strftime("%H:%M")
            if previous and previous.end_time:
                departure = dt.datetime.strptime(previous.end_time, "%H:%M")
                arrival = departure + dt.timedelta(minutes=minutes)
                return departure.strftime("%H:%M"), arrival.strftime("%H:%M")
        except ValueError:
            pass
        return "", ""
