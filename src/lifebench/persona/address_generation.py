"""Ground persona core addresses and derive a consistent location sidecar."""

import json
import math
import os
import random
import threading
from collections import defaultdict
from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.lifebench.utils.maptool import MapMaintenanceTool
from src.lifebench.utils.structured_llm import StructuredLLMCaller

from .canonicalizer import locked_fact_errors
from .prompts import build_address_places_prompt


LOCATION_KEYS = (
    "name", "location", "formatted_address", "city", "district",
    "streetName", "streetNumber", "description",
)


class AddressGenerationError(RuntimeError):
    pass


# 地图落地一个地点后，用 LLM 判断该 POI 是否与圈子/地点语义一致；若不一致则重新生成
# 检索词再次查询，最多重试 _POI_MAX_RETRIES 次，仍不合理就放弃真实 POI、沿用 LLM 原始内容。
_POI_MAX_RETRIES = 2

# 关系圈类型 → 用于 LLM 合理性判断的地点类型描述。
_CIRCLE_PLACE_KIND = {
    "school": "学校",
    "sports_club": "运动场馆",
    "hobby_group": "线下聚会地点",
}


class AddressAssignmentRegistry:
    """Track assignments inside one generation batch without changing output data."""

    _REUSE_COST = {
        "居住地": 0.85, "工作地": 0.35, "常去地": 0.18,
        "联系人居住地": 1.35, "关系圈固定地": 0.25,
    }

    def __init__(self):
        self._counts = defaultdict(lambda: defaultdict(int))
        self._global_counts = defaultdict(int)
        self._lock = threading.RLock()

    @staticmethod
    def _key(poi: Dict[str, Any]) -> str:
        direct = _text(poi.get("id")) or _text(poi.get("location"))
        fallback = "%s|%s" % (
            _text(poi.get("name")), _text(poi.get("structured_address")),
        )
        return direct or (fallback if fallback != "|" else "")

    @staticmethod
    def _aliases(poi: Dict[str, Any]) -> List[str]:
        values = []
        for prefix, value in (
            ("id", _text(poi.get("id"))),
            ("loc", _text(poi.get("location"))),
            ("addr", _text(poi.get("structured_address")) or _text(poi.get("formatted_address"))),
            ("name", _text(poi.get("name"))),
        ):
            if value:
                values.append("%s:%s" % (prefix, value))
        return values

    def penalty(self, address_type: str, poi: Dict[str, Any]) -> float:
        aliases = self._aliases(poi)
        if not aliases:
            return 0.0
        with self._lock:
            own_count = max(self._counts[address_type][key] for key in aliases)
            global_count = max(self._global_counts[key] for key in aliases)
            own = own_count * self._REUSE_COST.get(address_type, 0.2)
            cross = global_count * (0.55 if address_type in {"居住地", "联系人居住地"} else 0.08)
            return own + cross

    def usage_count(self, poi: Dict[str, Any]) -> int:
        aliases = self._aliases(poi)
        with self._lock:
            return max((self._global_counts[key] for key in aliases), default=0)

    def reserve(self, address_type: str, poi: Dict[str, Any]) -> None:
        aliases = self._aliases(poi)
        if not aliases:
            return
        with self._lock:
            for key in aliases:
                self._counts[address_type][key] += 1
                self._global_counts[key] += 1


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(_text(item) for item in value)
    return "" if value is None else str(value).strip()


def _address_text(address: Dict[str, Any]) -> str:
    province = _text(address.get("province"))
    city = _text(address.get("city"))
    parts = [province]
    if city and city != province:
        parts.append(city)
    parts.extend((
        _text(address.get("district")),
        _text(address.get("street_name")),
        _text(address.get("street_number")),
    ))
    return "".join(part for part in parts if part)


def _coordinates(poi: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    try:
        longitude, latitude = _text(poi.get("location")).split(",")
        return float(longitude), float(latitude)
    except (TypeError, ValueError):
        return None


def _haversine_km(left: Dict[str, Any], right: Dict[str, Any]) -> Optional[float]:
    left_coords = _coordinates(left)
    right_coords = _coordinates(right)
    if not left_coords or not right_coords:
        return None
    lon1, lat1 = map(math.radians, left_coords)
    lon2, lat2 = map(math.radians, right_coords)
    dlon, dlat = lon2 - lon1, lat2 - lat1
    value = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371.0088 * 2 * math.asin(math.sqrt(value))


def _range_score(value: float, minimum: float, maximum: float) -> float:
    """Return 1 inside a preferred range and decay smoothly outside it."""
    if minimum <= value <= maximum:
        midpoint = (minimum + maximum) / 2
        half_width = max((maximum - minimum) / 2, 1)
        return 1.0 - 0.12 * abs(value - midpoint) / half_width
    distance = minimum - value if value < minimum else value - maximum
    scale = max((maximum - minimum) / 2, 5)
    return math.exp(-distance / scale)


def _weighted_choice(rng: random.Random, scored: List[Tuple[float, Any]], top_n: int = 3) -> Any:
    ranked = sorted(scored, key=lambda item: item[0], reverse=True)[:max(1, top_n)]
    if not ranked:
        return None
    floor = min(score for score, _ in ranked)
    weights = [max(0.05, score - floor + 0.15) for score, _ in ranked]
    return rng.choices([item for _, item in ranked], weights=weights, k=1)[0]


def _workplace_type(profile: Dict[str, Any]) -> str:
    text = "%s %s" % (profile.get("job", ""), profile.get("occupation", ""))
    for words, place_type in (
        (("教师", "学校", "教育"), "学校"),
        (("医生", "护士", "医疗", "医院"), "医院"),
        (("工厂", "制造", "生产"), "产业园"),
        (("餐饮", "厨师", "餐馆"), "餐饮场所"),
        (("零售", "销售", "商场"), "商业建筑"),
    ):
        if any(word in text for word in words):
            return place_type
    return "办公楼"


def _has_daily_workplace(profile: Dict[str, Any]) -> bool:
    text = "%s %s" % (profile.get("job", ""), profile.get("occupation", ""))
    return not any(word in text for word in ("无业", "退休", "家庭主妇", "无固定单位"))


class PersonaAddressService:
    def __init__(
        self,
        caller: Optional[StructuredLLMCaller] = None,
        map_tool: Optional[MapMaintenanceTool] = None,
        map_api_key: Optional[str] = None,
    ):
        self.caller = caller
        self.map_tool = map_tool or MapMaintenanceTool(api_key=map_api_key or self._load_api_key())
        self._map_lock = threading.RLock()
        self._assignment_lock = threading.RLock()
        self.assignment_registry = AddressAssignmentRegistry()
        self.last_assignment_metrics: Dict[str, Any] = {}
        self._contact_candidate_cache: Dict[Tuple[str, str, str, int], List[Dict[str, Any]]] = {}
        self._birthplace_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    @staticmethod
    def _load_api_key() -> str:
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        config_path = os.path.join(project_root, "config", "config.json")
        with open(config_path, "r", encoding="utf-8") as stream:
            return str(json.load(stream).get("map_tool", {}).get("api_key", ""))

    def reserve_existing_addresses(self, addresses: Optional[List[Dict[str, Any]]]) -> None:
        """Seed duplicate avoidance with addresses assigned by previous batches."""
        pending: List[Any] = list(addresses or [])
        while pending:
            item = pending.pop()
            if isinstance(item, list):
                pending.extend(item)
                continue
            if not isinstance(item, dict):
                continue
            relation = item.get("relation")
            if isinstance(relation, list):
                pending.extend(relation)
            if "home_address" in item:
                values = [item.get("home_address"), item.get("workplace")]
            else:
                values = [item]
            for value in values:
                if not isinstance(value, dict):
                    continue
                poi = {
                    "id": value.get("id", ""),
                    "name": value.get("name", ""),
                    "location": value.get("location", ""),
                    "structured_address": value.get("formatted_address") or _address_text(value),
                }
                self.assignment_registry.reserve("联系人居住地", poi)

    def allocate_persona_addresses(
        self, profile: Dict[str, Any], locked_facts: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None, mobility_profile: Optional[Dict[str, Any]] = None,
        reserved_addresses: Optional[List[Dict[str, Any]]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Public allocation API for a realistic home/work pair."""
        self.reserve_existing_addresses(reserved_addresses)
        return self.ground_core_addresses(profile, locked_facts, seed, mobility_profile)

    def allocate_persona_batch(
        self, profiles: List[Dict[str, Any]],
        locked_facts: Optional[List[Dict[str, Any]]] = None,
        seeds: Optional[List[int]] = None,
        mobility_profiles: Optional[List[Dict[str, Any]]] = None,
        reserved_addresses: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
        """Allocate real, de-duplicated home/work pairs for a persona batch."""
        self.reserve_existing_addresses(reserved_addresses)
        locks = locked_facts or [{} for _ in profiles]
        seed_values = seeds or list(range(len(profiles)))
        mobility_values = mobility_profiles or [{} for _ in profiles]
        if not (len(profiles) == len(locks) == len(seed_values) == len(mobility_values)):
            raise ValueError("profiles、locked_facts、seeds、mobility_profiles 数量必须一致")
        return [
            self.ground_core_addresses(profile, lock, seed, mobility)
            for profile, lock, seed, mobility in zip(profiles, locks, seed_values, mobility_values)
        ]

    @staticmethod
    def _region_matches(expected: Dict[str, Any], geocode: Dict[str, Any]) -> bool:
        for expected_key, actual_key in (("province", "province"), ("city", "city"), ("district", "district")):
            wanted = _text(expected.get(expected_key))
            actual = _text(geocode.get(actual_key))
            if wanted and actual and wanted not in actual and actual not in wanted:
                return False
        return True

    def _core_poi(
        self,
        profile: Dict[str, Any],
        field: str,
        address_type: str,
        locked_address: Dict[str, Any],
    ) -> Dict[str, Any]:
        address = deepcopy(profile.get(field) or {})
        if not isinstance(address, dict) or not (address.get("city") or address.get("province")):
            raise AddressGenerationError("%s 缺少可用于地图落地的省市信息" % field)
        city = _text(address.get("city"))
        exact_locked = bool(locked_address.get("street_name") or locked_address.get("street_number"))
        if exact_locked:
            query = _address_text(address)
            with self._map_lock:
                geocode = self.map_tool.amap_geocode(query, city=city)
            if not geocode or not geocode.get("location"):
                raise AddressGenerationError("无法地理编码用户锁定的%s: %s" % (address_type, query))
            return {
                "name": query,
                "location": geocode.get("location", ""),
                "structured_address": query,
                "geocode": geocode,
                "address_type": address_type,
                "description": "人物的日常%s" % address_type,
            }

        region = "".join(_text(address.get(key)) for key in ("province", "city", "district"))
        place_type = "住宅小区" if field == "home_address" else _workplace_type(profile)
        candidates = [
            "%s %s" % (region, place_type),
            "%s%s %s" % (_text(address.get("city")), _text(address.get("district")), place_type),
        ]
        for keyword in dict.fromkeys(item.strip() for item in candidates if item.strip()):
            with self._map_lock:
                poi = self.map_tool.get_poi(keyword=keyword, city=city)
            if poi and poi.get("location") and self._region_matches(address, poi.get("geocode") or {}):
                result = deepcopy(poi)
                result.update({
                    "address_type": address_type,
                    "description": "人物的日常%s" % address_type,
                })
                return result
        raise AddressGenerationError("无法在画像行政区域内落地%s: %s" % (address_type, region))

    def _core_candidates(
        self,
        profile: Dict[str, Any],
        field: str,
        address_type: str,
        locked_address: Dict[str, Any],
        limit: int = 15,
    ) -> List[Dict[str, Any]]:
        """Build a cheap candidate pool; geocoding is deferred until selection."""
        address = deepcopy(profile.get(field) or {})
        if not isinstance(address, dict) or not (address.get("city") or address.get("province")):
            raise AddressGenerationError("%s 缺少可用于地图落地的省市信息" % field)
        if locked_address.get("street_name") or locked_address.get("street_number"):
            return [self._core_poi(profile, field, address_type, locked_address)]

        city = _text(address.get("city"))
        region = "".join(_text(address.get(key)) for key in ("province", "city", "district"))
        place_type = "住宅小区" if field == "home_address" else _workplace_type(profile)
        queries = list(dict.fromkeys(filter(None, (
            ("%s %s" % (region, place_type)).strip(),
            ("%s%s %s" % (city, _text(address.get("district")), place_type)).strip(),
        ))))
        candidates: List[Dict[str, Any]] = []
        search = getattr(self.map_tool, "search_poi_candidates", None)
        minimum_pool_size = min(limit, 6)
        if callable(search):
            for keyword in queries:
                with self._map_lock:
                    found = search(keyword=keyword, city=city, limit=limit)
                for raw in found or []:
                    if raw.get("location") and self._region_matches(address, raw.get("geocode") or {}):
                        candidate = deepcopy(raw)
                        candidate.update({
                            "address_type": address_type,
                            "description": "人物的日常%s" % address_type,
                            "_needs_selected_geocode": True,
                        })
                        candidates.append(candidate)
                if len(candidates) >= minimum_pool_size:
                    break
        if not candidates:
            candidates = [self._core_poi(profile, field, address_type, locked_address)]

        unique = []
        seen = set()
        for candidate in candidates:
            key = _text(candidate.get("id")) or _text(candidate.get("location"))
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(candidate)
        return unique[:limit]

    def _candidate_score(
        self, candidate: Dict[str, Any], expected: Dict[str, Any], address_type: str,
    ) -> float:
        geocode = candidate.get("geocode") or {}
        score = 0.0
        score += 0.65 if _text(candidate.get("name")) else 0.0
        score += 0.45 if _text(candidate.get("structured_address")) else 0.0
        score += 0.25 if _text(geocode.get("district")) else 0.0
        score += 0.20 if _text(geocode.get("street")) else 0.0
        score += 0.25 if self._region_matches(expected, geocode) else -2.0
        score -= self.assignment_registry.penalty(address_type, candidate)
        return score

    @staticmethod
    def _commute_preferences(
        profile: Dict[str, Any], mobility_profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Tuple[float, float]]:
        text = " ".join(_text(profile.get(key)) for key in (
            "job", "occupation", "description", "lifestyle_desc", "work_desc",
            "economic_desc", "economic_situation", "daily_routine",
        ))
        city = _text((profile.get("home_address") or {}).get("city"))
        structured_transport = str((mobility_profile or {}).get("primary_transport") or "")
        if any(word in text for word in ("远程", "居家办公", "在家办公")):
            return "walking", (0.0, 15.0)
        if structured_transport in {"walking", "bicycling", "transit", "driving"}:
            transport = structured_transport
        elif any(word in text for word in ("无车", "公交", "地铁", "公共交通")):
            transport = "transit"
        elif any(word in text for word in ("步行", "走路上班")):
            transport = "walking"
        elif any(word in text for word in ("骑行", "自行车", "电动车")):
            transport = "bicycling"
        else:
            transport = "driving"
        major_cities = ("北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "重庆", "武汉", "苏州")
        if any(name in city for name in major_cities):
            ranges = {
                "walking": (8.0, 35.0), "bicycling": (12.0, 40.0),
                "transit": (25.0, 60.0), "driving": (20.0, 50.0),
            }
        else:
            ranges = {
                "walking": (5.0, 30.0), "bicycling": (10.0, 35.0),
                "transit": (15.0, 45.0), "driving": (10.0, 40.0),
            }
        return transport, ranges[transport]

    @staticmethod
    def _estimated_minutes(distance_km: float, transport: str) -> float:
        speeds = {"walking": 4.8, "bicycling": 14.0, "transit": 18.0, "driving": 25.0}
        overhead = {"walking": 0.0, "bicycling": 2.0, "transit": 9.0, "driving": 5.0}
        return distance_km / speeds.get(transport, 25.0) * 60 + overhead.get(transport, 5.0)

    def _select_core_pair(
        self,
        profile: Dict[str, Any],
        homes: List[Dict[str, Any]],
        works: List[Dict[str, Any]],
        rng: random.Random,
        mobility_profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        transport, target_range = self._commute_preferences(profile, mobility_profile)
        home_expected = profile.get("home_address") or {}
        work_expected = profile.get("workplace") or {}
        unused_homes = [item for item in homes if self.assignment_registry.usage_count(item) == 0]
        unused_works = [item for item in works if self.assignment_registry.usage_count(item) == 0]
        homes = unused_homes or homes
        works = unused_works or works
        prescored = []
        for home in homes:
            for work in works:
                distance = _haversine_km(home, work)
                if distance is None:
                    continue
                estimate = self._estimated_minutes(distance, transport)
                score = (
                    self._candidate_score(home, home_expected, "居住地")
                    + self._candidate_score(work, work_expected, "工作地")
                    + 1.8 * _range_score(estimate, *target_range)
                    - max(0.0, estimate - 90.0) / 25.0
                )
                prescored.append((score, home, work, distance, estimate))
        if not prescored:
            return homes[0], works[0]

        # Routing is the expensive step: evaluate only the strongest straight-line pairs.
        routed = []
        duration_method = getattr(self.map_tool, "get_duration_between_pois", None)
        for score, home, work, distance, estimate in sorted(prescored, reverse=True, key=lambda x: x[0])[:2]:
            duration = None
            if callable(duration_method):
                with self._map_lock:
                    duration = duration_method(
                        home, work, transport,
                        origin_city=_text(home_expected.get("city")),
                        dest_city=_text(work_expected.get("city")),
                    )
            minutes = duration / 60.0 if duration is not None else estimate
            routed_score = score + 2.2 * _range_score(minutes, *target_range) - max(0.0, minutes - 90.0) / 18.0
            routed.append((routed_score, (home, work, distance, minutes, transport, duration is not None)))
        verified = [item for item in routed if item[1][-1]]
        selected = _weighted_choice(rng, verified or routed, top_n=3)
        home, work, distance, minutes, transport, routed_ok = selected
        self.last_assignment_metrics = {
            "commute_transport": transport,
            "commute_minutes": round(minutes, 1),
            "straight_distance_km": round(distance, 2),
            "route_api_used": routed_ok,
        }
        return home, work

    def _enrich_selected_candidate(self, poi: Dict[str, Any], city: str) -> Dict[str, Any]:
        """Spend at most one geocode request for a selected POI, never per candidate."""
        selected = deepcopy(poi)
        if not selected.pop("_needs_selected_geocode", False):
            return selected
        geocode_method = getattr(self.map_tool, "amap_geocode", None)
        if not callable(geocode_method):
            return selected
        query = _text(selected.get("structured_address")) or _text(selected.get("address"))
        if not query:
            query = _text(selected.get("name"))
        elif _text(selected.get("name")) and _text(selected.get("name")) not in query:
            query = "%s%s" % (query, _text(selected.get("name")))
        with self._map_lock:
            geocode = geocode_method(query, city=city) if query else None
        if geocode:
            geocode = deepcopy(geocode)
            if not _text(geocode.get("street")):
                geocode["street"] = _text(selected.get("address")) or _text(selected.get("name"))
            if not _text(geocode.get("formatted_address")) or not _text(geocode.get("street")):
                geocode["formatted_address"] = "".join(
                    _text(geocode.get(key)) for key in ("province", "city", "district", "street", "number")
                )
            selected["geocode"] = geocode
            selected["structured_address"] = _text(geocode.get("formatted_address")) or query
        # The POI coordinate is more precise than a road/address centroid.
        selected["location"] = _text(poi.get("location")) or _text((geocode or {}).get("location"))
        return selected

    @staticmethod
    def _synchronize_address(
        profile: Dict[str, Any], field: str, poi: Dict[str, Any],
        locked_address: Dict[str, Any],
    ) -> None:
        original = deepcopy(profile.get(field) or {})
        geocode = poi.get("geocode") or {}
        for target_key, source_key in (
            ("province", "province"), ("city", "city"), ("district", "district"),
            ("street_name", "street"), ("street_number", "number"),
        ):
            value = _text(geocode.get(source_key))
            if value:
                original[target_key] = value
        for key, value in locked_address.items():
            original[key] = deepcopy(value)
        profile[field] = original
        geocode = dict(geocode)
        for target_key, source_key in (
            ("province", "province"), ("city", "city"), ("district", "district"),
            ("street_name", "street"), ("street_number", "number"),
        ):
            if original.get(target_key) not in (None, ""):
                geocode[source_key] = _text(original[target_key])
        poi["geocode"] = geocode
        poi["structured_address"] = _address_text(original) or _text(poi.get("structured_address"))

    @staticmethod
    def _location_record(poi: Dict[str, Any]) -> Dict[str, Any]:
        geocode = poi.get("geocode") or {}
        prefix = _text(poi.get("address_type"))
        poi_name = _text(poi.get("name")) or prefix
        value = {
            "name": "%s·%s" % (prefix, poi_name) if prefix and not poi_name.startswith(prefix) else poi_name,
            "location": _text(poi.get("location")),
            "formatted_address": _text(poi.get("structured_address")),
            "city": _text(geocode.get("city")),
            "district": _text(geocode.get("district")),
            "streetName": _text(geocode.get("street")),
            "streetNumber": _text(geocode.get("number")),
            "description": _text(poi.get("description")),
        }
        return {key: value[key] for key in LOCATION_KEYS}

    def ground_core_addresses(
        self, profile: Dict[str, Any], locked_facts: Optional[Dict[str, Any]] = None,
        seed: Optional[int] = None, mobility_profile: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        grounded = deepcopy(profile)
        locked_facts = locked_facts or {}
        rng = random.Random(seed)
        self.last_assignment_metrics = {}
        home_candidates = self._core_candidates(
            grounded, "home_address", "居住地", locked_facts.get("home_address") or {},
        )
        work_candidates: List[Dict[str, Any]] = []
        workplace = grounded.get("workplace")
        has_work = _has_daily_workplace(grounded) and isinstance(workplace, dict) and (
            workplace.get("city") or workplace.get("province")
        )
        if has_work:
            work_candidates = self._core_candidates(
                grounded, "workplace", "工作地", locked_facts.get("workplace") or {},
            )
        with self._assignment_lock:
            if has_work:
                home_poi, work_poi = self._select_core_pair(
                    grounded, home_candidates, work_candidates, rng, mobility_profile,
                )
            else:
                unused_homes = [
                    item for item in home_candidates
                    if self.assignment_registry.usage_count(item) == 0
                ]
                scored_homes = [
                    (self._candidate_score(item, grounded.get("home_address") or {}, "居住地"), item)
                    for item in (unused_homes or home_candidates)
                ]
                home_poi = _weighted_choice(rng, scored_homes, top_n=4)
                work_poi = None
            self.assignment_registry.reserve("居住地", home_poi)
            if work_poi is not None:
                self.assignment_registry.reserve("工作地", work_poi)

        home_poi = self._enrich_selected_candidate(
            home_poi, _text((grounded.get("home_address") or {}).get("city")),
        )
        self._synchronize_address(
            grounded, "home_address", home_poi,
            locked_facts.get("home_address") or {},
        )
        core = [home_poi]
        if work_poi is not None:
            work_poi = self._enrich_selected_candidate(
                work_poi, _text((grounded.get("workplace") or {}).get("city")),
            )
            self._synchronize_address(
                grounded, "workplace", work_poi,
                locked_facts.get("workplace") or {},
            )
            core.append(work_poi)
        lock_errors = locked_fact_errors(grounded, locked_facts)
        if lock_errors:
            raise AddressGenerationError("地址落地修改了输入事实: %s" % "; ".join(lock_errors))
        return grounded, core

    @staticmethod
    def _core_by_type(core_locations: List[Dict[str, Any]], address_type: str) -> Optional[Dict[str, Any]]:
        return next((item for item in core_locations or [] if item.get("address_type") == address_type), None)

    def _resolve_named_place(
        self, name: str, city: str, fallback_keyword: str,
        circle_id: str, description: str, seed: Optional[int] = None,
        base_poi: Optional[Dict[str, Any]] = None,
        nearby_radius: Optional[int] = None,
    ) -> Dict[str, Any]:
        search = getattr(self.map_tool, "search_poi_candidates", None)
        candidates = []
        queries = list(dict.fromkeys(filter(None, (name.strip(), fallback_keyword.strip()))))
        base_location = _text((base_poi or {}).get("location"))
        around = getattr(self.map_tool, "search_around_candidates", None)
        if nearby_radius is not None:
            if not base_location:
                raise AddressGenerationError("关系圈 %s 缺少住宅坐标，无法搜索附近兴趣地点" % circle_id)
            if callable(around):
                for query in queries:
                    with self._map_lock:
                        candidates = around(
                            location=base_location, keywords=query, city=city,
                            radius=nearby_radius, limit=30, sortrule="weight",
                        ) or []
                    if candidates:
                        break
            elif hasattr(self.map_tool, "search_around_poi_random"):
                with self._map_lock:
                    selected = self.map_tool.search_around_poi_random(
                        location=base_location, keywords=queries[-1], city=city,
                        radius=nearby_radius, sortrule="weight",
                    )
                candidates = [selected] if selected else []
            if not candidates:
                raise AddressGenerationError(
                    "住宅 %.1f 公里内无法为关系圈 %s 找到真实兴趣地点: %s"
                    % (nearby_radius / 1000.0, circle_id, name or fallback_keyword)
                )
        elif callable(search):
            for query in queries:
                with self._map_lock:
                    candidates = search(keyword="%s %s" % (city, query), city=city, limit=20) or []
                if candidates:
                    break
        if nearby_radius is None and not candidates:
            with self._map_lock:
                fallback = self.map_tool.get_poi(keyword="%s %s" % (city, queries[-1]), city=city)
            candidates = [fallback] if fallback else []
        if not candidates:
            raise AddressGenerationError("无法为关系圈 %s 落地真实地点: %s" % (circle_id, name or fallback_keyword))
        scored = []
        for item in candidates:
            if not item or not item.get("location"):
                continue
            distance_km = _haversine_km(item, base_poi) if base_poi else None
            distance_score = 0.0
            if nearby_radius is not None and distance_km is not None:
                distance_score = 1.5 * _range_score(distance_km, 0.2, nearby_radius / 1000.0 * 0.75)
            score = (
                (1.1 if name and name in _text(item.get("name")) else 0.0)
                + (0.4 if _text(item.get("structured_address")) else 0.0)
                + distance_score
                - self.assignment_registry.penalty("关系圈固定地", item)
            )
            scored.append((score, item))
        selected = _weighted_choice(random.Random("%s:%s:%s" % (seed, circle_id, name)), scored, top_n=4)
        if not selected:
            raise AddressGenerationError("关系圈 %s 没有带坐标的真实地点候选" % circle_id)
        result = deepcopy(selected)
        result.update({
            "address_type": "关系圈固定地",
            "description": description,
            "_circle_id": circle_id,
            "_distance_from_home_km": round(_haversine_km(result, base_poi), 2) if base_poi and _haversine_km(result, base_poi) is not None else None,
        })
        self.assignment_registry.reserve("关系圈固定地", result)
        return result

    @staticmethod
    def _interest_radius(circle_type: str, facts: Dict[str, Any]) -> int:
        text = " ".join(_text(facts.get(key)) for key in ("frequency", "activity_schedule", "activity"))
        if any(word in text for word in ("每天", "每日", "daily", "工作日", "高频")):
            return 3000
        if any(word in text for word in ("每周", "weekly", "周末")):
            return 6000
        return 8000 if circle_type == "hobby_group" else 7000

    @staticmethod
    def _interest_keyword(circle_type: str, facts: Dict[str, Any]) -> str:
        activity = _text(facts.get("activity"))
        if "羽毛球" in activity:
            return "羽毛球馆"
        if any(word in activity for word in ("健身", "力量", "器械")):
            return "健身房"
        if any(word in activity for word in ("跑步", "夜跑", "跑团")):
            return "公园 体育场"
        if any(word in activity for word in ("篮球", "足球", "网球", "游泳")):
            return "%s场馆" % activity
        return "文化活动场所" if circle_type == "hobby_group" else "体育馆 健身房"

    def _judge_poi_reasonableness(
        self, place_kind: str, context_text: str, poi: Dict[str, Any],
    ) -> Tuple[bool, Optional[str]]:
        """用 LLM 判断地图返回的 POI 是否与圈子/地点语义一致。

        返回 (reasonable, suggested_query)：一致时 suggested_query 为 None；不一致时
        返回一个更合适、可在地图检索到的查询词。LLM 不可用或调用失败时按一致处理，
        避免因为审查环节本身出错而中断整条生成。
        """
        if self.caller is None:
            return True, None
        poi_name = _text(poi.get("name"))
        poi_address = _text(poi.get("structured_address")) or _text(poi.get("formatted_address"))
        prompt = (
            "你是人物画像地址落地的一致性审查员。判断地图返回的地点 POI 是否与该圈子的语义一致，"
            "如果不一致，给出一个更合理、可在地图检索到的查询词。\n\n"
            "地点类型：%s\n"
            "圈子/地点上下文：\n%s\n\n"
            "地图返回的候选 POI：\n"
            "- 名称：%s\n"
            "- 地址：%s\n\n"
            "判断规则：\n"
            "1. POI 的类别与层级必须与上下文匹配。例如「学校」若是高等教育（硕士/博士/研究生/本科/大学等），"
            "POI 不能是中小学、幼儿园、培训机构（名称含「小学」「中学」「初中」「高中」「实验学校」「幼儿园」"
            "「培训」「技校」「中专」等）；「运动场馆」「聚会地点」应是能承载对应活动的真实场所。\n"
            "2. 若 POI 与上下文明显不符，判定为不合理。\n"
            "3. 合理则 reasonable=true 且 suggested_query 为空字符串；不合理则 reasonable=false，"
            "并给出 suggested_query（一个更符合上下文的真实地点名或检索词，便于地图检索）。\n\n"
            "只输出 JSON：{\"reasonable\": <bool>, \"suggested_query\": \"<string>\"}"
            % (place_kind, context_text, poi_name, poi_address)
        )

        def validate(data: Any) -> List[str]:
            if not isinstance(data, dict):
                return ["输出必须是 JSON 对象"]
            if not isinstance(data.get("reasonable"), bool):
                return ["reasonable 必须是布尔值"]
            if not isinstance(data.get("suggested_query"), str):
                return ["suggested_query 必须是字符串"]
            return []

        try:
            result = self.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
        except Exception:
            return True, None
        reasonable = bool(result.data.get("reasonable"))
        suggested = _text(result.data.get("suggested_query"))
        return reasonable, suggested or None

    def _resolve_with_llm_gate(
        self, place_kind: str, context_text: str, initial_query: str,
        search_fn: Callable[[str], Optional[Dict[str, Any]]],
    ) -> Optional[Dict[str, Any]]:
        """查询 → LLM 判合理性 → 不合理重新生成检索词再查，最多重试 _POI_MAX_RETRIES 次。

        仍不合理时返回 None，由调用方放弃真实 POI、沿用 LLM 原始内容。
        """
        if self.caller is None:
            return search_fn(initial_query)
        query = _text(initial_query)
        for attempt in range(_POI_MAX_RETRIES + 1):
            poi = search_fn(query)
            if poi is None:
                return None
            reasonable, suggested = self._judge_poi_reasonableness(place_kind, context_text, poi)
            if reasonable:
                return poi
            if attempt >= _POI_MAX_RETRIES or not suggested:
                return None
            query = suggested
        return None

    def _circle_context_text(
        self, circle_type: str, circle_name: str, facts: Dict[str, Any], profile: Dict[str, Any],
    ) -> str:
        lines = ["圈子名：%s" % _text(circle_name)]
        if circle_type == "school":
            education = _text(profile.get("education"))
            if education:
                lines.append("人物教育背景：%s" % education)
        keys = {
            "school": ("institution_name", "major", "direction", "shared_period", "degree", "discipline"),
            "sports_club": ("venue_name", "activity", "frequency", "activity_schedule"),
            "hobby_group": ("meeting_place", "activity", "frequency", "group_name"),
        }.get(circle_type, ("activity", "frequency"))
        for key in keys:
            value = _text(facts.get(key))
            if value:
                lines.append("%s：%s" % (key, value))
        return "\n".join(lines)

    def _resolve_named_place_with_llm(
        self, name: str, city: str, fallback_keyword: str,
        circle_id: str, description: str, circle_type: str, circle_name: str,
        facts: Dict[str, Any], profile: Dict[str, Any], seed: Optional[int] = None,
        base_poi: Optional[Dict[str, Any]] = None, nearby_radius: Optional[int] = None,
    ) -> Optional[Dict[str, Any]]:
        place_kind = _CIRCLE_PLACE_KIND.get(circle_type, circle_type)
        context_text = self._circle_context_text(circle_type, circle_name, facts, profile)

        def search_fn(query: str) -> Optional[Dict[str, Any]]:
            try:
                return self._resolve_named_place(
                    query, city, fallback_keyword, circle_id, description, seed,
                    base_poi, nearby_radius,
                )
            except AddressGenerationError:
                return None

        return self._resolve_with_llm_gate(
            place_kind, context_text, _text(name), search_fn,
        )

    def ground_circle_anchors(
        self, circle_anchors: List[Dict[str, Any]], profile: Dict[str, Any],
        core_locations: List[Dict[str, Any]], seed: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Resolve shared schools, sports venues and homes to real map POIs."""
        grounded = deepcopy(circle_anchors or [])
        city = _text((profile.get("home_address") or {}).get("city"))
        resolved_by_parent: Dict[str, Dict[str, Any]] = {}
        fixed_pois: List[Dict[str, Any]] = []
        home_poi = self._core_by_type(core_locations, "居住地")
        work_poi = self._core_by_type(core_locations, "工作地")
        for anchor in grounded:
            circle_type = _text(anchor.get("circle_type"))
            circle_id = _text(anchor.get("circle_id"))
            parent_id = _text(anchor.get("parent_anchor_id")) or circle_id
            facts = anchor.setdefault("shared_facts", {})
            poi = resolved_by_parent.get(parent_id)
            fact_key = ""
            if circle_type == "current_work":
                poi = work_poi
                fact_key = "workplace_poi"
            elif circle_type in {"household", "neighborhood"}:
                poi = home_poi
                fact_key = "shared_place"
            elif circle_type == "school":
                fact_key = "institution_name"
                if poi is None:
                    poi = self._resolve_named_place_with_llm(
                        _text(facts.get(fact_key)), city, "学校", circle_id,
                        "%s共同就读或任教的真实学校" % _text(anchor.get("social_circle")),
                        circle_type, _text(anchor.get("social_circle")), facts, profile,
                        seed,
                    )
            elif circle_type == "sports_club":
                fact_key = "venue_name"
                if poi is None:
                    radius = self._interest_radius(circle_type, facts)
                    poi = self._resolve_named_place_with_llm(
                        _text(facts.get(fact_key)), city, self._interest_keyword(circle_type, facts), circle_id,
                        "%s共同活动的真实场馆" % _text(anchor.get("social_circle")),
                        circle_type, _text(anchor.get("social_circle")), facts, profile,
                        seed, home_poi, radius,
                    )
                    if poi is not None:
                        facts["max_home_distance_km"] = radius / 1000.0
            elif circle_type == "hobby_group" and _text(facts.get("meeting_place")):
                fact_key = "meeting_place"
                if poi is None:
                    radius = self._interest_radius(circle_type, facts)
                    poi = self._resolve_named_place_with_llm(
                        _text(facts.get(fact_key)), city, self._interest_keyword(circle_type, facts), circle_id,
                        "%s线下聚会的真实地点" % _text(anchor.get("social_circle")),
                        circle_type, _text(anchor.get("social_circle")), facts, profile,
                        seed, home_poi, radius,
                    )
                    if poi is not None:
                        facts["max_home_distance_km"] = radius / 1000.0
            if not poi:
                continue
            resolved_by_parent[parent_id] = poi
            facts[fact_key or "shared_place"] = _text(poi.get("name"))
            facts["place_address"] = _text(poi.get("structured_address"))
            facts["place_location"] = _text(poi.get("location"))
            if circle_type in {"sports_club", "hobby_group"}:
                distance = _haversine_km(poi, home_poi) if home_poi else None
                if distance is None:
                    raise AddressGenerationError("关系圈 %s 无法计算兴趣地点到住宅的距离" % circle_id)
                facts["distance_from_home_km"] = round(distance, 2)
                if distance > float(facts.get("max_home_distance_km") or 8.0):
                    raise AddressGenerationError("关系圈 %s 的兴趣地点距离住宅过远: %.2fkm" % (circle_id, distance))
            if circle_type == "school":
                anchor["parent_anchor_id"] = "school:%s" % _text(poi.get("name"))
            elif circle_type == "sports_club":
                anchor["parent_anchor_id"] = "venue:%s" % _text(poi.get("name"))
            elif circle_type == "hobby_group":
                anchor["parent_anchor_id"] = "place:%s" % _text(poi.get("name"))
            if poi.get("address_type") == "关系圈固定地" and not any(
                AddressAssignmentRegistry._key(item) == AddressAssignmentRegistry._key(poi)
                for item in fixed_pois
            ):
                fixed_pois.append(deepcopy(poi))
        return grounded, fixed_pois

    @staticmethod
    def _address_from_poi(poi: Dict[str, Any]) -> Dict[str, Any]:
        geocode = poi.get("geocode") or {}
        return {
            "province": _text(geocode.get("province")),
            "city": _text(geocode.get("city")),
            "district": _text(geocode.get("district")),
            "street_name": _text(geocode.get("street")) or _text(poi.get("address")) or _text(poi.get("name")),
            "street_number": _text(geocode.get("number")),
        }

    def _residential_candidates(
        self, expected: Dict[str, Any], anchor_poi: Optional[Dict[str, Any]], radius: int,
    ) -> List[Dict[str, Any]]:
        city = _text(expected.get("city") or expected.get("province"))
        district = _text(expected.get("district"))
        anchor_location = _text((anchor_poi or {}).get("location"))
        cache_key = (city, district, anchor_location, radius)
        if cache_key in self._contact_candidate_cache:
            return deepcopy(self._contact_candidate_cache[cache_key])
        candidates: List[Dict[str, Any]] = []
        around = getattr(self.map_tool, "search_around_candidates", None)
        if anchor_location and callable(around):
            with self._map_lock:
                candidates = around(
                    location=anchor_location, keywords="住宅小区", city=city,
                    radius=radius, limit=40, sortrule="weight",
                ) or []
        search = getattr(self.map_tool, "search_poi_candidates", None)
        if not candidates and callable(search):
            keyword = "%s%s 住宅小区" % (city, district)
            with self._map_lock:
                candidates = search(keyword=keyword, city=city, limit=40) or []
        if not candidates:
            query = "%s%s 住宅小区" % (city, district)
            with self._map_lock:
                poi = self.map_tool.get_poi(keyword=query, city=city)
            candidates = [poi] if poi else []
        candidates = [item for item in candidates if item and item.get("location")]
        self._contact_candidate_cache[cache_key] = deepcopy(candidates)
        return candidates

    def _ground_birth_place(self, value: Dict[str, Any]) -> Dict[str, Any]:
        query = "".join(_text(value.get(key)) for key in ("province", "city", "district"))
        city = _text(value.get("city"))
        if not query:
            raise AddressGenerationError("联系人 birth_place 缺少行政区信息")
        key = (query, city)
        geocode = self._birthplace_cache.get(key)
        if geocode is None:
            with self._map_lock:
                geocode = self.map_tool.amap_geocode(query, city=city)
            if not geocode:
                raise AddressGenerationError("联系人出生地无法通过地图 API 验证: %s" % query)
            self._birthplace_cache[key] = deepcopy(geocode)
        return {
            "province": _text(geocode.get("province")) or _text(value.get("province")),
            "city": _text(geocode.get("city")) or city,
            "district": _text(geocode.get("district")) or _text(value.get("district")),
        }

    def ground_contact_addresses(
        self, profile: Dict[str, Any], contacts: List[Any], circle_anchor: Dict[str, Any],
        core_locations: List[Dict[str, Any]], fixed_pois: Optional[List[Dict[str, Any]]] = None,
        seed: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Replace LLM contact addresses with verified real residential POIs."""
        circle_type = _text(circle_anchor.get("circle_type"))
        circle_id = _text(circle_anchor.get("circle_id"))
        home_poi = self._core_by_type(core_locations, "居住地")
        work_poi = self._core_by_type(core_locations, "工作地")
        fixed = next((item for item in fixed_pois or [] if item.get("_circle_id") == circle_id), None)
        anchor_poi = {
            "current_work": work_poi,
            "neighborhood": home_poi,
            "school": fixed,
            "sports_club": fixed,
            "hobby_group": fixed,
        }.get(circle_type)
        radius = {
            "neighborhood": 2500, "current_work": 30000, "school": 20000,
            "sports_club": 12000, "hobby_group": 15000,
        }.get(circle_type, 0)
        audits = []
        rng = random.Random("%s:%s" % (seed, circle_id))
        for index, contact in enumerate(contacts):
            if circle_type == "household":
                contact.home_address = deepcopy(profile.get("home_address") or {})
                source_poi = home_poi or {"structured_address": _address_text(contact.home_address)}
            else:
                expected = deepcopy(contact.home_address or {})
                main_city = _text((profile.get("home_address") or {}).get("city"))
                contact_city = _text(expected.get("city"))
                usable_anchor = anchor_poi if anchor_poi and (not contact_city or contact_city == main_city) else None
                candidates = self._residential_candidates(expected, usable_anchor, radius)
                if not candidates:
                    raise AddressGenerationError("联系人 %s 没有真实住宅候选" % contact.name)
                target_range = {
                    "neighborhood": (0.1, 2.5), "current_work": (2.0, 25.0),
                    "school": (1.0, 20.0), "sports_club": (0.5, 12.0),
                    "hobby_group": (0.5, 15.0),
                }.get(circle_type, (0.0, 40.0))
                scored = []
                for candidate in candidates:
                    distance = _haversine_km(candidate, usable_anchor) if usable_anchor else None
                    score = self._candidate_score(candidate, expected, "联系人居住地")
                    if distance is not None:
                        score += 1.2 * _range_score(distance, *target_range)
                    scored.append((score, candidate))
                unused = [item for item in scored if self.assignment_registry.usage_count(item[1]) == 0]
                source_poi = _weighted_choice(rng, unused or scored, top_n=5)
                if source_poi is None:
                    raise AddressGenerationError("联系人 %s 的住宅候选无法分配" % contact.name)
                contact.home_address = self._address_from_poi(source_poi)
                self.assignment_registry.reserve("联系人居住地", source_poi)
            contact.birth_place = self._ground_birth_place(contact.birth_place)
            audits.append({
                "contact_name": contact.name,
                "circle_id": circle_id,
                "home_poi_name": _text(source_poi.get("name")),
                "home_location": _text(source_poi.get("location")),
                "home_address": _address_text(contact.home_address),
                "birth_place_verified": True,
            })
        return audits

    def _select_surrounding_poi(
        self, plan: Dict[str, Any], keyword: str, base: Optional[Dict[str, Any]],
        radius: int, target: int, frequency: str, scope: str, profile: Dict[str, Any],
        rng: random.Random, selected_keys: set,
    ) -> Optional[Dict[str, Any]]:
        """为一个常去地计划做一次地图查询并选定 POI（不判合理性，返回 None 表示无候选）。"""
        poi = None
        around_candidates = getattr(self.map_tool, "search_around_candidates", None)
        if scope == "city":
            city = _text((profile.get("home_address") or {}).get("city"))
            search = getattr(self.map_tool, "search_poi_candidates", None)
            candidates = []
            if callable(search):
                with self._map_lock:
                    candidates = search(
                        keyword="%s %s" % (city, keyword),
                        city=city, limit=30, types=_text(plan.get("poi_type")) or None,
                    ) or []
            if not candidates:
                with self._map_lock:
                    fallback = self.map_tool.get_poi(keyword="%s %s" % (city, keyword), city=city)
                candidates = [fallback] if fallback else []
            with self._assignment_lock:
                scored = [
                    (
                        0.5 + (0.3 if _text(item.get("structured_address")) else 0.0)
                        - self.assignment_registry.penalty("常去地", item), item,
                    )
                    for item in candidates
                    if item and AddressAssignmentRegistry._key(item) not in selected_keys
                ]
                poi = _weighted_choice(rng, scored, top_n=6)
                if poi:
                    self.assignment_registry.reserve("常去地", poi)
        elif callable(around_candidates):
            with self._map_lock:
                candidates = around_candidates(
                    location=_text(base.get("location")),
                    keywords=keyword,
                    types=_text(plan.get("poi_type")) or None,
                    city=_text((base.get("geocode") or {}).get("city")),
                    radius=radius,
                    limit=25,
                    sortrule="distance" if frequency == "daily" else "weight",
                )
            with self._assignment_lock:
                scored = []
                for candidate in candidates or []:
                    key = AddressAssignmentRegistry._key(candidate)
                    if not key or key in selected_keys:
                        continue
                    distance = float(candidate.get("distance_m") or 0)
                    distance_score = _range_score(distance, target * 0.35, target * 1.75)
                    quality = 0.25 if _text(candidate.get("structured_address")) else 0.0
                    quality += 0.15 if _text(candidate.get("name")) else 0.0
                    score = distance_score + quality - self.assignment_registry.penalty("常去地", candidate)
                    scored.append((score, candidate))
                poi = _weighted_choice(rng, scored, top_n=5)
                if poi:
                    self.assignment_registry.reserve("常去地", poi)
        else:
            with self._map_lock:
                legacy_args = {
                    "location": _text(base.get("location")),
                    "keywords": keyword,
                    "types": _text(plan.get("poi_type")) or None,
                    "city": _text((base.get("geocode") or {}).get("city")),
                }
                try:
                    poi = self.map_tool.search_around_poi_random(radius=radius, **legacy_args)
                except TypeError:
                    poi = self.map_tool.search_around_poi_random(**legacy_args)
            if poi:
                with self._assignment_lock:
                    self.assignment_registry.reserve("常去地", poi)
        return poi

    def generate_surrounding_locations(
        self, profile: Dict[str, Any], core: List[Dict[str, Any]], seed: Optional[int] = None,
        fixed_pois: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if self.caller is None:
            raise AddressGenerationError("生成常去地点需要 StructuredLLMCaller")
        core_types = {item.get("address_type") for item in core}
        prompt = build_address_places_prompt(profile, core)

        def validate(items):
            errors = []
            if not 6 <= len(items) <= 12:
                errors.append("场所规划数量必须在 6～12")
            plan_keys = set()
            frequencies = set()
            city_scope_count = 0
            purchase_words = ("超市", "便利店", "菜市场", "菜场", "生鲜", "药店", "药房", "水果")
            restaurant_words = ("餐馆", "餐厅", "饭店", "快餐", "面馆", "火锅", "烧烤", "小吃", "食堂", "简餐", "早餐", "外卖")
            instant_words = purchase_words + restaurant_words + ("咖啡", "奶茶")
            home_purchase = home_restaurant = False
            work_instant = "工作地" not in core_types
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    errors.append("items[%d] 必须是对象" % index)
                    continue
                scope = _text(item.get("scope")) or "around"
                if scope not in {"around", "city"}:
                    errors.append("items[%d].scope 必须是 around 或 city" % index)
                if scope == "city":
                    city_scope_count += 1
                elif item.get("base_address_type") not in core_types:
                    errors.append("items[%d].base_address_type 不属于核心地址" % index)
                keyword = str(item.get("keyword") or "").strip()
                if not keyword:
                    errors.append("items[%d].keyword 不能为空" % index)
                interest_words = ("健身", "羽毛球", "篮球", "足球", "网球", "游泳", "跑步", "跑团", "运动", "瑜伽", "舞蹈", "公园", "书店", "图书馆", "阅读", "兴趣班")
                if scope == "around" and any(word in keyword for word in interest_words) and item.get("base_address_type") != "居住地":
                    errors.append("items[%d] 高频兴趣地点必须基于居住地搜索" % index)
                frequency = _text(item.get("frequency"))
                if frequency not in {"daily", "weekly", "monthly"}:
                    errors.append("items[%d].frequency 必须是 daily、weekly 或 monthly" % index)
                else:
                    frequencies.add(frequency)
                base_type = item.get("base_address_type")
                if frequency in {"daily", "weekly"}:
                    if base_type == "居住地" and any(word in keyword for word in purchase_words):
                        home_purchase = True
                    if base_type == "居住地" and any(word in keyword for word in restaurant_words):
                        home_restaurant = True
                    if base_type == "工作地" and frequency == "daily" and any(word in keyword for word in instant_words):
                        work_instant = True
                plan_key = (item.get("base_address_type"), _text(item.get("keyword")), frequency)
                if plan_key in plan_keys:
                    errors.append("items[%d] 与已有场所规划重复" % index)
                plan_keys.add(plan_key)
            if "daily" not in frequencies or "weekly" not in frequencies:
                errors.append("周边场所规划至少包含一个 daily 和一个 weekly")
            if city_scope_count < 1:
                errors.append("场所规划至少包含一个城市级公共地点")
            if not home_purchase:
                errors.append("居住地周边至少规划一个超市/便利店/菜市场/药店类采购场所（daily 或 weekly）")
            if not home_restaurant:
                errors.append("居住地周边至少规划一个餐馆/餐厅/快餐类餐饮场所（daily 或 weekly）")
            if not work_instant:
                errors.append("工作地周边至少规划一个餐馆/快餐/便利店/咖啡类即时场所（daily）")
            return errors

        result = self.caller.call_json_array(prompt, validator=validate)
        all_fixed = list(fixed_pois or [])
        locations = [self._location_record(item) for item in core]
        locations.extend(self._location_record(item) for item in all_fixed)
        core_by_type = {item.get("address_type"): item for item in core}
        rng = random.Random(seed)
        selected_keys = {
            AddressAssignmentRegistry._key(item) for item in list(core) + all_fixed
            if AddressAssignmentRegistry._key(item)
        }
        if seed is not None and hasattr(self.map_tool, "set_random_seed"):
            self.map_tool.set_random_seed(seed)
        city_landmark_count = 0
        for plan in result.data:
            scope = _text(plan.get("scope")) or "around"
            base = core_by_type.get(plan.get("base_address_type"))
            if scope == "around" and not base:
                continue
            frequency = _text(plan.get("frequency"))
            if frequency == "daily":
                radius, target = ((1200, 350) if plan.get("base_address_type") == "工作地" else (1800, 650))
            elif frequency == "monthly":
                radius, target = 20000, 6500
            else:
                radius, target = 8000, 2500

            context_text = "地点用途：%s\n检索关键词：%s\n范围：%s\n频次：%s" % (
                _text(plan.get("description")), _text(plan.get("keyword")), scope, frequency,
            )
            poi = self._resolve_with_llm_gate(
                "常去地", context_text, _text(plan.get("keyword")),
                lambda kw: self._select_surrounding_poi(
                    plan, kw, base, radius, target, frequency, scope, profile, rng, selected_keys,
                ),
            )
            if not poi:
                continue
            poi = deepcopy(poi)
            poi.update({
                "address_type": "常去地",
                "description": _text(plan.get("description")),
            })
            selected_keys.add(AddressAssignmentRegistry._key(poi))
            locations.append(self._location_record(poi))
            if scope == "city":
                city_landmark_count += 1
        surrounding_count = sum(
            1 for item in locations if str(item.get("name") or "").startswith("常去地·")
        )
        if surrounding_count < 3:
            raise AddressGenerationError(
                "常去地点落地不完整：规划 %d 个，成功 %d 个，最低要求 3 个"
                % (len(result.data), surrounding_count)
            )
        planned_city_count = sum((_text(item.get("scope")) or "around") == "city" for item in result.data)
        if planned_city_count and not city_landmark_count:
            raise AddressGenerationError("城市级公共地点未能通过地图 API 落地")
        return locations

    @staticmethod
    def consistency_errors(profile: Dict[str, Any], locations: List[Dict[str, Any]]) -> List[str]:
        errors = []
        expected = {"居住地": _address_text(profile.get("home_address") or {})}
        if _has_daily_workplace(profile) and isinstance(profile.get("workplace"), dict):
            expected["工作地"] = _address_text(profile.get("workplace") or {})
        for address_type, expected_text in expected.items():
            matches = [
                item for item in locations
                if str(item.get("name") or "").startswith(address_type + "·")
            ]
            if not matches:
                errors.append("location 缺少%s核心地址" % address_type)
            elif expected_text and matches[0].get("formatted_address") != expected_text:
                errors.append(
                    "%s与画像不一致，location=%r，persona=%r"
                    % (address_type, matches[0].get("formatted_address"), expected_text)
                )
        return errors
