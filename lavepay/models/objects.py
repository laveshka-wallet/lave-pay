from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import Field

from ..money import as_amount, parse_amount
from ..tools import payload_json
from .base import APIModel

Money = Decimal


class Payer(APIModel):
    telegram_id: int
    username: str | None = None


class WebhookHealth(APIModel):
    state: str
    url: str = ""
    failure_streak: int = 0
    failing_since: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    disabled_at: datetime | None = None
    disabled_reason: str = ""


class Merchant(APIModel):
    id: int
    name: str
    description: str = ""
    project_url: str = ""
    avatar_url: str = ""
    status: str
    fee_bps: int
    payouts_enabled: bool
    webhook: WebhookHealth
    created_at: datetime | None = None
    balance: Decimal | None = None
    currency: str | None = None
    balances: dict[str, Decimal] = Field(default_factory=dict)


class Invoice(APIModel):
    id: str
    merchant_id: int
    status: str
    amount: Decimal
    fee: Decimal
    net: Decimal
    currency: str = "USD"
    face_amount: str = ""
    accept: list[str] = Field(default_factory=list)
    paid_asset: str | None = None
    paid_amount: Decimal | None = None
    paid_via: str | None = None
    description: str = ""
    order_id: str = ""
    payload: str = ""
    return_url: str = ""
    pay_url: str
    payer: Payer | None = None
    created_at: datetime | None = None
    expires_at: datetime | None = None
    paid_at: datetime | None = None
    refunded_at: datetime | None = None

    def payload_json(self) -> Any:
        return payload_json(self.payload)

    def matches(
        self,
        *,
        amount: Any = None,
        currency: str | None = None,
        order_id: str | None = None,
    ) -> bool:
        """Оплачен и совпадает с суммой и номером заказа."""
        if self.status != "paid":
            return False
        if order_id is not None and self.order_id != order_id:
            return False
        if currency is not None and self.currency.upper() != currency.upper():
            return False
        if amount is not None and self.amount != parse_amount(as_amount(amount)):
            return False
        return True

    async def refresh(self) -> Invoice:
        return await self._require().invoices.get(self.id)

    async def cancel(self) -> Invoice:
        return await self._require().invoices.cancel(self.id)

    async def refund(self) -> Invoice:
        return await self._require().invoices.refund(self.id)


class Transfer(APIModel):
    id: str
    amount: Decimal
    currency: str = "USD"
    recipient: Payer
    comment: str = ""
    created_at: datetime | None = None

    def poll(self, **data: Any) -> None:
        raise TypeError("перевод проходит сразу, поллить его не нужно")


class Cheque(APIModel):
    id: str
    public_id: str
    status: str
    amount: Decimal
    total: Decimal
    currency: str = "USD"
    activations_total: int = 1
    activations_used: int = 0
    comment: str = ""
    recipient: str = ""
    url: str
    idempotency_key: str = ""
    created_at: datetime | None = None
    closed_at: datetime | None = None

    async def refresh(self) -> Cheque:
        return await self._require().cheques.get(self.id)

    async def cancel(self) -> Cheque:
        return await self._require().cheques.cancel(self.id)


class HistoryItem(APIModel):
    id: str
    type: str
    direction: str
    amount: Decimal
    asset: str
    balance_after: Decimal
    object_id: str | None = None
    status: str | None = None
    created_at: datetime | None = None

    def poll(self, **data: Any) -> None:
        raise TypeError("строка истории не опрашивается")


class QrRate(APIModel):
    available: bool
    reason: str | None = None
    currency: str = "USDT"
    rate: Decimal | None = None
    rate_large: Decimal | None = None
    small_max_rub: Decimal
    min_rub: Decimal
    max_rub: Decimal
    quote_ttl: int
    max_affordable_rub: Decimal | None = None


class QrQuote(APIModel):
    quote_id: str
    payee: str = ""
    amount_rub: Decimal
    debit: Decimal
    currency: str = "USDT"
    rate: Decimal
    expires_at: datetime | None = None


class QrPayment(APIModel):
    id: str
    status: str
    payee: str = ""
    amount_rub: Decimal
    debit: Decimal
    currency: str = "USDT"
    rate: Decimal
    error: str | None = None
    returned: Decimal | None = None
    returned_at: datetime | None = None
    idempotency_key: str = ""
    replayed: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None

    async def refresh(self) -> QrPayment:
        return await self._require().qr.get(self.id)


class CardPrice(APIModel):
    amount_rub: Decimal
    debit: Decimal
    rate: Decimal


class CardRate(APIModel):
    available: bool
    reason: str | None = None
    currency: str = "USDT"
    rate: Decimal | None = None
    examples: list[CardPrice] = Field(default_factory=list)
    min_rub: Decimal
    max_rub: Decimal
    max_affordable_rub: Decimal | None = None
    review_above: Decimal | None = None
    price: CardPrice | None = None


class CardRef(APIModel):
    brand: str
    last4: str
    masked: str


class CardPayout(APIModel):
    id: str
    status: str
    requires_review: bool = False
    amount_rub: Decimal
    debit: Decimal
    currency: str = "USDT"
    rate: Decimal
    card: CardRef
    error: str | None = None
    idempotency_key: str = ""
    replayed: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None

    async def refresh(self) -> CardPayout:
        return await self._require().card.get(self.id)


class SteamCurrency(APIModel):
    code: str
    rate: Decimal


class SteamEstimate(APIModel):
    amount_usd: Decimal
    debit: Decimal


class SteamRate(APIModel):
    available: bool
    reason: str | None = None
    currency: str = "USDT"
    min_usd: Decimal
    max_usd: Decimal
    price_factor: Decimal
    currencies: list[SteamCurrency] = Field(default_factory=list)
    max_affordable_usd: Decimal | None = None
    estimate: SteamEstimate | None = None


class SteamOrder(APIModel):
    id: str
    status: str
    account: str
    amount_usd: Decimal
    steam_currency: str
    amount_local: Decimal
    debit: Decimal
    currency: str = "USDT"
    waiting: bool = False
    error: str | None = None
    idempotency_key: str = ""
    replayed: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None

    async def refresh(self) -> SteamOrder:
        return await self._require().steam.get(self.id)


class StarsPreset(APIModel):
    quantity: int
    debit: Decimal


class StarsTerms(APIModel):
    price_per_unit: Decimal
    min_quantity: int
    max_quantity: int
    presets: list[StarsPreset] = Field(default_factory=list)


class PremiumOption(APIModel):
    months: int
    debit: Decimal


class PremiumTerms(APIModel):
    available: bool
    options: list[PremiumOption] = Field(default_factory=list)


class TelegramPrice(APIModel):
    service: str
    quantity: int
    debit: Decimal


class TelegramRate(APIModel):
    available: bool
    reason: str | None = None
    currency: str = "USDT"
    stars: StarsTerms
    premium: PremiumTerms
    max_purchase: Decimal | None = None
    price: TelegramPrice | None = None


class TelegramOrder(APIModel):
    id: str
    status: str
    service: str
    recipient: str
    quantity: int
    debit: Decimal
    currency: str = "USDT"
    refunded: bool = False
    error: str | None = None
    idempotency_key: str = ""
    replayed: bool = False
    created_at: datetime | None = None
    completed_at: datetime | None = None

    async def refresh(self) -> TelegramOrder:
        return await self._require().telegram.get(self.id)


class BuyPrice(APIModel):
    amount_rub: Decimal
    amount_usdt: Decimal
    rate: Decimal


class BuyRate(APIModel):
    available: bool
    reason: str | None = None
    currency: str = "USDT"
    rate: Decimal | None = None
    min_rub: Decimal | None = None
    max_rub: Decimal | None = None
    payment_minutes: int | None = None
    open_orders: int = 0
    max_open_orders: int = 0
    blocked_until: datetime | None = None
    price: BuyPrice | None = None


class BuyOrder(APIModel):
    id: str
    status: str
    amount_rub: Decimal
    amount_usdt: Decimal
    currency: str = "USDT"
    rate: Decimal
    payment_url: str | None = None
    pay_until: datetime | None = None
    cancel_reason: str | None = None
    can_cancel: bool = False
    idempotency_key: str = ""
    replayed: bool = False
    created_at: datetime | None = None
    closed_at: datetime | None = None

    async def refresh(self) -> BuyOrder:
        return await self._require().buy.get(self.id)

    async def cancel(self) -> BuyOrder:
        return await self._require().buy.cancel(self.id)


class Delivery(APIModel):
    id: str
    type: str
    status: str
    url: str
    attempts: int
    last_status_code: int | None = None
    last_error: str = ""
    last_response: str = ""
    last_duration_ms: int | None = None
    next_attempt_at: datetime | None = None
    created_at: datetime | None = None
    delivered_at: datetime | None = None

    def poll(self, **data: Any) -> None:
        raise TypeError("доставка вебхука не опрашивается")


class DeliveryRef(APIModel):
    delivery: Delivery | None = None


class WebhookTest(APIModel):
    message: str = ""
    merchant_id: int | None = None
