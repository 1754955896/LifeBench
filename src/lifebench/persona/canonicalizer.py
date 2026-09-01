"""Build the fixed public persona skeleton from sparse normalized facts."""

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, List

from .internal_models import STANDARD_PERSONA_KEYS
from .source_models import CanonicalSeed, NormalizedSource


NARRATIVE_FIELDS = frozenset({
    "healthy_desc", "lifestyle_desc", "economic_desc", "work_desc",
    "experience_desc", "description",
})


def empty_persona_scaffold() -> Dict[str, Any]:
    result = OrderedDict((key, None) for key in STANDARD_PERSONA_KEYS)
    result["relation"] = []
    return result


def _merge_partial(target: Any, source: Any) -> Any:
    if isinstance(target, dict) and isinstance(source, dict):
        merged = deepcopy(target)
        for key, value in source.items():
            merged[key] = _merge_partial(merged.get(key), value)
        return merged
    return deepcopy(source)


def canonicalize_source(source: NormalizedSource) -> CanonicalSeed:
    if source.conflicts:
        messages = [str(item.get("message") or item) if isinstance(item, dict) else str(item) for item in source.conflicts]
        raise ValueError("输入信息存在冲突: %s" % "; ".join(messages))
    allowed = set(STANDARD_PERSONA_KEYS) - {"relation"}
    extra = sorted(set(source.explicit_facts) - allowed)
    if extra:
        raise ValueError("规范化结果包含非标准字段: %s" % extra)

    scaffold = empty_persona_scaffold()
    locked = OrderedDict()
    narrative_fragments = []
    for key, value in source.explicit_facts.items():
        if value is None or value == "":
            continue
        if key in NARRATIVE_FIELDS:
            if value:
                narrative_fragments.append(str(value))
            continue
        scaffold[key] = _merge_partial(scaffold.get(key), value)
        locked[key] = deepcopy(value)

    for field in NARRATIVE_FIELDS:
        scaffold[field] = ""
    return CanonicalSeed(
        data=scaffold,
        locked_facts=locked,
        soft_clues=deepcopy(source.soft_clues),
        source_description="\n".join(
            item for item in [source.source_description] + narrative_fragments if item
        ),
    )


def locked_fact_errors(actual: Dict[str, Any], locked: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    def compare(actual_value: Any, expected_value: Any, path: str) -> None:
        if isinstance(expected_value, dict):
            if not isinstance(actual_value, dict):
                errors.append("%s 必须保持为对象" % path)
                return
            for key, value in expected_value.items():
                if key not in actual_value:
                    errors.append("%s.%s 缺失输入锁定值" % (path, key))
                else:
                    compare(actual_value[key], value, "%s.%s" % (path, key))
            return
        if isinstance(expected_value, list):
            if not isinstance(actual_value, list) or not all(item in actual_value for item in expected_value):
                errors.append("%s 必须包含输入值 %r" % (path, expected_value))
            return
        if actual_value != expected_value:
            errors.append("%s 修改了输入锁定值，实际=%r，期望=%r" % (path, actual_value, expected_value))

    for key, expected in locked.items():
        if key not in actual:
            errors.append("%s 缺失输入锁定字段" % key)
        else:
            compare(actual[key], expected, key)
    return errors
