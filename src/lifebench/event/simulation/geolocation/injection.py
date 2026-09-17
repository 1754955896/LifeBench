# -*- coding: utf-8 -*-
"""把结构化分配渲染为供下游 LLM 优先采用的轨迹参考。"""
from typing import List

from .models import TrajectoryAssignment


MODE_LABELS = {
    "none": "无需通行", "walking": "步行", "bicycling": "骑行",
    "transit": "公共交通", "driving": "驾车/打车", "running": "跑步",
}


def render_assignment_summary(assignment: TrajectoryAssignment) -> str:
    lines = [
        "【轨迹高优先级参考】以下内容来自地图候选、活动重规划和结构化路线计算。合理时应优先使用；若与事件语义、时间表或人物日常逻辑明显冲突，可做最小必要调整。map_verified/amap 为地图数据；llm_plausible/heuristic 为合理估算，不得把估算冒充地图事实。"
    ]  # type: List[str]
    decisions = {
        str(item.get("stop_id") or ""): item
        for item in assignment.diagnostics.get("epr_decisions", [])
        if isinstance(item, dict)
    }
    for index, stop in enumerate(assignment.stops, 1):
        address = stop.address or (stop.city + " " + stop.name).strip()
        decision = decisions.get(stop.stop_id, {})
        lock_hint = (
            "｜位置约束:locked_gravity"
            if decision.get("selection_policy") == "gravity"
            and stop.map_verified and not stop.degraded
            and decision.get("final_decision", "accepted") == "accepted"
            else ""
        )
        lines.append("【参考地点%02d】%s｜%s｜事件:%s｜坐标:%s｜stop_id:%s｜location_id:%s｜活动:%s｜来源:%s｜地图核验:%s｜置信度:%.2f%s" % (
            index, stop.name, address, stop.event_ref, stop.coordinates,
            stop.stop_id, stop.location_id, stop.activity_type, stop.source,
            "是" if stop.map_verified else "否", stop.confidence, lock_hint,
        ))
        if index <= len(assignment.legs):
            leg = assignment.legs[index - 1]
            if leg.mode == "none" and leg.duration_minutes == 0:
                continue
            time_hint = ""
            if leg.departure_time or leg.arrival_time:
                time_hint = "｜%s-%s" % (leg.departure_time or "?", leg.arrival_time or "?")
            leg_label = "参考本地环线" if leg.leg_type == "local_loop" else "参考通行"
            lines.append("【%s%02d】%s→%s｜leg_id:%s｜%s｜%d分钟｜约%.2f公里%s｜来源:%s｜地图核验:%s｜置信度:%.2f" % (
                leg_label,
                index, leg.origin_name, leg.destination_name, leg.leg_id,
                MODE_LABELS.get(leg.mode, leg.mode), leg.duration_minutes,
                leg.distance_km, time_hint, leg.source,
                "是" if leg.map_verified else "否", leg.confidence,
            ))
            if leg.narrative_route:
                lines.append("【环线/估算路线%02d】%s" % (index, leg.narrative_route))
    for dropped in assignment.diagnostics.get("activity_plan_dropped", []):
        lines.append("【建议已合并活动】%s→%s｜%s；若无新的叙事必要，不要恢复为独立外出。" % (
            dropped.get("activity_id", ""),
            dropped.get("merged_into", ""),
            dropped.get("reason", ""),
        ))
    if assignment.violations:
        lines.append("【约束提示】存在%d项降级/预算告警；不得通过虚构更短通行时间掩盖。" % len(assignment.violations))
        for violation in assignment.violations:
            stop_id = str(violation.get("stop_id") or "?")
            code = str(violation.get("code") or "unknown")
            message = str(violation.get("message") or "")
            lines.append("  - [%s] %s: %s" % (stop_id, code, message))
    return "\n".join(lines)
