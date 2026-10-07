from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from ..models import HistoryItem, Invoice
from ..models.base import Page
from ..money import Amount, as_amount
from .base import Resource, object_path


class Invoices(Resource):
    async def create(
        self,
        amount: Amount,
        *,
        currency: str = "USD",
        accept: list[str] | None = None,
        description: str = "",
        order_id: str = "",
        payload: str = "",
        return_url: str = "",
        ttl: int | None = None,
    ) -> Invoice:
        data = await self._http.request(
            "POST",
            "/invoices",
            json={
                "amount": as_amount(amount),
                "currency": currency,
                "accept": accept,
                "description": description,
                "order_id": order_id,
                "payload": payload,
                "return_url": return_url,
                "ttl": ttl,
            },
            idempotent=bool(order_id),
        )
        return self._one(Invoice, data)

    async def get(self, invoice_id: str) -> Invoice:
        data = await self._http.request("GET", object_path("/invoices", invoice_id), idempotent=True)
        return self._one(Invoice, data)

    async def list(
        self,
        *,
        status: str | None = None,
        order_id: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[Invoice]:
        data = await self._http.request(
            "GET",
            "/invoices",
            params={"status": status, "order_id": order_id, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(Invoice, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        order_id: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[Invoice]:
        async for item in self._iter(
            Invoice, "/invoices", status=status, order_id=order_id, limit=limit, before=before,
        ):
            yield item

    async def cancel(self, invoice_id: str) -> Invoice:
        data = await self._http.request("POST", object_path("/invoices", invoice_id) + "/cancel")
        return self._one(Invoice, data)

    async def refund(self, invoice_id: str) -> Invoice:
        data = await self._http.request("POST", object_path("/invoices", invoice_id) + "/refund")
        return self._one(Invoice, data)

    async def wait(
        self,
        invoice_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> Invoice:
        return await self._wait("invoice", invoice_id, timeout=timeout, interval=interval, until=until, long_poll=False)


class History(Resource):
    async def list(self, *, limit: int = 50, before: int | None = None) -> Page[HistoryItem]:
        data = await self._http.request(
            "GET", "/history", params={"limit": limit, "before": before}, idempotent=True,
        )
        return self._page(HistoryItem, data)

    async def iter(self, *, limit: int = 50, before: int | None = None) -> AsyncIterator[HistoryItem]:
        async for item in self._iter(HistoryItem, "/history", limit=limit, before=before):
            yield item

    def get(self, *_: Any, **__: Any) -> Any:
        raise TypeError("история читается списком")
