"""Data models for diagnostic records."""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

@dataclass
class DiagnosticRecord:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    cls: str = ""
    severity: str = "info"
    layer: str = ""
    message: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: Optional[str] = None
    reproducible_cmd: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)
