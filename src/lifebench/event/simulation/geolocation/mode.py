# -*- coding: utf-8 -*-
"""画像约束下的交通方式选择和地图时长查询。"""
import re
from dataclasses import dataclass
from typing import Any, List

from .models import LocationCandidate, StopIntent
from .selector import haversine_km


@dataclass
class RouteChoice:
    mode: str
    duration_minutes: int
    distance_km: float
    source: str
    leg_type: str = "transfer"
    narrative_route: str = ""
    confidence: float = 1.0
    map_verified: bool = False


class ModePlanner:
    def __init__(self, maptools: Any, persona: Any):
        self.maptools = maptools
        self.persona_text = str(persona or "")

    def route(self, origin: LocationCandidate, destination: LocationCandidate, intent: StopIntent) -> RouteChoice:
        distance = haversine_km(origin.coordinates, destination.coordinates)
        if origin.coordinates == destination.coordinates:
            return RouteChoice("none", 0, 0.0, "same_location", map_verified=True)
        # LLM 指定的交通方式优先：先只查它，查不到再退回代码分配。
        hint = (intent.mode_hint or "").strip()
        if hint in ("walking", "bicycling", "transit", "driving"):
            seconds = self.maptools.get_duration_between_pois(
                origin.as_poi(), destination.as_poi(), hint,
                origin.city or None, destination.city or None,
            )
            if seconds is not None:
                return RouteChoice(
                    hint, max(1, int(round(seconds / 60.0))), distance, "amap",
                    confidence=1.0, map_verified=True,
                )
        modes = self._modes(distance, "")
        choices = []
        for mode in modes:
            seconds = self.maptools.get_duration_between_pois(
                origin.as_poi(), destination.as_poi(), mode,
                origin.city or None, destination.city or None,
            )
            if seconds is not None:
                choices.append(RouteChoice(
                    mode, max(1, int(round(seconds / 60.0))), distance, "amap",
                    confidence=1.0, map_verified=True,
                ))
        if choices:
            # “最快”不是唯一目标：给不符合距离/画像优先序的方式增加换乘、停车等广义成本。
            return min(choices, key=lambda item: (
                item.duration_minutes + modes.index(item.mode) * 5,
                modes.index(item.mode),
            ))
        mode = modes[0]
        speeds = {"walking": 4.5, "bicycling": 12.0, "transit": 20.0, "driving": 28.0}
        overhead = {"walking": 0, "bicycling": 2, "transit": 8, "driving": 5}
        minutes = max(1, int(round(distance / speeds[mode] * 60 + overhead[mode])))
        return RouteChoice(mode, minutes, distance, "heuristic", confidence=0.7, map_verified=False)

    def commute_target(self) -> int:
        patterns = (r"通勤.{0,12}?(\d{1,3})\s*分钟", r"(\d{1,3})\s*分钟.{0,12}?通勤")
        for pattern in patterns:
            match = re.search(pattern, self.persona_text)
            if match:
                return int(match.group(1))
        return 0

    def _modes(self, distance: float, hint: str) -> List[str]:
        if distance <= 1.2:
            modes = ["walking", "bicycling", "transit", "driving"]
        elif distance <= 3:
            modes = ["bicycling", "transit", "walking", "driving"]
        elif distance <= 10:
            modes = ["transit", "driving", "bicycling"]
        else:
            modes = ["transit", "driving"]
        if any(term in self.persona_text for term in ("无车", "不开车", "不会开车")):
            modes = [mode for mode in modes if mode != "driving"]
        if any(term in self.persona_text for term in ("地铁", "公交", "公共交通")) and "transit" in modes:
            modes.remove("transit")
            modes.insert(0, "transit")
        if distance > 3 and any(term in self.persona_text for term in ("自驾", "开车", "有车")) and "driving" in modes:
            modes.remove("driving")
            modes.insert(0, "driving")
        if hint in modes:
            modes.remove(hint)
            modes.insert(0, hint)
        return modes or ["transit"]
