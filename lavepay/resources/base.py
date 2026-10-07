from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import quote

from ..models.base import Page
from ..polling.kinds import WAIT_DONE


class Resource:
    def __init__(self, client: Any) -> None:
        self._client = client

    @property
    def _http(self):
        return self._client._http

    def _one(self, model: type, data: Any):
        if data is None:
            return None
        return model.model_validate(data).bind(self._client)

    def _page(self, model: type, data: dict) -> Page:
        items = [self._one(model, row) for row in data.get("items") or []]
        return Page(items, data.get("next_cursor"))

    async def _iter(self, model: type, path: str, **filters: Any) -> AsyncIterator:
        before = filters.pop("before", None)
        while True:
            params = {key: value for key, value in filters.items() if value is not None}
            if before is not None:
                params["before"] = before
            data = await self._http.request("GET", path, params=params, idempotent=True)
            page = self._page(model, data)
            for item in page.items:
                yield item
            if page.next_cursor is None:
                return
            before = page.next_cursor

    async def _wait(
        self,
        kind: str,
        obj_id: str,
        *,
        timeout: float,
        interval: float,
        until: str | None,
        long_poll: bool,
    ):
        deadline = time.monotonic() + timeout
        known: str | None = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"статус {obj_id} не сменился за {timeout} с")
            if long_poll:
                obj = await self.get(obj_id, wait=min(25, remaining), known=known)  # type: ignore[attr-defined]
            else:
                obj = await self.get(obj_id)  # type: ignore[attr-defined]
            if (until is not None and obj.status == until) or obj.status in WAIT_DONE[kind]:
                return obj
            known = obj.status
            if not long_poll:
                pause = min(interval, max(0.0, deadline - time.monotonic()))
                await asyncio.sleep(pause)


def object_path(prefix: str, obj_id: str) -> str:
    return f"{prefix}/{quote(str(obj_id), safe='')}"
