from __future__ import annotations

from collections.abc import AsyncIterator

from ..models import Delivery, DeliveryRef, WebhookHealth
from ..models.base import Page
from .base import Resource, object_path


class Webhooks(Resource):
    async def get(self) -> WebhookHealth:
        data = await self._http.request("GET", "/webhook", idempotent=True)
        return self._one(WebhookHealth, data)

    async def test(self) -> DeliveryRef:
        data = await self._http.request("POST", "/webhook/test")
        return self._one(DeliveryRef, data)

    async def deliveries(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> Page[Delivery]:
        data = await self._http.request(
            "GET",
            "/webhook/deliveries",
            params={"status": status, "limit": limit, "before": before},
            idempotent=True,
        )
        return self._page(Delivery, data)

    async def iter_deliveries(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        before: int | None = None,
    ) -> AsyncIterator[Delivery]:
        async for item in self._iter(
            Delivery, "/webhook/deliveries", status=status, limit=limit, before=before,
        ):
            yield item

    async def retry(self, event_id: str) -> Delivery:
        data = await self._http.request(
            "POST", object_path("/webhook/deliveries", event_id) + "/retry",
        )
        return self._one(Delivery, data)
