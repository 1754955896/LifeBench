"""Internal models for arbitrary persona source normalization."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class NormalizedSource:
    """Facts extracted from one arbitrary source record.

    This object is internal-only.  It is deliberately separate from the public
    persona schema so provenance and uncertainty never leak into final output.
    """

    explicit_facts: Dict[str, Any] = field(default_factory=dict)
    soft_clues: Dict[str, Any] = field(default_factory=dict)
    source_description: str = ""
    conflicts: List[Dict[str, Any]] = field(default_factory=list)
    unmapped_information: List[Any] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "NormalizedSource":
        return cls(
            explicit_facts=dict(value.get("explicit_facts") or {}),
            soft_clues=dict(value.get("soft_clues") or {}),
            source_description=str(value.get("source_description") or "").strip(),
            conflicts=list(value.get("conflicts") or []),
            unmapped_information=list(value.get("unmapped_information") or []),
        )


@dataclass
class CanonicalSeed:
    data: Dict[str, Any]
    locked_facts: Dict[str, Any]
    soft_clues: Dict[str, Any]
    source_description: str
