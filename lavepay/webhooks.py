from __future__ import annotations

import hashlib
import hmac
import time
from datetime import datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict

from .errors import BadSignature, StaleWebhook
from .models import (
    BuyOrder,
    CardPayout,
    Cheque,
    Invoice,
    QrPayment,
    SteamOrder,
    TelegramOrder,
    WebhookTest,
)

TOLERANCE = 300

_CAST: dict[str, type[BaseModel]] = {}
for _name, _model in (
    ("invoice.paid", Invoice),
    ("invoice.expired", Invoice),
    ("invoice.cancelled", Invoice),
    ("invoice.refunded", Invoice),
    ("cheque.activated", Cheque),
    ("cheque.completed", Cheque),
    ("cheque.cancelled", Cheque),
    ("qr_payment.completed", QrPayment),
    ("qr_payment.failed", QrPayment),
    ("qr_payment.reversed", QrPayment),
    ("card_payout.completed", CardPayout),
    ("card_payout.failed", CardPayout),
    ("steam_order.completed", SteamOrder),
    ("steam_order.failed", SteamOrder),
    ("steam_order.waiting", SteamOrder),
    ("telegram_order.completed", TelegramOrder),
    ("telegram_order.failed", TelegramOrder),
    ("buy_order.completed", BuyOrder),
    ("buy_order.cancelled", BuyOrder),
    ("buy_order.overdue", BuyOrder),
    ("webhook.test", WebhookTest),
):
    _CAST[_name] = _model


class WebhookEvent(BaseModel):

    model_config = ConfigDict(extra="ignore")

    id: str
    type: str
    created_at: datetime
    merchant_id: int
    data: Any

    def cast(self) -> Any:
        model = _CAST.get(self.type)
        if model is None or isinstance(self.data, model):
            return self.data
        if isinstance(self.data, dict):
            return model.model_validate(self.data)
        return self.data


def sign(secret: str, timestamp: int | str, body: bytes | str) -> str:
    raw = body if isinstance(body, bytes) else body.encode("utf-8")
    digest = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.".encode("utf-8") + raw,
        hashlib.sha256,
    ).hexdigest()
    return f"v1={digest}"


def verify_webhook(
    secret: str,
    body: bytes | str,
    headers: Mapping[str, str],
    *,
    tolerance: int = TOLERANCE,
    now: float | None = None,
) -> WebhookEvent:
    """Подпись считается по сырым байтам. ``request.json()`` до этого её ломает."""
    if not secret:
        raise BadSignature("не задан секрет вебхука")
    raw = body if isinstance(body, bytes) else body.encode("utf-8")
    timestamp = _header(headers, "x-lavepay-timestamp")
    signature = _header(headers, "x-lavepay-signature")
    if not timestamp.isdigit():
        raise BadSignature("нет метки времени")
    moment = time.time() if now is None else now
    if abs(moment - int(timestamp)) > tolerance:
        raise StaleWebhook("устаревшая подпись")
    expected = sign(secret, timestamp, raw)
    if not hmac.compare_digest(expected, signature):
        raise BadSignature("подпись не сошлась")
    return WebhookEvent.model_validate_json(raw)


def _header(headers: Mapping[str, str], name: str) -> str:
    direct = headers.get(name)
    if direct:
        return str(direct)
    lowered = name.lower()
    for key, value in headers.items():
        if str(key).lower() == lowered and value:
            return str(value)
    return ""
