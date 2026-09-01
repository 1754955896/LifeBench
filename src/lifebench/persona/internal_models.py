"""Internal-only models and output contracts for persona synthesis."""

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


STANDARD_PERSONA_KEYS = (
    "name", "birth", "age", "nationality", "home_address", "birth_place",
    "gender", "education", "job", "occupation", "workplace", "belief",
    "salary", "body", "family", "personality", "hobbies", "favorite_foods",
    "memory_date", "aim", "healthy_desc", "lifestyle_desc", "economic_desc",
    "work_desc", "experience_desc", "description", "relation",
)

STANDARD_CONTACT_KEYS = (
    "name", "relation", "social circle", "gender", "age", "birth_date",
    "home_address", "birth_place", "personality", "economic_level",
    "occupation", "organization", "nickname", "relation_description",
)

VALID_MBTI = frozenset({
    "INTJ", "INTP", "ENTJ", "ENTP", "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ", "ISTP", "ISFP", "ESTP", "ESFP",
})

VALID_CIRCLE_TYPES = frozenset({
    "current_work", "school", "household", "family", "sports_club",
    "neighborhood", "online_community", "professional_community",
    "hobby_group", "other",
})

INTERNAL_KEYS = frozenset({
    "internal_id", "slot_id", "source_index", "ref_index", "_index",
    "_ref_index", "_original_person", "_core_locations", "_quality_context", "note", "validation_report",
})


@dataclass
class InternalContact:
    internal_id: str
    name: str
    relation: str
    social_circle: str
    gender: str
    age: int
    birth_date: date
    home_address: Dict[str, Any]
    birth_place: Dict[str, Any]
    personality: str
    economic_level: str
    occupation: str
    organization: str
    nickname: str
    relation_description: str


@dataclass
class InternalPersona:
    internal_id: str
    data: Dict[str, Any]
    relation_groups: List[List[InternalContact]]
    original_top_level_keys: List[str]
    source_index: Optional[int] = None
    ref_index: Optional[int] = None


@dataclass
class RelationSlot:
    slot_id: str
    name_hint: str
    relation: str
    social_circle: str
    circle_id: str = ""
    circle_type: str = "other"
    parent_anchor_id: str = ""
    shared_facts: Dict[str, Any] = field(default_factory=dict)
    secondary_tags: List[str] = field(default_factory=list)


@dataclass
class CircleAnchor:
    circle_id: str
    circle_type: str
    parent_anchor_id: str
    social_circle: str
    shared_facts: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PersonaResult:
    source_index: int
    output: Optional[Dict[str, Any]] = None
    errors: List[str] = field(default_factory=list)
    stage: str = ""
    locations: List[Dict[str, Any]] = field(default_factory=list)
    quality_context: Dict[str, Any] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.output is not None and not self.errors


@dataclass
class BatchResult:
    items: List[PersonaResult]

    @property
    def complete(self) -> bool:
        return bool(self.items) and all(item.succeeded for item in self.items)

    @property
    def outputs(self) -> List[Dict[str, Any]]:
        return [item.output for item in self.items if item.output is not None]
