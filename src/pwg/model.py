from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Finding:
    classification: str
    subject_id: str
    declared: dict[str, Any] = field(default_factory=dict)
    observed: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    confidence: str = "low"
    suggested_operation: str | None = None
    risk: str = "low"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
