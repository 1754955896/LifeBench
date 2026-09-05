# -*- coding: utf-8 -*-
"""把最终统一地理事实导出为一天 48 个半小时位置样本。"""
from __future__ import annotations

import hashlib
import math
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from .coordinates import gcj02_to_wgs84


def _minute(value: Any) -> Optional[int]:
    try:
        hour, minute = (int(part) for part in str(value).split(":", 1))
    except (TypeError, ValueError):
        return None
    return hour * 60 + minute if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def _point(stop: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    try:
        return float(stop["longitude"]), float(stop["latitude"])
    except (KeyError, TypeError, ValueError):
        return None


def _interpolate(first: Tuple[float, float], second: Tuple[float, float], fraction: float) -> Tuple[float, float]:
    fraction = max(0.0, min(1.0, fraction))
    return first[0] + (second[0] - first[0]) * fraction, first[1] + (second[1] - first[1]) * fraction


def _loop_point(anchor: Tuple[float, float], fraction: float, distance_km: float, salt: str) -> Tuple[float, float]:
    """生成闭合局部环线；只用于统计采样，不伪装成地图路线。"""
    radius_m = min(1500.0, max(100.0, float(distance_km or 0.0) * 1000.0) / (2.0 * math.pi))
    angle0 = int(hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8], 16) / 0xFFFFFFFF * 2 * math.pi
    theta = 2 * math.pi * max(0.0, min(1.0, fraction))
    east = radius_m * (math.sin(theta + angle0) - math.sin(angle0))
    north = radius_m * (math.cos(angle0) - math.cos(theta + angle0))
    lon, lat = anchor
    return lon + east / max(1.0, 111320.0 * math.cos(math.radians(lat))), lat + north / 110570.0


def build_half_hour_trajectory(location_records: Any, *, date: str = "", instance_id: Any = "", slot_minutes: int = 30) -> Dict[str, Any]:
    """从最终 event_segments 采样固定时间网格；空档延续最近宏观地点。"""
    records = location_records if isinstance(location_records, dict) else {}
    stops = [row for row in records.get("stops", []) if isinstance(row, dict)]
    segments = [row for row in records.get("event_segments", []) if isinstance(row, dict)]
    legs = [row for row in records.get("legs", []) if isinstance(row, dict)]
    by_stop = {str(row.get("stop_id") or ""): row for row in stops}
    by_leg = {str(row.get("leg_id") or ""): row for row in legs}
    parsed = []
    for order, segment in enumerate(segments):
        start, end = _minute(segment.get("start_time")), _minute(segment.get("end_time"))
        if start is None or end is None:
            continue
        if end <= start:
            end += 1440
        parsed.append((start, end, order, segment))
    parsed.sort(key=lambda row: (row[0], row[2]))
    first_stop = next((by_stop.get(str(s.get("stop_id") or "")) for _, _, _, s in parsed if s.get("kind") == "activity"), None)
    if first_stop is None and stops:
        first_stop = stops[0]
    carried = first_stop
    slots: List[Dict[str, Any]] = []
    step = max(1, int(slot_minutes))
    for slot_index, slot_start in enumerate(range(0, 1440, step)):
        sample_minute = slot_start + step / 2.0
        active_row = next(((start, end, s) for start, end, _, s in parsed if start <= sample_minute < end), None)
        active = active_row[2] if active_row else None
        row: Dict[str, Any] = {"slot_index": slot_index, "time": "%02d:%02d" % (slot_start // 60, slot_start % 60), "sample_minute": int(sample_minute), "coordinate_system": records.get("coordinate_system", "GCJ-02")}
        if active is None:
            # 非整点结束的短通行可能没有任何采样点；空档开始前仍需把位置推进到
            # 最近已完成段的终点，不能错误延续通行前地点。
            completed = [item for item in parsed if item[1] <= sample_minute]
            if completed:
                latest = completed[-1][3]
                if latest.get("kind") == "activity":
                    carried = by_stop.get(str(latest.get("stop_id") or ""), carried)
                else:
                    leg = by_leg.get(str(latest.get("leg_id") or ""), {})
                    carried = by_stop.get(str(latest.get("destination_stop_id") or leg.get("destination_stop_id") or ""), carried)
            point = _point(carried or {})
            row.update({"state": "gap_carry", "fact_source": "temporal_carry"})
            if carried:
                row.update({"stop_id": carried.get("stop_id"), "location_id": carried.get("location_id")})
        elif active.get("kind") == "activity":
            carried = by_stop.get(str(active.get("stop_id") or ""), carried)
            point = _point(carried or {})
            row.update({"state": "activity", "segment_id": active.get("segment_id"), "stop_id": (carried or {}).get("stop_id"), "location_id": (carried or {}).get("location_id"), "fact_source": (carried or {}).get("fact_source") or (carried or {}).get("source") or "unknown"})
        else:
            leg = by_leg.get(str(active.get("leg_id") or ""), {})
            origin = by_stop.get(str(active.get("origin_stop_id") or leg.get("origin_stop_id") or ""), {})
            destination = by_stop.get(str(active.get("destination_stop_id") or leg.get("destination_stop_id") or ""), {})
            start, end = active_row[0], active_row[1]
            fraction = (sample_minute - start) / max(1.0, end - start)
            origin_point, destination_point = _point(origin), _point(destination)
            if active.get("kind") == "local_loop" and origin_point:
                point = _loop_point(origin_point, fraction, float(active.get("distance_km") or leg.get("distance_km") or 0.0), str(active.get("segment_id") or slot_index))
                state = "local_loop"
            elif origin_point and destination_point:
                point, state = _interpolate(origin_point, destination_point, fraction), "travel"
            else:
                point, state = origin_point or destination_point or _point(carried or {}), "travel_unresolved"
            row.update({"state": state, "segment_id": active.get("segment_id"), "leg_id": active.get("leg_id"), "mode": active.get("mode") or leg.get("mode"), "fact_source": leg.get("fact_source") or leg.get("source") or "unknown"})
            if sample_minute >= end - step / 2.0 and destination:
                carried = destination
        if point:
            row["longitude"], row["latitude"] = round(point[0], 7), round(point[1], 7)
            canonical = gcj02_to_wgs84(point[0], point[1])
            row["canonical_longitude"] = round(canonical[0], 7)
            row["canonical_latitude"] = round(canonical[1], 7)
            row["canonical_coordinate_system"] = "WGS-84"
        else:
            row["longitude"], row["latitude"] = None, None
            row["canonical_longitude"], row["canonical_latitude"] = None, None
            row["canonical_coordinate_system"] = "WGS-84"
        slots.append(row)
    return {"schema_version": "half_hour_trajectory_v1", "instance_id": instance_id, "date": date or str(records.get("date") or ""), "slot_minutes": step, "coordinate_system": records.get("coordinate_system", "GCJ-02"), "canonical_coordinate_system": "WGS-84", "slots": slots, "diagnostics": {"slot_count": len(slots), "resolved_slot_count": sum(row.get("longitude") is not None for row in slots), "travel_slot_count": sum(row.get("state") in {"travel", "local_loop"} for row in slots), "source": "final_location_records"}}


def write_half_hour_trajectory(path: str, trajectory: Dict[str, Any]) -> None:
    """按日期幂等更新 JSONL，避免整日重试造成重复记录。"""
    rows: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as source:
            for line in source:
                try:
                    item = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(item, dict) and item.get("date"):
                    rows[str(item["date"])] = item
    rows[str(trajectory.get("date") or "")] = trajectory
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as target:
        for key in sorted(rows):
            target.write(json.dumps(rows[key], ensure_ascii=False, separators=(",", ":")) + "\n")
