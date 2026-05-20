from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


@dataclass(frozen=True)
class NumericalPolicy:
    monetary_precision: int
    monetary_type_name: str
    rounding_mode: str
    price_display_precision: int
    percentage_precision: int


DEFAULT_NUMERICAL_POLICY = NumericalPolicy(
    monetary_precision=28,
    monetary_type_name="Decimal",
    rounding_mode=ROUND_HALF_UP,
    price_display_precision=2,
    percentage_precision=6,
)


def validate_numerical_policy(policy: NumericalPolicy) -> None:
    if policy.monetary_precision != 28:
        raise ValueError("monetary_precision must be 28")
    if policy.monetary_type_name != "Decimal":
        raise ValueError("monetary_type_name must be Decimal")
    if policy.rounding_mode != ROUND_HALF_UP:
        raise ValueError("rounding_mode must be ROUND_HALF_UP")
    if policy.price_display_precision < 0:
        raise ValueError("price_display_precision must be non-negative")
    if policy.percentage_precision < 0:
        raise ValueError("percentage_precision must be non-negative")


def serialize_decimal(value: Decimal) -> str:
    return format(value, "f")
