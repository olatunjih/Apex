from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext

from .errors import APEXError, ErrorCategory, ErrorSeverity

getcontext().prec = 28


@dataclass(frozen=True)
class MonetaryValue:
    amount: Decimal

    def quantize_price(self) -> Decimal:
        return self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def enforce_decimal(value: object, field_name: str = "value") -> Decimal:
    if isinstance(value, Decimal):
        return value
    raise APEXError(
        code="NUMERICAL_TYPE_VIOLATION",
        category=ErrorCategory.VALIDATION,
        severity=ErrorSeverity.HIGH,
        retryable=False,
        message=f"{field_name} must be Decimal, got {type(value).__name__}",
        user_visible=True,
    )
