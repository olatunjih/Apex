from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ErrorCategory(str, Enum):
    VALIDATION = "validation"
    EXTERNAL = "external"
    SYSTEM = "system"
    DATA = "data"


class ErrorSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class APEXError(Exception):
    code: str
    category: ErrorCategory
    severity: ErrorSeverity
    retryable: bool
    message: str
    max_retries: int = 0
    retry_delay_ms: int = 0
    user_visible: bool = False

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
