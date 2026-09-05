# -*- coding: utf-8 -*-
"""轨迹分配使用的稳定数据结构。"""
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StopIntent:
    stop_id: str
    order: int
    activity_type: str = "other"
    query_type: str = "search"
    event_ref: str = ""
    explicit_name: str = ""
    explicit_location: str = ""
    keyword: str = ""
    search_queries: List[str] = field(default_factory=list)
    poi_type: str = ""
    city: str = ""
    anchor_role: str = ""
    reuse_policy: str = "prefer_return"
    reuse_location_id: str = ""
    epr_applicable: bool = False
    historical_candidate_ids: List[str] = field(default_factory=list)
    history_match_reason: str = ""
    selection_policy: str = "gravity"
    start_time: str = ""
    end_time: str = ""
    minimum_dwell_minutes: int = 0
    mode_hint: str = ""
    parent_event_id: str = ""
    required: bool = False
    provenance: str = "inferred"
    flexibility: str = "movable"
    spatial_scope: str = "city"
    maximum_travel_minutes: int = 0
    mobility_pattern: str = "destination"
    allow_plausible_location: bool = False
    preferred_radius_m: int = 0
    target_distance_km: float = 0.0
    target_duration_minutes: int = 0
    fallback_queries: List[str] = field(default_factory=list)
    fallback_area: str = ""
    allow_citywide_fallback: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LocationCandidate:
    location_id: str
    name: str
    address: str
    coordinates: str
    city: str = ""
    province: str = ""
    district: str = ""
    adcode: str = ""
    category: str = "other"
    role: str = ""
    source: str = "map_search"
    anchor_id: str = ""
    distance_m: Optional[float] = None
    map_rank: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    map_verified: bool = False

    def as_poi(self) -> Dict[str, Any]:
        return {"name": self.name, "location": self.coordinates, "city": self.city}


@dataclass
class ResolvedStop:
    stop_id: str
    event_ref: str
    activity_type: str
    location_id: str
    name: str
    address: str
    coordinates: str
    city: str
    category: str
    source: str
    degraded: bool = False
    original_order: int = 0
    parent_event_id: str = ""
    required: bool = False
    provenance: str = "inferred"
    flexibility: str = "movable"
    spatial_scope: str = "city"
    confidence: float = 1.0
    map_verified: bool = False

    def as_poi(self) -> Dict[str, Any]:
        return {"name": self.name, "location": self.coordinates, "city": self.city}


@dataclass
class TravelLeg:
    leg_id: str
    origin_stop_id: str
    destination_stop_id: str
    origin_name: str
    destination_name: str
    mode: str
    duration_minutes: int
    distance_km: float
    departure_time: str = ""
    arrival_time: str = ""
    source: str = "amap"
    feasible: bool = True
    confidence: float = 1.0
    leg_type: str = "transfer"
    narrative_route: str = ""
    map_verified: bool = False


@dataclass
class PlausibleLocationSpec:
    stop_id: str
    name: str
    narrative_address: str
    location_kind: str = "destination"
    spatial_scope: str = "neighborhood"
    estimated_distance_m: int = 0
    estimated_travel_minutes: int = 0
    mode: str = "walking"
    narrative_route: str = ""
    generation_reason: str = ""
    confidence: float = 0.45


@dataclass
class TrajectoryAssignment:
    date: str
    stops: List[ResolvedStop] = field(default_factory=list)
    legs: List[TravelLeg] = field(default_factory=list)
    feasible: bool = True
    violations: List[Dict[str, Any]] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
