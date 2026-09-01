"""Narrow LLM stages for persona synthesis."""

import random
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

from src.lifebench.utils.structured_llm import StructuredLLMCaller

from .constraints import apply_derived_values, validate_rules
from .canonicalizer import locked_fact_errors
from .internal_models import InternalContact, InternalPersona, RelationSlot, VALID_CIRCLE_TYPES, VALID_MBTI
from .grounding import circle_contact_errors, is_current_work_contact, narrative_grounding_errors
from .normalization import (
    group_slots_by_circle,
    circle_anchor_from_slots,
    normalize_contact_items,
    normalize_persona_input,
    normalize_profile_response,
    normalize_relation_plan,
)
from .prompts import (
    ABSTRACT_TRAIT_MARKERS,
    ENRICH_DIMENSIONS,
    ENRICH_FIELDS,
    NARRATIVE_FIELDS,
    build_base_profile_prompt,
    build_contact_group_prompt,
    build_enrich_consistency_prompt,
    build_enrich_prompt,
    build_narrative_prompt,
    build_persona_consistency_prompt,
    build_profile_enrich_prompt,
    build_relation_plan_prompt,
    build_variant_blueprint_prompt,
)
from .variant_models import VARIANT_BLUEPRINT_KEYS, VariantBlueprint
from .validation import validate_profile_keys


@dataclass
class GenerationContext:
    as_of_date: date
    caller: StructuredLLMCaller
    references: Dict[str, List[str]]
    variant_instruction: Optional[str] = None
    min_contacts: int = 16
    max_contacts: int = 28
    locked_facts: Dict[str, Any] = field(default_factory=dict)
    soft_clues: Dict[str, Any] = field(default_factory=dict)
    source_description: str = ""
    variant_blueprint: Dict[str, Any] = field(default_factory=dict)
    diversity: str = "low"
    variant_index: int = 0
    run_seed: Optional[int] = None
    employer_anchor: Dict[str, Any] = field(default_factory=dict)
    mobility_profile: Dict[str, Any] = field(default_factory=dict)
    grounding_context: Dict[str, Any] = field(default_factory=dict)
    circle_anchors: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def as_of_text(self) -> str:
        return self.as_of_date.strftime("%Y-%m-%d")


def generate_base_profile(seed_person: Dict[str, Any], context: GenerationContext):
    seed = deepcopy(seed_person)
    if "relation" in seed:
        seed["relation"] = []
    expected = list(seed.keys())
    prompt = build_base_profile_prompt(
        seed, context.references, context.as_of_text, context.variant_instruction,
        locked_facts=context.locked_facts,
        soft_clues=context.soft_clues,
        source_description=context.source_description,
        variant_blueprint=context.variant_blueprint,
    )
    def validate(data):
        key_report = validate_profile_keys(data, expected, "base")
        if not key_report.valid:
            return key_report.messages()
        try:
            normalized = normalize_profile_response(data, expected)
            internal = normalize_persona_input(normalized)
            apply_derived_values(internal, context.as_of_date)
            errors = locked_fact_errors(internal.data, context.locked_facts)
            errors.extend([
                "%s %s: %s" % (item.rule_id, item.path, item.message)
                for item in validate_rules(internal, context.as_of_date)
                if item.severity == "error"
            ])
            return errors
        except Exception as exc:
            return [str(exc)]

    result = context.caller.call_json_object(prompt, validator=validate)
    return normalize_profile_response(result.data, expected), result.prompt_hash


def generate_narratives(profile: Dict[str, Any], context: GenerationContext):
    prompt = build_narrative_prompt(
        profile, context.as_of_text, context.source_description,
        context.variant_blueprint, context.grounding_context,
    )

    def validate(data):
        report = validate_profile_keys(data, list(NARRATIVE_FIELDS), "narrative")
        return report.messages() + narrative_grounding_errors(data, context.grounding_context)

    result = context.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
    narratives = normalize_profile_response(result.data, list(NARRATIVE_FIELDS))
    return narratives, result.prompt_hash


_PLACEHOLDER_MARKERS = (
    "某某", "某大学", "某中学", "某公司", "某医院", "某地", "某市",
    "某单位", "某机构", "某场馆", "某品牌", "待定", "TBD", "占位",
)


def _placeholder_violations(data: Dict[str, Any]) -> List[str]:
    errors = []
    for key, value in (data or {}).items():
        text = value if isinstance(value, str) else str(value or "")
        for marker in _PLACEHOLDER_MARKERS:
            if marker in text:
                errors.append("%s 不得出现占位符 %s" % (key, marker))
    return errors


def generate_profile_enrich(profile: Dict[str, Any], context: GenerationContext):
    """对稀疏的基础画像做一次性补全与丰富，输出完整画像，其余字段保持不变。"""
    expected = list(profile.keys())
    prompt = build_profile_enrich_prompt(
        profile, context.as_of_text, expected,
        references=context.references,
        locked_facts=context.locked_facts,
        soft_clues=context.soft_clues,
        source_description=context.source_description,
        variant_blueprint=context.variant_blueprint,
    )

    def validate(data):
        key_report = validate_profile_keys(data, expected, "profile_enrich")
        if not key_report.valid:
            return key_report.messages()
        try:
            normalized = normalize_profile_response(data, expected)
            internal = normalize_persona_input(normalized)
            apply_derived_values(internal, context.as_of_date)
            errors = locked_fact_errors(internal.data, context.locked_facts)
            errors.extend([
                "%s %s: %s" % (item.rule_id, item.path, item.message)
                for item in validate_rules(internal, context.as_of_date)
                if item.severity == "error"
            ])
            errors.extend(_placeholder_violations(data))
            return errors
        except Exception as exc:
            return [str(exc)]

    result = context.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
    return normalize_profile_response(result.data, expected), result.prompt_hash


_ENRICH_CONSISTENCY_RETRIES = 2


def _enrich_consistency_issues(profile: Dict[str, Any], enriched: Dict[str, Any], context: GenerationContext) -> List[str]:
    """让 LLM 审查改写后的描述是否与冻结事实冲突，返回冲突列表。"""
    prompt = build_enrich_consistency_prompt(
        profile, enriched, context.as_of_text,
        grounding_context=context.grounding_context,
        circle_anchors=context.circle_anchors,
    )

    def validate(data):
        if set(data) != {"inconsistencies"}:
            return ["一致性审查必须且只能输出 inconsistencies 字段"]
        if not isinstance(data.get("inconsistencies"), list):
            return ["inconsistencies 必须是数组"]
        return []

    result = context.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
    return [str(item) for item in result.data.get("inconsistencies", []) if str(item).strip()]


def generate_enrich(profile: Dict[str, Any], context: GenerationContext):
    """随机抽取 2～4 个补充维度，把独特兴趣/偏好/习惯/癖好/经历织入描述字段。

    生成后用 LLM 审查一致性，若发现与冻结事实冲突则回填重写，最多修复两次。
    """
    seed = context.run_seed if context.run_seed is not None else context.variant_index
    rng = random.Random(seed)
    dimensions = rng.sample(ENRICH_DIMENSIONS, rng.randint(2, 4))

    def build_prompt():
        return build_enrich_prompt(
            profile, context.as_of_text, dimensions,
            grounding_context=context.grounding_context,
            circle_anchors=context.circle_anchors,
        )

    def validate(data):
        report = validate_profile_keys(data, list(ENRICH_FIELDS), "enrich")
        return report.messages() + _placeholder_violations(data)

    result = context.caller.call_json_object(build_prompt(), validator=validate, use_reason_model=True)
    enriched = normalize_profile_response(result.data, list(ENRICH_FIELDS))
    prompt_hash = result.prompt_hash
    for _ in range(_ENRICH_CONSISTENCY_RETRIES):
        issues = _enrich_consistency_issues(profile, enriched, context)
        if not issues:
            break
        repair_prompt = (
            build_prompt()
            + "\n\n上一次改写与冻结事实冲突，只修正下列问题并重新输出完整 JSON 对象（仅 %s 字段）：\n- "
            % (list(ENRICH_FIELDS),)
            + "\n- ".join(issues)
        )
        result = context.caller.call_json_object(repair_prompt, validator=validate, use_reason_model=True)
        enriched = normalize_profile_response(result.data, list(ENRICH_FIELDS))
        prompt_hash = result.prompt_hash
    return enriched, prompt_hash


def generate_persona_consistency(persona: InternalPersona, context: GenerationContext):
    """定稿前的一致性审查：把抽象/自相矛盾的 traits 重写为具体行为特质，并修正社交圈名与描述的冲突。"""
    profile_view = {key: deepcopy(value) for key, value in persona.data.items() if key != "relation"}
    relation_view = [
        {
            "group_index": group_index,
            "social_circle": group[0].social_circle if group else "",
            "members": [
                {
                    "name": contact.name,
                    "relation": contact.relation,
                    "relation_description": contact.relation_description,
                }
                for contact in group
            ],
        }
        for group_index, group in enumerate(persona.relation_groups)
    ]
    prompt = build_persona_consistency_prompt(
        profile_view, relation_view, context.as_of_text, soft_clues=context.soft_clues,
    )

    group_count = len(persona.relation_groups)

    def validate(data):
        if not isinstance(data, dict):
            return ["一致性修正必须输出 JSON 对象"]
        if set(data) != {"traits", "circle_renames"}:
            return ["一致性修正必须且只能输出 traits 和 circle_renames 字段"]
        errors = []
        traits = data.get("traits")
        if not isinstance(traits, list) or not 2 <= len(traits) <= 4:
            errors.append("traits 必须是 2～4 项字符串数组")
        else:
            for index, trait in enumerate(traits):
                text = str(trait or "").strip()
                if not text:
                    errors.append("traits[%d] 不能为空" % index)
                    continue
                for marker in ABSTRACT_TRAIT_MARKERS:
                    if marker in text:
                        errors.append("traits[%d] 不得使用抽象价值观词「%s」" % (index, marker))
                        break
        renames = data.get("circle_renames")
        if not isinstance(renames, list):
            errors.append("circle_renames 必须是数组")
        else:
            seen_indices = set()
            final_names = {
                group_index: str(group[0].social_circle).strip()
                for group_index, group in enumerate(persona.relation_groups)
                if group
            }
            for index, item in enumerate(renames):
                if not isinstance(item, dict):
                    errors.append("circle_renames[%d] 必须是对象" % index)
                    continue
                gi = item.get("group_index")
                name = str(item.get("social_circle") or "").strip()
                if not isinstance(gi, int) or not 0 <= gi < group_count:
                    errors.append("circle_renames[%d].group_index 必须是 [0,%d) 的整数" % (index, group_count))
                    continue
                if gi in seen_indices:
                    errors.append("circle_renames 不能重复修改同一组")
                seen_indices.add(gi)
                if not name:
                    errors.append("circle_renames[%d].social_circle 不能为空" % index)
                else:
                    final_names[gi] = name
            values = [name for name in final_names.values() if name]
            if len(values) != len(set(values)):
                errors.append("修正后各圈名不得重复")
        errors.extend(_placeholder_violations(data))
        return errors

    result = context.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
    data = result.data
    traits = [str(item).strip() for item in data.get("traits", []) if str(item).strip()]
    if traits and isinstance(persona.data.get("personality"), dict):
        persona.data["personality"]["traits"] = traits
    for item in data.get("circle_renames") or []:
        if not isinstance(item, dict):
            continue
        gi = item.get("group_index")
        name = str(item.get("social_circle") or "").strip()
        if not name or not isinstance(gi, int) or not 0 <= gi < len(persona.relation_groups):
            continue
        for contact in persona.relation_groups[gi]:
            contact.social_circle = name
    return result.prompt_hash


def generate_relation_slots(persona: InternalPersona, context: GenerationContext):
    prompt = build_relation_plan_prompt(
        persona.data, context.as_of_text, context.min_contacts,
        context.max_contacts, context.variant_blueprint,
        context.employer_anchor, context.grounding_context,
    )

    def validate(items):
        try:
            slots = normalize_relation_plan(items)
        except Exception as exc:
            return [str(exc)]
        errors = []
        if not context.min_contacts <= len(slots) <= context.max_contacts:
            errors.append("联系人槽位数量必须在 %d～%d" % (context.min_contacts, context.max_contacts))
        if any(not slot.relation or not slot.social_circle for slot in slots):
            errors.append("每个槽位必须有 relation 和 social_circle")
        ids = [slot.slot_id for slot in slots]
        if len(ids) != len(set(ids)):
            errors.append("slot_id 必须唯一")
        if isinstance(items, list) and items and all(isinstance(circle, dict) and ("members" in circle or "slots" in circle) for circle in items):
            circle_ids = [str(circle.get("circle_id") or "") for circle in items]
            circle_names = [str(circle.get("social_circle") or circle.get("social circle") or "") for circle in items]
            if any(not value for value in circle_ids) or len(circle_ids) != len(set(circle_ids)):
                errors.append("circle_id 必须非空且唯一")
            if len(circle_names) != len(set(circle_names)):
                errors.append("相同 social_circle 必须合并为一个圈子计划")
            for circle_index, circle in enumerate(items):
                circle_type = str(circle.get("circle_type") or "") if isinstance(circle, dict) else ""
                facts = circle.get("shared_facts") or {} if isinstance(circle, dict) else {}
                if circle_type not in VALID_CIRCLE_TYPES:
                    errors.append("items[%d].circle_type 非法" % circle_index)
                if circle_type == "school" and not str(facts.get("institution_name") or "").strip():
                    errors.append("items[%d].shared_facts.institution_name 不能为空" % circle_index)
                if circle_type == "sports_club" and not str(facts.get("venue_name") or "").strip():
                    errors.append("items[%d].shared_facts.venue_name 不能为空" % circle_index)
                if circle_type in {"professional_community", "hobby_group"} and not str(facts.get("group_name") or "").strip():
                    errors.append("items[%d].shared_facts.group_name 不能为空" % circle_index)
                if circle_type == "online_community" and (
                    not str(facts.get("platform") or "").strip()
                    or not str(facts.get("group_name") or "").strip()
                ):
                    errors.append("items[%d] 线上社群必须提供 platform 和 group_name" % circle_index)
                if circle_type == "current_work" and not str(context.employer_anchor.get("name") or "").strip():
                    errors.append("items[%d] 声明当前工作圈，但人物没有当前雇主锚点" % circle_index)
        return errors

    result = context.caller.call_json_array(prompt, validator=validate)
    slots = normalize_relation_plan(result.data)
    anchors = []
    for group in group_slots_by_circle(slots).values():
        anchor = circle_anchor_from_slots(group)
        if anchor.circle_type == "current_work":
            anchor.parent_anchor_id = "current_employer"
            anchor.shared_facts.update({
                "organization": context.employer_anchor.get("name", ""),
                "workplace_poi": context.employer_anchor.get("workplace_poi", ""),
            })
        elif anchor.circle_type == "school":
            institution = str(anchor.shared_facts.get("institution_name") or "").strip()
            if institution:
                anchor.parent_anchor_id = "school:%s" % institution
        elif anchor.circle_type == "sports_club":
            venue = str(anchor.shared_facts.get("venue_name") or "").strip()
            if venue:
                anchor.parent_anchor_id = "venue:%s" % venue
        elif anchor.circle_type == "household":
            anchor.parent_anchor_id = "current_home"
            anchor.shared_facts["shared_address"] = deepcopy(persona.data.get("home_address") or {})
        elif anchor.circle_type == "neighborhood":
            home = persona.data.get("home_address") or {}
            anchor.shared_facts.setdefault("neighborhood_region", home.get("district", ""))
        for slot in group:
            slot.parent_anchor_id = anchor.parent_anchor_id
            slot.shared_facts = deepcopy(anchor.shared_facts)
        anchors.append({
            "circle_id": anchor.circle_id,
            "circle_type": anchor.circle_type,
            "parent_anchor_id": anchor.parent_anchor_id,
            "social_circle": anchor.social_circle,
            "shared_facts": deepcopy(anchor.shared_facts),
        })
    context.circle_anchors = anchors
    context.grounding_context["circle_anchors"] = deepcopy(anchors)
    return slots, result.prompt_hash


def _slot_dict(slot: RelationSlot) -> Dict[str, Any]:
    return {
        "slot_id": slot.slot_id,
        "name_hint": slot.name_hint,
        "relation": slot.relation,
        "social_circle": slot.social_circle,
        "secondary_tags": list(slot.secondary_tags),
    }


def generate_contact_group(
    persona: InternalPersona,
    slots: List[RelationSlot],
    context: GenerationContext,
    group_index: int,
):
    slot_dicts = [_slot_dict(slot) for slot in slots]
    anchor = circle_anchor_from_slots(slots)
    circle_context = {
        "circle_id": anchor.circle_id,
        "circle_type": anchor.circle_type,
        "parent_anchor_id": anchor.parent_anchor_id,
        "social_circle": anchor.social_circle,
        "shared_facts": deepcopy(anchor.shared_facts),
    }
    prompt = build_contact_group_prompt(
        persona.data, slot_dicts, context.as_of_text, context.variant_blueprint,
        context.employer_anchor, context.grounding_context, circle_context,
    )

    def validate(items):
        try:
            contacts = normalize_contact_items(items, "%s:g%d" % (persona.internal_id, group_index))
        except Exception as exc:
            return [str(exc)]
        errors = []
        if len(contacts) != len(slots):
            return ["联系人数必须与槽位数一致"]
        for index, (contact, slot) in enumerate(zip(contacts, slots)):
            if contact.relation != slot.relation:
                errors.append("items[%d].relation 必须为 %s" % (index, slot.relation))
            if contact.social_circle != slot.social_circle:
                errors.append("items[%d].social_circle 必须为 %s" % (index, slot.social_circle))
            if contact.personality not in VALID_MBTI:
                errors.append("items[%d].personality 不是标准 MBTI" % index)
            employer_name = str(context.employer_anchor.get("name") or "")
            if employer_name and is_current_work_contact(contact.relation, contact.social_circle) and contact.organization != employer_name:
                errors.append("items[%d].organization 必须为当前雇主锚点 %s" % (index, employer_name))
            try:
                contact.age = persona_age(contact.birth_date, context.as_of_date)
            except ValueError as exc:
                errors.append("items[%d].birth_date: %s" % (index, exc))
        errors.extend(circle_contact_errors(contacts, circle_context, persona.data))
        if not errors:
            prospective = deepcopy(persona)
            prospective.relation_groups = list(persona.relation_groups) + [contacts]
            errors.extend(
                "%s %s: %s" % (item.rule_id, item.path, item.message)
                for item in validate_rules(prospective, context.as_of_date)
                if item.severity == "error"
            )
        return errors

    result = context.caller.call_json_array(prompt, validator=validate)
    contacts = normalize_contact_items(result.data, "%s:g%d" % (persona.internal_id, group_index))
    for contact in contacts:
        contact.age = persona_age(contact.birth_date, context.as_of_date)
    return contacts, result.prompt_hash


def persona_age(birth: date, as_of_date: date) -> int:
    from .constraints import calculate_age
    return calculate_age(birth, as_of_date)


def group_relation_slots(slots: List[RelationSlot]):
    return group_slots_by_circle(slots)


def generate_variant_blueprint(
    context: GenerationContext,
    previous_blueprints: Optional[List[Dict[str, Any]]] = None,
) -> VariantBlueprint:
    variant_seed = context.run_seed if context.run_seed is not None else context.variant_index
    prompt = build_variant_blueprint_prompt(
        context.locked_facts,
        context.soft_clues,
        context.source_description,
        context.references,
        context.diversity,
        context.variant_index,
        int(variant_seed),
        previous_blueprints or [],
    )

    def validate(data):
        errors = []
        if set(data) != set(VARIANT_BLUEPRINT_KEYS):
            return ["变体蓝图字段必须且只能是 %s" % (list(VARIANT_BLUEPRINT_KEYS),)]
        for key in VARIANT_BLUEPRINT_KEYS[:6]:
            if not isinstance(data.get(key), str) or not data[key].strip():
                errors.append("%s 必须是非空字符串" % key)
        for key in VARIANT_BLUEPRINT_KEYS[6:]:
            if not isinstance(data.get(key), list):
                errors.append("%s 必须是数组" % key)
        return errors

    result = context.caller.call_json_object(prompt, validator=validate, use_reason_model=True)
    return VariantBlueprint.from_dict(result.data)
