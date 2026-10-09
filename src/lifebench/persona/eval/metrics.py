"""Dependency-light quality metrics shared by persona evaluation and generation."""

import math
from collections import Counter
from typing import Any, Dict, Iterable, Iterator, List, Optional


def flatten_relation_groups(relation: Any) -> List[Dict[str, Any]]:
    """Flatten supported relation nesting without dropping later groups."""
    result: List[Dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            result.append(value)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(relation)
    return result


def get_social_circle(contact: Dict[str, Any]) -> Optional[str]:
    value = contact.get("social circle")
    if value in (None, "", " "):
        value = contact.get("social_circle")
    return value if value not in (None, "", " ") else None


def normalized_entropy(values: Iterable[Any]) -> float:
    counts = Counter(values)
    total = sum(counts.values())
    if total == 0 or len(counts) <= 1:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return entropy / math.log(len(counts))


def effective_category_count(values: Iterable[Any]) -> float:
    counts = Counter(values)
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = -sum((count / total) * math.log(count / total) for count in counts.values())
    return math.exp(entropy)


def duplicate_contact_rate(personas: Iterable[Dict[str, Any]]) -> float:
    duplicate_count = 0
    contact_count = 0
    for persona in personas:
        seen = set()
        for contact in flatten_relation_groups(persona.get("relation", [])):
            contact_count += 1
            key = (contact.get("name"), contact.get("relation"))
            if key in seen:
                duplicate_count += 1
            seen.add(key)
    return duplicate_count / contact_count if contact_count else 0.0


def unknown_social_circle_rate(personas: Iterable[Dict[str, Any]]) -> float:
    contacts = [
        contact
        for persona in personas
        for contact in flatten_relation_groups(persona.get("relation", []))
    ]
    if not contacts:
        return 0.0
    return sum(get_social_circle(contact) is None for contact in contacts) / len(contacts)
