# -*- coding: utf-8 -*-
"""轨迹生成器：真实 POI 定位与事件轨迹调整。

从 Mind.map 与 Mind._adjust_event_trajectory 迁出。
"""
import hashlib
import json
import os
import re
from dataclasses import replace

from src.lifebench.event.templates.template_simulation import (
    template_poi_real_location_assign,
    template_poi_real_location_assign_legacy,
    template_event_traffic_adjust,
    template_final_location_reconcile,
    template_trajectory_reorganize,
)
from src.lifebench.event.simulation.activity import (
    plan_activity_intents,
)
from src.lifebench.event.simulation.geolocation import (
    TrajectoryAllocator,
    TrajectoryAssignment,
    build_personal_epr_profile,
    build_location_records,
    parse_stop_intents,
    reconcile_final_itinerary,
    remember_location_records,
    render_assignment_summary,
)
from src.lifebench.event.simulation.geolocation.allocator import offset_coordinates
from src.lifebench.event.simulation.geolocation.catalog import city_matches
from src.lifebench.event.simulation.geolocation.models import (
    ResolvedStop, TravelLeg,
)
from src.lifebench.event.simulation.geolocation.selector import haversine_km
from src.lifebench.event.simulation.geolocation.validator import (
    validate_assignment, validate_location_records,
)


def _extract_json_object(response):
    if isinstance(response, dict):
        return response
    value = str(response or "")
    first_bracket = value.find('{')
    last_bracket = value.rfind('}')
    if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
        value = value[first_bracket:last_bracket + 1]
    return json.loads(value)


def _trajectory_config(mind):
    config = getattr(mind, "config", {})
    config = config if isinstance(config, dict) else {}
    value = config.get("trajectory_assignment", {})
    return value if isinstance(value, dict) else {}


def _legacy_route(mind, data):
    if "instruction" not in data:
        return ""
    result, _ = mind.maptools.process_instruction_route(data)
    return mind.maptools.extract_poi_route_simplified(result)


def _write_trajectory_trace(mind, assignment):
    try:
        os.makedirs(mind.sim_dir, exist_ok=True)
        shard_key = getattr(mind, "interval_start", None) or "unknown"
        path = os.path.join(
            mind.sim_dir,
            "trajectory_trace_%s_%s.jsonl" % (mind.instance_id, shard_key),
        )
        with open(path, "a", encoding="utf-8") as file:
            file.write(json.dumps(assignment.to_dict(), ensure_ascii=False) + "\n")
    except Exception as error:
        print("轨迹追踪写入失败: %s" % error)


def _address_catalog_with_history(mind):
    base = list(getattr(mind.maptools, "persona_address_data", None) or [])
    history = list(getattr(mind, "trajectory_location_history", None) or [])
    return base + history


def _compact_location_registry(mind, limit=80):
    """给 LLM 的动态地点视图：足够做实体选择，但不暴露冗余原始地图数据。"""
    rows = []
    history = getattr(mind, "trajectory_location_history", None) or []
    valid = [item for item in history if isinstance(item, dict)]
    valid.sort(key=lambda item: (
        -int(item.get("visit_count", 0) or 0),
        str(item.get("name") or ""),
    ))
    for item in valid[:max(1, int(limit))]:
        location_id = str(item.get("location_id") or item.get("id") or "").strip()
        if not location_id:
            continue
        rows.append({
            "location_id": location_id,
            "name": str(item.get("name") or ""),
            "aliases": list(item.get("aliases") or [])[-5:],
            "address": str(item.get("formatted_address") or item.get("address") or ""),
            "city": str(item.get("city") or ""),
            "category": str(item.get("category") or "other"),
            "visit_count": int(item.get("visit_count", 0) or 0),
            "first_seen_date": str(item.get("first_seen_date") or ""),
            "last_seen_date": str(item.get("last_seen_date") or ""),
            "recent_visit_dates": list(item.get("recent_visit_dates") or [])[-5:],
            "map_verified": bool(item.get("map_verified", False)),
        })
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def _remember_final_locations(mind, records):
    """仅在最终行程通过门禁后写回，避免失败/未采用地点污染注册表。"""
    history = list(getattr(mind, "trajectory_location_history", None) or [])
    mind.trajectory_location_history = remember_location_records(
        history, records, limit=200,
        date=str(getattr(mind, "current_date", "") or ""),
    )


def _identity_from_stop(stop):
    return {
        "location_id": stop.location_id, "name": stop.name, "address": stop.address,
        "coordinates": stop.coordinates, "city": stop.city, "category": stop.category,
        "source": stop.source, "confidence": stop.confidence, "map_verified": stop.map_verified,
    }


def _identity_from_candidate(candidate):
    return {
        "location_id": candidate.location_id, "name": candidate.name, "address": candidate.address,
        "coordinates": candidate.coordinates, "city": candidate.city, "category": candidate.category,
        "source": candidate.source, "confidence": candidate.confidence, "map_verified": candidate.map_verified,
    }


def _make_stop(intent, identity):
    """用当前意图的 stop 身份 + 被引用地点的身份构造最终停留点。"""
    return ResolvedStop(
        stop_id=intent.stop_id, event_ref=intent.event_ref,
        activity_type=intent.activity_type,
        location_id=identity["location_id"], name=identity["name"],
        address=identity["address"], coordinates=identity["coordinates"],
        city=identity["city"], category=identity["category"],
        source=identity["source"], degraded=False,
        original_order=intent.order, parent_event_id=intent.parent_event_id,
        required=intent.required, provenance=intent.provenance,
        flexibility=intent.flexibility, spatial_scope=intent.spatial_scope,
        confidence=identity["confidence"], map_verified=identity["map_verified"],
    )


def _build_travel_leg(maptools, allocator, origin, dest, mode, leg_id,
                      origin_intent, dest_intent):
    """按 organizer 指定的 mode 计算真实通行时长，构造 TravelLeg。"""
    same_location = origin.coordinates == dest.coordinates
    if same_location or mode == "none":
        return TravelLeg(
            leg_id=leg_id, origin_stop_id=origin.stop_id, destination_stop_id=dest.stop_id,
            origin_name=origin.name, destination_name=dest.name,
            mode="none", duration_minutes=0, distance_km=0.0,
            departure_time="", arrival_time="", source="same_location",
            feasible=True, confidence=1.0, leg_type="transfer",
            narrative_route="", map_verified=True,
        )
    distance = haversine_km(origin.coordinates, dest.coordinates)
    seconds = maptools.get_duration_between_pois(
        origin.as_poi(), dest.as_poi(), mode,
        origin.city or None, dest.city or None,
    )
    if seconds is not None:
        duration = max(1, int(round(seconds / 60.0)))
        source, confidence, map_verified = "amap", 1.0, True
    else:
        # 查不到才兜底：跨城 transit 用里程估算，其余用速度表启发式。
        intercity_transit = (
            mode == "transit"
            and bool(origin.city and dest.city and not city_matches(origin.city, dest.city))
        )
        if intercity_transit:
            duration = max(15, int(round(distance / 200.0 * 60)))
            source, confidence, map_verified = "heuristic", 0.7, False
        else:
            speeds = {"walking": 4.5, "bicycling": 12.0, "transit": 20.0, "driving": 28.0, "running": 8.0}
            overhead = {"walking": 0, "bicycling": 2, "transit": 8, "driving": 5, "running": 0}
            duration = max(1, int(round(distance / speeds.get(mode, 20.0) * 60 + overhead.get(mode, 5))))
            source, confidence, map_verified = "heuristic", 0.7, False
    departure, arrival = allocator._leg_times(origin_intent, dest_intent, duration, "transfer")
    return TravelLeg(
        leg_id=leg_id, origin_stop_id=origin.stop_id, destination_stop_id=dest.stop_id,
        origin_name=origin.name, destination_name=dest.name,
        mode=mode, duration_minutes=duration, distance_km=round(distance, 2),
        departure_time=departure, arrival_time=arrival, source=source,
        feasible=True, confidence=confidence, leg_type="transfer",
        narrative_route="", map_verified=map_verified,
    )


def _resolve_stop(intent, spec, identity_by_location_id, round1_by_stop_id, allocator):
    """把 organizer 的单个 stop spec 解析成 ResolvedStop（requery 除外）。"""
    resolution = str(spec.get("resolution") or "resolved")
    location = spec.get("location") if isinstance(spec.get("location"), dict) else {}

    if resolution == "plausible":
        name = str(spec.get("name") or intent.explicit_name or intent.event_ref or "附近活动地点").strip()
        anchor_stop_id = str(spec.get("anchor_stop_id") or "")
        anchor_identity = None
        anchor_stop = round1_by_stop_id.get(anchor_stop_id)
        if anchor_stop is not None:
            anchor_identity = _identity_from_stop(anchor_stop)
        else:
            anchor_identity = identity_by_location_id.get(anchor_stop_id)
        if anchor_identity is None:
            home = allocator.catalog.anchor("home")
            anchor_identity = _identity_from_candidate(home) if home is not None else None
        if anchor_identity is None:
            return None
        anchor_coordinates = str(anchor_identity.get("coordinates") or "")
        if len(anchor_coordinates.split(",")) != 2:
            return round1_by_stop_id.get(intent.stop_id)
        coordinates = offset_coordinates(anchor_coordinates, 80, intent.stop_id)
        address = (anchor_identity["address"] + "附近").strip() or (
            (anchor_identity["city"] + " " + name).strip() if anchor_identity["city"] else name
        )
        identity = {
            "location_id": "plausible_" + hashlib.sha1(
                (anchor_identity["location_id"] + "|" + name).encode("utf-8")
            ).hexdigest()[:12],
            "name": name, "address": address, "coordinates": coordinates,
            "city": anchor_identity["city"], "category": intent.activity_type,
            "source": "llm_plausible", "confidence": 0.5, "map_verified": False,
        }
        return _make_stop(intent, identity)

    if location.get("location_id"):
        identity = identity_by_location_id.get(str(location["location_id"]).strip())
        if identity is None:
            fallback = round1_by_stop_id.get(intent.stop_id)
            return fallback if fallback is not None else None
        return _make_stop(intent, identity)

    if location.get("coordinates"):
        coordinates = str(location["coordinates"]).strip()
        if len(coordinates.split(",")) == 2:
            name = str(location.get("name") or intent.explicit_name or intent.event_ref or "").strip()
            city = str(location.get("city") or intent.city or "").strip()
            address = str(location.get("address") or "").strip()
            if not address:
                address = ("%s %s" % (city, name)).strip() if city and name else name
            identity = {
                "location_id": "llmdirect_" + hashlib.sha1(
                    (name + "|" + coordinates).encode("utf-8")
                ).hexdigest()[:12],
                "name": name, "address": address, "coordinates": coordinates,
                "city": city, "category": str(location.get("category") or intent.activity_type).strip(),
                "source": "llm_direct", "confidence": 0.5, "map_verified": False,
            }
            return _make_stop(intent, identity)

    fallback = round1_by_stop_id.get(intent.stop_id)
    return fallback


def _geocode_point(maptools, query, city):
    """按「城市+关键词」地理编码取中心坐标，失败返回 None。"""
    geocode = getattr(maptools, "amap_geocode", None)
    if not callable(geocode):
        return None
    try:
        result = geocode(query, city)
    except Exception:
        return None
    if isinstance(result, dict):
        location = str(result.get("location") or "").strip()
        if len(location.split(",")) == 2:
            return location
    return None


def _anchor_district(anchor, allocator):
    """取相邻停留点所在区名：优先目录，其次地址字符串正则。"""
    if anchor is None:
        return ""
    entry = allocator.catalog.by_location_id(anchor.location_id)
    district = str(getattr(entry, "district", "") or "").strip() if entry is not None else ""
    if district:
        return district
    match = re.search(r"([一-龥]{1,8}(?:区|县|市))", str(anchor.address or ""))
    return match.group(1) if match else ""


def _deterministic_distance(salt, low_m, high_m):
    """确定性随机距离：同一 stop_id 复现相同偏移，保证可复现。"""
    digest = hashlib.sha256(("distance|" + str(salt)).encode("utf-8")).hexdigest()[:8]
    fraction = int(digest, 16) / float(0xFFFFFFFF)
    return int(low_m + fraction * (high_m - low_m))


TIER_LABELS = {"nearby": "附近", "district": "同区", "city": "同城"}


def _fallback_requery_stop(intent, spec, prev_stop, next_stop, allocator, issues):
    """两轮查询均失败后进入兜底：策略由组织 LLM 选择（fallback_tier），名称由 LLM 给出。"""
    name = str(spec.get("name") or intent.explicit_name or intent.event_ref or "附近活动地点").strip()
    city = str(spec.get("city") or intent.city or "").strip()
    tier = str(spec.get("fallback_tier") or "city").strip().lower()
    if tier not in TIER_LABELS:
        tier = "city"
    maptools = allocator.maptools

    adjacent = [
        stop for stop in (prev_stop, next_stop)
        if stop is not None and getattr(stop, "coordinates", "")
    ]

    def same_city(stop):
        return bool(city and stop.city and city_matches(city, stop.city))

    anchor = next((stop for stop in adjacent if same_city(stop)), None)
    if anchor is None and adjacent:
        anchor = adjacent[0]

    coordinates = None
    address = ""
    used = "city"

    if tier == "nearby" and anchor is not None:
        # 附近：基于上/下一站坐标小偏移。
        coordinates = offset_coordinates(anchor.coordinates, 300, intent.stop_id)
        address = (anchor.address + "附近").strip() or (
            (city + " " + name).strip() if city else name
        )
        used = "nearby"
    elif tier == "district" and anchor is not None:
        # 同区：geocode 城市+区中心，再 2~9km 确定性随机偏移。
        district = _anchor_district(anchor, allocator)
        center = _geocode_point(maptools, city + district, city) if district else None
        if center is not None:
            distance = _deterministic_distance(intent.stop_id, 2000, 9000)
            coordinates = offset_coordinates(center, distance, intent.stop_id)
            address = (city + district + name).strip()
            used = "district"

    if coordinates is None:
        # 同城（含 nearby/district 缺锚点或区中心时的兜底）：城市中心 + 偏移。
        center = _geocode_point(maptools, city, city)
        if center is None and prev_stop is not None:
            center = getattr(prev_stop, "coordinates", "")
        if not center or len(str(center).split(",")) != 2:
            issues.append("stop %s 兜底失败：无法获取城市中心坐标" % intent.stop_id)
            return None
        coordinates = offset_coordinates(center, 4000, intent.stop_id)
        address = (city + name).strip() if city else name
        used = "city"

    location_id = "requery_" + hashlib.sha1(
        (city + "|" + name + "|" + coordinates).encode("utf-8")
    ).hexdigest()[:12]
    identity = {
        "location_id": location_id, "name": name, "address": address,
        "coordinates": coordinates, "city": city, "category": intent.activity_type,
        "source": "llm_plausible", "confidence": 0.4, "map_verified": False,
    }
    issues.append("stop %s 两轮查询均失败，进入%s兜底" % (intent.stop_id, TIER_LABELS[used]))
    return _make_stop(intent, identity)


def _requery_resolve(intent, spec, prev_stop, next_stop, allocator, issues):
    """requery stop：两轮纯查询（new_queries → fallback_queries），仍失败才进兜底。"""
    new_queries = [str(q).strip() for q in (spec.get("new_queries") or []) if str(q).strip()]
    fallback_queries = [str(q).strip() for q in (spec.get("fallback_queries") or []) if str(q).strip()]
    if not new_queries:
        new_queries = [q for q in (intent.search_queries or []) if str(q).strip()] or [
            q for q in (intent.explicit_name, intent.poi_type) if str(q).strip()
        ]
    city = str(spec.get("city") or intent.city or "").strip()

    def search(queries):
        if not queries:
            return []
        requery_intent = replace(
            intent,
            query_type="search", search_queries=list(queries),
            explicit_name="", explicit_location="", keyword="", poi_type="",
            city=city, selection_policy="best_match", reuse_policy="may_explore",
            reuse_location_id="", historical_candidate_ids=[], epr_applicable=False,
        )
        try:
            return allocator.provider.get(requery_intent, None, search_only=True)
        except Exception:
            return []

    for queries in (new_queries, fallback_queries):
        pool = search(queries)
        if pool:
            return _make_stop(intent, _identity_from_candidate(pool[0]))

    return _fallback_requery_stop(intent, spec, prev_stop, next_stop, allocator, issues)


def _unify_same_entity_stops(resolved_stops, intents, requery_stop_ids):
    """同一未具名地点的多次随机选择必须落到同一个 POI。

    随机选择对每个 stop 独立洗牌，导致「上午客户厂区」与「午后返回客户厂区」这种
    语义同一、检索词也相同的两个 stop 取到不同工厂。这里在 organizer 之后做确定性
    统一：签名（城市+活动+搜索方式+检索词）相同的 random stop 强制复用首个成员的
    location_id，除非该 stop 已被 organizer 标记为 requery（那是明确的重新查询意图）。
    """
    intent_by_id = {intent.stop_id: intent for intent in intents}
    canonical = {}  # signature -> ResolvedStop（组内首个成员）
    for stop in resolved_stops:
        intent = intent_by_id.get(stop.stop_id)
        if intent is None or intent.selection_policy != "random":
            continue
        if intent.query_type not in {"search", "around"}:
            continue
        if stop.stop_id in requery_stop_ids:
            continue
        signature = (
            intent.city, intent.activity_type, intent.query_type,
            tuple(intent.search_queries or []),
        )
        first = canonical.get(signature)
        if first is None:
            canonical[signature] = stop
        elif stop.location_id != first.location_id:
            stop.location_id = first.location_id
            stop.name = first.name
            stop.address = first.address
            stop.coordinates = first.coordinates
            stop.city = first.city
            stop.category = first.category
    return resolved_stops


def _reorganize_trajectory(mind, allocator, intents, assignment, pt, plan, config):
    """用一轮 LLM 取代 allocate 的预算分析/最终评估与 replan 决策。"""
    prompt = template_trajectory_reorganize.format(
        assignment=render_assignment_summary(assignment),
        location_registry=_compact_location_registry(mind),
        persona=mind.persona,
        plan=plan or {},
        event=pt or "",
    )
    diagnostics = {"enabled": True, "applied": False, "requery_stop_count": 0, "issues": []}
    try:
        response = _extract_json_object(mind.llm_call_j(prompt, 0))
    except Exception as error:
        diagnostics["issues"].append("轨迹重组失败，沿用初始分配：%s" % error)
        return assignment, diagnostics

    stops_spec = response.get("stops", []) if isinstance(response, dict) else []
    stops_spec = [item for item in stops_spec if isinstance(item, dict)]
    leg_modes = [str(m).strip() for m in (response.get("leg_modes", []) or [])]
    spec_by_stop_id = {str(item.get("stop_id")): item for item in stops_spec if item.get("stop_id")}

    intent_by_id = {item.stop_id: item for item in intents}
    round1_by_stop_id = {stop.stop_id: stop for stop in assignment.stops}

    identity_by_location_id = {}
    for stop in assignment.stops:
        identity_by_location_id.setdefault(stop.location_id, _identity_from_stop(stop))
    for candidate in allocator.catalog.items:
        identity_by_location_id.setdefault(candidate.location_id, _identity_from_candidate(candidate))

    # organizer 给出的顺序优先；遗漏的 intent 按原 order 补齐。
    provided_ids = []
    provided_seen = set()
    for spec in stops_spec:
        sid = str(spec.get("stop_id"))
        if sid and sid not in provided_seen:
            provided_ids.append(sid)
            provided_seen.add(sid)
    final_seq = list(provided_ids)
    for intent in sorted(intents, key=lambda item: item.order):
        if intent.stop_id not in provided_seen:
            final_seq.append(intent.stop_id)

    resolved_stops = []
    requery_stop_ids = set()
    prev_stop = None
    for index, stop_id in enumerate(final_seq):
        intent = intent_by_id.get(stop_id)
        if intent is None:
            continue
        spec = spec_by_stop_id.get(stop_id) or {}
        next_stop = (
            round1_by_stop_id.get(final_seq[index + 1])
            if index + 1 < len(final_seq) else None
        )
        if str(spec.get("resolution") or "resolved") == "requery":
            stop = _requery_resolve(
                intent, spec, prev_stop, next_stop, allocator, diagnostics["issues"],
            )
            requery_stop_ids.add(stop_id)
            diagnostics["requery_stop_count"] += 1
        else:
            stop = _resolve_stop(
                intent, spec, identity_by_location_id, round1_by_stop_id, allocator,
            )
        if stop is None:
            stop = round1_by_stop_id.get(stop_id)
        if stop is None:
            diagnostics["issues"].append("stop %s 无法解析，已跳过" % stop_id)
            continue
        resolved_stops.append(stop)
        prev_stop = stop

    resolved_stops = _unify_same_entity_stops(resolved_stops, intents, requery_stop_ids)

    legs = []
    for index in range(len(resolved_stops) - 1):
        origin = resolved_stops[index]
        dest = resolved_stops[index + 1]
        mode = leg_modes[index] if index < len(leg_modes) else ""
        mode = mode or "transit"
        legs.append(_build_travel_leg(
            mind.maptools, allocator, origin, dest, mode,
            "leg_%03d" % index, intent_by_id[origin.stop_id], intent_by_id[dest.stop_id],
        ))

    final_assignment = TrajectoryAssignment(
        date=assignment.date, stops=resolved_stops, legs=legs,
        feasible=True, violations=[], diagnostics={
            "allocator": assignment.diagnostics.get("allocator", ""),
            "budget_aware": assignment.diagnostics.get("budget_aware", False),
            "stop_count": len(resolved_stops),
            "leg_count": len(legs),
            "requery_stop_count": diagnostics["requery_stop_count"],
            "reorganized_stop_count": len(stops_spec),
        },
    )
    diagnostics["applied"] = True
    return final_assignment, diagnostics


def generate_poi_route(mind, pt, plan=None):
    """
    获取真实 POI 数据与通行信息。

    参数:
        mind: Mind 实例（读取 persona 与 maptools）
        pt: 事件数据

    返回:
        str: 精简后的 POI/路线指令；出错时返回空字符串
    """
    config = _trajectory_config(mind)
    intent_template = (
        template_poi_real_location_assign
        if config.get("enabled", True)
        else template_poi_real_location_assign_legacy
    )
    prompt = intent_template.format(
        persona=mind.persona,
        data=pt,
        plan=plan or {},
        persona_address_data=mind.maptools.persona_address_data,
        location_registry=_compact_location_registry(mind),
    )
    res = mind.llm_call_j(prompt, 0)
    print("poi分析-----------------------------------------------------------------------")
    mind.last_trajectory_assignment = None
    try:
        data = _extract_json_object(res)
        if not config.get("enabled", True):
            return _legacy_route(mind, data)
        intents = parse_stop_intents(data)
        activity_plan = plan_activity_intents(intents)
        intents = activity_plan.intents
        mind.last_activity_plan = activity_plan.to_dict()
        day_variation = (
            (getattr(mind, "last_subjective_context", None) or {}).get(
                "day_variation_context", {}
            ) or {}
        )
        epr_profile = build_personal_epr_profile(
            getattr(mind, "behavior_history", None) or [],
            getattr(mind, "trajectory_location_history", None) or [],
        )
        allocator = TrajectoryAllocator(
            maptools=mind.maptools,
            persona_addresses=_address_catalog_with_history(mind),
            persona=mind.persona,
            seed="%s|%s|%s" % (
                config.get("seed", 0), getattr(mind, "instance_id", 0),
                getattr(mind, "current_date", ""),
            ),
            candidate_limit=int(config.get("candidate_limit", 12)),
            route_top_k=int(config.get("route_top_k", 4)),
            novelty_level=str(day_variation.get("novelty_level", "medium")),
            mobility_level=str(day_variation.get("mobility_level", "medium")),
            epr_profile=epr_profile,
        )
        # 一轮 LLM 取代 allocate 的预算分析/最终评估与 replan 决策：allocate
        # 只负责召回+选择+真实通行时长，语义去重/修正/重排交给组织 LLM。
        assignment = allocator.allocate(
            intents, str(getattr(mind, "current_date", "")),
            budget_aware=False,
        )
        assignment, reorganize_diagnostics = _reorganize_trajectory(
            mind, allocator, intents, assignment, pt, plan or {}, config,
        )
        assignment.diagnostics["activity_plan_dropped"] = activity_plan.dropped
        assignment.diagnostics["trajectory_reorganize"] = reorganize_diagnostics
        structure_issues = validate_assignment(
            assignment, accuracy_validation=config.get("accuracy_validation", True),
        )
        if structure_issues:
            raise ValueError("轨迹结构校验失败: " + "; ".join(structure_issues))
        mind.last_trajectory_assignment = assignment
        _write_trajectory_trace(mind, assignment)
        return render_assignment_summary(assignment)
    except Exception as e:
        print(f"map函数出错: {str(e)}")
        if config.get("enabled", True) and config.get("strict_validation", True):
            # 交给 daily_event_gen1 返回失败，再由 DailySimulationEngine 的既有机制
            # 重试整日。禁止把旧版字符串当作新版地理成功数据。
            raise RuntimeError("新版地理位置分配失败: %s" % e) from e
        try:
            data = _extract_json_object(res)
            return _legacy_route(mind, data)
        except Exception as fallback_error:
            print("旧版轨迹回退也失败: %s" % fallback_error)
            return ""


def adjust_event_trajectory(mind, poi_data, event, daily_event_reference="", history=""):
    """
    调整事件轨迹。

    参数:
        mind: Mind 实例（读取 persona_address_data/cognition 及日志/LLM 工具）
        poi_data: POI 数据
        event: 事件数据
        daily_event_reference: 当日事件参考
        history: 历史

    返回:
        str: 调整后的事件内容
    """
    # 简化 persona_address_data，只保留 name、formatted_address 和 description 字段
    simplified_address_data = []
    if mind.persona_address_data and isinstance(mind.persona_address_data, list):
        for address in mind.persona_address_data:
            simplified_address = {
                "name": address.get("name", ""),
                "formatted_address": address.get("formatted_address", ""),
                "description": address.get("description", "")
            }
            simplified_address_data.append(simplified_address)

    print("[DEBUG _adjust_event_trajectory] daily_event_reference type=" + str(type(daily_event_reference)))
    print("[DEBUG _adjust_event_trajectory] daily_event_reference content=" + str(daily_event_reference))
    if isinstance(daily_event_reference, dict):
        print("[DEBUG _adjust_event_trajectory] daily_event_reference keys=" + str(list(daily_event_reference.keys())))

    config = _trajectory_config(mind)
    assignment = getattr(mind, "last_trajectory_assignment", None)
    if config.get("enabled", True) and config.get("strict_validation", True):
        if assignment is None or not getattr(assignment, "stops", None):
            raise RuntimeError("最终事件调整前没有可用的新版轨迹分配")

    prompt = template_event_traffic_adjust.format(
        poi=poi_data,
        event=event,
        daily_event_reference=daily_event_reference,
        history=history,
        persona=mind.cognition,
        persona_address_data=simplified_address_data,
        known_location_registry=_compact_location_registry(mind),
    )
    adjusted_events = mind.llm_call_s(prompt, 0)
    base_location_records = build_location_records(assignment)
    mind.final_location_records = base_location_records
    mind.last_location_reconciliation = {
        "estimated_stop_ids": [], "estimated_stop_count": 0, "issues": [],
    }
    if assignment is not None and hasattr(mind, "llm_call_j"):
        compact_records = {
            "coordinate_system": base_location_records.get("coordinate_system", "GCJ-02"),
            "stops": [
                {
                    key: stop.get(key) for key in (
                        "stop_id", "name", "address", "longitude", "latitude",
                        "activity_type", "source", "map_verified", "city",
                    )
                }
                for stop in base_location_records.get("stops", [])
                if isinstance(stop, dict)
            ],
        }
        reconcile_prompt = template_final_location_reconcile.format(
            adjusted_events=adjusted_events,
            location_records=json.dumps(
                compact_records, ensure_ascii=False, separators=(",", ":"),
            ),
        )
        try:
            seed = "%s|%s|%s" % (
                _trajectory_config(mind).get("seed", 0),
                getattr(mind, "instance_id", 0),
                getattr(mind, "current_date", ""),
            )
            final_records = None
            attempt_prompt = reconcile_prompt
            retry_count = max(0, int(
                _trajectory_config(mind).get("final_itinerary_retry_count", 1)
            ))
            for attempt in range(retry_count + 1):
                response = _extract_json_object(mind.llm_call_j(attempt_prompt, 0))
                final_records = reconcile_final_itinerary(
                    base_location_records, response, seed=seed,
                    known_locations=getattr(mind, "trajectory_location_history", None) or [],
                    accuracy_validation=config.get("accuracy_validation", True),
                    maptools=getattr(mind, "maptools", None),
                )
                diagnostics = final_records.get("itinerary_reconciliation", {})
                if diagnostics.get("applied"):
                    break
                if attempt < retry_count:
                    attempt_prompt = reconcile_prompt + (
                        "\n上一次结构未能完整解析。错误为：%s。请重新输出完整 JSON，"
                        "确保每一行都有可解析的已有 stop_id 或 location_key。"
                        % json.dumps(diagnostics.get("issues", []), ensure_ascii=False)
                    )
            diagnostics = (final_records or {}).get("itinerary_reconciliation", {})
            reconciled = bool(diagnostics.get("applied"))
            if not reconciled:
                # 核对未完整解析时降级：沿用分配阶段地点记录（结构完整），
                # 交由后续 adjust 阶段处理，不阻断整日重试。
                mind.last_location_reconciliation["issues"].append(
                    "最终行程核对未完整解析，沿用分配阶段地点记录：%s"
                    % json.dumps(diagnostics.get("issues", []), ensure_ascii=False)
                )
            final_issues = validate_location_records(
                final_records,
                require_itinerary=config.get("strict_validation", True) and reconciled,
                accuracy_validation=config.get("accuracy_validation", True),
            )
            if config.get("strict_validation", True) and reconciled and final_issues:
                raise RuntimeError("最终轨迹数值校验失败: " + "; ".join(final_issues))
            mind.final_location_records = final_records
            mind.last_location_reconciliation = final_records.get(
                "post_adjustment_reconciliation", mind.last_location_reconciliation,
            )
            mind.last_location_reconciliation["itinerary"] = final_records.get(
                "itinerary_reconciliation", {}
            )
        except Exception as error:
            mind.last_location_reconciliation["issues"].append(
                "最终叙事地点核对失败，沿用调整前地点记录：%s" % error
            )
            if config.get("strict_validation", True):
                raise
    if config.get("enabled", True) and config.get("strict_validation", True):
        final_issues = validate_location_records(
            mind.final_location_records,
            require_itinerary=bool(
                (mind.final_location_records or {}).get("event_segments")
            ),
            accuracy_validation=config.get("accuracy_validation", True),
        )
        if final_issues:
            raise RuntimeError("最终地理记录门禁失败: " + "; ".join(final_issues))
    _remember_final_locations(mind, mind.final_location_records)
    mind._log_event("轨迹调整-----------------------------------------------------------------------")
    mind._log_event(adjusted_events)
    mind._log_event(
        "最终地点核对：" + json.dumps(
            mind.last_location_reconciliation, ensure_ascii=False,
        )
    )
    mind._save_log("", "t3", adjusted_events)
    return adjusted_events
