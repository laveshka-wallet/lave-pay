from __future__ import annotations

from collections.abc import AsyncIterator

from ..models import Cheque, Transfer
from ..models.base import Page
from ..money import Amount, as_amount
from .base import Resource, object_path


class Transfers(Resource):
    async def create(
        self,
        recipient: str,
        amount: Amount,
        *,
        idempotency_key: str,
        comment: str = "",
    ) -> Transfer:
        data = await self._http.request(
            "POST",
            "/transfers",
            json={
                "recipient": recipient,
                "amount": as_amount(amount),
                "comment": comment,
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
        )
        return self._one(Transfer, data)


class Cheques(Resource):
    async def create(
        self,
        amount: Amount,
        *,
        idempotency_key: str,
        asset: str = "USDT",
        activations: int = 1,
        comment: str = "",
        recipient: str = "",
    ) -> Cheque:
        data = await self._http.request(
            "POST",
            "/cheques",
            json={
                "amount": as_amount(amount),
                "asset": asset,
                "activations": activations,
                "comment": comment,
                "recipient": recipient,
                "idempotency_key": idempotency_key,
            },
            idempotent=True,
        )
        return self._one(Cheque, data)

    async def get(self, cheque_id: str) -> Cheque:
        data = await self._http.request("GET", object_path("/cheques", cheque_id), idempotent=True)
        return self._one(Cheque, data)

    async def list(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[Cheque]:
        data = await self._http.request(
            "GET",
            "/cheques",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(Cheque, data)

    async def iter(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[Cheque]:
        async for item in self._iter(Cheque, "/cheques", status=status, limit=limit, before=before):
            yield item

    async def cancel(self, cheque_id: str) -> Cheque:
        data = await self._http.request("POST", object_path("/cheques", cheque_id) + "/cancel")
        return self._one(Cheque, data)

    async def wait(
        self,
        cheque_id: str,
        *,
        timeout: float = 60,
        interval: float = 2,
        until: str | None = None,
    ) -> Cheque:
        return await self._wait("cheque", cheque_id, timeout=timeout, interval=interval, until=until, long_poll=False)
