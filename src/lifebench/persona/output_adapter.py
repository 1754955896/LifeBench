"""Convert internal persona state back to the unchanged legacy JSON contract."""

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, List

from .internal_models import InternalContact, InternalPersona, STANDARD_CONTACT_KEYS
from .validation import validate_output_contract


def contact_to_output(contact: InternalContact) -> Dict[str, Any]:
    output = OrderedDict([
        ("name", contact.name),
        ("relation", contact.relation),
        ("social circle", contact.social_circle),
        ("gender", contact.gender),
        ("age", int(contact.age)),
        ("birth_date", contact.birth_date.strftime("%Y-%m-%d")),
        ("home_address", deepcopy(contact.home_address)),
        ("birth_place", deepcopy(contact.birth_place)),
        ("personality", contact.personality),
        ("economic_level", contact.economic_level),
        ("occupation", contact.occupation),
        ("organization", contact.organization),
        ("nickname", contact.nickname),
        ("relation_description", contact.relation_description),
    ])
    if tuple(output.keys()) != STANDARD_CONTACT_KEYS:
        raise ValueError("联系人输出字段契约发生内部错误")
    return output


def to_legacy_output(persona: InternalPersona, expected_top_level_keys: List[str]) -> Dict[str, Any]:
    output = OrderedDict()
    for key in expected_top_level_keys:
        if key == "relation":
            output[key] = [
                [contact_to_output(contact) for contact in group]
                for group in persona.relation_groups
            ]
        else:
            if key not in persona.data:
                raise ValueError("缺少最终顶层字段: %s" % key)
            output[key] = deepcopy(persona.data[key])
    report = validate_output_contract(output, expected_top_level_keys)
    if not report.valid:
        raise ValueError("最终输出契约失败: %s" % "; ".join(report.messages()))
    return output
