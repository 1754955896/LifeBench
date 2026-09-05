# -*- coding: utf-8 -*-
"""跨日地点注册表：让同一语义地点稳定复用 location_id 与坐标。"""
import hashlib
import datetime as dt
import re
import math
from typing import Any, Dict, Iterable, List, Optional

from .catalog import city_matches, normalize_city


def normalize_place_name(value: Any) -> str:
    return re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]", "", str(value or "")).lower()


def _coordinates(item: Dict[str, Any]) -> str:
    value = item.get("location")
    if isinstance(value, str) and len(value.split(",")) == 2:
        return value
    try:
        return "%.6f,%.6f" % (float(item["longitude"]), float(item["latitude"]))
    except (KeyError, TypeError, ValueError):
        return ""


def _coordinate_distance_m(first: str, second: str) -> float:
    try:
        lon1, lat1 = (math.radians(float(v)) for v in first.split(","))
        lon2, lat2 = (math.radians(float(v)) for v in second.split(","))
    except (AttributeError, TypeError, ValueError):
        return float("inf")
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371008.8 * 2 * math.asin(min(1.0, math.sqrt(value)))


def find_registered_location(
    registry: Iterable[Dict[str, Any]], name: str, address: str = "",
    city: str = "", category: str = "", coordinates: str = "",
) -> Optional[Dict[str, Any]]:
    """按稳定名称/别名或完整地址查找历史地点，不做有风险的模糊猜测。"""
    wanted_name = normalize_place_name(name)
    wanted_address = normalize_place_name(address)
    matches = []
    for item in registry or []:
        if not isinstance(item, dict) or not _coordinates(item):
            continue
        item_city = str(item.get("city") or "")
        if city and item_city and not city_matches(city, item_city):
            continue
        aliases = [item.get("name", "")] + list(item.get("aliases") or [])
        names = {normalize_place_name(value) for value in aliases if value}
        item_address = normalize_place_name(
            item.get("formatted_address") or item.get("address") or ""
        )
        same_name = bool(wanted_name and wanted_name in names)
        same_address = bool(wanted_address and item_address and wanted_address == item_address)
        same_point = bool(
            coordinates and _coordinate_distance_m(coordinates, _coordinates(item)) <= 40.0
        )
        if not same_name and not same_address and not same_point:
            continue
        category_match = not category or not item.get("category") or item.get("category") == category
        matches.append((1 if same_point else 0, 1 if same_name else 0, 1 if category_match else 0,
                        int(item.get("visit_count", 0) or 0), item))
    if not matches:
        return None
    return max(matches, key=lambda value: value[:4])[4]


def _lifecycle(item: Dict[str, Any], date: str) -> None:
    category = str(item.get("category") or "other")
    source = str(item.get("origin_source") or item.get("source") or "")
    dates = sorted(set(str(value) for value in item.get("recent_visit_dates", []) if value))
    active_days = len(dates)
    span_days = 0
    try:
        span_days = (
            dt.datetime.strptime(dates[-1], "%Y-%m-%d")
            - dt.datetime.strptime(dates[0], "%Y-%m-%d")
        ).days
    except (IndexError, ValueError):
        pass
    if source == "persona_catalog" or category == "home":
        tier = "anchor"
    elif item.get("lifecycle_hint") in {"temporary", "episodic"}:
        tier = str(item["lifecycle_hint"])
    elif active_days >= 3 and span_days >= 7:
        tier = "routine"
    else:
        tier = "occasional"
    visits = int(item.get("visit_count", 0) or 0)
    familiarity = min(1.0, 0.12 * active_days + 0.08 * math.log1p(visits) + (0.18 if tier == "anchor" else 0.0))
    location_id = str(item.get("location_id") or "")
    if source.startswith("amap_"):
        canonical_id = location_id if location_id.startswith("amap:") else "amap:" + location_id
    elif source == "persona_catalog":
        canonical_id = "persona:" + location_id
    else:
        canonical_id = "synthetic:" + location_id
    item.update({
        "canonical_location_id": canonical_id,
        "location_tier": tier,
        "lifecycle_status": "active",
        "active_day_count": active_days,
        "compatible_activity_types": sorted(set(
            list(item.get("compatible_activity_types") or []) + [category]
        )),
        "familiarity": round(familiarity, 4),
        "return_eligible": tier in {"anchor", "routine"} or active_days >= 2,
        "retention_score": round(min(1.0, familiarity + 0.12), 4),
    })


def stable_location_id(name: str, address: str, city: str, anchor_id: str = "") -> str:
    identity = "|".join((
        normalize_city(city), normalize_place_name(name),
        normalize_place_name(address), str(anchor_id or ""),
    ))
    return "plausible_" + hashlib.sha1(identity.encode("utf-8")).hexdigest()[:12]


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


def remember_location_records(
    history: Iterable[Dict[str, Any]], records: Dict[str, Any], limit: int = 200,
    date: str = "",
) -> List[Dict[str, Any]]:
    """将最终采用的地点写回注册表；同一实体累计访问，不因日期创建新ID。"""
    result = [dict(item) for item in (history or []) if isinstance(item, dict)]
    stop_buckets = {}
    if isinstance(records, dict):
        for segment in records.get("event_segments", []) or []:
            if not isinstance(segment, dict) or segment.get("kind") != "activity":
                continue
            stop_id = str(segment.get("stop_id") or "")
            if stop_id:
                stop_buckets.setdefault(stop_id, set()).add(
                    _time_bucket(date, segment.get("start_time"))
                )
    for stop in records.get("stops", []) if isinstance(records, dict) else []:
        if not isinstance(stop, dict):
            continue
        coordinates = _coordinates(stop)
        name = str(stop.get("name") or "").strip()
        if not coordinates or not name:
            continue
        address = str(stop.get("address") or stop.get("formatted_address") or "")
        city = str(stop.get("city") or "")
        category = str(stop.get("activity_type") or stop.get("category") or "other")
        known = find_registered_location(result, name, address, city, category, coordinates)
        if known is None:
            location_id = str(stop.get("location_id") or "") or stable_location_id(
                name, address, city, str(stop.get("anchor_stop_id") or ""),
            )
            result.append({
                "id": location_id,
                "location_id": location_id,
                "name": name,
                "aliases": [name],
                "location": coordinates,
                "formatted_address": address,
                "city": city,
                "category": category,
                "description": "模拟轨迹中曾实际采用的地点",
                "source": "trajectory_history",
                "origin_source": str(stop.get("source") or ""),
                "map_verified": bool(stop.get("map_verified", False)),
                "confidence": float(stop.get("confidence", 0.5) or 0.0),
                "visit_count": 1,
                "first_seen_date": date,
                "last_seen_date": date,
                "recent_visit_dates": [date] if date else [],
                "visit_time_buckets": {
                    bucket: 1 for bucket in stop_buckets.get(str(stop.get("stop_id") or ""), set())
                },
            })
            _lifecycle(result[-1], date)
            continue
        aliases = list(known.get("aliases") or [])
        if name not in aliases:
            aliases.append(name)
        known["aliases"] = aliases[-10:]
        known["visit_count"] = int(known.get("visit_count", 0) or 0) + 1
        if date:
            known["first_seen_date"] = str(known.get("first_seen_date") or date)
            known["last_seen_date"] = date
            recent_dates = [str(item) for item in known.get("recent_visit_dates", []) if item]
            if date not in recent_dates:
                recent_dates.append(date)
            known["recent_visit_dates"] = recent_dates[-30:]
        buckets = dict(known.get("visit_time_buckets") or {})
        for bucket in stop_buckets.get(str(stop.get("stop_id") or ""), set()):
            buckets[bucket] = int(buckets.get(bucket, 0) or 0) + 1
        known["visit_time_buckets"] = buckets
        _lifecycle(known, date)
        # 地图核验结果可以提升历史记录；估算结果不能覆盖已核验坐标。
        if bool(stop.get("map_verified", False)) and not bool(known.get("map_verified", False)):
            known.update({
                "location": coordinates, "formatted_address": address,
                "map_verified": True, "confidence": float(stop.get("confidence", 1.0) or 1.0),
            })
    return result[-max(1, int(limit)):]
