"""Internal semantic anchors shared by persona generation stages.

The values in this module are generation metadata only.  They must never be
added to the public 27-field persona contract.
"""

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Dict, List, Optional


def _all_text(*values: Any) -> str:
    return " ".join(
        json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value or "")
        for value in values
    )


def extract_mobility_profile(
    profile: Dict[str, Any], soft_clues: Optional[Dict[str, Any]] = None,
    source_description: str = "",
) -> Dict[str, Any]:
    """Turn free-form travel clues into one stable internal preference."""
    text = _all_text(source_description, soft_clues or {}, {
        key: profile.get(key) for key in (
            "job", "occupation", "description", "lifestyle_desc", "work_desc",
            "economic_desc", "economic_situation", "daily_routine",
        )
    })
    rules = (
        ("walking", ("步行通勤", "走路上班", "主要步行")),
        ("bicycling", ("骑行通勤", "自行车通勤", "电动车通勤", "主要骑行")),
        ("transit", ("不自驾", "不开车", "无车", "没有私家车", "地铁", "公交", "公共交通")),
        ("driving", ("自驾通勤", "开车上班", "驾车通勤", "主要开车")),
    )
    primary = "driving"
    evidence: List[str] = []
    for mode, keywords in rules:
        hits = [word for word in keywords if word in text]
        if hits:
            primary, evidence = mode, hits
            break
    owns_car = None
    if any(word in text for word in ("不自驾", "不开车", "无车", "没有私家车")):
        owns_car = False
    elif any(word in text for word in ("有车", "私家车", "自驾通勤", "开车上班", "驾车通勤")):
        owns_car = True
    return {
        "primary_transport": primary,
        "owns_car": owns_car,
        "evidence": evidence,
        "explicit": bool(evidence),
    }


def _is_daily_worker(profile: Dict[str, Any]) -> bool:
    text = _all_text(profile.get("job"), profile.get("occupation"), profile.get("work_desc"))
    return not any(word in text for word in ("退休", "无业", "待业", "在校", "学生", "自由职业", "居家办公"))


def build_employer_anchor(profile: Dict[str, Any], seed: Optional[int] = None) -> Dict[str, Any]:
    """Create a deterministic fictional current-employer identity."""
    if not _is_daily_worker(profile):
        return {}
    address = profile.get("workplace") if isinstance(profile.get("workplace"), dict) else {}
    city = str(address.get("city") or address.get("province") or "本地").replace("市", "")
    job_text = _all_text(profile.get("job"), profile.get("occupation"))
    if any(word in job_text for word in ("软件", "开发", "算法", "产品", "互联网", "数据", "科技")):
        suffix, industry = "智能科技有限公司", "科技"
    elif any(word in job_text for word in ("教师", "教育", "培训")):
        suffix, industry = "教育服务有限公司", "教育"
    elif any(word in job_text for word in ("医生", "护士", "医疗", "健康")):
        suffix, industry = "健康服务有限公司", "医疗健康"
    elif any(word in job_text for word in ("工程", "制造", "机械", "设备")):
        suffix, industry = "装备技术有限公司", "工程制造"
    elif any(word in job_text for word in ("设计", "媒体", "内容", "广告", "文化")):
        suffix, industry = "文化创意有限公司", "文化创意"
    else:
        suffix, industry = "企业服务有限公司", "综合服务"
    names = ("云衡", "启澜", "知远", "辰序", "嘉禾", "明川", "和光", "远策")
    material = _all_text(city, job_text, profile.get("name"), seed)
    index = int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:8], 16) % len(names)
    return {
        "name": "%s%s%s" % (city, names[index], suffix),
        "industry": industry,
        "workplace_poi": "",
        "workplace_address": deepcopy(address),
    }


def enrich_grounding_context(
    core_locations: List[Dict[str, Any]], assignment_metrics: Optional[Dict[str, Any]],
    employer_anchor: Optional[Dict[str, Any]], mobility_profile: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    core = []
    for item in core_locations or []:
        core.append({
            "address_type": item.get("address_type", ""),
            "name": item.get("name", ""),
            "structured_address": item.get("structured_address", ""),
            "description": item.get("description", ""),
        })
    workplace = next((item for item in core if item["address_type"] == "工作地"), None)
    if workplace is not None and employer_anchor is not None:
        employer_anchor["workplace_poi"] = workplace["name"]
        employer_anchor["workplace_address_text"] = workplace["structured_address"]
    return {
        "core_pois": core,
        "commute": deepcopy(assignment_metrics or {}),
        "employer_anchor": deepcopy(employer_anchor or {}),
        "mobility_profile": deepcopy(mobility_profile or {}),
    }


def is_current_work_contact(relation: Any, social_circle: Any) -> bool:
    relation_text = str(relation or "")
    circle_text = str(social_circle or "")
    if any(word in relation_text for word in ("前同事", "前领导", "配偶同事", "丈夫同事", "妻子同事", "父亲同事", "母亲同事")):
        return False
    direct = ("同事", "上级", "下属", "直属领导", "主管", "老板", "部门负责人")
    return relation_text in direct or (
        any(word in relation_text for word in direct)
        and any(word in circle_text for word in ("公司", "工作", "职场", "部门", "同事"))
    )


def narrative_grounding_errors(narratives: Dict[str, Any], context: Dict[str, Any]) -> List[str]:
    errors = []
    workplace = next((item for item in context.get("core_pois", []) if item.get("address_type") == "工作地"), None)
    if workplace and workplace.get("name") and workplace["name"] not in str(narratives.get("work_desc") or ""):
        errors.append("work_desc 必须提及已落地工作 POI：%s" % workplace["name"])
    return errors


def _contact_value(contact: Any, field: str) -> Any:
    if isinstance(contact, dict):
        return contact.get(field)
    return getattr(contact, field.replace(" ", "_"), None)


def circle_contact_errors(
    contacts: List[Any], circle_anchor: Dict[str, Any], profile: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """Validate the shared entity appropriate for one kind of social circle."""
    errors = []
    circle_type = str(circle_anchor.get("circle_type") or "other")
    facts = circle_anchor.get("shared_facts") or {}
    circle_name = str(circle_anchor.get("social_circle") or circle_anchor.get("circle_id") or "")
    if circle_type in {"sports_club", "hobby_group"}:
        try:
            distance = float(facts.get("distance_from_home_km"))
            maximum = float(facts.get("max_home_distance_km"))
            if distance > maximum:
                errors.append("圈子 %s 的兴趣地点距离住宅过远：%.2fkm > %.2fkm" % (circle_name, distance, maximum))
        except (TypeError, ValueError):
            if facts.get("place_location"):
                errors.append("圈子 %s 缺少可验证的住宅距离" % circle_name)
    if circle_type == "current_work":
        expected = str(facts.get("organization") or "")
        for index, contact in enumerate(contacts):
            if expected and str(_contact_value(contact, "organization") or "") != expected:
                errors.append("圈子 %s 联系人[%d]未继承当前雇主 %s" % (circle_name, index, expected))
    elif circle_type == "school":
        institution = str(facts.get("institution_name") or "")
        for index, contact in enumerate(contacts):
            description = str(_contact_value(contact, "relation_description") or "")
            if institution and institution not in description:
                errors.append("圈子 %s 联系人[%d]的关系描述未提及共同学校 %s" % (circle_name, index, institution))
    elif circle_type == "sports_club":
        venue = str(facts.get("venue_name") or "")
        for index, contact in enumerate(contacts):
            description = str(_contact_value(contact, "relation_description") or "")
            if venue and venue not in description:
                errors.append("圈子 %s 联系人[%d]的关系描述未提及共同场馆 %s" % (circle_name, index, venue))
    elif circle_type == "household":
        expected_address = facts.get("shared_address") or (profile or {}).get("home_address") or {}
        for index, contact in enumerate(contacts):
            actual = _contact_value(contact, "home_address") or {}
            if isinstance(expected_address, dict) and isinstance(actual, dict):
                mismatch = any(
                    expected_address.get(key) not in (None, "")
                    and actual.get(key) != expected_address.get(key)
                    for key in ("province", "city", "district", "street_name", "street_number")
                )
                if mismatch:
                    errors.append("圈子 %s 联系人[%d]未使用共同住宅地址" % (circle_name, index))
            else:
                errors.append("圈子 %s 联系人[%d]共同住宅地址类型错误" % (circle_name, index))
    elif circle_type == "neighborhood":
        region = str(facts.get("neighborhood_region") or "")
        for index, contact in enumerate(contacts):
            address = _contact_value(contact, "home_address") or {}
            if facts.get("_structured_plan") and region and (
                not isinstance(address, dict) or str(address.get("district") or "") != region
            ):
                errors.append("圈子 %s 联系人[%d]不在共同社区行政区 %s" % (circle_name, index, region))
    elif circle_type in {"professional_community", "hobby_group", "online_community"}:
        anchors = [
            str(facts.get(key) or "").strip()
            for key in ("group_name", "platform", "meeting_place")
            if str(facts.get(key) or "").strip()
        ]
        for index, contact in enumerate(contacts):
            description = str(_contact_value(contact, "relation_description") or "")
            if anchors and not any(value in description for value in anchors):
                errors.append("圈子 %s 联系人[%d]的关系描述未体现共享社群实体" % (circle_name, index))
    return errors


def semantic_quality_errors(
    persona: Dict[str, Any], locations: Optional[List[Dict[str, Any]]],
    context: Optional[Dict[str, Any]],
) -> List[str]:
    context = context or {}
    errors = narrative_grounding_errors(persona, context)
    anchor = context.get("employer_anchor") or {}
    expected_org = str(anchor.get("name") or "")
    work_orgs = []
    for group in persona.get("relation") or []:
        for contact in group if isinstance(group, list) else []:
            if is_current_work_contact(contact.get("relation"), contact.get("social circle")):
                work_orgs.append(str(contact.get("organization") or ""))
    if expected_org and any(org != expected_org for org in work_orgs):
        errors.append("当前工作联系人 organization 必须统一为内部雇主锚点 %s" % expected_org)
    circle_anchors = context.get("circle_anchors") or []
    parent_signatures: Dict[str, set] = {}
    for circle_anchor in circle_anchors:
        parent_id = str(circle_anchor.get("parent_anchor_id") or "")
        facts = circle_anchor.get("shared_facts") or {}
        circle_type = circle_anchor.get("circle_type")
        shared_value = {
            "current_work": facts.get("organization"),
            "school": facts.get("institution_name"),
            "sports_club": facts.get("venue_name"),
            "household": json.dumps(facts.get("shared_address") or {}, ensure_ascii=False, sort_keys=True),
        }.get(circle_type)
        if parent_id and shared_value not in (None, "", "{}"):
            parent_signatures.setdefault(parent_id, set()).add(str(shared_value))
    for parent_id, signatures in parent_signatures.items():
        if len(signatures) > 1:
            errors.append("父级圈子锚点 %s 存在冲突共享事实" % parent_id)
    for circle_anchor in circle_anchors:
        circle_contacts = [
            contact
            for group in persona.get("relation") or [] if isinstance(group, list)
            for contact in group
            if str(contact.get("social circle") or "") == str(circle_anchor.get("social_circle") or "")
        ]
        errors.extend(circle_contact_errors(circle_contacts, circle_anchor, persona))
    if "contact_address_audit" in context:
        audits = context.get("contact_address_audit") or []
        contact_count = sum(len(group) for group in persona.get("relation") or [] if isinstance(group, list))
        if len(audits) != contact_count:
            errors.append("联系人真实地址审计数量与联系人数不一致")
        non_household_locations = []
        circle_types = {
            str(item.get("circle_id") or ""): str(item.get("circle_type") or "")
            for item in circle_anchors
        }
        for audit in audits:
            if not audit.get("home_address") or not audit.get("birth_place_verified"):
                errors.append("联系人 %s 的住宅或出生地未通过地图验证" % audit.get("contact_name", ""))
            if circle_types.get(str(audit.get("circle_id") or "")) != "household":
                location = str(audit.get("home_location") or "")
                if not location:
                    errors.append("联系人 %s 的真实住宅缺少坐标" % audit.get("contact_name", ""))
                else:
                    non_household_locations.append(location)
        duplicate_locations = {
            location for location in non_household_locations
            if non_household_locations.count(location) > 2
        }
        if duplicate_locations:
            errors.append("非同住联系人过度复用同一住宅 POI: %s" % sorted(duplicate_locations))
    if locations is not None:
        location_names = {str(item.get("name") or "") for item in locations}
        for fixed in context.get("circle_fixed_pois") or []:
            expected_name = "关系圈固定地·%s" % str(fixed.get("name") or "")
            if expected_name not in location_names:
                errors.append("location sidecar 缺少关系圈固定地点 %s" % fixed.get("name", ""))
    commute = context.get("commute") or {}
    mobility = context.get("mobility_profile") or {}
    if mobility.get("explicit") and commute.get("commute_transport") and commute["commute_transport"] != mobility.get("primary_transport"):
        errors.append("地址分配交通方式与结构化交通偏好不一致")
    if locations is not None:
        common_count = sum(str(item.get("name") or "").startswith("常去地·") for item in locations)
        if common_count < 3:
            errors.append("常去地点少于 3 个")
    return errors
