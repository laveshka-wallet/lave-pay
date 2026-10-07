from __future__ import annotations

from collections.abc import AsyncIterator

from ..models import (
    CardPayout,
    CardRate,
    QrPayment,
    QrQuote,
    QrRate,
    SteamOrder,
    SteamRate,
    TelegramOrder,
    TelegramRate,
)
from ..models.base import Page
from ..money import Amount, as_amount, one_of
from .base import Resource, object_path


class Qr(Resource):
    async def rate(self) -> QrRate:
        data = await self._http.request("GET", "/qr/rate", idempotent=True)
        return self._one(QrRate, data)

    async def check(self, qr: str) -> QrQuote:
        data = await self._http.request("POST", "/qr/check", json={"qr": qr})
        return self._one(QrQuote, data)

    async def pay(self, quote_id: str, *, idempotency_key: str) -> QrPayment:
        data = await self._http.request(
            "POST",
            "/qr/payments",
            json={"quote_id": quote_id, "idempotency_key": idempotency_key},
            idempotent=True,
        )
        return self._one(QrPayment, data)

    async def pay_link(self, qr: str, *, idempotency_key: str) -> QrPayment:
        quote = await self.check(qr)
        return await self.pay(quote.quote_id, idempotency_key=idempotency_key)

    async def get(self, payment_id: str, *, wait: float | None = None, known: str | None = None) -> QrPayment:
        data = await self._http.request(
            "GET",
            object_path("/qr/payments", payment_id),
            params={"wait": wait, "known": known},
            idempotent=True,
            timeout=self._client._http._timeout + (wait or 0),
        )
        return self._one(QrPayment, data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[QrPayment]:
        data = await self._http.request(
            "GET",
            "/qr/payments",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(QrPayment, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[QrPayment]:
        async for item in self._iter(QrPayment, "/qr/payments", status=status, limit=limit, before=before):
            yield item

    async def wait(
        self,
        payment_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> QrPayment:
        return await self._wait(
            "qr_payment", payment_id, timeout=timeout, interval=interval, until=until, long_poll=True,
        )


class Card(Resource):
    async def rate(
        self,
        *,
        amount_rub: Amount | None = None,
        amount_usdt: Amount | None = None,
    ) -> CardRate:
        data = await self._http.request(
            "GET",
            "/card/rate",
            params={
                "amount_rub": None if amount_rub is None else as_amount(amount_rub),
                "amount_usdt": None if amount_usdt is None else as_amount(amount_usdt),
            },
            idempotent=True,
        )
        return self._one(CardRate, data)

    async def payout(
        self,
        card_number: str,
        *,
        idempotency_key: str,
        amount_rub: Amount | None = None,
        amount_usdt: Amount | None = None,
        max_debit: Amount | None = None,
    ) -> CardPayout:
        one_of(amount_rub=amount_rub, amount_usdt=amount_usdt)
        data = await self._http.request(
            "POST",
            "/card/payouts",
            json={
                "card_number": card_number,
                "amount_rub": None if amount_rub is None else as_amount(amount_rub),
                "amount_usdt": None if amount_usdt is None else as_amount(amount_usdt),
                "max_debit": None if max_debit is None else as_amount(max_debit),
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
        )
        return self._one(CardPayout, data)

    async def get(self, payout_id: str) -> CardPayout:
        data = await self._http.request("GET", object_path("/card/payouts", payout_id), idempotent=True)
        return self._one(CardPayout, data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[CardPayout]:
        data = await self._http.request(
            "GET",
            "/card/payouts",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(CardPayout, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[CardPayout]:
        async for item in self._iter(CardPayout, "/card/payouts", status=status, limit=limit, before=before):
            yield item

    async def wait(
        self,
        payout_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> CardPayout:
        return await self._wait(
            "card_payout", payout_id, timeout=timeout, interval=interval, until=until, long_poll=False,
        )


class Steam(Resource):
    async def rate(
        self,
        *,
        amount: Amount | None = None,
        steam_currency: str | None = None,
    ) -> SteamRate:
        data = await self._http.request(
            "GET",
            "/steam/rate",
            params={
                "amount": None if amount is None else as_amount(amount),
                "steam_currency": steam_currency,
            },
            idempotent=True,
        )
        return self._one(SteamRate, data)

    async def order(
        self,
        account: str,
        *,
        idempotency_key: str,
        amount: Amount | None = None,
        amount_usdt: Amount | None = None,
        steam_currency: str = "USD",
        max_debit: Amount | None = None,
    ) -> SteamOrder:
        one_of(amount=amount, amount_usdt=amount_usdt)
        data = await self._http.request(
            "POST",
            "/steam/orders",
            json={
                "account": account,
                "amount": None if amount is None else as_amount(amount),
                "amount_usdt": None if amount_usdt is None else as_amount(amount_usdt),
                "steam_currency": steam_currency,
                "max_debit": None if max_debit is None else as_amount(max_debit),
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
            timeout=max(self._client._http._timeout, 40),
        )
        return self._one(SteamOrder, data)

    async def get(self, order_id: str) -> SteamOrder:
        data = await self._http.request("GET", object_path("/steam/orders", order_id), idempotent=True)
        return self._one(SteamOrder, data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[SteamOrder]:
        data = await self._http.request(
            "GET",
            "/steam/orders",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(SteamOrder, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[SteamOrder]:
        async for item in self._iter(SteamOrder, "/steam/orders", status=status, limit=limit, before=before):
            yield item

    async def wait(
        self,
        order_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> SteamOrder:
        return await self._wait(
            "steam_order", order_id, timeout=timeout, interval=interval, until=until, long_poll=False,
        )


class Telegram(Resource):
    async def rate(
        self,
        *,
        service: str | None = None,
        quantity: int | None = None,
    ) -> TelegramRate:
        data = await self._http.request(
            "GET",
            "/telegram/rate",
            params={"service": service, "quantity": quantity},
            idempotent=True,
        )
        return self._one(TelegramRate, data)

    async def order(
        self,
        service: str,
        recipient: str,
        quantity: int,
        *,
        idempotency_key: str,
        max_debit: Amount | None = None,
    ) -> TelegramOrder:
        data = await self._http.request(
            "POST",
            "/telegram/orders",
            json={
                "service": service,
                "recipient": recipient,
                "quantity": quantity,
                "max_debit": None if max_debit is None else as_amount(max_debit),
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
        )
        return self._one(TelegramOrder, data)

    async def get(self, order_id: str) -> TelegramOrder:
        data = await self._http.request("GET", object_path("/telegram/orders", order_id), idempotent=True)
        return self._one(TelegramOrder, data)

    async def list(
        self,
        *,
        status: str | None = None,
        service: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[TelegramOrder]:
        data = await self._http.request(
            "GET",
            "/telegram/orders",
            params={"status": status, "service": service, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(TelegramOrder, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        service: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[TelegramOrder]:
        async for item in self._iter(
            TelegramOrder,
            "/telegram/orders",
            status=status,
            service=service,
            limit=limit,
            before=before,
        ):
            yield item

    async def wait(
        self,
        order_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> TelegramOrder:
        return await self._wait(
            "telegram_order", order_id, timeout=timeout, interval=interval, until=until, long_poll=False,
        )
