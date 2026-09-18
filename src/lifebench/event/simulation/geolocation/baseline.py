# -*- coding: utf-8 -*-
"""simple 基线 v3：LLM 配备地理工具（function calling）的 agentic 地理分配。

与完整版 TrajectoryAllocator 完全独立，且本文件内不做任何数值计算或算法：
无 haversine、无偏移、无速度表、无通行方式启发式、无按时间/距离排序、无预算、
无候选分层、无 direct 索引匹配。所有坐标 / 通行时长 / 距离都来自高德工具
（maptools）的返回值，或 LLM 自己的判断。代码只做三件事：

  1. 把 maptools 的高德方法暴露成 LLM 可调用的工具（function schema + 薄分发）；
  2. 跑一个 function-calling 循环，直到 LLM 不再请求工具；
  3. 把 LLM / 工具的返回字段原样映射成与完整版一致的 final_location_records。

流程（两个 LLM 阶段 + 薄回填）：
  阶段 A（gather）  : LLM 用工具解析每个事件的地点（search_place / search_around /
                      geocode），输出 stops（含真实坐标），返回 poi 参考串。
  阶段 B（adjust）  : LLM 依据地点参考写出最终事件叙述 + 最终地点清单（可编造新地点，
                      并自行为每次通行指定交通方式 mode）。
  阶段 C（回填）    : 对最终地点逐条回填坐标（复用 A / 工具正向搜索，搜不到跳过），
                      相邻不同地点之间调 route_between 工具取真实通行时长/距离，
                      组装 stops + legs + event_segments 成 final_location_records。

最终地点记录的导出/校验（build_location_records / validate_location_records /
build_half_hour_trajectory）复用完整版共享下游，保证与完整版在同一口径下对比。
"""
import json

from src.lifebench.utils.llm_call import llm_agent

from .models import ResolvedStop, TrajectoryAssignment, TravelLeg
from .export import build_location_records
from .validator import validate_location_records


_VALID_MODES = {"walking", "driving", "transit", "bicycling"}


# --------------------------------------------------------------------------- #
# 工具 schema（暴露给 LLM 的高德工具）与薄分发
# --------------------------------------------------------------------------- #
_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_place",
            "description": "按关键词在高德文本搜索候选地点，返回最多5个候选（name/location/address/city/district）。用于发现具体店铺/场所。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "店铺名或业态关键词，如“星巴克”“健身房”"},
                    "city": {"type": "string", "description": "城市名，如“北京”；可空表示全国"},
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_around",
            "description": "在指定中心点附近按关键词搜索候选地点，返回最多5个候选。用于“在某地附近找某类场所”。",
            "parameters": {
                "type": "object",
                "properties": {
                    "center": {"type": "string", "description": "中心点坐标“经度,纬度”"},
                    "keyword": {"type": "string", "description": "业态关键词，如“餐厅”"},
                    "city": {"type": "string", "description": "城市名，可空"},
                    "radius": {"type": "integer", "description": "搜索半径（米），默认3000"},
                },
                "required": ["center", "keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "geocode",
            "description": "地理编码：把名称或地址解析成坐标与结构化地址。用于把某具体地址/名称转成坐标。",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "地点名称或地址"},
                    "city": {"type": "string", "description": "城市名，可空"},
                },
                "required": ["address"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "route_between",
            "description": "计算两点之间某种交通方式的通行耗时与距离。用于估算相邻事件之间的通行。",
            "parameters": {
                "type": "object",
                "properties": {
                    "origin": {"type": "string", "description": "起点坐标“经度,纬度”"},
                    "destination": {"type": "string", "description": "终点坐标“经度,纬度”"},
                    "mode": {"type": "string", "enum": list(_VALID_MODES), "description": "交通方式"},
                },
                "required": ["origin", "destination", "mode"],
            },
        },
    },
]


def _candidate_public(candidate):
    """把 maptools 的候选 POI 压缩成写回 LLM 的公开字段。"""
    geo = candidate.get("geocode") or {}
    return {
        "name": str(candidate.get("name") or ""),
        "location": str(candidate.get("location") or ""),
        "address": str(candidate.get("structured_address") or candidate.get("address") or ""),
        "city": str(geo.get("city") or candidate.get("cityname") or candidate.get("city") or ""),
        "district": str(geo.get("district") or candidate.get("adname") or ""),
    }


def _dispatch_tool(mind, name, args):
    """薄分发：按工具名调用 maptools 方法，把结果格式化为 JSON-safe 字典。"""
    name = str(name or "")
    mt = mind.maptools
    try:
        if name == "search_place":
            keyword = str(args.get("keyword") or "").strip()
            city = str(args.get("city") or "").strip() or None
            candidates = mt.search_poi_candidates(keyword, city=city, limit=5) or []
            return {"results": [_candidate_public(c) for c in candidates]}
        if name == "search_around":
            center = str(args.get("center") or "").strip()
            keyword = str(args.get("keyword") or "").strip()
            city = str(args.get("city") or "").strip() or None
            radius = int(args.get("radius") or 3000)
            candidates = mt.search_around_candidates(
                center, keywords=keyword, city=city, radius=radius, limit=5,
            ) or []
            return {"results": [_candidate_public(c) for c in candidates]}
        if name == "geocode":
            address = str(args.get("address") or "").strip()
            city = str(args.get("city") or "").strip() or None
            geo = mt.amap_geocode(address, city)
            if not geo or not geo.get("location"):
                return {"found": False, "result": None}
            return {"found": True, "result": {
                "name": address,
                "location": str(geo.get("location") or ""),
                "formatted_address": str(geo.get("formatted_address") or ""),
                "city": str(geo.get("city") or city or ""),
                "district": str(geo.get("district") or ""),
            }}
        if name == "route_between":
            origin = str(args.get("origin") or "").strip()
            destination = str(args.get("destination") or "").strip()
            mode = str(args.get("mode") or "driving").strip()
            payload = mt.route_between_pois(
                {"location": origin}, {"location": destination}, mode,
            )
            if not payload:
                return {"found": False, "result": None}
            return {"found": True, "result": {
                "mode": mode,
                "duration_minutes": max(1, int(round(payload["duration_seconds"] / 60.0))),
                "distance_km": round(payload["distance_meters"] / 1000.0, 2),
            }}
    except Exception as exc:  # 工具异常不应中断整个 agent 循环
        return {"error": "%s 调用失败: %s" % (name, type(exc).__name__)}
    return {"error": "unknown tool: %s" % name}


# --------------------------------------------------------------------------- #
# 提示词与辅助
# --------------------------------------------------------------------------- #
_SIMPLE_GATHER_SYSTEM = (
    "你是地理查询助手。你拥有高德地图工具（search_place/search_around/geocode/route_between），"
    "可以自主设计查询、多次调用工具，并只根据工具返回的真实数据作答。所有坐标必须来自工具返回"
    "或已知地址，禁止自行编造坐标。"
)

_SIMPLE_GATHER_PROMPT = '''你是人物的地理助手。下面给出“已知地址”表（含坐标，直接使用即可）、人物画像和当天事件清单。

请为每个需要真实物理地点的【事件】确定一个地点，输出地点清单。规则：
- 回家/上班/去熟悉地点/拜访他人等固定地点：直接使用“已知地址”表中的 name 和 location 坐标，不要改写；
- 需要发现具体店铺/场所（餐饮、购物、健身、娱乐等）：调用 search_place / search_around / geocode 工具得到真实坐标；
- 调用工具后必须使用工具返回的 name/location/address，不得编造坐标；
- 无法定位的线上事件不要输出；
- 每个事件一行，按时间先后排列，start_time/end_time 用 "HH:MM"。

最终只输出一个 JSON 对象，不要输出解释文字，格式：
{"stops":[{"event":"事件简述","name":"地点名","location":"经度,纬度","address":"地址","city":"城市","start_time":"HH:MM","end_time":"HH:MM"}]}

人物画像：
__PERSONA__

已知地址（含坐标）：
__ADDRESSES__

当天事件：
__EVENTS__
'''

_SIMPLE_ADJUST_PROMPT = '''你是人物行为数据生成助手。根据人物画像、当天客观事件、以及已解析的“地点参考”（含真实坐标），写出当天最终事件叙述，并给出最终地点清单。

要求：
- 地点优先采用“地点参考”里已有的地点（直接引用其 name）；
- 若事件语义需要一个新的具体地点（地点参考里没有），可自行取名，后续会用地图工具回填坐标；
- 每个最终地点一行，按时间顺序；start_time/end_time 用 "HH:MM"；
- 每个地点可带一个 "mode" 字段（可选），表示从上一地点到达该地点的交通方式
  （walking/driving/transit/bicycling 之一）；第一项无需 mode。
- 叙述中的日期必须以"当天日期"为准；人物画像里出现的日期是旧快照日期，不得沿用。

只输出一个 JSON 对象：
{"events":"<Markdown 叙述>","locations":[{"event":"事件简述","name":"地点名","city":"城市","start_time":"HH:00","end_time":"HH:00","mode":"driving"}]}

当天日期：
__DATE__

人物画像：
__PERSONA__

地点参考：
__REFERENCE__

当天事件：
__EVENTS__
'''


def _extract_json(text):
    """容错地提取 LLM 输出中的 JSON 对象或数组。"""
    if isinstance(text, (dict, list)):
        return text
    value = str(text or "")
    for open_c, close_c in (("{", "}"), ("[", "]")):
        first = value.find(open_c)
        last = value.rfind(close_c)
        if first != -1 and last != -1 and first < last:
            try:
                return json.loads(value[first:last + 1])
            except (json.JSONDecodeError, ValueError):
                continue
    return {}


def _persona_text(mind, use_cognition=False):
    """把画像转成可注入提示词的文本。"""
    value = getattr(mind, "cognition", "") if use_cognition else getattr(mind, "persona", "")
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _known_addresses_text(mind):
    """把已知地址压缩成 LLM 可直接引用的字段列表（含坐标，排除城市机会池）。"""
    rows = []
    for item in getattr(mind, "persona_address_data", None) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("location_role") or "") == "city_reference":
            continue
        name = str(item.get("name") or "").strip()
        location = str(item.get("location") or "").strip()
        address = str(item.get("formatted_address") or item.get("address") or "").strip()
        if not name or not location:
            continue
        rows.append({
            "name": name,
            "location": location,
            "address": address,
            "role": str(item.get("location_role") or ""),
        })
    return json.dumps(rows, ensure_ascii=False, separators=(",", ":"))


def _events_text(events):
    return events if isinstance(events, str) else json.dumps(events, ensure_ascii=False)


def _render_geo_reference(stops):
    lines = ["【地点参考】以下坐标均来自高德地图工具或已知地址（真实）。"]
    for index, stop in enumerate(stops, 1):
        lines.append("【参考地点%02d】%s｜%s｜事件:%s｜坐标:%s｜城市:%s｜%s-%s" % (
            index, stop.get("name") or "", stop.get("address") or "",
            stop.get("event") or "", stop.get("location") or "",
            stop.get("city") or "", stop.get("start_time") or "?",
            stop.get("end_time") or "?",
        ))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 阶段 A：地理收集 agent
# --------------------------------------------------------------------------- #
def simple_gather_geo(mind, events, plan=None):
    """阶段 A：LLM 用工具解析每个事件地点，输出真实坐标的 stops，返回 poi 参考串。"""
    # simple 模式不再使用完整版的 TrajectoryAssignment 分配算法。
    mind.last_trajectory_assignment = None
    mind._simple_geo_reference = {"stops": []}

    prompt = (
        _SIMPLE_GATHER_PROMPT
        .replace("__PERSONA__", _persona_text(mind))
        .replace("__ADDRESSES__", _known_addresses_text(mind))
        .replace("__EVENTS__", _events_text(events))
    )
    messages = [
        {"role": "system", "content": _SIMPLE_GATHER_SYSTEM},
        {"role": "user", "content": prompt},
    ]
    raw = None
    try:
        raw = llm_agent(messages, _TOOL_SCHEMAS, lambda name, args: _dispatch_tool(mind, name, args))
    except Exception as exc:
        print("[simple_geo] 地理收集 agent 失败（%s），跳过地理分配" % type(exc).__name__)

    payload = _extract_json(raw)
    rows = payload.get("stops", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []
    stops = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        location = str(row.get("location") or "").strip()
        if len(location.split(",")) != 2:
            continue
        stops.append({
            "event": str(row.get("event") or "").strip(),
            "name": str(row.get("name") or "").strip(),
            "location": location,
            "address": str(row.get("address") or "").strip(),
            "city": str(row.get("city") or "").strip(),
            "start_time": str(row.get("start_time") or "").strip(),
            "end_time": str(row.get("end_time") or "").strip(),
        })
    mind._simple_geo_reference = {"stops": stops}
    return _render_geo_reference(stops)


# --------------------------------------------------------------------------- #
# 阶段 B + C：adjust + 回填 + 组装最终记录
# --------------------------------------------------------------------------- #
def _match_ref(ref_stops, name):
    """按名称（先精确后包含）在阶段 A 的 stops 里找已有地点；找不到返回 None。"""
    if not name:
        return None
    for stop in ref_stops:
        if stop.get("name") and stop.get("name") == name:
            return stop
    for stop in ref_stops:
        if stop.get("name") and (stop.get("name") in name or name in stop.get("name")):
            return stop
    return None


def _backfill_location(mind, name, city):
    """用工具正向搜索/地理编码回填一个编造地点的真实坐标；搜不到返回 None。"""
    if not name:
        return None
    poi = mind.maptools.get_poi(name, city or None)
    if not poi or not poi.get("location"):
        geo = mind.maptools.amap_geocode(name, city or None)
        if not geo or not geo.get("location"):
            return None
        return {
            "name": name,
            "location": str(geo.get("location") or ""),
            "address": str(geo.get("formatted_address") or ""),
            "city": str(geo.get("city") or city or ""),
        }
    geo = poi.get("geocode") or {}
    return {
        "name": str(poi.get("name") or name),
        "location": str(poi.get("location") or ""),
        "address": str(poi.get("structured_address") or poi.get("address") or ""),
        "city": str(geo.get("city") or poi.get("cityname") or city or ""),
    }


def _route_tool(mind, origin_coords, dest_coords, mode):
    """调 route_between 工具取真实通行时长(分)/距离(公里)；失败返回 None。"""
    if mode not in _VALID_MODES:
        mode = "driving"
    payload = mind.maptools.route_between_pois(
        {"location": origin_coords}, {"location": dest_coords}, mode,
    )
    if not payload:
        return None
    return {
        "mode": mode,
        "duration_minutes": max(1, int(round(payload["duration_seconds"] / 60.0))),
        "distance_km": round(payload["distance_meters"] / 1000.0, 2),
    }


def _hhmm_add_minutes(hhmm, minutes):
    """把 "HH:MM" 加上分钟数得到到达时刻；非法输入返回空串。

    仅用于把工具返回的通行时长换算成 travel 段的到达时刻，属时间格式换算，
    不是地理分配算法（不做任何距离/速度/方式推断）。
    """
    try:
        hour, minute = (int(part) for part in str(hhmm).split(":", 1))
    except (TypeError, ValueError):
        return ""
    total = (hour * 60 + minute + int(minutes or 0)) % 1440
    return "%02d:%02d" % (total // 60, total % 60)


def _make_stop(index, info):
    return ResolvedStop(
        stop_id="stop_%03d" % index,
        event_ref=info["event"],
        activity_type="other",
        location_id=info["location_id"],
        name=info["name"],
        address=info["address"],
        coordinates=info["location"],
        city=info["city"],
        category="other",
        source="amap",
        degraded=False,
        original_order=index,
        required=False,
        provenance="inferred",
        flexibility="movable",
        spatial_scope="city",
        confidence=1.0,
        map_verified=True,
        fact_source="map_accepted",
        override_reason="",
        anchor_location_id="",
        estimate_method="llm_tool_search",
    )


def simple_adjust_trajectory(mind, poi_data, event, daily_event_reference="", history=""):
    """阶段 B + C：写出最终事件叙述 + 回填坐标 + 组装 final_location_records。"""
    ref_stops = (getattr(mind, "_simple_geo_reference", {}) or {}).get("stops", []) or []

    prompt = (
        _SIMPLE_ADJUST_PROMPT
        .replace("__DATE__", str(getattr(mind, "current_date", "") or ""))
        .replace("__PERSONA__", _persona_text(mind, use_cognition=True))
        .replace("__REFERENCE__", poi_data or _render_geo_reference(ref_stops))
        .replace("__EVENTS__", _events_text(event))
    )
    payload = {}
    try:
        payload = _extract_json(mind.llm_call_j(prompt, 0))
    except Exception as exc:
        print("[simple_geo] adjust LLM 失败（%s）" % type(exc).__name__)
    if not isinstance(payload, dict):
        payload = {}

    events_narrative = payload.get("events") or ""
    if not isinstance(events_narrative, str):
        events_narrative = str(events_narrative)
    locations = payload.get("locations", []) if isinstance(payload.get("locations"), list) else []

    # 阶段 C：逐条回填坐标（复用 A / 工具搜索，搜不到跳过）。
    final_stops = []
    location_ids = {}
    skipped = []
    backfilled = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        name = str(loc.get("name") or "").strip()
        city = str(loc.get("city") or "").strip()
        resolved = _match_ref(ref_stops, name)
        provenance = "reference"
        if resolved is None and name:
            resolved = _backfill_location(mind, name, city)
            provenance = "backfill"
            if resolved is not None:
                backfilled.append(name)
            else:
                skipped.append(name)
        if resolved is None:
            continue
        coords = str(resolved.get("location") or "").strip()
        if len(coords.split(",")) != 2:
            skipped.append(name)
            continue
        location_id = location_ids.get(coords)
        if location_id is None:
            location_id = "amap_%03d" % len(location_ids)
            location_ids[coords] = location_id
        final_stops.append({
            "event": str(loc.get("event") or name).strip(),
            "name": str(resolved.get("name") or name).strip(),
            "location": coords,
            "address": str(resolved.get("address") or "").strip(),
            "city": str(resolved.get("city") or city).strip(),
            "start_time": str(loc.get("start_time") or "").strip(),
            "end_time": str(loc.get("end_time") or "").strip(),
            "mode": str(loc.get("mode") or "").strip(),
            "location_id": location_id,
            "provenance": provenance,
        })

    stops = [_make_stop(i, info) for i, info in enumerate(final_stops)]

    # 组装 legs（mode 由 LLM 在阶段 B 指定，duration/distance 来自 route_between 工具）。
    legs = []
    segments = []
    for i in range(len(final_stops)):
        info = final_stops[i]
        segments.append({
            "segment_id": "segment_%03d" % (2 * i),
            "event_group_id": "group_%03d" % i,
            "kind": "activity",
            "start_time": info["start_time"],
            "end_time": info["end_time"],
            "event_ref": info["event"],
            "source_plan_ids": [],
            "stop_id": stops[i].stop_id,
            "location_detail": info["address"],
            "location_identity_mode": "source_identity",
            "narrative_location_name": info["name"],
            "location_override_reason": "",
        })
        if i >= len(final_stops) - 1:
            continue
        nxt = final_stops[i + 1]
        if info["location_id"] == nxt["location_id"]:
            continue  # 同地点停留，无通行段
        mode = nxt.get("mode") or "driving"
        route = _route_tool(mind, stops[i].coordinates, stops[i + 1].coordinates, mode)
        if route is None:
            duration, distance, source, verified, confidence = 0, 0.0, "unresolved", False, 0.5
        else:
            duration = route["duration_minutes"]
            distance = route["distance_km"]
            source, verified, confidence = "amap", True, 1.0
        # 到达时刻 = 出发时刻 + 工具返回的通行时长（时间格式换算，非分配算法）。
        departure = info["end_time"]
        arrival = _hhmm_add_minutes(departure, duration) if duration > 0 else nxt["start_time"]
        leg = TravelLeg(
            leg_id="leg_%03d" % len(legs),
            origin_stop_id=stops[i].stop_id,
            destination_stop_id=stops[i + 1].stop_id,
            origin_name=stops[i].name,
            destination_name=stops[i + 1].name,
            mode=mode,
            duration_minutes=duration,
            distance_km=distance,
            departure_time=departure,
            arrival_time=arrival,
            source=source,
            feasible=True,
            confidence=confidence,
            leg_type="transfer",
            narrative_route="",
            map_verified=verified,
        )
        legs.append(leg)
        segments.append({
            "segment_id": "segment_%03d" % (2 * i + 1),
            "event_group_id": "group_%03d" % i,
            "kind": "travel",
            "start_time": departure,
            "end_time": arrival,
            "event_ref": "",
            "source_plan_ids": [],
            "leg_id": leg.leg_id,
            "origin_stop_id": leg.origin_stop_id,
            "destination_stop_id": leg.destination_stop_id,
            "mode": leg.mode,
            "duration_minutes": leg.duration_minutes,
            "distance_km": leg.distance_km,
        })

    assignment = TrajectoryAssignment(
        date=str(getattr(mind, "current_date", "") or ""),
        stops=stops,
        legs=legs,
        feasible=True,
        violations=[],
        diagnostics={"allocation_mode": "simple_tool_agent"},
    )
    records = build_location_records(assignment)
    records["event_segments"] = segments
    records["schema_version"] = "simulation_location_v2"

    issues = validate_location_records(records, require_itinerary=True, accuracy_validation=True)
    mind.final_location_records = records
    mind.last_location_reconciliation = {
        "estimated_stop_ids": [],
        "estimated_stop_count": 0,
        "backfilled": backfilled,
        "skipped": skipped,
        "stop_count": len(stops),
        "leg_count": len(legs),
        "issues": issues,
    }
    return events_narrative
