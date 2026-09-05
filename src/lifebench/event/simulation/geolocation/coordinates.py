# -*- coding: utf-8 -*-
"""Coordinate transforms used to compare AMap GCJ-02 output with WGS-84 datasets."""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple


_A = 6378245.0
_EE = 0.00669342162296594323


def _outside_china(longitude: float, latitude: float) -> bool:
    return not (72.004 <= longitude <= 137.8347 and 0.8293 <= latitude <= 55.8271)


def _transform_latitude(x: float, y: float) -> float:
    value = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    value += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    value += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return value


def _transform_longitude(x: float, y: float) -> float:
    value = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    value += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    value += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    value += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return value


def gcj02_to_wgs84(longitude: float, latitude: float) -> Tuple[float, float]:
    """Convert AMap coordinates to WGS-84; outside China coordinates pass through."""
    longitude, latitude = float(longitude), float(latitude)
    if _outside_china(longitude, latitude):
        return longitude, latitude
    delta_latitude = _transform_latitude(longitude - 105.0, latitude - 35.0)
    delta_longitude = _transform_longitude(longitude - 105.0, latitude - 35.0)
    radians = latitude / 180.0 * math.pi
    magic = 1 - _EE * math.sin(radians) ** 2
    sqrt_magic = math.sqrt(magic)
    delta_latitude = delta_latitude * 180.0 / ((_A * (1 - _EE)) / (magic * sqrt_magic) * math.pi)
    delta_longitude = delta_longitude * 180.0 / (_A / sqrt_magic * math.cos(radians) * math.pi)
    return longitude * 2 - (longitude + delta_longitude), latitude * 2 - (latitude + delta_latitude)


def attach_wgs84(point: Dict[str, Any]) -> Dict[str, Any]:
    """Attach canonical WGS-84 fields to a GCJ-02 point in place."""
    try:
        longitude = float(point["longitude"])
        latitude = float(point["latitude"])
    except (KeyError, TypeError, ValueError):
        return point
    canonical_longitude, canonical_latitude = gcj02_to_wgs84(longitude, latitude)
    point["coordinate_system"] = str(point.get("coordinate_system") or "GCJ-02")
    point["canonical_longitude"] = round(canonical_longitude, 7)
    point["canonical_latitude"] = round(canonical_latitude, 7)
    point["canonical_coordinate_system"] = "WGS-84"
    return point


def attach_record_wgs84(records: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize every final stop/leg endpoint after narrative reconciliation."""
    if not isinstance(records, dict):
        return records
    records.setdefault("coordinate_system", "GCJ-02")
    records["canonical_coordinate_system"] = "WGS-84"
    for stop in records.get("stops", []):
        if isinstance(stop, dict):
            attach_wgs84(stop)
    for leg in records.get("legs", []):
        if not isinstance(leg, dict):
            continue
        for key in ("origin", "destination"):
            if isinstance(leg.get(key), dict):
                attach_wgs84(leg[key])
    return records
