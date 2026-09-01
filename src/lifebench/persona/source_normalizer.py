"""LLM-backed semantic normalization for arbitrary persona inputs."""

from typing import Any, Dict, List

from src.lifebench.utils.structured_llm import StructuredLLMCaller

from .internal_models import STANDARD_PERSONA_KEYS
from .prompts.input_normalization import build_input_normalization_prompt
from .source_models import NormalizedSource


NORMALIZED_SOURCE_KEYS = (
    "explicit_facts", "soft_clues", "source_description",
    "conflicts", "unmapped_information",
)


class SourceNormalizer:
    def __init__(self, caller: StructuredLLMCaller, as_of_date: str):
        self.caller = caller
        self.as_of_date = as_of_date

    @staticmethod
    def _validate(value: Dict[str, Any]) -> List[str]:
        errors = []
        if set(value) != set(NORMALIZED_SOURCE_KEYS):
            errors.append("规范化输出必须且只能包含 %s" % (list(NORMALIZED_SOURCE_KEYS),))
            return errors
        if not isinstance(value.get("explicit_facts"), dict):
            errors.append("explicit_facts 必须是对象")
        if not isinstance(value.get("soft_clues"), dict):
            errors.append("soft_clues 必须是对象")
        if not isinstance(value.get("source_description"), str):
            errors.append("source_description 必须是字符串")
        if not isinstance(value.get("conflicts"), list):
            errors.append("conflicts 必须是数组")
        if not isinstance(value.get("unmapped_information"), list):
            errors.append("unmapped_information 必须是数组")
        facts = value.get("explicit_facts")
        if isinstance(facts, dict):
            allowed = set(STANDARD_PERSONA_KEYS) - {"relation"}
            extra = sorted(set(facts) - allowed)
            if extra:
                errors.append("explicit_facts 包含非标准字段: %s" % extra)
            if "age" in facts and not isinstance(facts["age"], int):
                errors.append("explicit_facts.age 必须是整数")
            if "salary" in facts and not isinstance(facts["salary"], (int, float)):
                errors.append("explicit_facts.salary 必须是数值")
            for key in ("home_address", "workplace", "birth_place", "body", "personality"):
                if key in facts and not isinstance(facts[key], dict):
                    errors.append("explicit_facts.%s 必须是对象" % key)
            for key in ("hobbies", "favorite_foods", "memory_date", "aim"):
                if key in facts and not isinstance(facts[key], list):
                    errors.append("explicit_facts.%s 必须是数组" % key)
        return errors

    def normalize(self, source: Any) -> NormalizedSource:
        prompt = build_input_normalization_prompt(source, self.as_of_date)
        result = self.caller.call_json_object(prompt, validator=self._validate, use_reason_model=True)
        return NormalizedSource.from_dict(result.data)
