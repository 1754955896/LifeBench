"""Small structured-output wrapper built on the existing LLM helpers.

This module is intentionally domain agnostic. Business validation is supplied by
the caller through a callback.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

@dataclass
class StructuredCallResult:
    data: Any
    attempts: int
    prompt_hash: str
    errors: List[str] = field(default_factory=list)


class StructuredOutputError(RuntimeError):
    def __init__(self, message: str, errors: Optional[List[str]] = None):
        super().__init__(message)
        self.errors = errors or []


def parse_json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        raise ValueError("响应不是 JSON 字符串或对象")
    text = value.strip()
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        text = match.group(1)
    return json.loads(text)


def _validation_errors(validator: Optional[Callable[[Any], Any]], data: Any) -> List[str]:
    if validator is None:
        return []
    result = validator(data)
    if result is None or result is True:
        return []
    if result is False:
        return ["结构校验失败"]
    if isinstance(result, list):
        return [str(item) for item in result]
    if hasattr(result, "valid"):
        if result.valid:
            return []
        if hasattr(result, "messages"):
            return list(result.messages())
        return [str(item) for item in getattr(result, "violations", [])]
    return [str(result)]


class StructuredLLMCaller:
    def __init__(
        self,
        max_retries: int = 2,
        object_call: Optional[Callable[[str], str]] = None,
        reason_object_call: Optional[Callable[[str], str]] = None,
    ):
        if max_retries < 0:
            raise ValueError("max_retries 不能小于 0")
        if object_call is None or reason_object_call is None:
            from .llm_call import llm_call_j, llm_call_reason_j
            object_call = object_call or llm_call_j
            reason_object_call = reason_object_call or llm_call_reason_j
        self.max_retries = max_retries
        self.object_call = object_call
        self.reason_object_call = reason_object_call

    def call_json_object(
        self,
        prompt: str,
        validator: Optional[Callable[[Any], Any]] = None,
        use_reason_model: bool = False,
        retry_prompt_builder: Optional[
            Callable[[str, List[str], int], str]
        ] = None,
    ) -> StructuredCallResult:
        errors = []
        current_prompt = prompt
        call = self.reason_object_call if use_reason_model else self.object_call
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        for attempt in range(1, self.max_retries + 2):
            try:
                raw = call(current_prompt)
                if raw is None or (isinstance(raw, str) and not raw.strip()):
                    raise ValueError("empty_response")
                data = parse_json(raw)
                if not isinstance(data, dict):
                    raise ValueError("响应顶层必须是 JSON 对象")
                validation_errors = _validation_errors(validator, data)
                if not validation_errors:
                    return StructuredCallResult(data, attempt, prompt_hash, errors)
                errors.extend(validation_errors)
            except Exception as exc:
                errors.append(str(exc))
            if attempt <= self.max_retries:
                next_attempt = attempt + 1
                if retry_prompt_builder is not None:
                    current_prompt = retry_prompt_builder(
                        prompt, list(errors), next_attempt,
                    )
                else:
                    current_prompt = (
                        prompt
                        + "\n\n上一次输出未通过校验。只修正下列错误并重新输出完整 JSON 对象：\n- "
                        + "\n- ".join(errors[-10:])
                    )
        raise StructuredOutputError("结构化 JSON 调用重试耗尽", errors)

    def call_json_array(
        self,
        prompt: str,
        validator: Optional[Callable[[Any], Any]] = None,
        use_reason_model: bool = False,
    ) -> StructuredCallResult:
        def wrapped_validator(data):
            items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(items, list):
                return ["顶层对象必须包含数组字段 items"]
            return _validation_errors(validator, items)

        result = self.call_json_object(
            prompt,
            validator=wrapped_validator,
            use_reason_model=use_reason_model,
        )
        return StructuredCallResult(
            data=result.data["items"],
            attempts=result.attempts,
            prompt_hash=result.prompt_hash,
            errors=result.errors,
        )
