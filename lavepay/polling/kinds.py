from __future__ import annotations

from typing import Any

KINDS = (
    "invoice",
    "cheque",
    "qr_payment",
    "card_payout",
    "steam_order",
    "telegram_order",
    "buy_order",
)

_BY_CLASS = {
    "Invoice": "invoice",
    "Cheque": "cheque",
    "QrPayment": "qr_payment",
    "CardPayout": "card_payout",
    "SteamOrder": "steam_order",
    "TelegramOrder": "telegram_order",
    "BuyOrder": "buy_order",
}

NOTABLE: dict[str, frozenset[str]] = {
    "invoice": frozenset({"paid", "expired", "cancelled", "refunded"}),
    "cheque": frozenset({"completed", "cancelled"}),
    "qr_payment": frozenset({"completed", "failed"}),
    "card_payout": frozenset({"completed", "failed"}),
    "steam_order": frozenset({"completed", "failed"}),
    "telegram_order": frozenset({"completed", "failed"}),
    "buy_order": frozenset({"completed", "cancelled", "overdue"}),
}

# overdue у покупки не конечный: поздний платёж ещё может зачислиться.
WAIT_DONE: dict[str, frozenset[str]] = {
    "invoice": frozenset({"paid", "expired", "cancelled", "refunded"}),
    "cheque": frozenset({"completed", "cancelled"}),
    "qr_payment": frozenset({"completed", "failed"}),
    "card_payout": frozenset({"completed", "failed"}),
    "steam_order": frozenset({"completed", "failed"}),
    "telegram_order": frozenset({"completed", "failed"}),
    "buy_order": frozenset({"completed", "cancelled"}),
}

OPEN_STATUSES: dict[str, tuple[str, ...]] = {
    "invoice": ("active",),
    "cheque": ("active",),
    "qr_payment": ("pending", "processing"),
    "card_payout": ("pending", "processing"),
    "steam_order": ("pending", "processing"),
    "telegram_order": ("pending", "processing"),
    "buy_order": ("pending", "awaiting_payment", "overdue"),
}


def kind_of(obj: Any) -> str:
    kind = _BY_CLASS.get(type(obj).__name__)
    if kind is None:
        raise TypeError(f"поллинг не ведёт {type(obj).__name__}")
    return kind


def events_for(kind: str, previous: Any, current: Any, *, announce: bool) -> list[str]:
    events: list[str] = []
    status = current.status
    prev_status = None if previous is None else previous.status
    if status in NOTABLE[kind] and (announce or prev_status != status):
        events.append(f"{kind}.{status}")
    if kind == "cheque" and status == "active":
        prev_used = 0 if previous is None else previous.activations_used
        if current.activations_used > prev_used and (previous is not None or current.activations_used > 0):
            events.append("cheque.activated")
    if kind == "qr_payment" and current.returned:
        prev_returned = None if previous is None else previous.returned
        if announce or not prev_returned:
            events.append("qr_payment.reversed")
    if (
        kind == "steam_order"
        and current.waiting
        and status not in {"completed", "failed"}
        and (announce or previous is None or not previous.waiting)
    ):
        events.append("steam_order.waiting")
    return events
