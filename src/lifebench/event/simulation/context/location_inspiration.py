# -*- coding: utf-8 -*-
"""Build a compact, deterministic daily view of a person's location opportunities."""
from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from src.lifebench.event.simulation.geolocation.catalog import (
    LocationCatalog, flatten_location_data, infer_role,
)
from src.lifebench.event.simulation.geolocation.selector import haversine_km


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_range(value: Any, default: Sequence[int]) -> List[int]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return [int(default[0]), int(default[1])]
    try:
        low, high = int(value[0]), int(value[1])
    except (TypeError, ValueError):
        return [int(default[0]), int(default[1])]
    return [max(0, min(low, high)), max(low, high)]


def _rng(seed: Any, instance_id: Any, date: str) -> random.Random:
    raw = "location-inspiration-v1|%s|%s|%s" % (seed, instance_id, date)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return random.Random(int(digest, 16))


def _coordinates(row: Mapping[str, Any]) -> str:
    value = str(row.get("location") or "")
    return value if len(value.split(",")) == 2 else ""


def _location_role(row: Mapping[str, Any]) -> str:
    explicit = str(row.get("location_role") or "")
    if explicit:
        return explicit
    inferred = infer_role(str(row.get("name") or ""), str(row.get("description") or ""))
    if inferred:
        return "anchor"
    if str(row.get("source") or "") == "trajectory_history":
        return "familiar"
    # Legacy location.json consisted of known persona places; preserve that meaning.
    return "familiar"


def _compact(row: Mapping[str, Any], home_coordinates: str = "") -> Dict[str, Any]:
    distance = row.get("distance_from_home_km")
    if distance in (None, "") and home_coordinates and _coordinates(row):
        distance = round(haversine_km(home_coordinates, _coordinates(row)), 2)
    try:
        distance = round(float(distance), 2) if distance not in (None, "") else None
    except (TypeError, ValueError):
        distance = None
    raw_tags = row.get("activity_tags", [])
    if not isinstance(raw_tags, (list, tuple)):
        raw_tags = [raw_tags] if raw_tags else []
    result = {
        "location_id": str(row.get("location_id") or row.get("id") or ""),
        "name": str(row.get("name") or ""),
        "category": str(row.get("activity_category") or row.get("category") or "other"),
        "district": str(row.get("district") or ""),
        "distance_from_home_km": distance,
        "visit_state": str(row.get("knowledge_state") or (
            "visited" if int(row.get("visit_count", 0) or 0) > 0 else "known"
        )),
        "activity_tags": [str(item) for item in raw_tags[:5]],
        "location_role": _location_role(row),
    }
    if row.get("related_person"):
        result["related_person"] = str(row.get("related_person"))
    if row.get("access_policy"):
        result["access_policy"] = str(row.get("access_policy"))
    return result


def _weight(row: Mapping[str, Any], day_type: str, distance_target: Sequence[float]) -> float:
    try:
        attraction = max(0.05, float(row.get("attraction_weight", 0.6) or 0.6))
    except (TypeError, ValueError):
        attraction = 0.6
    suitable = [str(item) for item in row.get("suitable_day_types", [])]
    suitability = 1.6 if day_type and day_type in suitable else 1.0
    try:
        distance = float(row.get("distance_from_home_km", 0) or 0)
    except (TypeError, ValueError):
        distance = 0.0
    low, high = (float(distance_target[0]), float(distance_target[1])) if len(distance_target) >= 2 else (0.0, 60.0)
    if low <= distance <= high:
        distance_fit = 1.35
    elif distance < low:
        distance_fit = math.exp(-(low - distance) / max(2.0, low + 1.0))
    else:
        distance_fit = math.exp(-(distance - high) / max(3.0, high * 0.6))
    return max(1e-6, attraction * suitability * distance_fit)


def _sample_weighted(
    rows: Iterable[Dict[str, Any]], count: int, rng: random.Random,
    day_type: str, distance_target: Sequence[float],
) -> List[Dict[str, Any]]:
    raced = []
    for row in rows:
        weight = _weight(row, day_type, distance_target)
        race = -math.log(max(1e-12, rng.random())) / weight
        raced.append((race, str(row.get("location_id") or row.get("id") or ""), row))
    raced.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in raced[:max(0, count)]]


def build_location_inspiration_context(
    *, location_data: Any, trajectory_history: Any, mobility_profile: Any,
    date: str, instance_id: Any = 0, seed: Any = 0, config: Any = None,
) -> Dict[str, Any]:
    """Sample compact location inspiration; showing a place never counts as a visit."""
    settings = _dict(config)
    rng = _rng(seed, instance_id, date)
    rows = flatten_location_data(location_data)
    history = [dict(item) for item in (trajectory_history or []) if isinstance(item, dict)]
    known_ids = {str(row.get("location_id") or row.get("id") or "") for row in rows}
    rows.extend(
        item for item in history
        if str(item.get("location_id") or item.get("id") or "") not in known_ids
    )
    # Ensure every catalogued point has a stable ID before it can be exposed to the LLM.
    catalog_by_coordinate = {
        item.coordinates: item for item in LocationCatalog(rows).items
    }
    for row in rows:
        if not row.get("location_id") and _coordinates(row) in catalog_by_coordinate:
            row["location_id"] = catalog_by_coordinate[_coordinates(row)].location_id

    anchors = [row for row in rows if _location_role(row) == "anchor"]
    familiar = [
        row for row in rows if _location_role(row) == "familiar"
        and str(row.get("knowledge_state") or "") != "known_unvisited"
    ]
    citywide = [row for row in rows if _location_role(row) == "city_reference"]
    social = [row for row in rows if _location_role(row) == "social_location"]
    home = next((row for row in anchors if infer_role(
        str(row.get("name") or ""), str(row.get("description") or "")
    ) == "home" or str(row.get("anchor_role") or "") == "home"), None)
    home_coordinates = _coordinates(home or {})

    profile = _dict(mobility_profile)
    day_type = str(profile.get("day_archetype") or profile.get("day_type") or "")
    distance_target = profile.get("destination_distance_band_km")
    if not isinstance(distance_target, list):
        total = profile.get("daily_distance_band_km", [0, 30])
        distance_target = [0, max(3.0, float(total[1] if isinstance(total, list) and len(total) > 1 else 30) / 2.0)]

    familiar_range = _int_range(settings.get("daily_familiar_quota"), (2, 4))
    city_range = _int_range(settings.get("daily_citywide_quota"), (4, 8))
    social_range = _int_range(settings.get("daily_social_quota"), (0, 2))
    familiar_count = rng.randint(*familiar_range)
    city_count = rng.randint(*city_range)
    social_count = rng.randint(*social_range)
    if day_type in {"home_recovery", "low_mobility"}:
        city_count = min(city_count, 2)
        social_count = min(social_count, 1)
    elif day_type in {"citywide_leisure", "social_activity", "social_or_leisure", "exploratory", "long_distance"}:
        city_count = max(city_count, min(len(citywide), 6))

    chosen_familiar = _sample_weighted(familiar, familiar_count, rng, day_type, distance_target)
    chosen_city = _sample_weighted(citywide, city_count, rng, day_type, distance_target)
    chosen_social = _sample_weighted(social, social_count, rng, day_type, distance_target)
    return {
        "schema_version": "location_inspiration_context_v1",
        "seed_key": "location-inspiration-v1|%s|%s|%s" % (seed, instance_id, date),
        "guidance": "候选仅是今日灵感，不代表已访问或必须采用；亲友住所需先联系、约定或受邀。",
        "anchors": [_compact(row, home_coordinates) for row in anchors[:4]],
        "familiar_options": [_compact(row, home_coordinates) for row in chosen_familiar],
        "citywide_options": [_compact(row, home_coordinates) for row in chosen_city],
        "social_options": [_compact(row, home_coordinates) for row in chosen_social],
        "diagnostics": {
            "available": {"familiar": len(familiar), "citywide": len(citywide), "social": len(social)},
            "sampled": {"familiar": len(chosen_familiar), "citywide": len(chosen_city), "social": len(chosen_social)},
            "display_does_not_count_as_visit": True,
        },
    }
