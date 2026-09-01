"""Internal model for one deliberately distinct persona direction."""

from dataclasses import dataclass, field
from typing import Any, Dict, List


VARIANT_BLUEPRINT_KEYS = (
    "profile_direction", "career_track", "family_track", "personality_track",
    "economic_track", "health_track", "interest_track", "social_track",
    "distinctive_details",
)


@dataclass
class VariantBlueprint:
    profile_direction: str = ""
    career_track: str = ""
    family_track: str = ""
    personality_track: str = ""
    economic_track: str = ""
    health_track: str = ""
    interest_track: List[str] = field(default_factory=list)
    social_track: List[str] = field(default_factory=list)
    distinctive_details: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "VariantBlueprint":
        return cls(**{key: value.get(key) for key in VARIANT_BLUEPRINT_KEYS})

    def to_dict(self) -> Dict[str, Any]:
        return {key: getattr(self, key) for key in VARIANT_BLUEPRINT_KEYS}
