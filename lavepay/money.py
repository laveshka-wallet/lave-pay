from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

Amount = Decimal | str | int


def as_amount(value: Amount) -> str:
    if isinstance(value, bool) or isinstance(value, float):
        raise TypeError("суммы передавайте Decimal или строкой, не float")
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("сумма должна быть конечным числом")
        return format(value, "f")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation as exc:
            raise ValueError(f"не сумма: {value}") from exc
        if not parsed.is_finite():
            raise ValueError("сумма должна быть конечным числом")
        return value
    raise TypeError("суммы передавайте Decimal или строкой, не float")


def parse_amount(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float) or isinstance(value, bool):
        raise TypeError("сумма не должна быть float")
    return Decimal(str(value))


def parse_amount_opt(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return parse_amount(value)


def dump(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    out: dict[str, Any] = {}
    for key, value in data.items():
        if value is None:
            continue
        out[key] = _dump_value(value)
    return out


def _dump_value(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise TypeError("суммы передавайте Decimal или строкой, не float")
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (list, tuple)):
        return [_dump_value(item) for item in value]
    return value


def one_of(**fields: Any) -> None:
    present = [name for name, value in fields.items() if value is not None]
    if len(present) != 1:
        names = ", ".join(fields)
        raise ValueError(f"укажите ровно одно из: {names}")
