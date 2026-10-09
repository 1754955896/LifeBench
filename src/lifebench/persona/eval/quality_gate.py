"""Batch-level output gate for the public persona contract."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence

from ..grounding import semantic_quality_errors
from ..validation import validate_output_contract
from .metrics import duplicate_contact_rate, unknown_social_circle_rate


@dataclass(frozen=True)
class QualityGateResult:
    valid: bool
    errors: List[str]
    metrics: Dict[str, float]


def evaluate_output_batch(
    personas: Sequence[Dict[str, Any]],
    expected_key_orders: Sequence[Sequence[str]],
    location_batches: Optional[Sequence[List[Dict[str, Any]]]] = None,
    semantic_contexts: Optional[Sequence[Dict[str, Any]]] = None,
) -> QualityGateResult:
    errors: List[str] = []
    if len(personas) != len(expected_key_orders):
        errors.append("输出数量与输入数量不一致")
    if location_batches is not None and len(location_batches) != len(personas):
        errors.append("地址 sidecar 数量与画像数量不一致")
    if semantic_contexts is not None and len(semantic_contexts) != len(personas):
        errors.append("内部语义上下文数量与画像数量不一致")
    for index, (persona, expected_keys) in enumerate(zip(personas, expected_key_orders)):
        report = validate_output_contract(persona, list(expected_keys))
        errors.extend("persona[%d] %s" % (index, message) for message in report.messages())
        locations = location_batches[index] if location_batches is not None and index < len(location_batches) else None
        context = semantic_contexts[index] if semantic_contexts is not None and index < len(semantic_contexts) else None
        errors.extend(
            "persona[%d] SEMANTIC: %s" % (index, message)
            for message in semantic_quality_errors(persona, locations, context)
        )
    metrics = {
        "schema_contract_rate": (len(personas) - len({error.split()[0] for error in errors if error.startswith("persona[")})) / len(personas) if personas else 1.0,
        "duplicate_contact_rate": duplicate_contact_rate(personas),
        "unknown_social_circle_rate": unknown_social_circle_rate(personas),
    }
    return QualityGateResult(not errors, errors, metrics)
