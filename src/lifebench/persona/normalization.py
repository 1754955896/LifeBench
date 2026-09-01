"""Normalize external and model-produced persona data into internal structures."""

import json
import re
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict, List, Optional

from .internal_models import CircleAnchor, InternalContact, InternalPersona, RelationSlot


class NormalizationError(ValueError):
    pass


class NormalizationConflict(NormalizationError):
    pass


def parse_json_response(response: Any) -> Any:
    if isinstance(response, (dict, list)):
        return deepcopy(response)
    if not isinstance(response, str):
        raise NormalizationError("模型响应必须是 JSON 字符串、对象或数组")
    text = response.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise NormalizationError("模型响应不是有效 JSON: %s" % exc) from exc


def _parse_date(value: Any, path: str):
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day"):
        return value
    if not isinstance(value, str):
        raise NormalizationError("%s 必须是 YYYY-MM-DD 字符串" % path)
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise NormalizationError("%s 不是有效日期: %r" % (path, value)) from exc


def _circle_value(raw: Dict[str, Any], path: str) -> str:
    spaced = raw.get("social circle")
    underscored = raw.get("social_circle")
    if spaced not in (None, "") and underscored not in (None, "") and spaced != underscored:
        raise NormalizationConflict("%s 的 social circle 与 social_circle 冲突" % path)
    return str(spaced or underscored or "").strip()


def normalize_contact_address(value: Any, path: str) -> Dict[str, Any]:
    """Normalize model address variants without changing the public field name."""
    if isinstance(value, dict):
        return deepcopy(value)
    if not isinstance(value, str) or not value.strip():
        raise NormalizationError("%s 必须是非空地址对象或字符串" % path)
    text = re.sub(r"\s+", "", value.strip())
    province = city = district = ""
    rest = text
    municipality = next((name for name in ("北京市", "天津市", "上海市", "重庆市") if text.startswith(name)), "")
    if municipality:
        province = city = municipality
        rest = text[len(municipality):]
    else:
        province_match = re.match(r"^(.+?(?:省|自治区))", rest)
        if province_match:
            province = province_match.group(1)
            rest = rest[len(province):]
        city_match = re.match(r"^(.+?(?:市|州|盟))", rest)
        if city_match:
            city = city_match.group(1)
            rest = rest[len(city):]
    district_match = re.match(r"^(.+?(?:区|县|旗))", rest)
    if district_match:
        district = district_match.group(1)
        rest = rest[len(district):]
    number_match = re.search(r"(\d+(?:号|弄|栋|座).*)$", rest)
    street_number = number_match.group(1) if number_match else ""
    street_name = rest[:number_match.start()] if number_match else rest
    result = {
        "province": province,
        "city": city,
        "district": district,
    }
    if street_name or street_number:
        result.update({"street_name": street_name, "street_number": street_number})
    return result


def _contact_from_dict(raw: Dict[str, Any], internal_id: str, path: str) -> InternalContact:
    if not isinstance(raw, dict):
        raise NormalizationError("%s 必须是联系人对象" % path)
    relation_description = raw.get("relation_description")
    if relation_description in (None, "") and "description" in raw:
        relation_description = raw.get("description")
    relation = raw.get("relation", raw.get("relaton", ""))
    age = raw.get("age", 0)
    try:
        age = int(age)
    except (TypeError, ValueError) as exc:
        raise NormalizationError("%s.age 必须是整数" % path) from exc
    return InternalContact(
        internal_id=internal_id,
        name=str(raw.get("name", "")).strip(),
        relation=str(relation or "").strip(),
        social_circle=_circle_value(raw, path),
        gender=str(raw.get("gender", "")).strip(),
        age=age,
        birth_date=_parse_date(raw.get("birth_date"), path + ".birth_date"),
        home_address=normalize_contact_address(raw.get("home_address"), path + ".home_address"),
        birth_place=normalize_contact_address(raw.get("birth_place"), path + ".birth_place"),
        personality=str(raw.get("personality", "")).strip().upper(),
        economic_level=str(raw.get("economic_level", "")).strip(),
        occupation=str(raw.get("occupation", "")).strip(),
        organization=str(raw.get("organization", "")).strip(),
        nickname=str(raw.get("nickname", "")).strip(),
        relation_description=str(relation_description or "").strip(),
    )


def normalize_relation_groups(value: Any, internal_id: str = "persona") -> List[List[InternalContact]]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise NormalizationError("relation 必须是数组")
    if not value:
        return []
    raw_groups = value if all(isinstance(item, list) for item in value) else [value]
    result = []
    for group_index, raw_group in enumerate(raw_groups):
        if not isinstance(raw_group, list):
            raise NormalizationError("relation[%d] 必须是数组" % group_index)
        contacts = []
        for contact_index, raw_contact in enumerate(raw_group):
            contact_id = "%s:g%d:c%d" % (internal_id, group_index, contact_index)
            contacts.append(_contact_from_dict(
                raw_contact, contact_id,
                "relation[%d][%d]" % (group_index, contact_index),
            ))
        if contacts:
            result.append(contacts)
    return result


def normalize_persona_input(raw: Dict[str, Any], source_index: int = 0) -> InternalPersona:
    if not isinstance(raw, dict):
        raise NormalizationError("画像必须是 JSON 对象")
    internal_id = "persona-%06d" % source_index
    data = OrderedDict((key, deepcopy(value)) for key, value in raw.items())
    groups = normalize_relation_groups(data.get("relation", []), internal_id)
    data["relation"] = []
    return InternalPersona(
        internal_id=internal_id,
        data=data,
        relation_groups=groups,
        original_top_level_keys=list(raw.keys()),
        source_index=source_index,
    )


def normalize_profile_response(raw: Any, expected_keys: List[str]) -> Dict[str, Any]:
    value = parse_json_response(raw)
    if not isinstance(value, dict):
        raise NormalizationError("基础画像响应必须是 JSON 对象")
    value.pop("note", None)
    actual = list(value.keys())
    if set(actual) != set(expected_keys):
        missing = sorted(set(expected_keys) - set(actual))
        extra = sorted(set(actual) - set(expected_keys))
        raise NormalizationError("画像字段不匹配，缺失=%s，新增=%s" % (missing, extra))
    return OrderedDict((key, deepcopy(value[key])) for key in expected_keys)


def classify_circle_type(social_circle: Any, relations: Any = "") -> str:
    text = "%s %s" % (social_circle or "", relations or "")
    if any(word in text for word in ("合租", "室友", "同住")):
        return "household"
    if any(word in text for word in ("家庭", "亲属", "家人")):
        return "family"
    if (
        any(word in text for word in ("公司", "部门", "产品线", "管理层", "职场", "工作圈"))
        and not any(word in text for word in ("前同事", "前公司", "配偶工作", "丈夫工作", "妻子工作", "父亲工作", "母亲工作"))
    ):
        return "current_work"
    if any(word in text for word in ("学校", "大学", "中学", "母校", "同学", "导师", "校友")):
        return "school"
    if any(word in text for word in ("健身", "球馆", "跑团", "跑友", "羽毛球", "篮球", "足球", "游泳", "瑜伽")):
        return "sports_club"
    if any(word in text for word in ("社区", "邻里", "业主")):
        return "neighborhood"
    if any(word in text for word in ("线上", "豆瓣", "微信群", "网友")):
        return "online_community"
    if any(word in text for word in ("社群", "协会", "行业", "同行")):
        return "professional_community"
    if any(word in text for word in ("桌游", "徒步", "摄影", "读书", "兴趣")):
        return "hobby_group"
    return "other"


def _normalize_circle(
    circle: Dict[str, Any], circle_index: int,
) -> List[RelationSlot]:
    if not isinstance(circle, dict):
        raise NormalizationError("circles[%d] 必须是对象" % circle_index)
    social_circle = str(circle.get("social_circle") or circle.get("social circle") or "").strip()
    members = circle.get("members", circle.get("slots"))
    if not social_circle or not isinstance(members, list):
        raise NormalizationError("circles[%d] 必须包含 social_circle 和 members" % circle_index)
    relation_text = " ".join(str(item.get("relation") or "") for item in members if isinstance(item, dict))
    circle_type = str(circle.get("circle_type") or classify_circle_type(social_circle, relation_text)).strip()
    circle_id = str(circle.get("circle_id") or "circle-%03d" % circle_index).strip()
    parent_anchor_id = str(circle.get("parent_anchor_id") or "").strip()
    if circle_type == "current_work":
        parent_anchor_id = "current_employer"
    shared_facts = deepcopy(circle.get("shared_facts") or {})
    if not isinstance(shared_facts, dict):
        raise NormalizationError("circles[%d].shared_facts 必须是对象" % circle_index)
    shared_facts["_structured_plan"] = True
    result = []
    for member_index, item in enumerate(members):
        if not isinstance(item, dict):
            raise NormalizationError("circles[%d].members[%d] 必须是对象" % (circle_index, member_index))
        result.append(RelationSlot(
            slot_id=str(item.get("slot_id") or "%s-slot-%03d" % (circle_id, member_index)),
            name_hint=str(item.get("name_hint") or item.get("name") or "").strip(),
            relation=str(item.get("relation") or item.get("relaton") or "").strip(),
            social_circle=social_circle,
            circle_id=circle_id,
            circle_type=circle_type,
            parent_anchor_id=parent_anchor_id,
            shared_facts=deepcopy(shared_facts),
            secondary_tags=[str(value).strip() for value in item.get("secondary_tags", []) if str(value).strip()],
        ))
    return result


def normalize_relation_plan(raw: Any) -> List[RelationSlot]:
    value = parse_json_response(raw)
    if isinstance(value, dict) and "circles" in value:
        circles = value.get("circles")
        if not isinstance(circles, list):
            raise NormalizationError("circles 必须是数组")
        return [slot for index, circle in enumerate(circles) for slot in _normalize_circle(circle, index)]
    if isinstance(value, dict):
        value = value.get("items")
    if not isinstance(value, list):
        raise NormalizationError("关系计划必须是数组或包含 items 的对象")
    if value and all(isinstance(item, dict) and ("members" in item or "slots" in item) for item in value):
        return [slot for index, circle in enumerate(value) for slot in _normalize_circle(circle, index)]
    result = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise NormalizationError("关系计划第 %d 项必须是对象" % index)
        circle = _circle_value(item, "items[%d]" % index)
        social_circle = circle
        circle_type = classify_circle_type(social_circle, item.get("relation"))
        result.append(RelationSlot(
            slot_id=str(item.get("slot_id") or "slot-%03d" % index),
            name_hint=str(item.get("name_hint") or item.get("name") or "").strip(),
            relation=str(item.get("relation") or item.get("relaton") or "").strip(),
            social_circle=circle,
            circle_id=str(item.get("circle_id") or "legacy:%s" % social_circle),
            circle_type=str(item.get("circle_type") or circle_type),
            parent_anchor_id="current_employer" if circle_type == "current_work" else str(item.get("parent_anchor_id") or ""),
            shared_facts=deepcopy(item.get("shared_facts") or {}),
            secondary_tags=[str(value).strip() for value in item.get("secondary_tags", []) if str(value).strip()],
        ))
    return result


def normalize_contact_items(raw: Any, prefix: str = "contact") -> List[InternalContact]:
    value = parse_json_response(raw)
    if isinstance(value, dict):
        value = value.get("items")
    if not isinstance(value, list):
        raise NormalizationError("联系人响应必须是数组或包含 items 的对象")
    return [
        _contact_from_dict(item, "%s-%03d" % (prefix, index), "items[%d]" % index)
        for index, item in enumerate(value)
    ]


def group_slots_by_circle(slots: List[RelationSlot]):
    groups = OrderedDict()
    for slot in slots:
        groups.setdefault(slot.circle_id or slot.social_circle, []).append(slot)
    return groups


def circle_anchor_from_slots(slots: List[RelationSlot]) -> CircleAnchor:
    if not slots:
        raise NormalizationError("无法从空槽位组创建圈子锚点")
    first = slots[0]
    return CircleAnchor(
        circle_id=first.circle_id or first.social_circle,
        circle_type=first.circle_type,
        parent_anchor_id=first.parent_anchor_id,
        social_circle=first.social_circle,
        shared_facts=deepcopy(first.shared_facts),
    )
