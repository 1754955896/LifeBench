# -*- coding: utf-8 -*-
"""将轨迹调整后的最终地点与移动链合并进地理 sidecar。"""
import copy
import hashlib
import math
import re
from typing import Any, Dict, Iterable, List, Optional

from .allocator import offset_coordinates
from .catalog import city_matches
from .registry import find_registered_location, normalize_place_name, stable_location_id
from .validator import validate_location_records


SCOPE_DISTANCE_LIMITS = {
    "room": 30,
    "building": 100,
    "compound": 300,
    "neighborhood": 1500,
    "district": 8000,
    "city": 15000,
}

DEFAULT_DISTANCE_M = {
    "room": 10,
    "building": 50,
    "compound": 150,
    "neighborhood": 600,
    "district": 3000,
    "city": 8000,
}

ACTIVITY_TYPES = {
    "home", "work", "education", "meal", "fitness", "shopping",
    "medical", "leisure", "other",
}


def _integer(value: Any, default: int) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return default


def _confidence(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        result = 0.45
    return max(0.2, min(result, 0.55))


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _home_or_first(stops: List[Dict[str, Any]]) -> Dict[str, Any]:
    for stop in stops:
        if stop.get("activity_type") == "home":
            return stop
    return stops[0] if stops else {}


def _district_hint(anchor: Dict[str, Any]) -> str:
    """从锚点提取区县名，作为 geocode 查询前缀；取不到返回空串。"""
    if not isinstance(anchor, dict):
        return ""
    district = str(anchor.get("district") or "").strip()
    if district:
        return district
    match = re.search(r"([一-龥]{1,8}(?:区|县|市))", str(anchor.get("address") or ""))
    return match.group(1) if match else ""


def _geocode_named_place(
    maptools: Any, name: str, address: str, city: str, district: str = "",
) -> Optional[Dict[str, str]]:
    """对 LLM 新造地名做地理编码，取一个大致合理的地理坐标。

    优先按「省市区 + name」拼接查询，保证即使名称较泛也能落到目标城市；
    省/市取自 city，区县尽可能从同城锚点地址提取。只要拿到坐标即视为可用，
    不再过滤命中级别。
    """
    if maptools is None:
        return None
    geocode = getattr(maptools, "amap_geocode", None)
    if not callable(geocode):
        return None
    prefix = "".join(part for part in (city, district) if part)
    queries = []
    if prefix:
        queries.append(prefix + name)
    if city and (city + name) not in queries:
        queries.append(city + name)
    queries.append(name)
    if address and address not in queries:
        queries.append(address)
    for query in queries:
        if not query:
            continue
        try:
            result = geocode(query, city)
        except Exception:
            continue
        if not isinstance(result, dict):
            continue
        location = str(result.get("location") or "").strip()
        if len(location.split(",")) != 2:
            continue
        result_city = str(result.get("city") or "")
        if city and result_city and not city_matches(city, result_city):
            continue
        return {
            "location": location,
            "formatted_address": str(result.get("formatted_address") or ""),
            "city": result_city,
            "district": str(result.get("district") or ""),
            "province": str(result.get("province") or ""),
            "adcode": str(result.get("adcode") or ""),
        }
    return None


def reconcile_estimated_locations(
    location_records: Dict[str, Any],
    estimated_locations: Iterable[Dict[str, Any]],
    seed: str = "0",
    known_locations: Iterable[Dict[str, Any]] = (),
    maptools: Any = None,
) -> Dict[str, Any]:
    """把 LLM 声明的非地图地点转成带估算坐标的最终停留点。

    LLM 只决定地点语义、锚点和距离；坐标由程序相对可信锚点稳定偏移生成。
    原始地图/画像地点保持不变，新增地点明确标记为未经过地图核验。
    """
    records = copy.deepcopy(location_records) if isinstance(location_records, dict) else {}
    stops = records.get("stops")
    if not isinstance(stops, list):
        stops = []
        records["stops"] = stops
    if not isinstance(records.get("legs"), list):
        records["legs"] = []

    by_id = {
        str(stop.get("stop_id") or ""): stop
        for stop in stops if isinstance(stop, dict) and stop.get("stop_id")
    }
    existing_by_identity = {
        (str(stop.get("name") or "").strip(), str(stop.get("address") or "").strip()): stop
        for stop in stops if isinstance(stop, dict)
    }
    default_anchor = _home_or_first(stops)
    added = []
    location_key_to_stop_id = {}
    issues = []

    rows = estimated_locations if isinstance(estimated_locations, (list, tuple)) else []
    for index, raw in enumerate(rows):
        if not isinstance(raw, dict):
            issues.append("estimated_locations[%d] 不是对象" % index)
            continue
        name = str(raw.get("name") or "").strip()
        address = str(raw.get("narrative_address") or raw.get("address") or "").strip()
        requested_city = str(raw.get("city") or "").strip()
        if not name:
            issues.append("estimated_locations[%d] 缺少 name" % index)
            continue
        activity_type = str(raw.get("activity_type") or "other")
        if activity_type not in ACTIVITY_TYPES:
            activity_type = "other"
        location_key = str(raw.get("location_key") or "").strip()
        duplicate = existing_by_identity.get((name, address))
        if duplicate is not None:
            if location_key and duplicate.get("stop_id"):
                location_key_to_stop_id[location_key] = str(duplicate["stop_id"])
            continue

        registered = find_registered_location(
            known_locations, name, address, requested_city,
            str(raw.get("activity_type") or ""),
        )
        if registered is not None:
            coordinates = str(registered.get("location") or "")
            longitude, latitude = (float(value) for value in coordinates.split(","))
            stable_id = str(
                registered.get("location_id") or registered.get("id") or ""
            ) or stable_location_id(name, address, requested_city)
            occurrence_identity = "%s|%s|%s" % (seed, location_key, stable_id)
            stop_id = "final_reused_" + hashlib.sha1(
                occurrence_identity.encode("utf-8")
            ).hexdigest()[:12]
            point = {
                "location_id": stable_id,
                "stop_id": stop_id,
                "name": name,
                "address": address or str(registered.get("formatted_address") or ""),
                "longitude": longitude,
                "latitude": latitude,
                "coordinate_system": records.get("coordinate_system", "GCJ-02"),
                "source": "trajectory_history",
                "map_verified": bool(registered.get("map_verified", False)),
                "confidence": float(registered.get("confidence", 0.7) or 0.0),
                "spatial_scope": str(raw.get("spatial_scope") or "city"),
                "event_ref": str(raw.get("event_ref") or name),
                "activity_type": str(raw.get("activity_type") or "other"),
                "parent_event_id": str(raw.get("parent_event_id") or ""),
                "original_order": len(stops),
                "city": requested_city or str(registered.get("city") or ""),
                "reused_from_registry": True,
                "location_key": location_key,
            }
            stops.append(point)
            by_id[stop_id] = point
            existing_by_identity[(point["name"], point["address"])] = point
            added.append(stop_id)
            if location_key:
                location_key_to_stop_id[location_key] = stop_id
            continue

        # 先解析锚点（仅用于提取区县提示），再做地理编码。
        requested_anchor_id = str(raw.get("anchor_stop_id") or "").strip()
        anchor = by_id.get(requested_anchor_id) or default_anchor
        if requested_anchor_id and requested_anchor_id not in by_id:
            issues.append("%s 的 anchor_stop_id 无效，改用默认锚点" % name)

        # LLM 新造地名：优先按「省市区 + name」geocode 拿大致合理坐标，
        # 取代锚点偏移的估算值。仅在编码失败/落错城市时退回后续锚点偏移分支。
        district_hint = _district_hint(anchor)
        geocoded = _geocode_named_place(
            maptools, name, address, requested_city, district_hint,
        )
        if geocoded is not None:
            coordinates = geocoded["location"]
            longitude, latitude = (float(value) for value in coordinates.split(","))
            resolved_city = geocoded.get("city") or requested_city or (
                str(default_anchor.get("city") or "") if default_anchor else ""
            )
            stable_id = stable_location_id(name, address, resolved_city)
            occurrence_identity = "%s|%s|%s" % (seed, location_key, stable_id)
            stop_id = "final_geocoded_" + hashlib.sha1(
                occurrence_identity.encode("utf-8")
            ).hexdigest()[:12]
            point = {
                "location_id": stable_id,
                "stop_id": stop_id,
                "name": name,
                "address": address or geocoded.get("formatted_address") or "",
                "longitude": longitude,
                "latitude": latitude,
                "coordinate_system": records.get("coordinate_system", "GCJ-02"),
                "source": "amap_geocode",
                "map_verified": True,
                "confidence": 0.85,
                "spatial_scope": str(raw.get("spatial_scope") or "city"),
                "event_ref": str(raw.get("event_ref") or name),
                "activity_type": activity_type,
                "parent_event_id": str(raw.get("parent_event_id") or ""),
                "original_order": len(stops),
                "city": resolved_city,
                "district": geocoded.get("district") or "",
                "generation_reason": str(
                    raw.get("generation_reason") or "轨迹调整后采用具名地点，经地理编码核验"
                ),
                "is_local_loop": _boolean(raw.get("is_local_loop", False)),
                "location_key": location_key,
            }
            stops.append(point)
            by_id[stop_id] = point
            existing_by_identity[(point["name"], point["address"])] = point
            added.append(stop_id)
            if location_key:
                location_key_to_stop_id[location_key] = stop_id
            continue

        if not anchor or anchor.get("longitude") is None or anchor.get("latitude") is None:
            issues.append("%s 没有可用坐标锚点" % name)
            continue
        anchor_city = str(anchor.get("city") or "")
        if requested_city and anchor_city and not city_matches(requested_city, anchor_city):
            issues.append(
                "%s 是跨城地点(%s)，不能相对 %s 的局部锚点估算坐标"
                % (name, requested_city, anchor_city)
            )
            continue

        scope = str(raw.get("spatial_scope") or "neighborhood").strip()
        if scope not in SCOPE_DISTANCE_LIMITS:
            scope = "neighborhood"
        limit = SCOPE_DISTANCE_LIMITS[scope]
        distance_m = _integer(raw.get("estimated_distance_m"), DEFAULT_DISTANCE_M[scope])
        distance_m = max(0, min(distance_m, limit))
        is_local_loop = _boolean(raw.get("is_local_loop", False))
        if not is_local_loop:
            distance_m = max(30, distance_m)
        anchor_coordinates = "%s,%s" % (anchor["longitude"], anchor["latitude"])
        city = requested_city or str(anchor.get("city") or "")
        # location_id 与日期无关，确保跨日再次提到同一地点时身份稳定。
        stable_id = stable_location_id(
            name, address, city, str(anchor.get("location_id") or ""),
        )
        identity = "%s|%s|%s" % (
            str(anchor.get("location_id") or anchor.get("stop_id") or ""),
            normalize_place_name(name), normalize_place_name(address),
        )
        coordinates = anchor_coordinates if is_local_loop else offset_coordinates(
            anchor_coordinates, distance_m, identity,
        )
        longitude, latitude = (float(value) for value in coordinates.split(","))
        digest = hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]
        stop_id = "final_virtual_" + digest
        point = {
            "location_id": stable_id,
            "stop_id": stop_id,
            "name": name,
            "address": address or (str(anchor.get("address") or "") + "附近"),
            "longitude": longitude,
            "latitude": latitude,
            "coordinate_system": records.get("coordinate_system", "GCJ-02"),
            "source": "llm_post_adjustment_plausible",
            "map_verified": False,
            "confidence": _confidence(raw.get("confidence")),
            "spatial_scope": scope,
            "event_ref": str(raw.get("event_ref") or name),
            "activity_type": activity_type,
            "parent_event_id": str(raw.get("parent_event_id") or ""),
            "original_order": len(stops),
            "anchor_stop_id": str(anchor.get("stop_id") or ""),
            "estimated_distance_m": distance_m,
            "generation_reason": str(raw.get("generation_reason") or "轨迹调整后采用叙事地点"),
            "is_local_loop": is_local_loop,
            "location_key": location_key,
            "city": city,
        }
        stops.append(point)
        by_id[stop_id] = point
        existing_by_identity[(point["name"], point["address"])] = point
        added.append(stop_id)
        if location_key:
            location_key_to_stop_id[location_key] = stop_id

    records.setdefault("schema_version", "simulation_location_v1")
    records.setdefault("coordinate_system", "GCJ-02")
    records["post_adjustment_reconciliation"] = {
        "estimated_stop_ids": added,
        "estimated_stop_count": len(added),
        "location_key_to_stop_id": location_key_to_stop_id,
        "issues": issues,
    }
    return records


FINAL_SEGMENT_KINDS = {"activity", "travel", "local_loop"}
FINAL_MODES = {"walking", "running", "bicycling", "transit", "driving", "none"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _haversine_km(origin: Dict[str, Any], destination: Dict[str, Any]) -> float:
    """计算端点直线距离，仅作为未核验路段的保守估算。"""
    try:
        lon1, lat1 = math.radians(float(origin["longitude"])), math.radians(float(origin["latitude"]))
        lon2, lat2 = math.radians(float(destination["longitude"])), math.radians(float(destination["latitude"]))
    except (KeyError, TypeError, ValueError):
        return 0.0
    delta_lon = lon2 - lon1
    delta_lat = lat2 - lat1
    value = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(value)))


def _public_point(point: Dict[str, Any]) -> Dict[str, Any]:
    keys = (
        "location_id", "stop_id", "name", "address", "longitude", "latitude",
        "coordinate_system", "source", "map_verified", "confidence", "spatial_scope",
        "city",
    )
    return {key: point.get(key) for key in keys}


def _resolve_stop_ref(
    value: Any,
    by_stop_id: Dict[str, Dict[str, Any]],
    location_key_to_stop_id: Dict[str, str],
) -> str:
    reference = str(value or "").strip()
    if reference in by_stop_id:
        return reference
    return location_key_to_stop_id.get(reference, "")


def _matching_base_leg(
    legs: List[Dict[str, Any]], origin_stop_id: str, destination_stop_id: str,
) -> Dict[str, Any]:
    for leg in legs:
        if (
            str(leg.get("origin_stop_id") or "") == origin_stop_id
            and str(leg.get("destination_stop_id") or "") == destination_stop_id
        ):
            return leg
    return {}


def _string_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item is not None and str(item).strip()]
    if value is None or value == "":
        return []
    return [str(value)]


def reconcile_final_itinerary(
    location_records: Dict[str, Any],
    itinerary: Dict[str, Any],
    seed: str = "0",
    known_locations: Iterable[Dict[str, Any]] = (),
    accuracy_validation: bool = True,
    maptools: Any = None,
) -> Dict[str, Any]:
    """依据 LLM 给出的紧凑最终行程重建最终停留点、事件段和通行段。

    语义判断由 LLM 完成；本函数只解析显式 ID/引用、补充虚拟地点坐标并建立引用关系。
    当 ``segments`` 缺失时保持 v1 行为，以兼容旧中间结果和失败回退。
    """
    payload = itinerary if isinstance(itinerary, dict) else {}
    records = reconcile_estimated_locations(
        location_records,
        payload.get("estimated_locations", []),
        seed=seed,
        known_locations=known_locations,
        maptools=maptools,
    )
    raw_segments = payload.get("segments")
    if not isinstance(raw_segments, list):
        return records

    all_stops = [item for item in records.get("stops", []) if isinstance(item, dict)]
    by_stop_id = {
        str(item.get("stop_id") or ""): item
        for item in all_stops if item.get("stop_id")
    }
    base_legs = [item for item in records.get("legs", []) if isinstance(item, dict)]
    reconciliation = records.get("post_adjustment_reconciliation", {})
    key_mapping = reconciliation.get("location_key_to_stop_id", {})
    key_mapping = key_mapping if isinstance(key_mapping, dict) else {}
    issues = []
    final_segments = []
    final_legs = []
    used_stop_ids = set()

    for index, raw in enumerate(raw_segments):
        if not isinstance(raw, dict):
            issues.append("segments[%d] 不是对象" % index)
            continue
        kind = str(raw.get("kind") or "").strip()
        if kind not in FINAL_SEGMENT_KINDS:
            issues.append("segments[%d] 的 kind 无效" % index)
            continue
        segment = {
            "segment_id": str(raw.get("segment_id") or "segment_%03d" % index),
            "event_group_id": str(raw.get("event_group_id") or "group_%03d" % index),
            "kind": kind,
            "start_time": str(raw.get("start_time") or ""),
            "end_time": str(raw.get("end_time") or ""),
            "event_ref": str(raw.get("event_ref") or ""),
            "source_plan_ids": _string_list(raw.get("source_plan_ids")),
        }

        if kind == "activity":
            stop_id = _resolve_stop_ref(raw.get("stop_ref"), by_stop_id, key_mapping)
            if not stop_id:
                issues.append("%s 的 stop_ref 无法解析" % segment["segment_id"])
                continue
            segment.update({
                "stop_id": stop_id,
                "location_detail": str(raw.get("location_detail") or ""),
            })
            used_stop_ids.add(stop_id)
            final_segments.append(segment)
            continue

        origin_stop_id = _resolve_stop_ref(raw.get("origin_ref"), by_stop_id, key_mapping)
        destination_stop_id = _resolve_stop_ref(raw.get("destination_ref"), by_stop_id, key_mapping)
        if kind == "local_loop" and origin_stop_id and not destination_stop_id:
            destination_stop_id = origin_stop_id
        if not origin_stop_id or not destination_stop_id:
            issues.append("%s 的起终点引用无法解析" % segment["segment_id"])
            continue
        origin = by_stop_id[origin_stop_id]
        destination = by_stop_id[destination_stop_id]
        base_leg = _matching_base_leg(base_legs, origin_stop_id, destination_stop_id)
        mode = str(raw.get("mode") or base_leg.get("mode") or ("walking" if kind == "local_loop" else "none"))
        if mode not in FINAL_MODES:
            mode = "walking" if kind == "local_loop" else "none"
        duration = max(0, _integer(raw.get("duration_minutes"), _integer(base_leg.get("duration_minutes"), 0)))
        distance = max(0.0, _number(raw.get("distance_km"), _number(base_leg.get("distance_km"), 0.0)))
        if distance <= 0 and origin_stop_id != destination_stop_id:
            distance = _haversine_km(origin, destination)
        if kind == "local_loop" and distance <= 0:
            distance = max(0.0, _number(raw.get("loop_distance_km"), 0.0))

        preserves_base = bool(base_leg) and (
            not raw.get("mode") or mode == str(base_leg.get("mode") or "")
        ) and (
            raw.get("duration_minutes") in (None, "")
            or duration == _integer(base_leg.get("duration_minutes"), 0)
        ) and (
            raw.get("distance_km") in (None, "", 0, 0.0)
            or abs(distance - _number(base_leg.get("distance_km"), 0.0)) < 0.001
        )
        leg_id = "final_leg_%03d" % len(final_legs)
        leg_type = "local_loop" if kind == "local_loop" else "transfer"
        leg = {
            "leg_id": leg_id,
            "origin_stop_id": origin_stop_id,
            "destination_stop_id": destination_stop_id,
            "origin": _public_point(origin),
            "destination": _public_point(destination),
            "mode": mode,
            "duration_minutes": duration,
            "distance_km": round(distance, 3),
            "departure_time": segment["start_time"],
            "arrival_time": segment["end_time"],
            "source": str(base_leg.get("source") or "") if preserves_base else "llm_post_adjustment_estimate",
            "map_verified": bool(base_leg.get("map_verified", False)) if preserves_base else False,
            "confidence": float(base_leg.get("confidence", 1.0) or 0.0) if preserves_base else 0.5,
            "leg_type": leg_type,
        }
        segment.update({
            "leg_id": leg_id,
            "origin_stop_id": origin_stop_id,
            "destination_stop_id": destination_stop_id,
            "mode": mode,
            "duration_minutes": duration,
            "distance_km": round(distance, 3),
        })
        used_stop_ids.update((origin_stop_id, destination_stop_id))
        final_legs.append(leg)
        final_segments.append(segment)

    candidate_records = copy.deepcopy(records)
    candidate_records["stops"] = [
        stop for stop in all_stops if str(stop.get("stop_id") or "") in used_stop_ids
    ]
    candidate_records["legs"] = final_legs
    candidate_records["event_segments"] = final_segments
    if bool(final_segments) and len(final_segments) == len(raw_segments) and not issues:
        issues.extend(validate_location_records(
            candidate_records, require_itinerary=True,
            accuracy_validation=accuracy_validation,
        ))
    complete = bool(final_segments) and len(final_segments) == len(raw_segments) and not issues
    # 只有所有显式行都成功解析时才替换旧链，避免把半截 LLM 输出当成成功数据。
    if complete:
        records["stops"] = candidate_records["stops"]
        records["legs"] = final_legs
        records["event_segments"] = final_segments
        records["schema_version"] = "simulation_location_v2"
    records["itinerary_reconciliation"] = {
        "applied": complete,
        "input_segment_count": len(raw_segments),
        "segment_count": len(final_segments),
        "activity_segment_count": sum(item["kind"] == "activity" for item in final_segments),
        "travel_segment_count": sum(item["kind"] in {"travel", "local_loop"} for item in final_segments),
        "final_stop_count": len(records.get("stops", [])),
        "issues": issues,
    }
    return records
