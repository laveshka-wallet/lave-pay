from __future__ import annotations

from collections.abc import AsyncIterator

from ..models import BuyOrder, BuyRate
from ..models.base import Page
from ..money import Amount, as_amount, one_of
from .base import Resource, object_path


class Buy(Resource):
    async def rate(
        self,
        *,
        amount_rub: Amount | None = None,
        amount_usdt: Amount | None = None,
    ) -> BuyRate:
        data = await self._http.request(
            "GET",
            "/buy/rate",
            params={
                "amount_rub": None if amount_rub is None else as_amount(amount_rub),
                "amount_usdt": None if amount_usdt is None else as_amount(amount_usdt),
            },
            idempotent=True,
        )
        return self._one(BuyRate, data)

    async def order(
        self,
        *,
        idempotency_key: str,
        amount_rub: Amount | None = None,
        amount_usdt: Amount | None = None,
        max_rate: Amount | None = None,
    ) -> BuyOrder:
        one_of(amount_rub=amount_rub, amount_usdt=amount_usdt)
        data = await self._http.request(
            "POST",
            "/buy/orders",
            json={
                "amount_rub": None if amount_rub is None else as_amount(amount_rub),
                "amount_usdt": None if amount_usdt is None else as_amount(amount_usdt),
                "max_rate": None if max_rate is None else as_amount(max_rate),
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
            timeout=max(self._client._http._timeout, 40),
        )
        return self._one(BuyOrder, data)

    async def get(self, order_id: str) -> BuyOrder:
        data = await self._http.request("GET", object_path("/buy/orders", order_id), idempotent=True)
        return self._one(BuyOrder, data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[BuyOrder]:
        data = await self._http.request(
            "GET",
            "/buy/orders",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(BuyOrder, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[BuyOrder]:
        async for item in self._iter(BuyOrder, "/buy/orders", status=status, limit=limit, before=before):
            yield item

    async def cancel(self, order_id: str) -> BuyOrder:
        data = await self._http.request("POST", object_path("/buy/orders", order_id) + "/cancel")
        return self._one(BuyOrder, data)

    async def wait(
        self,
        order_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> BuyOrder:
        return await self._wait("buy_order", order_id, timeout=timeout, interval=interval, until=until, long_poll=False)
