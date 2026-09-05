# -*- coding: utf-8 -*-
"""将轨迹分配转为最终事件可消费的地理 sidecar。

经纬度来自最终统一事实层：地图值或对最终叙事地点的显式估算。
"""
import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .coordinates import gcj02_to_wgs84


COORDINATE_SYSTEM = "GCJ-02"
TRAVEL_TERMS = ("前往", "返回", "通行", "通勤", "出发", "到达", "步行", "骑行", "公交", "地铁", "驾车", "跑步", "→", "->")


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        result = value.to_dict()
        return result if isinstance(result, dict) else {}
    return {}


def _coordinates(value: Any) -> Optional[Tuple[float, float]]:
    try:
        longitude, latitude = (float(part.strip()) for part in str(value or "").split(","))
    except (TypeError, ValueError):
        return None
    if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
        return None
    return longitude, latitude


def _point(stop: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    coordinates = _coordinates(stop.get("coordinates") or stop.get("location"))
    if coordinates is None:
        return None
    longitude, latitude = coordinates
    canonical_longitude, canonical_latitude = gcj02_to_wgs84(longitude, latitude)
    return {
        "location_id": str(stop.get("location_id") or stop.get("id") or ""),
        "stop_id": str(stop.get("stop_id") or ""),
        "name": str(stop.get("name") or ""),
        "address": str(stop.get("address") or stop.get("formatted_address") or ""),
        "longitude": longitude,
        "latitude": latitude,
        "coordinate_system": COORDINATE_SYSTEM,
        "canonical_longitude": round(canonical_longitude, 7),
        "canonical_latitude": round(canonical_latitude, 7),
        "canonical_coordinate_system": "WGS-84",
        "source": str(stop.get("source") or ""),
        "map_verified": bool(stop.get("map_verified", False)),
        "confidence": float(stop.get("confidence", 1.0) or 0.0),
        "spatial_scope": str(stop.get("spatial_scope") or "city"),
        "city": str(stop.get("city") or ""),
        "fact_source": str(stop.get("fact_source") or "allocator"),
        "override_reason": str(stop.get("override_reason") or ""),
        "anchor_location_id": str(stop.get("anchor_location_id") or ""),
        "estimate_method": str(stop.get("estimate_method") or ""),
    }


def build_location_records(assignment: Any) -> Dict[str, Any]:
    """建立可单独持久化的停留点和路段坐标记录。"""
    data = _as_dict(assignment)
    stops = []
    for raw in data.get("stops", []) if isinstance(data.get("stops"), list) else []:
        if not isinstance(raw, dict):
            continue
        point = _point(raw)
        if point is None:
            continue
        point.update({
            "event_ref": str(raw.get("event_ref") or ""),
            "activity_type": str(raw.get("activity_type") or "other"),
            "parent_event_id": str(raw.get("parent_event_id") or ""),
            "original_order": int(raw.get("original_order", len(stops)) or 0),
        })
        stops.append(point)

    by_stop_id = {item["stop_id"]: item for item in stops if item.get("stop_id")}
    legs = []
    for raw in data.get("legs", []) if isinstance(data.get("legs"), list) else []:
        if not isinstance(raw, dict):
            continue
        origin = by_stop_id.get(str(raw.get("origin_stop_id") or ""))
        destination = by_stop_id.get(str(raw.get("destination_stop_id") or ""))
        if origin is None or destination is None:
            continue
        legs.append({
            "leg_id": str(raw.get("leg_id") or ""),
            "origin_stop_id": origin["stop_id"],
            "destination_stop_id": destination["stop_id"],
            "origin": _public_point(origin),
            "destination": _public_point(destination),
            "mode": str(raw.get("mode") or "none"),
            "duration_minutes": int(raw.get("duration_minutes", 0) or 0),
            "distance_km": float(raw.get("distance_km", 0.0) or 0.0),
            "departure_time": str(raw.get("departure_time") or ""),
            "arrival_time": str(raw.get("arrival_time") or ""),
            "source": str(raw.get("source") or ""),
            "map_verified": bool(raw.get("map_verified", False)),
            "confidence": float(raw.get("confidence", 1.0) or 0.0),
            "leg_type": str(raw.get("leg_type") or "transfer"),
            "fact_source": str(raw.get("fact_source") or (
                "map_accepted" if raw.get("map_verified", False) else "narrative_estimated"
            )),
            "override_reason": str(raw.get("override_reason") or ""),
            "estimate_method": str(raw.get("estimate_method") or (
                "map_route" if raw.get("map_verified", False) else "route_estimate"
            )),
        })
    return {
        "schema_version": "simulation_location_v1",
        "date": str(data.get("date") or ""),
        "coordinate_system": COORDINATE_SYSTEM,
        "canonical_coordinate_system": "WGS-84",
        "stops": stops,
        "legs": legs,
    }


def _public_point(point: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "location_id", "stop_id", "name", "address", "longitude", "latitude",
        "coordinate_system", "canonical_longitude", "canonical_latitude",
        "canonical_coordinate_system", "source", "map_verified", "confidence", "spatial_scope",
        "city",
        "fact_source", "override_reason", "anchor_location_id", "estimate_method",
    )
    return {key: point.get(key) for key in keys}


def _normalized(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", str(value or "")).lower()


def _contains(text: str, fragment: Any) -> bool:
    needle = _normalized(fragment)
    return len(needle) >= 2 and needle in text


def _event_text(event: Dict[str, Any]) -> Tuple[str, str]:
    location = _normalized(event.get("location"))
    all_text = _normalized(" ".join(str(event.get(key) or "") for key in (
        "name", "description", "location",
    )))
    return location, all_text


def _stop_score(event: Dict[str, Any], stop: Dict[str, Any]) -> float:
    location, all_text = _event_text(event)
    score = 0.0
    if str(event.get("stop_id") or "") == stop.get("stop_id"):
        score += 100.0
    if _contains(location, stop.get("name")):
        score += 14.0
    if _contains(location, stop.get("address")):
        score += 12.0
    if _contains(all_text, stop.get("name")):
        score += 6.0
    if _contains(all_text, stop.get("address")):
        score += 5.0
    event_ref = _normalized(stop.get("event_ref"))
    if event_ref:
        similarity = SequenceMatcher(None, _normalized(event.get("name")), event_ref).ratio()
        if similarity >= 0.35:
            score += similarity * 5.0
    return score


def _leg_score(event: Dict[str, Any], leg: Dict[str, Any]) -> float:
    location, all_text = _event_text(event)
    if str(event.get("leg_id") or "") == leg.get("leg_id"):
        return 100.0
    origin = leg.get("origin", {})
    destination = leg.get("destination", {})
    score = 0.0
    origin_hit = _contains(location, origin.get("name")) or _contains(all_text, origin.get("name"))
    destination_hit = _contains(location, destination.get("name")) or _contains(all_text, destination.get("name"))
    same_endpoint = (
        origin.get("location_id") == destination.get("location_id")
        or (
            origin.get("longitude") == destination.get("longitude")
            and origin.get("latitude") == destination.get("latitude")
        )
    )
    if origin_hit:
        score += 6.0
    if destination_hit and not same_endpoint:
        score += 6.0
    has_travel_term = any(_contains(all_text, term) for term in TRAVEL_TERMS)
    if has_travel_term:
        score += 3.0
    duration = int(leg.get("duration_minutes", 0) or 0)
    if duration and _contains(all_text, "%d分钟" % duration):
        score += 3.0
    if leg.get("leg_type") == "local_loop" and any(
        _contains(all_text, term) for term in ("晨跑", "夜跑", "散步", "遛狗", "环线")
    ):
        score += 8.0
    return score


def attach_event_geodata(events: Iterable[Dict[str, Any]], location_records: Any) -> List[Dict[str, Any]]:
    """为 Formatter 事件附加 geo/mobility；无可靠匹配时不猜测坐标。"""
    records = location_records if isinstance(location_records, dict) else {}
    stops = [item for item in records.get("stops", []) if isinstance(item, dict)]
    legs = [item for item in records.get("legs", []) if isinstance(item, dict)]
    segments = [item for item in records.get("event_segments", []) if isinstance(item, dict)]
    result = []
    stops_by_id = {str(item.get("stop_id") or ""): item for item in stops}
    legs_by_id = {str(item.get("leg_id") or ""): item for item in legs}
    segments_by_id = {
        str(item.get("segment_id") or ""): item
        for item in segments if item.get("segment_id")
    }
    for raw_event in events or []:
        if not isinstance(raw_event, dict):
            continue
        event = dict(raw_event)
        explicit_segment = segments_by_id.get(str(event.get("segment_id") or ""))
        if explicit_segment is not None:
            event["event_group_id"] = explicit_segment.get("event_group_id", "")
            event["kind"] = explicit_segment.get("kind", event.get("kind") or "activity")
            if explicit_segment.get("location_detail"):
                event["location_detail"] = explicit_segment["location_detail"]
            if explicit_segment.get("stop_id"):
                event["stop_id"] = explicit_segment["stop_id"]
                event.pop("leg_id", None)
            elif explicit_segment.get("leg_id"):
                event["leg_id"] = explicit_segment["leg_id"]
                event.pop("stop_id", None)
        explicit_leg = legs_by_id.get(str(event.get("leg_id") or ""))
        explicit_stop = stops_by_id.get(str(event.get("stop_id") or ""))
        if explicit_leg is not None:
            event["kind"] = "local_loop" if explicit_leg.get("leg_type") == "local_loop" else "travel"
            event["geo"] = {
                "origin": explicit_leg.get("origin"),
                "destination": explicit_leg.get("destination"),
                "coordinate_system": records.get("coordinate_system", COORDINATE_SYSTEM),
            }
            event["mobility"] = {
                key: explicit_leg.get(key) for key in (
                    "leg_id", "mode", "duration_minutes", "distance_km", "source",
                    "map_verified", "confidence", "leg_type",
                )
            }
            result.append(event)
            continue
        if explicit_stop is not None:
            event["kind"] = event.get("kind") or "activity"
            event["geo"] = _public_point(explicit_stop)
            result.append(event)
            continue
        best_leg = max(legs, key=lambda item: _leg_score(event, item), default=None)
        leg_score = _leg_score(event, best_leg) if best_leg else 0.0
        if best_leg is not None and leg_score >= 11.0:
            event["kind"] = "local_loop" if best_leg.get("leg_type") == "local_loop" else "travel"
            event["leg_id"] = best_leg.get("leg_id", "")
            event["geo"] = {
                "origin": best_leg.get("origin"),
                "destination": best_leg.get("destination"),
                "coordinate_system": records.get("coordinate_system", COORDINATE_SYSTEM),
            }
            event["mobility"] = {
                key: best_leg.get(key) for key in (
                    "leg_id", "mode", "duration_minutes", "distance_km", "source",
                    "map_verified", "confidence", "leg_type",
                )
            }
            result.append(event)
            continue

        best_stop = max(stops, key=lambda item: _stop_score(event, item), default=None)
        stop_score = _stop_score(event, best_stop) if best_stop else 0.0
        if best_stop is not None and stop_score >= 5.0:
            event["kind"] = event.get("kind") or "activity"
            event["stop_id"] = best_stop.get("stop_id", "")
            event["geo"] = _public_point(best_stop)
        result.append(event)
    return result
