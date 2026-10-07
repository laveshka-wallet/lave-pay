from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

def idempotency_key(*parts: object) -> str:
    """Одинаковые части дают один ключ. Без частей ключ случайный."""
    if not parts:
        return uuid.uuid4().hex
    raw = "\x1f".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def payment_url(obj: Any) -> str:
    for name in ("pay_url", "url", "payment_url"):
        value = getattr(obj, name, None)
        if value:
            return str(value)
    raise ValueError("у объекта нет ссылки на оплату")


def seconds_left(moment: datetime | None, *, now: datetime | None = None) -> float | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    clock = now or datetime.now(timezone.utc)
    if clock.tzinfo is None:
        clock = clock.replace(tzinfo=timezone.utc)
    return (moment - clock).total_seconds()


def payload_json(payload: str) -> Any:
    if not payload:
        return None
    return json.loads(payload)
