# -*- coding: utf-8 -*-
"""把新版停留意图和旧版 instruction JSON 统一成 StopIntent。"""
from typing import Any, Dict, List

from .catalog import infer_category
from .models import StopIntent


def _value(item: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        if item.get(key) is not None:
            return str(item[key]).strip()
    return ""


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return str(value or "").strip().lower() in {"1", "true", "yes", "required"}


def _string_list(value: Any) -> List[str]:
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    for separator in ("|", "；", ";"):
        if separator in text:
            return [part.strip() for part in text.split(separator) if part.strip()]
    return [text]


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _distance_band(value: Any, tier: str) -> List[float]:
    defaults = {"local": [0.0, 3.0], "urban": [3.0, 15.0], "long": [15.0, 500.0]}
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        try:
            low, high = max(0.0, float(value[0])), max(0.0, float(value[1]))
            if high > low:
                return [low, high]
        except (TypeError, ValueError):
            pass
    return defaults[tier]


def _policy(category: str, query_type: str) -> str:
    if category in {"home", "education"} or query_type == "existing":
        return "must_return"
    if category == "work":
        # 固定公司应由 existing 命中；search 类型的工作地点通常是客户单位、
        # 外勤现场或临时办公点，不能强制复用日常公司。
        return "may_explore"
    if category in {"meal", "fitness", "shopping"}:
        return "prefer_return"
    return "may_explore"


def _selection_policy(
    category: str, query_type: str, explicit_name: str,
    explicit_location: str, required: bool,
) -> str:
    if query_type == "existing" or explicit_name or explicit_location:
        return "best_match"
    if category in {"meal", "fitness", "shopping", "leisure"}:
        return "gravity"
    if required and query_type in {"search", "city"}:
        return "random"
    return "gravity"


def _location_decision(
    row: Dict[str, Any], category: str, query_type: str, explicit_name: str,
    explicit_location: str, required: bool, historical_candidate_ids: List[str],
) -> tuple[str, str, str]:
    """Normalize semantic location agency into one executable policy.

    New prompts emit ``location_control`` and ``location_binding``.  Old data
    remains accepted, but an explicitly self-chosen preferred/open destination
    must not collapse to best_match merely because an inspiration supplied a
    name or location id.
    """
    control = _value(row, "location_control")
    binding = _value(row, "location_binding")
    if control not in {"self", "fixed", "external_unspecified"}:
        control = ""
    if binding not in {"fixed", "preferred", "open"}:
        binding = ""

    declared_policy = _value(row, "selection_policy")
    declared_reuse = (
        _value(row, "reuse_location_id")
        or _value(row, "selected_location_id")
    )
    # Backward-compatible explicit reuse remains a hard binding unless the new
    # schema explicitly marks it preferred/open.
    if declared_reuse and not binding:
        binding = "fixed"
    if declared_reuse and not control and row.get("selected_location_id"):
        control = "self"
    if control == "fixed":
        binding, policy = "fixed", "best_match"
    elif control == "external_unspecified":
        binding, policy = "open", "random"
    elif control == "self":
        policy = "best_match" if binding == "fixed" else "gravity"
    elif declared_policy in {"gravity", "best_match", "random"}:
        policy = declared_policy
    else:
        policy = _selection_policy(
            category, query_type, explicit_name, explicit_location, required,
        )

    if not control:
        control = {
            "gravity": "self",
            "best_match": "fixed",
            "random": "external_unspecified",
        }[policy]
    if not binding:
        if policy == "best_match" or query_type == "existing":
            binding = "fixed"
        elif historical_candidate_ids:
            binding = "preferred"
        else:
            binding = "open"
    if binding == "fixed":
        policy = "best_match"
    elif control == "self":
        policy = "gravity"
    return control, binding, policy


def parse_stop_intents(data: Dict[str, Any]) -> List[StopIntent]:
    if not isinstance(data, dict):
        raise ValueError("轨迹意图必须是JSON对象")
    rows = data.get("stops")
    legacy = rows is None
    rows = data.get("instruction", []) if legacy else rows
    if not isinstance(rows, list) or not rows:
        raise ValueError("轨迹意图中没有停留点")
    cities = data.get("city", []) if isinstance(data.get("city"), list) else []
    transports = data.get("transport", []) if isinstance(data.get("transport"), list) else []
    intents = []  # type: List[StopIntent]
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        legacy_type = str(row.get("type", "")) if legacy else ""
        query_type = _value(row, "query_type") or {"1": "existing", "2": "search", "3": "around"}.get(legacy_type, "search")
        name = _value(row, "explicit_name", "name")
        keyword = _value(row, "keyword", "Keyword")
        poi_type = _value(row, "poi_type", "poiType")
        event_ref = _value(row, "event_ref", "event", "activity")
        category = _value(row, "activity_type") or infer_category(" ".join((event_ref, name, keyword, poi_type)))
        city = _value(row, "city") or (str(cities[index]) if index < len(cities) else "")
        explicit_location = _value(row, "explicit_location", "location")
        required = _boolean(row.get("required", False))
        mode_hint = _value(row, "mode_hint")
        if legacy and index > 0 and index - 1 < len(transports):
            mode_hint = str(transports[index - 1])
        historical_candidate_ids = list(dict.fromkeys(
            _string_list(row.get("historical_candidate_ids"))
        ))[:5]
        preferred_candidate_ids = list(dict.fromkeys(
            _string_list(row.get("preferred_candidate_ids"))
            + _string_list(row.get("candidate_location_ids"))
        ))[:5]
        location_control, location_binding, selection_policy = _location_decision(
            row, category, query_type, name, explicit_location, required,
            historical_candidate_ids,
        )
        # A preferred/open self-chosen destination is a choice set, not an
        # already resolved entity.  Force it through candidate generation and
        # let EPR choose return versus exploration.
        if location_control == "self" and location_binding != "fixed":
            if query_type == "existing":
                query_type = "search"
            reuse_location_id = ""
            reuse_policy = _value(row, "reuse_policy") or _policy(category, query_type)
            if reuse_policy == "must_return":
                reuse_policy = "prefer_return" if historical_candidate_ids else "may_explore"
        else:
            reuse_location_id = (
                _value(row, "reuse_location_id")
                or _value(row, "selected_location_id")
            )
            reuse_policy = _value(row, "reuse_policy") or _policy(category, query_type)
        epr_applicable = (
            selection_policy == "gravity"
            and query_type not in {"existing", "micro"}
            and (
                _boolean(row.get("epr_applicable", False))
                or bool(historical_candidate_ids)
            )
        )
        distance_tier = _value(row, "distance_tier")
        if distance_tier not in {"local", "urban", "long"}:
            distance_tier = "local" if query_type in {"existing", "micro", "around"} else "urban"
        distance_sensitivity = _value(row, "distance_sensitivity")
        if distance_sensitivity not in {"high", "medium", "low"}:
            distance_sensitivity = "high" if distance_tier == "local" else "low" if distance_tier == "long" else "medium"
        intents.append(StopIntent(
            stop_id=_value(row, "stop_id") or "stop_%03d" % index,
            order=index,
            activity_type=category,
            query_type=query_type,
            event_ref=event_ref,
            explicit_name=name,
            explicit_location=explicit_location,
            keyword=keyword,
            search_queries=_string_list(row.get("search_queries")),
            poi_type=poi_type,
            city=city,
            anchor_role=_value(row, "anchor_role"),
            reuse_policy=reuse_policy,
            reuse_location_id=reuse_location_id,
            epr_applicable=epr_applicable,
            historical_candidate_ids=historical_candidate_ids if epr_applicable else [],
            preferred_candidate_ids=(
                preferred_candidate_ids
                if location_control == "self" and location_binding == "preferred"
                else []
            ),
            preference_strength=max(0.0, min(
                1.0, _float_value(row.get("preference_strength"), 0.75)
            )) if preferred_candidate_ids else 0.0,
            history_match_reason=_value(row, "history_match_reason"),
            location_control=location_control,
            location_binding=location_binding,
            selection_policy=selection_policy,
            start_time=_value(row, "start_time"),
            end_time=_value(row, "end_time"),
            minimum_dwell_minutes=int(row.get("minimum_dwell_minutes") or 0),
            mode_hint=mode_hint,
            parent_event_id=_value(row, "parent_event_id", "event_id"),
            required=required,
            provenance=_value(row, "provenance") or "inferred",
            flexibility=_value(row, "flexibility") or "movable",
            spatial_scope=_value(row, "spatial_scope") or "city",
            maximum_travel_minutes=int(row.get("maximum_travel_minutes") or 0),
            mobility_pattern=_value(row, "mobility_pattern") or "destination",
            allow_plausible_location=_boolean(row.get("allow_plausible_location", False)),
            preferred_radius_m=int(row.get("preferred_radius_m") or 0),
            target_distance_km=float(row.get("target_distance_km") or 0.0),
            target_duration_minutes=int(row.get("target_duration_minutes") or 0),
            fallback_queries=_string_list(row.get("fallback_queries")),
            fallback_area=_value(row, "fallback_area", "district"),
            allow_citywide_fallback=_boolean(row.get("allow_citywide_fallback", False)),
            distance_tier=distance_tier,
            distance_band_km=_distance_band(row.get("distance_band_km"), distance_tier),
            distance_sensitivity=distance_sensitivity,
            independent_trip=_boolean(row.get("independent_trip", False)),
            distance_tier_reason=_value(row, "distance_tier_reason"),
        ))
    if not intents:
        raise ValueError("没有可解析的停留点")
    return intents
