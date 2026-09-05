# -*- coding: utf-8 -*-
"""轨迹结构与数值完整性检查，不用关键词推断或改写 LLM 叙事。"""
from typing import Any, Dict, List

from .catalog import city_matches
from .models import TrajectoryAssignment
from .selector import haversine_km


MODE_MAX_SPEED_KMH = {
    "walking": 10.0, "running": 25.0, "bicycling": 45.0,
    "transit": 350.0, "driving": 180.0,
}


def validate_assignment(assignment: TrajectoryAssignment,
                        accuracy_validation: bool = True) -> List[str]:
    issues = []
    if not assignment.stops:
        issues.append("轨迹没有任何停留点")
    for violation in assignment.violations:
        code = violation.get("code")
        # location_unresolved / reuse_location_unresolved 意味着该 stop 根本没有
        # 创建，属于结构缺失，必须失败；city_mismatch 只是城市标签与意图不一致，
        # stop 仍带坐标存在，属于可接受的精度问题，按开关决定是否降级。
        if code in {"location_unresolved", "reuse_location_unresolved"}:
            issues.append(str(violation.get("message") or code))
        elif code == "city_mismatch" and accuracy_validation:
            issues.append(str(violation.get("message") or code))
    stop_ids = [stop.stop_id for stop in assignment.stops]
    if len(stop_ids) != len(set(stop_ids)):
        issues.append("停留点ID重复")
    for stop in assignment.stops:
        if len(stop.coordinates.split(",")) != 2:
            issues.append("%s缺少有效坐标" % stop.stop_id)
        if accuracy_validation and stop.source == "llm_plausible":
            if stop.map_verified:
                issues.append("%s叙事地点不应标记为地图核验" % stop.stop_id)
            if stop.confidence > 0.65:
                issues.append("%s叙事地点置信度过高" % stop.stop_id)
    for index, leg in enumerate(assignment.legs):
        if index + 1 >= len(assignment.stops):
            issues.append("%s没有对应停留点" % leg.leg_id)
            continue
        origin_stop = assignment.stops[index]
        destination_stop = assignment.stops[index + 1]
        # 楼内/院内 micro 活动与父地点共享坐标，属于“同地点停留”而非跨地点移动，
        # 不应要求正的时长或距离（与 validate_location_records 的 same_location 语义对齐）。
        same_location = (
            origin_stop.location_id == destination_stop.location_id
            or origin_stop.coordinates == destination_stop.coordinates
        )
        if leg.origin_stop_id != origin_stop.stop_id or leg.destination_stop_id != destination_stop.stop_id:
            issues.append("%s未连接相邻停留点" % leg.leg_id)
        if leg.duration_minutes < 0:
            issues.append("%s通行时间为负数" % leg.leg_id)
        if leg.leg_type != "local_loop" and not same_location and leg.origin_stop_id != leg.destination_stop_id:
            if leg.duration_minutes <= 0 or leg.distance_km <= 0:
                issues.append("%s跨地点移动缺少正的时长或距离" % leg.leg_id)
        if leg.leg_type == "local_loop":
            if leg.duration_minutes <= 0 or leg.distance_km <= 0:
                issues.append("%s本地环线缺少正的时长或距离" % leg.leg_id)
            if leg.mode not in {"walking", "running", "bicycling"}:
                issues.append("%s本地环线使用了不合理的交通方式" % leg.leg_id)
            if accuracy_validation and leg.map_verified:
                issues.append("%s叙事环线不应标记为地图核验" % leg.leg_id)
    return issues


def _point_coordinates(point: Dict[str, Any]) -> str:
    try:
        lon = float(point["longitude"])
        lat = float(point["latitude"])
    except (KeyError, TypeError, ValueError):
        return ""
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return ""
    return "%.8f,%.8f" % (lon, lat)


def validate_location_records(
    records: Dict[str, Any], require_itinerary: bool = True,
    accuracy_validation: bool = True,
) -> List[str]:
    """校验最终 sidecar，防止零时长、伪跨城和断裂移动链被当成成功。"""
    issues = []
    if not isinstance(records, dict):
        return ["最终地点记录不是对象"]
    stops = [item for item in records.get("stops", []) if isinstance(item, dict)]
    legs = [item for item in records.get("legs", []) if isinstance(item, dict)]
    segments = [item for item in records.get("event_segments", []) if isinstance(item, dict)]
    if not stops:
        issues.append("最终地点记录没有停留点")
    if require_itinerary and not segments:
        issues.append("最终地点记录没有事件分段")

    by_id = {}
    for stop in stops:
        stop_id = str(stop.get("stop_id") or "")
        if not stop_id:
            issues.append("存在缺少stop_id的停留点")
            continue
        if stop_id in by_id:
            issues.append("停留点ID重复:%s" % stop_id)
        by_id[stop_id] = stop
        if not _point_coordinates(stop):
            issues.append("%s缺少有效经纬度" % stop_id)

    for index, leg in enumerate(legs):
        leg_id = str(leg.get("leg_id") or "leg[%d]" % index)
        origin_id = str(leg.get("origin_stop_id") or "")
        destination_id = str(leg.get("destination_stop_id") or "")
        origin = by_id.get(origin_id)
        destination = by_id.get(destination_id)
        if origin is None or destination is None:
            issues.append("%s的起终点无法解析" % leg_id)
            continue
        try:
            duration = float(leg.get("duration_minutes", 0) or 0)
            distance = float(leg.get("distance_km", 0) or 0)
        except (TypeError, ValueError):
            issues.append("%s的距离或时长不是数值" % leg_id)
            continue
        leg_type = str(leg.get("leg_type") or "transfer")
        if leg_type == "local_loop":
            if duration <= 0 or distance <= 0:
                issues.append("%s本地环线缺少正的时长或距离" % leg_id)
            continue
        same_location = (
            origin_id == destination_id
            or str(origin.get("location_id") or "") == str(destination.get("location_id") or "")
        )
        if not same_location and (duration <= 0 or distance <= 0):
            issues.append("%s跨地点移动缺少正的时长或距离" % leg_id)
            continue
        coord_distance = haversine_km(
            _point_coordinates(origin), _point_coordinates(destination),
        )
        # 以下为「数值真实性/精度」校验：数据仍结构完整、有坐标，只是不够精确。
        # accuracy_validation=False 时降级为提示，不再 fail。
        if accuracy_validation and not same_location and coord_distance < 0.03:
            issues.append("%s的不同宏地点使用了相同坐标" % leg_id)
        if accuracy_validation and not same_location and coord_distance > 0.2 and distance + 0.1 < coord_distance * 0.75:
            issues.append("%s记录距离%.2f公里显著小于端点直线距离%.2f公里" % (
                leg_id, distance, coord_distance,
            ))
        origin_city = str(origin.get("city") or "")
        destination_city = str(destination.get("city") or "")
        if (
            accuracy_validation
            and origin_city and destination_city
            and not city_matches(origin_city, destination_city)
            and coord_distance < 20.0
        ):
            issues.append("%s跨城市但坐标距离不足20公里" % leg_id)
        if accuracy_validation and duration > 0 and distance > 0:
            speed = distance / (duration / 60.0)
            maximum = MODE_MAX_SPEED_KMH.get(str(leg.get("mode") or ""))
            if maximum is not None and speed > maximum:
                issues.append("%s的%s速度%.1fkm/h超出上限" % (
                    leg_id, leg.get("mode"), speed,
                ))

    # 相邻宏地点变化必须由显式 travel 连接，不能把高铁车厢当活动后直接跳城。
    activity_indices = [i for i, item in enumerate(segments) if item.get("kind") == "activity"]
    for left, right in zip(activity_indices, activity_indices[1:]):
        origin_id = str(segments[left].get("stop_id") or "")
        destination_id = str(segments[right].get("stop_id") or "")
        if not origin_id or not destination_id or origin_id == destination_id:
            continue
        between = segments[left + 1:right]
        cursor = origin_id
        for item in between:
            if item.get("kind") != "travel":
                continue
            if str(item.get("origin_stop_id") or "") == cursor:
                cursor = str(item.get("destination_stop_id") or "")
        connected = cursor == destination_id
        if not connected:
            issues.append("相邻活动地点%s→%s之间缺少travel段" % (origin_id, destination_id))
    return issues
