# -*- coding: utf-8 -*-
"""候选地点召回：画像目录优先，探索地点由地图 API 提供。"""
import hashlib
import math
from typing import Any, Dict, List, Optional

from .catalog import LocationCatalog, city_matches, infer_category
from .models import LocationCandidate, StopIntent


RADIUS_BY_ACTIVITY = {
    "meal": 5000,
    "shopping": 8000,
    "fitness": 8000,
    "medical": 15000,
    "leisure": 20000,
    "other": 12000,
}

RADIUS_BY_SCOPE = {
    "room": 0,
    "building": 100,
    "compound": 300,
    "neighborhood": 1200,
    "district": 8000,
    "city": 15000,
}

DEFAULT_SEARCH_QUERIES = {
    "meal": ["餐厅", "美食", "面馆", "火锅", "快餐", "肯德基", "麦当劳"],
    "fitness": ["健身房", "游泳馆", "体育中心", "羽毛球馆"],
    "shopping": ["商场", "超市", "购物中心", "便利店"],
    "medical": ["医院", "诊所", "药店"],
    "leisure": ["公园", "博物馆", "电影院", "咖啡馆", "景区"],
    "education": ["学校", "培训中心", "图书馆"],
    "work": ["写字楼", "产业园", "科技园"],
    "home": ["住宅", "小区"],
    "other": ["生活服务", "商业广场", "公共服务中心"],
}

CITY_FALLBACK_KEYWORDS = {
    "work": ["产业园", "工业园", "科技园", "商务园区", "写字楼"],
    "education": ["学校", "培训中心", "图书馆"],
    "medical": ["医院", "门诊部"],
    "meal": ["餐厅", "商业广场"],
    "fitness": ["体育中心", "公园"],
    "shopping": ["商场", "超市"],
    "leisure": ["公园", "博物馆", "文化中心"],
    "other": ["商业广场", "公共服务中心", "城市公园"],
}


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "".join(str(item) for item in value if item)
    return str(value or "")


def _offset_coordinates(coordinates: str, distance_m: int, salt: str) -> str:
    """相对坐标按稳定方向偏移（与 allocator.offset_coordinates 等价，避免循环导入）。"""
    try:
        lon, lat = (float(value) for value in coordinates.split(","))
    except (TypeError, ValueError):
        return coordinates
    digest = hashlib.sha256(salt.encode("utf-8")).hexdigest()[:8]
    bearing = int(digest, 16) / float(0xFFFFFFFF) * 2 * math.pi
    north_m = math.cos(bearing) * distance_m
    east_m = math.sin(bearing) * distance_m
    lat += north_m / 110570.0
    lon += east_m / max(1.0, 111320.0 * math.cos(math.radians(lat)))
    return "%.6f,%.6f" % (lon, lat)


def _deterministic_distance(salt: str, low_m: int, high_m: int) -> int:
    """确定性随机距离：同一 stop_id 复现相同偏移，保证可复现。"""
    digest = hashlib.sha256(("distance|" + str(salt)).encode("utf-8")).hexdigest()[:8]
    fraction = int(digest, 16) / float(0xFFFFFFFF)
    return int(low_m + fraction * (high_m - low_m))


def _haversine_km(first: str, second: str) -> float:
    try:
        lon1, lat1 = (math.radians(float(value)) for value in first.split(","))
        lon2, lat2 = (math.radians(float(value)) for value in second.split(","))
    except (AttributeError, TypeError, ValueError):
        return 0.0
    value = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0088 * 2 * math.asin(min(1.0, math.sqrt(value)))


class CandidateProvider:
    def __init__(self, maptools: Any, catalog: LocationCatalog, limit: int = 12,
                 urban_candidate_share: float = 0.35):
        self.maptools = maptools
        self.catalog = catalog
        self.limit = limit
        self.urban_candidate_share = max(0.15, min(0.70, float(urban_candidate_share)))

    def get(self, intent: StopIntent, previous: Optional[LocationCandidate],
            search_only: bool = False) -> List[LocationCandidate]:
        # LLM 显式选择历史 location_id 时，该选择是确定性的：命中即复用同一
        # 实体与坐标并跳过地图搜索；未命中返回空，由分配器作为硬错误处理。
        if intent.reuse_location_id:
            reused = self.catalog.by_location_id(intent.reuse_location_id)
            return [reused] if reused is not None else []
        candidates = []  # type: List[LocationCandidate]
        exact = self.catalog.exact(
            intent.explicit_name, intent.explicit_location, intent.city,
        )
        anchor = self.catalog.anchor(
            intent.anchor_role or intent.activity_type, intent.city,
        )
        if intent.query_type == "micro":
            # 显式 anchor_role 优先于上一停留点：快递柜、楼下便利店等“发生在
            # 家/锚点内部”的 micro 活动应锚到锚点，而不是被上一站（尤其跨城返程
            # 车站）错误借走。
            parent = anchor or previous or self.catalog.anchor("home")
            if parent is not None:
                # micro 只能依附于同城当前宏地点；跨城医院/车站等不能降级为
                # 出发地点的“内部/附近”。
                if not intent.city or not parent.city or city_matches(intent.city, parent.city):
                    return [self._micro_candidate(intent, parent)]
        if exact:
            candidates.append(exact)
            if intent.selection_policy == "best_match":
                return candidates
        elif anchor and intent.reuse_policy == "must_return":
            candidates.append(anchor)

        # 历史返回地点只参与人物自主选址，并且必须由 LLM 根据事件语义从
        # 动态地点注册表显式列出。程序只验证 ID、城市、类别和来源，不再把
        # 同类别的所有画像/历史地点都默认为可复访候选。
        if intent.selection_policy == "gravity" and intent.epr_applicable:
            for location_id in intent.historical_candidate_ids:
                historical = self.catalog.by_location_id(location_id)
                if historical is None or historical.source != "trajectory_history":
                    continue
                if historical.raw.get("return_eligible") is False:
                    continue
                if not city_matches(intent.city, historical.city):
                    continue
                if (
                    intent.activity_type != "other"
                    and historical.category not in {intent.activity_type, "other"}
                ):
                    continue
                candidates.append(historical)
        if intent.reuse_policy == "must_return" and candidates:
            return self._deduplicate(candidates)

        queries = self._queries(intent)
        raw = []  # type: List[Dict[str, Any]]
        origin = previous or anchor
        crosses_city = bool(
            origin and intent.city and origin.city
            and not city_matches(intent.city, origin.city)
        )
        # 跨城目标不能以出发城市坐标为圆心做 around 搜索，否则会把天津/石家庄
        # 的地点错误落在北京附近。跨城时直接在目标城市做文本 POI 搜索。
        if origin and origin.coordinates and not crosses_city and intent.query_type == "around":
            # 搜索半径只按活动类型确定，不再被 spatial_scope 收缩；spatial_scope
            # 仅用于兜底（虚拟点偏移）时的空间尺度，不参与真实地点搜索半径。
            radius = RADIUS_BY_ACTIVITY.get(intent.activity_type, 8000)
            if intent.preferred_radius_m:
                radius = min(radius, intent.preferred_radius_m)
            # 多个候选词时按维度均分限额，保证每个维度都能贡献候选，
            # 而不是第一个词就占满限额、后续维度（烤肉/日料/面馆…）永远搜不到。
            per_query = max(1, self.limit // max(1, len(queries)))
            for query in queries:
                raw.extend(self.maptools.search_around_candidates(
                    location=origin.coordinates,
                    keywords=query,
                    types=None,
                    city=intent.city or origin.city or None,
                    radius=radius,
                    limit=per_query,
                ))
                if len(raw) >= self.limit:
                    break
        elif intent.query_type in {"search", "city"} or (
            crosses_city and intent.query_type == "around"
        ):
            # search 明确表示全城市关键词检索，不再先用上一地点做周边搜索。
            # 跨城时 around 也应降级为按目标城市文本检索，避免搜索被完全跳过。
            # 多个候选词同样按维度均分限额，保证各维度都有召回。
            per_query = max(1, self.limit // max(1, len(queries)))
            for query in queries:
                raw.extend(self.maptools.search_poi_candidates(
                    keyword=query, city=intent.city or None,
                    limit=per_query, types=None,
                ))
                if len(raw) >= self.limit:
                    break
            # 城市活动不能只依赖文本搜索默认排序。自主选址且有同城起点时，
            # 再进行一次覆盖目标距离带的周边召回，使 3—15km 的候选真实进入池中。
            if (
                origin and origin.coordinates and not crosses_city
                and intent.selection_policy == "gravity"
                and intent.distance_tier in {"urban", "long"}
            ):
                high_km = max(intent.distance_band_km or [0.0, 15.0])
                radius = min(50000, max(5000, int(high_km * 1000)))
                per_query = max(2, self.limit // max(1, len(queries)))
                for query in queries:
                    raw.extend(self.maptools.search_around_candidates(
                        location=origin.coordinates, keywords=query, types=None,
                        city=intent.city or origin.city or None, radius=radius,
                        limit=per_query,
                    ))
        mapped = [self._from_map(item, index, intent) for index, item in enumerate(raw)]
        self._annotate_distances(mapped, origin)
        candidates.extend(self._stratify(mapped, intent))
        if not candidates and intent.city and (intent.explicit_location or intent.explicit_name):
            # 具名地点（如北京南站、天津站、特斯拉）优先精确地理编码拿真实坐标，
            # 而不是先落城市中心虚拟地址，避免两个真实地点被压到同一坐标。
            geocode = getattr(self.maptools, "amap_geocode", None)
            if callable(geocode):
                query = intent.explicit_location or intent.explicit_name
                result = geocode(query, intent.city)
                if isinstance(result, dict) and _text(result.get("location")):
                    candidates.append(self._from_geocode(result, intent, query))
        if not candidates and not search_only:
            local_scope = intent.spatial_scope in {"room", "building", "compound", "neighborhood"}
            if local_scope and not crosses_city:
                # 同城小范围：基准地点附近直接生成虚拟地址，不跨城借用上一地点。
                candidates.extend(self._nearby_virtual_fallback(intent, origin))
            elif intent.city:
                # 目标城市兜底：换相关词重搜，全空则在目标城市随机区生成虚拟地址。
                candidates.extend(self._citywide_fallback(intent))
        return self._deduplicate(candidates)

    def _annotate_distances(
        self, candidates: List[LocationCandidate], origin: Optional[LocationCandidate],
    ) -> None:
        if origin is None or not origin.coordinates:
            return
        for candidate in candidates:
            distance = _haversine_km(origin.coordinates, candidate.coordinates)
            candidate.distance_m = distance * 1000.0
            candidate.raw["distance_from_origin_km"] = round(distance, 3)
            candidate.raw["distance_band"] = (
                "local" if distance < 3.0 else "urban" if distance <= 15.0 else "long"
            )

    def _stratify(
        self, candidates: List[LocationCandidate], intent: StopIntent,
    ) -> List[LocationCandidate]:
        """保留多距离带覆盖；区间是软偏好，召回不足时不丢弃可用地点。"""
        if intent.selection_policy != "gravity" or len(candidates) <= self.limit:
            return candidates
        buckets = {"local": [], "urban": [], "long": [], "unknown": []}
        for candidate in candidates:
            bucket = str(candidate.raw.get("distance_band") or "unknown")
            buckets.setdefault(bucket, []).append(candidate)
        preferred = intent.distance_tier if intent.distance_tier in buckets else "urban"
        order = [preferred] + [key for key in ("local", "urban", "long", "unknown") if key != preferred]
        quota = max(2, int(round(
            self.limit * (self.urban_candidate_share if preferred == "urban" else 1.0 / 3.0)
        )))
        chosen = []
        for key in order:
            chosen.extend(buckets[key][:quota])
        if len(chosen) < self.limit:
            selected_ids = {id(item) for item in chosen}
            chosen.extend(item for item in candidates if id(item) not in selected_ids)
        return chosen[:self.limit]

    @staticmethod
    def _queries(intent: StopIntent) -> List[str]:
        values = list(intent.search_queries or [])
        values.extend((intent.keyword, intent.explicit_name))
        if not any(str(item or "").strip() for item in values):
            if intent.poi_type:
                values.append(intent.poi_type)
            values.extend(DEFAULT_SEARCH_QUERIES.get(intent.activity_type, DEFAULT_SEARCH_QUERIES["other"]))
        seen = set()
        result = []
        for value in values:
            query = str(value or "").strip()
            if query and query not in seen:
                seen.add(query)
                result.append(query)
        return result

    def _citywide_fallback(self, intent: StopIntent) -> List[LocationCandidate]:
        """在目标城市以宽泛功能词寻找真实POI；全空时退到城市内随机区虚拟地址。"""
        queries = list(intent.fallback_queries or [])
        queries.extend(CITY_FALLBACK_KEYWORDS.get(intent.activity_type, CITY_FALLBACK_KEYWORDS["other"]))
        area = str(intent.fallback_area or "").strip()
        results = []
        seen_queries = set()
        for raw_query in queries:
            query = " ".join(part for part in (area, str(raw_query or "").strip()) if part)
            if not query or query in seen_queries:
                continue
            seen_queries.add(query)
            # 宽泛兜底时不继承可能错误或过窄的 poi_type。
            rows = self.maptools.search_poi_candidates(
                keyword=query, city=intent.city, limit=self.limit, types=None,
            )
            results.extend(self._from_map(item, len(results) + index, intent)
                           for index, item in enumerate(rows))
            if len(results) >= self.limit:
                return self._deduplicate(results)
        if results:
            return self._deduplicate(results)

        geocode = getattr(self.maptools, "amap_geocode", None)
        if not callable(geocode):
            return []
        area_query = "".join(part for part in (intent.city, area) if part) or intent.city
        point = geocode(area_query, intent.city)
        if not isinstance(point, dict) or not _text(point.get("location")):
            return []
        center = _text(point.get("location"))
        # 目标城市随机区：在城市中心附近按确定性随机方向/距离偏移，
        # 模拟落在某个合理区内的位置，避免所有兜底地点堆在城市中心同一点。
        distance_m = _deterministic_distance(intent.stop_id, 3000, 8000)
        coordinates = _offset_coordinates(center, distance_m, intent.stop_id)
        digest = hashlib.sha1(
            (intent.city + "|" + area + "|" + intent.activity_type + "|" + coordinates).encode("utf-8")
        ).hexdigest()[:12]
        label = intent.explicit_name or "%s%s临时活动地点" % (area or intent.city, intent.activity_type)
        return [LocationCandidate(
            location_id="area_" + digest,
            name=label,
            address=(_text(point.get("formatted_address")) or area_query) + "附近",
            coordinates=coordinates,
            province=_text(point.get("province")),
            city=intent.city or _text(point.get("city")) or _text(point.get("province")),
            district=_text(point.get("district")) or area,
            adcode=_text(point.get("adcode")), category=intent.activity_type,
            role="citywide_fallback", source="amap_area_anchor",
            raw={"fallback_area": area, "search_queries": list(seen_queries), "random_offset_m": distance_m},
            confidence=0.45, map_verified=False,
        )]

    def _nearby_virtual_fallback(self, intent: StopIntent,
                                 base: Optional[LocationCandidate]) -> List[LocationCandidate]:
        """同城小范围候选为空时，在基准地点附近生成确定性虚拟地址。"""
        if base is None or not base.coordinates:
            return []
        scope = str(intent.spatial_scope or "neighborhood")
        radius = RADIUS_BY_SCOPE.get(scope, 1500)
        radius = max(radius, 80)
        distance_m = max(50, min(intent.preferred_radius_m or radius, 2000))
        coordinates = _offset_coordinates(base.coordinates, distance_m, intent.stop_id)
        label = intent.explicit_name or intent.keyword or intent.event_ref or "附近活动地点"
        digest = hashlib.sha1(
            (base.location_id + "|" + label + "|" + coordinates).encode("utf-8")
        ).hexdigest()[:12]
        return [LocationCandidate(
            location_id="virtual_" + digest,
            name=label,
            address=(base.address + "附近").strip(),
            coordinates=coordinates,
            province=base.province,
            city=base.city,
            district=base.district,
            adcode=base.adcode,
            category=intent.activity_type,
            role="nearby_virtual",
            source="llm_plausible",
            anchor_id=base.location_id,
            distance_m=float(distance_m),
            raw={"spatial_scope": scope, "generation_reason": "同城小范围候选为空，生成虚拟地址"},
            confidence=0.35,
            map_verified=False,
        )]

    @staticmethod
    def _from_geocode(item: Dict[str, Any], intent: StopIntent,
                      query: str) -> LocationCandidate:
        coordinates = _text(item.get("location"))
        city = _text(item.get("city")) or _text(item.get("province")) or intent.city
        digest = hashlib.sha1((query + "|" + coordinates).encode("utf-8")).hexdigest()[:12]
        return LocationCandidate(
            location_id="geocode_" + digest,
            name=intent.explicit_name or query,
            address=_text(item.get("formatted_address")) or query,
            coordinates=coordinates,
            province=_text(item.get("province")), city=city,
            district=_text(item.get("district")), adcode=_text(item.get("adcode")),
            category=intent.activity_type, source="amap_geocode",
            raw=dict(item), confidence=0.85, map_verified=True,
        )

    @staticmethod
    def _micro_candidate(intent: StopIntent, parent: LocationCandidate) -> LocationCandidate:
        label = intent.explicit_name or intent.keyword or intent.event_ref or "内部活动"
        digest = hashlib.sha1((parent.location_id + "|" + label).encode("utf-8")).hexdigest()[:12]
        return LocationCandidate(
            location_id="micro_" + digest,
            name=label,
            address=(parent.address + "（内部/附近）").strip(),
            coordinates=parent.coordinates,
            province=parent.province,
            city=parent.city,
            district=parent.district,
            adcode=parent.adcode,
            category=intent.activity_type,
            role="micro",
            source="llm_plausible",
            anchor_id=parent.location_id,
            distance_m=0.0,
            map_rank=0,
            raw={"spatial_scope": intent.spatial_scope, "parent_location_id": parent.location_id},
            confidence=0.65,
            map_verified=False,
        )

    @staticmethod
    def _from_map(item: Dict[str, Any], rank: int, intent: StopIntent) -> LocationCandidate:
        geocode = item.get("geocode") if isinstance(item.get("geocode"), dict) else {}
        coordinates = _text(item.get("location"))
        name = _text(item.get("name"))
        digest = hashlib.sha1((name + "|" + coordinates).encode("utf-8")).hexdigest()[:12]
        type_text = _text(item.get("type")) + intent.poi_type + intent.keyword
        # 候选点是按意图关键词定向搜出的，权威类别应跟随意图 activity_type，
        # 避免 infer_category 被高德 type 里的干扰词（如"住宅"）带偏（产业园→home）。
        category = (
            intent.activity_type
            if intent.activity_type not in (None, "", "other")
            else infer_category(type_text, "other")
        )
        return LocationCandidate(
            location_id=_text(item.get("id")) or "map_" + digest,
            name=name,
            address=_text(item.get("structured_address") or item.get("address")),
            coordinates=coordinates,
            province=_text(geocode.get("province") or item.get("pname")),
            city=_text(geocode.get("city") or item.get("cityname") or intent.city),
            district=_text(geocode.get("district") or item.get("adname")),
            adcode=_text(item.get("adcode")),
            category=category,
            source="amap_around" if item.get("distance_m") is not None else "amap_text",
            distance_m=float(item.get("distance_m") or 0) or None,
            map_rank=rank,
            raw=dict(item),
            confidence=0.95,
            map_verified=True,
        )

    @staticmethod
    def _deduplicate(items: List[LocationCandidate]) -> List[LocationCandidate]:
        seen = set()
        result = []
        for item in items:
            key = item.coordinates or item.location_id
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result
