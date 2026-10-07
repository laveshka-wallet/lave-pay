from __future__ import annotations

import asyncio
import os
import warnings
from typing import Any

import httpx

from .dedup import Deduper, MemoryDeduper
from .models import Invoice, Merchant
from .polling import Dispatcher, PollingConfig
from .polling.kinds import kind_of
from .resources import Buy, Card, Cheques, History, Invoices, Qr, Steam, Telegram, Transfers, Webhooks
from .transport import DEFAULT_BASE_URL, Transport
from .webhooks import WebhookEvent, verify_webhook


def _on(event: str, doc: str):
    def method(self: LavePay, handler=None, *, filter=None):
        return self.on(event, handler, filter=filter)

    method.__name__ = event.replace(".", "_")
    method.__doc__ = doc
    return method


class LavePay:
    """Клиент ``/merchant/v1``."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 40.0,
        webhook_secret: str | None = None,
        polling: PollingConfig | None = None,
        deduper: Deduper | None = None,
        context: dict[str, Any] | None = None,
        http_client: httpx.AsyncClient | None = None,
        max_retries: int = 2,
        max_retry_wait: float = 5.0,
    ) -> None:
        self.webhook_secret = webhook_secret or ""
        self._http = Transport(
            api_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            max_retry_wait=max_retry_wait,
            http_client=http_client,
        )
        self._tasks: set[asyncio.Task[Any]] = set()
        self._poll_warn = False
        self.invoices = Invoices(self)
        self.history = History(self)
        self.transfers = Transfers(self)
        self.cheques = Cheques(self)
        self.qr = Qr(self)
        self.card = Card(self)
        self.steam = Steam(self)
        self.telegram = Telegram(self)
        self.buy = Buy(self)
        self.webhooks = Webhooks(self)
        self.dispatcher = Dispatcher(
            client=self,
            config=polling or PollingConfig(),
            deduper=deduper or MemoryDeduper(),
        )
        if context:
            self.dispatcher.defaults.update(context)

    @classmethod
    def from_env(cls, **kwargs: Any) -> LavePay:
        """``LAVEPAY_API_KEY``, при желании ``LAVEPAY_BASE_URL`` и ``LAVEPAY_WEBHOOK_SECRET``."""
        key = os.environ["LAVEPAY_API_KEY"]
        kwargs.setdefault("base_url", os.environ.get("LAVEPAY_BASE_URL", DEFAULT_BASE_URL))
        kwargs.setdefault("webhook_secret", os.environ.get("LAVEPAY_WEBHOOK_SECRET"))
        return cls(key, **kwargs)

    def __setitem__(self, key: str, value: Any) -> None:
        self.dispatcher.defaults[key] = value

    async def __aenter__(self) -> LavePay:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        self.stop_polling()
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        for task in tasks:
            try:
                await task
            except BaseException:
                pass
        self._tasks.clear()
        await self._http.aclose()

    def spawn(self, coro: Any) -> Any:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def me(self) -> Merchant:
        data = await self._http.request("GET", "/me", idempotent=True)
        return Merchant.model_validate(data).bind(self)

    def on(self, event: str, handler=None, *, filter=None):
        """Например ``lp.on("invoice.paid", handler)``."""
        return self.dispatcher.on(event, handler, filter=filter)

    def watch(self, obj: Any, **data: Any) -> None:
        kind_of(obj)
        self.dispatcher.watch(obj, **data)

    def unwatch(self, obj: Any) -> None:
        self.dispatcher.unwatch(obj)

    async def emit(self, event: str, obj: Any, **extra: Any) -> bool:
        """Дёрнуть обработчики без запроса. Удобно в тестах."""
        return await self.dispatcher.emit(event, obj, extra=extra)

    async def feed(self, body: bytes | str, headers) -> WebhookEvent:
        """Проверить подпись и отдать событие обработчикам."""
        if self.dispatcher.running and not self._poll_warn:
            warnings.warn(
                "поллинг уже запущен: то же событие может прийти и вебхуком",
                stacklevel=2,
            )
            self._poll_warn = True
        event = verify_webhook(self.webhook_secret, body, headers)
        await self.dispatcher.dispatch_event(event)
        return event

    async def start_polling(self, *, discover: bool | None = None) -> None:
        """Крутить опрос, пока не вызовут ``stop_polling``."""
        await self.dispatcher.run(discover=discover)

    def stop_polling(self) -> None:
        self.dispatcher.stop()

    invoice_paid = _on("invoice.paid", "Счёт оплачен.")
    invoice_expired = _on("invoice.expired", "У счёта вышел срок.")
    invoice_cancelled = _on("invoice.cancelled", "Счёт отменён.")
    invoice_refunded = _on("invoice.refunded", "Оплата по счёту возвращена.")
    invoice_timeout = _on("invoice.timeout", "Локальный предел ожидания счёта вышел.")
    cheque_activated = _on("cheque.activated", "Чек забрали частично.")
    cheque_completed = _on("cheque.completed", "Все активации чека забраны.")
    cheque_cancelled = _on("cheque.cancelled", "Чек отозван.")
    cheque_timeout = _on("cheque.timeout", "Локальный предел ожидания чека вышел.")
    qr_payment_completed = _on("qr_payment.completed", "Оплата QR прошла.")
    qr_payment_failed = _on("qr_payment.failed", "Оплата QR не прошла.")
    qr_payment_reversed = _on("qr_payment.reversed", "Магазин вернул оплату QR.")
    qr_payment_timeout = _on("qr_payment.timeout", "Локальный предел ожидания QR вышел.")
    card_payout_completed = _on("card_payout.completed", "Рубли дошли до карты.")
    card_payout_failed = _on("card_payout.failed", "Выплата на карту не прошла.")
    card_payout_timeout = _on("card_payout.timeout", "Локальный предел ожидания выплаты вышел.")
    steam_order_completed = _on("steam_order.completed", "Steam зачислил пополнение.")
    steam_order_failed = _on("steam_order.failed", "Steam не принял заказ.")
    steam_order_waiting = _on("steam_order.waiting", "Заказ Steam идёт дольше обычного.")
    steam_order_timeout = _on("steam_order.timeout", "Локальный предел ожидания Steam вышел.")
    telegram_order_completed = _on("telegram_order.completed", "Stars или Premium доставлены.")
    telegram_order_failed = _on("telegram_order.failed", "Покупка Stars или Premium не прошла.")
    telegram_order_timeout = _on("telegram_order.timeout", "Локальный предел ожидания покупки вышел.")
    buy_order_completed = _on("buy_order.completed", "USDT зачислены на баланс мерчанта.")
    buy_order_cancelled = _on("buy_order.cancelled", "Покупка USDT закрыта без оплаты.")
    buy_order_overdue = _on("buy_order.overdue", "Время оплаты вышло, поздний платёж ещё может пройти.")
    buy_order_timeout = _on("buy_order.timeout", "Локальный предел ожидания покупки вышел.")
    webhook_test = _on("webhook.test", "Тестовое событие вебхука.")


def fake_invoice(**overrides: Any) -> Invoice:
    """Счёт для теста, без запроса."""
    data: dict[str, Any] = {
        "id": "inv_test",
        "merchant_id": 1,
        "status": "paid",
        "amount": "12.34",
        "fee": "0.00",
        "net": "12.34",
        "currency": "USD",
        "order_id": "ord-1",
        "pay_url": "https://t.me/laveshka?startapp=lpay_test",
        "created_at": "2026-08-22T09:10:00+00:00",
    }
    data.update(overrides)
    return Invoice.model_validate(data)
