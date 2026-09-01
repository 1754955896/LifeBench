"""Stage and final validation for persona generation."""

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, List

from .constraints import Violation, validate_rules
from .grounding import is_current_work_contact
from .internal_models import STANDARD_CONTACT_KEYS, InternalPersona


@dataclass
class ValidationReport:
    valid: bool
    stage: str
    violations: List[Violation]

    def messages(self) -> List[str]:
        return ["%s %s: %s" % (item.rule_id, item.path, item.message) for item in self.violations]


def validate_profile_keys(data: Dict[str, Any], expected_keys: List[str], stage: str = "profile") -> ValidationReport:
    actual = list(data.keys()) if isinstance(data, dict) else []
    violations = []
    if set(actual) != set(expected_keys) or len(actual) != len(expected_keys):
        violations.append(Violation(
            "KEY-001", "$", "error", "顶层字段与输入不一致",
            actual, list(expected_keys),
        ))
    return ValidationReport(not violations, stage, violations)


def validate_internal_persona(persona: InternalPersona, as_of_date: date, stage: str = "final") -> ValidationReport:
    violations = validate_rules(persona, as_of_date)
    return ValidationReport(not any(item.severity == "error" for item in violations), stage, violations)


def validate_output_contract(output: Dict[str, Any], expected_keys: List[str]) -> ValidationReport:
    violations = []
    current_work_organizations = []
    if not isinstance(output, dict) or list(output.keys()) != list(expected_keys):
        violations.append(Violation("KEY-001", "$", "error", "最终顶层字段或顺序不一致", list(output.keys()) if isinstance(output, dict) else type(output).__name__, list(expected_keys)))
    relation = output.get("relation") if isinstance(output, dict) else None
    if not isinstance(relation, list) or any(not isinstance(group, list) for group in relation):
        violations.append(Violation("KEY-002", "relation", "error", "最终 relation 必须是二维数组", relation))
    elif isinstance(relation, list):
        expected_contact_keys = set(STANDARD_CONTACT_KEYS)
        for group_index, group in enumerate(relation):
            for contact_index, contact in enumerate(group):
                path = "relation[%d][%d]" % (group_index, contact_index)
                if not isinstance(contact, dict) or set(contact.keys()) != expected_contact_keys:
                    violations.append(Violation("KEY-002", path, "error", "联系人字段必须保持固定 14 项", list(contact.keys()) if isinstance(contact, dict) else type(contact).__name__, list(STANDARD_CONTACT_KEYS)))
                elif "social_circle" in contact or "social circle" not in contact:
                    violations.append(Violation("KEY-002", path, "error", "最终联系人必须使用 social circle 键"))
                else:
                    for field in ("home_address", "birth_place"):
                        if not isinstance(contact.get(field), dict):
                            violations.append(Violation(
                                "ADDR-001", path + "." + field, "error",
                                "联系人地址必须统一为 JSON 对象", type(contact.get(field)).__name__, "object",
                            ))
                    if is_current_work_contact(contact.get("relation"), contact.get("social circle")):
                        organization = str(contact.get("organization") or "").strip()
                        if organization:
                            current_work_organizations.append(organization)
    if len(set(current_work_organizations)) > 1:
        violations.append(Violation(
            "WORK-001", "relation", "error",
            "当前同事、上级和下属必须共享同一雇主 organization",
            sorted(set(current_work_organizations)), "single employer anchor",
        ))
    return ValidationReport(not violations, "output", violations)
