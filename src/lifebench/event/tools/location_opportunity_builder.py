# -*- coding: utf-8 -*-
"""Build a reusable persona_locations_v2 asset before daily simulation shards start."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

from src.lifebench.event.simulation.geolocation.catalog import (
    flatten_location_data, infer_role,
)
from src.lifebench.event.simulation.geolocation.selector import haversine_km
from src.lifebench.utils.maptool import MapMaintenanceTool


SCHEMA_VERSION = "persona_locations_v2"
GENERATOR_VERSION = "location-opportunity-builder-v1"

_CATEGORY_DEFAULTS = {
    "scenic": (["游览", "散步", "拍照", "半日休闲"], ["citywide_leisure", "exploratory"], "outdoor"),
    "culture": (["展览", "参观", "半日休闲"], ["citywide_leisure", "exploratory", "social_activity"], "indoor"),
    "shopping": (["购物", "逛街", "就餐"], ["citywide_leisure", "social_activity"], "indoor"),
    "entertainment": (["电影", "KTV", "桌游", "娱乐"], ["social_activity", "evening_activity", "citywide_leisure"], "indoor"),
    "fitness": (["运动", "游泳", "球类", "恢复训练"], ["exercise_outing", "exploratory"], "mixed"),
    "meal": (["聚餐", "探店", "日常就餐"], ["social_activity", "evening_activity", "exploratory"], "indoor"),
    "nature": (["公园", "散步", "户外休闲"], ["local_leisure", "citywide_leisure"], "outdoor"),
}

_QUERY_PROMPT = '''
你负责为人物建立“同城活动机会池”的地图查询计划，而不是安排某一天的活动。
请根据人物画像、核心地点和关系，提出覆盖多个城区和距离层的公共POI查询，并识别少量人物合理知道住址的亲密关系。

要求：
1. 公共POI可覆盖 scenic/culture/shopping/entertainment/fitness/meal/nature；结合人物偏好，但不要只搜索画像已经反复出现的地点。
2. 同时覆盖附近、本城区、其他城区和少量同城较远地点；不要生成未来事件或假装人物已经访问。
3. query必须是地图可检索的通用类别、真实品牌或公共机构，不使用虚构店名。
4. 社会地点仅限家人、亲密朋友或画像明确说明人物知道其住址者；普通同事和弱关系不生成住所。
5. 只输出JSON对象，不输出解释。

输出格式：
{{"queries":[{{"keyword":"博物馆","city":"北京市","category":"culture","reason":"周末半日参观"}}],"social_locations":[{{"related_person":"姓名","relationship":"关系","city":"城市","district":"可空","query":"住宅小区","access_policy":"contact_or_invitation_required"}}]}}

人物画像：{persona}
已有核心地点：{anchors}
模拟起始日期：{simulation_start}
'''


def _stable_id(prefix: str, *values: Any) -> str:
    raw = "|".join(str(value or "") for value in values)
    return prefix + "_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _base_fingerprint(document: Dict[str, Any]) -> str:
    return _hash({
        "home_city": document.get("home_city", ""),
        "anchors": document.get("anchors", []),
        "familiar_places": document.get("familiar_places", []),
        "social_locations": document.get("social_locations", []),
    })


def location_asset_is_current(document: Any, persona: Any) -> bool:
    if not isinstance(document, dict) or document.get("schema_version") != SCHEMA_VERSION:
        return False
    manifest = document.get("asset_manifest")
    if not isinstance(manifest, dict):
        return False
    return (
        manifest.get("generator_version") == GENERATOR_VERSION
        and manifest.get("persona_hash") == _hash(persona)
        and manifest.get("base_location_hash") == _base_fingerprint(document)
    )


def _atomic_json(path: str, value: Any) -> None:
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as file:
        json.dump(value, file, ensure_ascii=False, indent=2)
    os.replace(temporary, path)


def _valid_coordinate(value: Any) -> bool:
    try:
        longitude, latitude = (float(item) for item in str(value or "").split(","))
    except (TypeError, ValueError):
        return False
    return -180 <= longitude <= 180 and -90 <= latitude <= 90


def _home_city(document: Dict[str, Any], persona: Any) -> str:
    for row in document.get("anchors", []):
        if str(row.get("anchor_role") or "") == "home" and row.get("city"):
            return str(row["city"])
    for row in document.get("anchors", []):
        if row.get("city"):
            return str(row["city"])
    return ""


def normalize_location_document(location_data: Any, persona: Any = None) -> Dict[str, Any]:
    """Normalize old arrays or a v2 object into a validated, role-separated document."""
    if isinstance(location_data, dict) and location_data.get("schema_version") == SCHEMA_VERSION:
        document = copy.deepcopy(location_data)
        for group in ("anchors", "familiar_places", "city_reference_pois", "social_locations"):
            if not isinstance(document.get(group), list):
                document[group] = []
    else:
        document = {
            "schema_version": SCHEMA_VERSION,
            "home_city": "",
            "anchors": [], "familiar_places": [],
            "city_reference_pois": [], "social_locations": [],
        }
        for row in flatten_location_data(location_data):
            role = infer_role(str(row.get("name") or ""), str(row.get("description") or ""))
            target = "anchors" if role else "familiar_places"
            item = dict(row)
            if role:
                item["location_role"] = "anchor"
                item["anchor_role"] = role
            else:
                item["location_role"] = "familiar"
                item.setdefault("knowledge_state", "visited")
                item.setdefault("return_eligible", True)
                item.setdefault("visit_count", 1)
            document[target].append(item)

    seen = set()
    for group, role in (
        ("anchors", "anchor"), ("familiar_places", "familiar"),
        ("city_reference_pois", "city_reference"), ("social_locations", "social_location"),
    ):
        normalized = []
        for raw in document[group]:
            if not isinstance(raw, dict) or not _valid_coordinate(raw.get("location")):
                continue
            row = dict(raw)
            row["location_role"] = role
            row.setdefault("location_id", _stable_id(
                "loc", row.get("name"), row.get("formatted_address"), row.get("location")
            ))
            identity = str(row["location_id"])
            if identity in seen:
                continue
            seen.add(identity)
            if role == "city_reference":
                row.setdefault("knowledge_state", "known_unvisited")
                row.setdefault("visit_count", 0)
                row.setdefault("return_eligible", False)
                row.setdefault("source", "map_preseed")
            elif role == "anchor":
                row.setdefault("source", "persona_catalog")
            elif role == "familiar":
                row.setdefault("source", "persona_familiar")
            else:
                row.setdefault("source", "persona_social_location")
            normalized.append(row)
        document[group] = normalized
    document["schema_version"] = SCHEMA_VERSION
    document["home_city"] = str(document.get("home_city") or _home_city(document, persona))
    return document


def _anchor(document: Dict[str, Any], role: str) -> Optional[Dict[str, Any]]:
    return next((
        row for row in document.get("anchors", [])
        if str(row.get("anchor_role") or "") == role
    ), None)


def _parse_llm_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    text = str(value or "")
    first, last = text.find("{"), text.rfind("}")
    if first < 0 or last <= first:
        return {}
    try:
        parsed = json.loads(text[first:last + 1])
    except (TypeError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


class LocationOpportunityBuilder:
    def __init__(
        self, maptool: Optional[MapMaintenanceTool] = None,
        llm_callable: Optional[Callable[[str], Any]] = None,
        target_count: int = 60, per_query_limit: int = 6,
    ) -> None:
        self.maptool = maptool
        self.llm_callable = llm_callable
        self.target_count = max(0, int(target_count))
        self.per_query_limit = max(1, min(20, int(per_query_limit)))

    def build(
        self, persona: Any, base_location_data: Any, simulation_start: str,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        document = normalize_location_document(base_location_data, persona)
        failures: List[str] = []
        payload: Dict[str, Any] = {"queries": [], "social_locations": []}
        if self.llm_callable is not None and self.maptool is not None and self.target_count > 0:
            prompt = _QUERY_PROMPT.format(
                persona=json.dumps(persona, ensure_ascii=False, separators=(",", ":")),
                anchors=json.dumps(document["anchors"], ensure_ascii=False, separators=(",", ":")),
                simulation_start=simulation_start,
            )
            payload = _parse_llm_json(self.llm_callable(prompt))
            if not payload:
                failures.append("location_query_plan_invalid")

        existing_keys = {
            (str(row.get("name") or "").strip().lower(), str(row.get("location") or ""))
            for row in flatten_location_data(document)
        }
        home = _anchor(document, "home")
        work = _anchor(document, "work")
        for query_index, query in enumerate(payload.get("queries", []) if isinstance(payload.get("queries"), list) else []):
            if len(document["city_reference_pois"]) >= self.target_count:
                break
            if not isinstance(query, dict):
                continue
            keyword = str(query.get("keyword") or "").strip()
            city = str(query.get("city") or document.get("home_city") or "").strip()
            category = str(query.get("category") or "leisure").strip()
            if category not in _CATEGORY_DEFAULTS or not keyword or self.maptool is None:
                continue
            candidates = self.maptool.search_poi_candidates(
                keyword=keyword, city=city or None, limit=self.per_query_limit,
            )
            if not candidates:
                failures.append("poi_query_empty:%s@%s" % (keyword, city))
            tags, day_types, environment = _CATEGORY_DEFAULTS[category]
            for rank, candidate in enumerate(candidates):
                coordinates = str(candidate.get("location") or "")
                name = str(candidate.get("name") or "").strip()
                key = (name.lower(), coordinates)
                if not name or not _valid_coordinate(coordinates) or key in existing_keys:
                    continue
                existing_keys.add(key)
                geocode = candidate.get("geocode") if isinstance(candidate.get("geocode"), dict) else {}
                row = {
                    "location_id": "cityref:" + str(candidate.get("id") or _stable_id("poi", name, coordinates)),
                    "name": name,
                    "location": coordinates,
                    "formatted_address": str(candidate.get("structured_address") or candidate.get("address") or ""),
                    "city": str(geocode.get("city") or candidate.get("cityname") or city),
                    "district": str(geocode.get("district") or candidate.get("adname") or ""),
                    "location_role": "city_reference", "category": category,
                    "activity_category": "shopping" if category == "shopping" else category,
                    "activity_tags": list(tags), "suitable_day_types": list(day_types),
                    "indoor_outdoor": environment, "typical_dwell_minutes": [60, 240],
                    "social_suitability": ["solo", "friend"],
                    "attraction_weight": round(max(0.2, 1.0 / (1.0 + rank * 0.16)), 4),
                    "knowledge_state": "known_unvisited", "visit_count": 0,
                    "return_eligible": False, "source": "map_preseed", "map_verified": True,
                    "query_reason": str(query.get("reason") or ""),
                }
                if home and _valid_coordinate(home.get("location")):
                    row["distance_from_home_km"] = round(haversine_km(str(home["location"]), coordinates), 2)
                if work and _valid_coordinate(work.get("location")):
                    row["distance_from_work_km"] = round(haversine_km(str(work["location"]), coordinates), 2)
                document["city_reference_pois"].append(row)
                if len(document["city_reference_pois"]) >= self.target_count:
                    break

        self._add_social_locations(document, payload.get("social_locations", []), failures)
        manifest = {
            "schema_version": "location_opportunity_manifest_v1",
            "persona_hash": _hash(persona),
            "base_location_hash": _base_fingerprint(document),
            "generator_version": GENERATOR_VERSION,
            "prompt_hash": _hash(_QUERY_PROMPT),
            "map_provider": "amap" if self.maptool is not None else "none",
            "home_city": document.get("home_city", ""),
            "simulation_start": simulation_start,
            "poi_count_by_category": self._counts(document["city_reference_pois"], "category"),
            "poi_count_by_distance_band": self._distance_counts(document["city_reference_pois"]),
            "partial_failures": failures,
        }
        document["asset_manifest"] = copy.deepcopy(manifest)
        return document, manifest

    def _add_social_locations(
        self, document: Dict[str, Any], specs: Any, failures: List[str],
    ) -> None:
        if not isinstance(specs, list) or self.maptool is None:
            return
        existing_people = {str(row.get("related_person") or "") for row in document["social_locations"]}
        for spec in specs[:6]:
            if not isinstance(spec, dict):
                continue
            person = str(spec.get("related_person") or "").strip()
            city = str(spec.get("city") or document.get("home_city") or "").strip()
            district = str(spec.get("district") or "").strip()
            query = str(spec.get("query") or "住宅小区").strip()
            if not person or person in existing_people:
                continue
            candidates = self.maptool.search_poi_candidates(
                keyword=(district + " " + query).strip(), city=city or None, limit=8,
            )
            if not candidates:
                failures.append("social_location_query_empty:%s" % person)
                continue
            index = int(hashlib.sha256(person.encode("utf-8")).hexdigest()[:8], 16) % len(candidates)
            candidate = candidates[index]
            coordinates = str(candidate.get("location") or "")
            if not _valid_coordinate(coordinates):
                continue
            geocode = candidate.get("geocode") if isinstance(candidate.get("geocode"), dict) else {}
            document["social_locations"].append({
                "location_id": _stable_id("social_home", person, coordinates),
                "name": person + "住所", "location": coordinates,
                "formatted_address": str(candidate.get("structured_address") or candidate.get("address") or ""),
                "city": str(geocode.get("city") or city),
                "district": str(geocode.get("district") or district),
                "location_role": "social_location", "category": "home",
                "related_person": person, "relationship": str(spec.get("relationship") or "亲密关系"),
                "access_policy": "contact_or_invitation_required",
                "knowledge_state": "known_location", "visit_count": 0,
                "return_eligible": False, "source": "plausible_relation_address",
                "map_verified": False,
            })
            existing_people.add(person)

    @staticmethod
    def _counts(rows: Iterable[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for row in rows:
            value = str(row.get(key) or "other")
            counts[value] = counts.get(value, 0) + 1
        return counts

    @staticmethod
    def _distance_counts(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        counts = {"0-3": 0, "3-10": 0, "10-20": 0, "20+": 0}
        for row in rows:
            try:
                value = float(row.get("distance_from_home_km"))
            except (TypeError, ValueError):
                continue
            key = "0-3" if value < 3 else ("3-10" if value < 10 else ("10-20" if value < 20 else "20+"))
            counts[key] += 1
        return counts


def build_and_save(
    *, persona: Any, base_location_data: Any, output_path: str,
    simulation_start: str, maptool: Optional[MapMaintenanceTool],
    llm_callable: Optional[Callable[[str], Any]], target_count: int = 60,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    builder = LocationOpportunityBuilder(
        maptool=maptool, llm_callable=llm_callable, target_count=target_count,
    )
    document, manifest = builder.build(persona, base_location_data, simulation_start)
    _atomic_json(output_path, document)
    manifest_path = os.path.join(os.path.dirname(os.path.abspath(output_path)), "location_opportunity_manifest.json")
    _atomic_json(manifest_path, manifest)
    return document, manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build persona_locations_v2 before simulation")
    parser.add_argument("--persona", required=True)
    parser.add_argument("--base-location", required=True)
    parser.add_argument("--simulation-start", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--target-count", type=int, default=60)
    args = parser.parse_args()
    with open(args.persona, "r", encoding="utf-8") as file:
        persona = json.load(file)
    with open(args.base_location, "r", encoding="utf-8") as file:
        locations = json.load(file)
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    with open(os.path.join(root, "config", "config.json"), "r", encoding="utf-8") as file:
        config = json.load(file)
    maptool = MapMaintenanceTool(str(config.get("map_tool", {}).get("api_key") or ""))
    from src.lifebench.utils.llm_call import llm_call_j
    build_and_save(
        persona=persona, base_location_data=locations, output_path=args.output,
        simulation_start=args.simulation_start, maptool=maptool,
        llm_callable=lambda prompt: llm_call_j(prompt), target_count=args.target_count,
    )


if __name__ == "__main__":
    main()
