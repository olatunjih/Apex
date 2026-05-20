from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Optional

from .errors import APEXError, ErrorCategory, ErrorSeverity

getcontext().prec = 28


@dataclass(frozen=True)
class NumericalPolicy:
    """Numerical policy configuration (Appendix G)."""
    monetary_precision: int = 28
    monetary_type_name: str = "Decimal"
    rounding_mode: str = "ROUND_HALF_UP"
    price_display_precision: int = 2
    percentage_precision: int = 6
    
    def __post_init__(self):
        if self.monetary_precision != 28:
            raise ValueError(f"monetary_precision must be 28, got {self.monetary_precision}")
        if self.monetary_type_name != "Decimal":
            raise ValueError(f"monetary_type_name must be 'Decimal', got {self.monetary_type_name}")


DEFAULT_NUMERICAL_POLICY = NumericalPolicy()


def validate_numerical_policy(policy: NumericalPolicy) -> None:
    """Validate numerical policy matches spec requirements."""
    if policy.monetary_precision != 28:
        raise ValueError(f"monetary_precision must be 28, got {policy.monetary_precision}")
    if policy.monetary_type_name != "Decimal":
        raise ValueError(f"monetary_type_name must be 'Decimal', got {policy.monetary_type_name}")
    if policy.rounding_mode != "ROUND_HALF_UP":
        raise ValueError(f"rounding_mode must be 'ROUND_HALF_UP', got {policy.rounding_mode}")


@dataclass(frozen=True)
class MonetaryValue:
    amount: Decimal

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            raise APEXError(
                code="NUMERICAL_TYPE_VIOLATION",
                category=ErrorCategory.VALIDATION,
                severity=ErrorSeverity.HIGH,
                retryable=False,
                message=f"MonetaryValue.amount must be Decimal, got {type(self.amount).__name__}",
                user_visible=True,
            )

    def quantize_price(self) -> Decimal:
        return self.amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def serialize_decimal(value: Decimal) -> str:
    """Serialize Decimal to string for JSON transit with full precision."""
    return str(value)


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
