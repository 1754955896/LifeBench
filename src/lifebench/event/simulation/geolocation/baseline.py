# -*- coding: utf-8 -*-
"""地理分配的朴素基线：LLM 出定位指令 → 高德查询/直接引用 → 构建轨迹分配。

与完整版 TrajectoryAllocator 完全独立，不做 EPR/重力、预算、交通方式规划、
候选分层、复访偏好等任何建模；但产出与完整版相同的数据结构 TrajectoryAssignment
（stops + legs），后续的 adjust event → 回填 → 通行统计完全复用完整版下游
（adjust_event_trajectory），确保与完整版在同一口径下对比。

流程（1 次 LLM 调用 + 若干地图调用；后续 adjust/reconcile 与完整版一致）：
  1. LLM 为每个事件生成一条定位指令（唯一一次指令级 LLM 调用），允许三种操作：
     - search  关键字搜索：给业态/店名，高德 text 搜索取 top1；
     - nearby  附近搜索：给“参考地点 + 业态”，先定位参考点再做周边搜索；
     - direct  直接使用：直接引用已知地址（location.json 里的 anchor/familiar/social），
               不再调用地图 API。
  2. 按指令逐条调用高德（direct 直接读地址目录），每条取一个地点，构造 ResolvedStop。
  3. 相邻停留点之间计算通行 TravelLeg（真实路由耗时，查不到则速度表启发式）。
  4. 返回 TrajectoryAssignment，写入 mind.last_trajectory_assignment；同时返回
     render_assignment_summary(assignment) 作为 poi 参考串，供 adjust_event_trajectory
     使用（与完整版 generate_poi_route 的返回契约一致）。

轨迹里的坐标只来自真实地图/地址（map_verified）；编造地点的坐标回填由完整版下游的
reconcile_final_itinerary 完成（search_named 正向搜索 / anchor_estimate 偏移，搜不到
则跳过）。
"""
import json
import math

from .injection import render_assignment_summary
from .models import ResolvedStop, TrajectoryAssignment, TravelLeg


# 低于此直线距离（公里）视为“同一宏地点”，与 _build_legs 的“同地点”阈值保持一致。
# 同地点停留点应复用同一 location_id，否则下游 validate_location_records 会把零时长
# 的腿误判为“跨地点移动缺少正的时长或距离”。
_SAME_LOCATION_KM = 0.05


_SIMPLE_QUERY_PROMPT = '''你是人物行为数据生成助手。下面给出人物画像、已知地址和当天事件。

请为每个需要真实物理地点的事件选择一种定位方式（op），并给出城市和起止时间。
只输出一个 JSON 对象，不要输出任何解释文字，格式如下：
{"stops":[
  {"event":"事件简述","op":"search","keyword":"查询关键词","city":"城市名","start_time":"HH:00","end_time":"HH:00"},
  {"event":"事件简述","op":"nearby","keyword":"业态类型","base":"参考地点名或地址","city":"城市名","start_time":"HH:00","end_time":"HH:00"},
  {"event":"事件简述","op":"direct","address":"已知地址的 name 或 location_id","start_time":"HH:00","end_time":"HH:00"}
]}

三种 op 的用法：
1. search（关键字搜索）：用于需要发现具体店/场所的事件，keyword 写具体店名或业态；
2. nearby（附近搜索）：用于“在某个已知地点附近找某类场所”，base 写参考地点名或地址，keyword 写业态类型；
3. direct（直接使用）：用于回家/上班/去熟悉地点/拜访某人等，address 必须原样引用“已知地址”列表中的 name 或 location_id，不要改写。

要求：
- 回家/上班/上学/去熟悉地点/拜访他人等固定地点，用 direct；
- 餐饮/购物/健身/娱乐等需要找具体场所的，用 search；
- 需要“在某地附近找某类场所”的，用 nearby；
- 纯线上或无法定位的事件不要生成；
- city 留空表示全国搜索。

人物画像：
__PERSONA__

已知地址：
__ADDRESSES__

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


def _minute(value):
    """解析 "HH:MM" 为分钟数，无效返回 None。"""
    try:
        hour, minute = (int(part) for part in str(value).split(":", 1))
    except (TypeError, ValueError):
        return None
    return hour * 60 + minute if 0 <= hour <= 23 and 0 <= minute <= 59 else None


def _build_known_addresses(mind):
    """从 location.json 的扁平地址目录中取“可直接使用”的已知地址。

    排除 city_reference（城市机会池是每日抽样候选，不是人物已知地点），
    保留 anchor / familiar / social（家、工作地、熟悉地点、社交地址）。
    返回 (有序列表, 键→条目索引)，键包括 name / location_id / formatted_address。
    """
    known = []
    index = {}
    for item in getattr(mind, "persona_address_data", None) or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("location_role") or "") == "city_reference":
            continue
        name = str(item.get("name") or "").strip()
        location_id = str(item.get("location_id") or "").strip()
        formatted_address = str(item.get("formatted_address") or item.get("address") or "").strip()
        entry = {
            "location_id": location_id,
            "name": name,
            "formatted_address": formatted_address,
            "location_role": str(item.get("location_role") or ""),
            "location": str(item.get("location") or ""),
            "city": str(item.get("city") or ""),
        }
        known.append(entry)
        for key in (name, location_id, formatted_address):
            if key:
                index[key] = entry
    return known, index


def _prompt_addresses(known):
    """把已知地址压缩成 LLM 可直接引用的字段列表。"""
    return json.dumps(
        [
            {
                "location_id": e["location_id"],
                "name": e["name"],
                "formatted_address": e["formatted_address"],
                "location_role": e["location_role"],
            }
            for e in known
        ],
        ensure_ascii=False, separators=(",", ":"),
    )


def _poi_from_result(poi, keyword, city):
    """把高德返回的 POI（或地址目录条目）归一化为写回字段；无效则返回 None。"""
    if not poi or not poi.get("location"):
        return None
    return {
        "name": str(poi.get("name") or keyword),
        "location": str(poi.get("location") or ""),
        "address": str(poi.get("formatted_address") or poi.get("structured_address") or poi.get("address") or ""),
        "city": str(
            (poi.get("geocode") or {}).get("city")
            or poi.get("cityname") or poi.get("city") or city or ""
        ),
    }


def _resolve_stop(mind, row, known, index):
    """把单条 LLM 定位指令解析成一个地点（dict 或 None）。"""
    op = str(row.get("op") or row.get("type") or "search").strip().lower()
    keyword = str(row.get("keyword") or "").strip()
    city = str(row.get("city") or "").strip()
    base = str(row.get("base") or "").strip()
    ref = str(row.get("address") or "").strip()

    if op in ("1", "direct", "use", "known"):
        # 直接使用已知地址：按 name / location_id / formatted_address 匹配。
        target = index.get(ref)
        if target is None:
            for entry in known:
                name = entry.get("name") or ""
                if name and (name in ref or ref in name):
                    target = entry
                    break
        return _poi_from_result(target, ref, city)

    if op in ("3", "nearby", "around", "near"):
        # 附近搜索：先定位参考点，再周边搜索；失败降级为关键字搜索。
        if not keyword:
            return None
        center_location = ""
        if base:
            target = index.get(base)
            if target:
                center_location = str(target.get("location") or "")
            else:
                geocode = mind.maptools.amap_geocode(base, city or None)
                center_location = str(geocode.get("location") or "") if geocode else ""
        poi = None
        if center_location:
            poi = mind.maptools.search_around_poi_random(
                location=center_location, keywords=keyword, city=city or None,
            )
        if not poi or not poi.get("location"):
            poi = mind.maptools.get_poi(keyword, city or None)
        return _poi_from_result(poi, keyword, city)

    # 默认 search：关键字搜索取 top1。
    if not keyword:
        return None
    return _poi_from_result(mind.maptools.get_poi(keyword, city or None), keyword, city)


def _haversine_km(lon1, lat1, lon2, lat2):
    """两点球面直线距离（公里）。"""
    try:
        lon1, lat1, lon2, lat2 = (float(v) for v in (lon1, lat1, lon2, lat2))
    except (TypeError, ValueError):
        return 0.0
    radius = 6371.0088
    dlon = math.radians(lon2 - lon1)
    dlat = math.radians(lat2 - lat1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2.0) ** 2
    )
    return radius * 2.0 * math.asin(min(1.0, math.sqrt(a)))


def _pick_mode(distance_km):
    """朴素通行方式启发式：短距离步行，其余驾车。"""
    return "walking" if distance_km < 1.5 else "driving"


def _home_anchor_entry(known):
    """从已知地址里取住宅锚点（首个 anchor 角色地址），取不到用第一个已知地址。"""
    for entry in known:
        if str(entry.get("location_role") or "") == "anchor":
            return entry
    return known[0] if known else None


def _dedup_location_id(resolved, groups, counter):
    """给解析出的地点分配 location_id：与已有点位直线距离 < _SAME_LOCATION_KM 时复用其 id。

    groups 为 [(location_id, (lon, lat))]，用于“同地点”判定；复用时不新增，否则
    分配新的 amap_%03d。返回 (location_id, 下一个可用序号)。
    """
    coords = str(resolved.get("location") or "")
    try:
        lon, lat = (float(part) for part in coords.split(","))
    except (TypeError, ValueError):
        return "amap_%03d" % counter, counter + 1
    for loc_id, (glon, glat) in groups:
        if _haversine_km(lon, lat, glon, glat) < _SAME_LOCATION_KM:
            return loc_id, counter
    groups.append(("amap_%03d" % counter, (lon, lat)))
    return "amap_%03d" % counter, counter + 1


def _make_stop(index, resolved, event_text, location_id=None):
    """把解析出的地点（name/location/address/city）构造成 ResolvedStop。

    location_id 缺省时按序号分配 amap_%03d；调用方可为“同地点”的停留点传入已复用的
    location_id，保证下游 validate_location_records 按同地点语义跳过正时长检查。
    """
    try:
        parts = str(resolved["location"]).split(",")
        float(parts[0]), float(parts[1])
    except (TypeError, ValueError, IndexError):
        return None
    return ResolvedStop(
        stop_id="stop_%03d" % index,
        event_ref=event_text,
        activity_type="other",
        location_id=location_id or ("amap_%03d" % index),
        name=resolved["name"],
        address=resolved.get("address") or "",
        coordinates=resolved["location"],
        city=resolved.get("city") or "",
        category="other",
        source="amap",
        degraded=False,
        original_order=index,
        parent_event_id="",
        required=False,
        provenance="inferred",
        flexibility="movable",
        spatial_scope="city",
        confidence=1.0,
        map_verified=True,
        fact_source="map_accepted",
        override_reason="",
        anchor_location_id="",
        estimate_method="amap_top1",
    )


def _build_legs(mind, stops, times):
    """按时间顺序的停留点构造通行 TravelLeg（真实路由，失败启发式）。"""
    legs = []
    speeds = {"walking": 4.5, "bicycling": 12.0, "transit": 20.0, "driving": 28.0, "running": 8.0}
    for i in range(len(stops) - 1):
        origin, dest = stops[i], stops[i + 1]
        origin_end, dest_start = times[i][1], times[i + 1][0]
        lon1, lat1 = (float(part) for part in origin.coordinates.split(","))
        lon2, lat2 = (float(part) for part in dest.coordinates.split(","))
        distance = _haversine_km(lon1, lat1, lon2, lat2)
        mode = _pick_mode(distance)

        if distance < _SAME_LOCATION_KM:
            mode, duration, source, map_verified, confidence = "none", 0, "same_location", True, 1.0
        else:
            seconds = mind.maptools.get_duration_between_pois(
                {"name": origin.name, "location": origin.coordinates, "city": origin.city},
                {"name": dest.name, "location": dest.coordinates, "city": dest.city},
                mode,
                origin.city or None,
                dest.city or None,
            )
            if seconds is not None:
                duration = max(1, int(round(seconds / 60.0)))
                source, map_verified, confidence = "amap", True, 1.0
            else:
                overhead = 8 if mode == "transit" else 5
                duration = max(1, int(round(distance / speeds.get(mode, 20.0) * 60 + overhead)))
                source, map_verified, confidence = "heuristic", False, 0.7

        legs.append(TravelLeg(
            leg_id="leg_%03d" % i,
            origin_stop_id=origin.stop_id,
            destination_stop_id=dest.stop_id,
            origin_name=origin.name,
            destination_name=dest.name,
            mode=mode,
            duration_minutes=duration,
            distance_km=round(distance, 2),
            departure_time=origin_end,
            arrival_time=dest_start,
            source=source,
            feasible=True,
            confidence=confidence,
            leg_type="transfer",
            narrative_route="",
            map_verified=map_verified,
        ))
    return legs


def simple_allocate_trajectory(mind, events, plan=None):
    """朴素基线入口：定位指令 → 高德查询/直接引用 → 构造轨迹分配。

    只做“分配”这一步，写入 mind.last_trajectory_assignment 并返回
    render_assignment_summary(assignment) 作为 poi 参考串；adjust event、
    最终回填与通行统计由完整版下游 adjust_event_trajectory 完成。
    """
    persona = str(getattr(mind, "persona", "") or "")
    known, index = _build_known_addresses(mind)
    addresses = _prompt_addresses(known)
    events_text = events if isinstance(events, str) else json.dumps(events, ensure_ascii=False)
    date = str(getattr(mind, "current_date", "") or "")

    # 步骤1：LLM 生成定位指令。
    prompt = (
        _SIMPLE_QUERY_PROMPT
        .replace("__PERSONA__", persona)
        .replace("__ADDRESSES__", addresses)
        .replace("__EVENTS__", events_text)
    )
    try:
        payload = _extract_json(mind.llm_call_j(prompt, 0))
    except Exception as exc:
        payload = {}
        print(
            "[simple_geolocation] LLM 定位指令生成失败（%s），"
            "跳过地理分配" % type(exc).__name__
        )
    rows = payload.get("stops", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        rows = []

    # 步骤2：逐条解析成真实坐标。
    entries = []  # (event_text, resolved, start_time, end_time)
    for row in rows:
        if not isinstance(row, dict):
            continue
        event_text = str(row.get("event") or row.get("keyword") or row.get("address") or "").strip()
        if not event_text:
            continue
        start_time = str(row.get("start_time") or "")
        end_time = str(row.get("end_time") or "")
        resolved = _resolve_stop(mind, row, known, index)
        if resolved is None:
            continue
        entries.append((event_text, resolved, start_time, end_time))

    # 全部解析失败时回退到住宅锚点，保证至少一个停留点（与完整版兜底一致）。
    if not entries:
        home = _home_anchor_entry(known)
        if home is not None:
            resolved = _poi_from_result(home, home.get("name") or "家", home.get("city") or "")
            if resolved is not None:
                entries.append(("回家", resolved, "", ""))

    # 按开始时间排序（无有效时间的排到最后）。
    entries.sort(key=lambda e: (_minute(e[2]) is None, _minute(e[2]) or 0))

    # 步骤3：构造 ResolvedStop；直线距离 < _SAME_LOCATION_KM 的停留点复用同一
    # location_id（对齐完整版“微活动共享父地点”语义），避免下游 validate_location_records
    # 把近距停留点的零时长腿误判为“跨地点移动缺少正的时长或距离”。
    stops = []
    times = []
    location_groups = []
    location_counter = 0
    for event_text, resolved, start_time, end_time in entries:
        location_id, location_counter = _dedup_location_id(
            resolved, location_groups, location_counter,
        )
        stop = _make_stop(len(stops), resolved, event_text, location_id=location_id)
        if stop is None:
            continue
        stops.append(stop)
        times.append((start_time, end_time))

    # 步骤4：相邻停留点构造 TravelLeg。
    legs = _build_legs(mind, stops, times)

    assignment = TrajectoryAssignment(
        date=date,
        stops=stops,
        legs=legs,
        feasible=True,
        violations=[],
        diagnostics={"allocation_mode": "simple"},
    )
    mind.last_trajectory_assignment = assignment
    return render_assignment_summary(assignment)
