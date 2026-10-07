from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .errors import NetworkError, RateLimitedError, error_from_payload
from .money import dump

logger = logging.getLogger("lavepay")

DEFAULT_BASE_URL = "https://api.laveshka.io/merchant/v1"
USER_AGENT = "lavepay/0.1"

Sleep = Callable[[float], Awaitable[None]]


class Transport:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 40.0,
        max_retries: int = 2,
        max_retry_wait: float = 5.0,
        http_client: httpx.AsyncClient | None = None,
        sleep: Sleep = asyncio.sleep,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_retries = max_retries
        self._max_retry_wait = max_retry_wait
        self._sleep = sleep
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        self._closed = False

    async def aclose(self) -> None:
        if self._closed:
            return
        self._closed = True
        if self._owns_client:
            await self._client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        idempotent: bool = False,
        timeout: float | None = None,
    ) -> Any:
        url = self._base_url + "/" + path.lstrip("/")
        body = dump(json)
        query = dump(params)
        headers = {"X-Api-Key": self._api_key}
        request_timeout = timeout if timeout is not None else self._timeout
        attempt = 0
        while True:
            try:
                response = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    json=body,
                    params=query,
                    timeout=request_timeout,
                )
            except httpx.TransportError as exc:
                if not idempotent or attempt >= self._max_retries:
                    raise NetworkError("нет связи с Lave Pay", code="network") from exc
                attempt += 1
                await self._sleep(min(2**attempt, 4))
                continue

            payload = _json(response)
            if response.status_code < 400 and payload.get("ok", True):
                logger.debug("%s %s -> %s", method, path, response.status_code)
                return payload.get("data")

            if response.status_code == 429 and attempt < self._max_retries:
                wait = _retry_after(response, payload)
                if wait is not None and wait <= self._max_retry_wait:
                    attempt += 1
                    await self._sleep(wait)
                    continue

            if response.status_code in (502, 503) and idempotent and attempt < self._max_retries:
                attempt += 1
                await self._sleep(min(2**attempt, 4))
                continue

            error = error_from_payload(payload, response.status_code)
            header_wait = _retry_after(response, payload)
            if isinstance(error, RateLimitedError) and header_wait is not None:
                error.details.setdefault("retry_after", header_wait)
            raise error


def _json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _retry_after(response: httpx.Response, payload: dict) -> float | None:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return float(header)
        except ValueError:
            pass
    error = payload.get("error")
    if isinstance(error, dict) and isinstance(error.get("details"), dict):
        value = error["details"].get("retry_after")
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    return None
