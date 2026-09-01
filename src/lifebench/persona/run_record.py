"""In-memory run metadata that is kept outside formal persona records."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PersonaRunRecord:
    as_of_date: str
    seed: Optional[int]
    requested_count: int = 0
    succeeded_count: int = 0
    failed_count: int = 0
    prompt_hashes: Dict[str, List[str]] = field(default_factory=dict)
    failures: List[dict] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    finished_at: Optional[str] = None

    def add_prompt_hash(self, stage: str, value: str) -> None:
        self.prompt_hashes.setdefault(stage, []).append(value)

    def finish(self) -> None:
        self.finished_at = datetime.utcnow().isoformat() + "Z"
