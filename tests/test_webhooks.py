from __future__ import annotations

import json
import time

import httpx
import pytest

from lavepay import BadSignature, StaleWebhook, fake_invoice, sign, verify_webhook
from lavepay.integrations.asgi import webhook_app

from .conftest import invoice, make_client

SECRET = "whsec_test"


def event_body(**overrides) -> bytes:
    payload = {
        "id": "evt_1",
        "type": "invoice.paid",
        "created_at": "2026-08-22T09:15:02+00:00",
        "merchant_id": 1,
        "data": invoice(status="paid", paid_at="2026-08-22T09:15:02+00:00"),
    }
    payload.update(overrides)
    return json.dumps(payload, separators=(",", ":")).encode()


def signed(body: bytes, *, ts: int | None = None, secret: str = SECRET) -> dict[str, str]:
    stamp = str(int(time.time()) if ts is None else ts)
    return {
        "x-lavepay-timestamp": stamp,
        "x-lavepay-signature": sign(secret, stamp, body),
    }


def test_signature_roundtrip_and_rejections():
    body = event_body()
    headers = signed(body)
    event = verify_webhook(SECRET, body, headers)
    assert event.type == "invoice.paid"
    assert event.cast().order_id == "ord-1"

    tampered = body + b" "
    with pytest.raises(BadSignature):
        verify_webhook(SECRET, tampered, signed(body))
    with pytest.raises(StaleWebhook):
        verify_webhook(SECRET, body, signed(body, ts=1), now=10_000)


async def test_feed_reaches_handler_once():
    body = event_body()
    headers = signed(body)
    seen = []

    lp, http = make_client(lambda request: httpx.Response(404), webhook_secret=SECRET)

    @lp.invoice_paid()
    async def paid(got):
        seen.append(got.id)

    async with http:
        await lp.feed(body, headers)
        await lp.feed(body, headers)
    assert seen == ["inv_1"]


async def test_asgi_rejects_bad_signature():
    lp, http = make_client(lambda request: httpx.Response(404), webhook_secret=SECRET)
    app = webhook_app(lp)
    body = event_body()
    async with http:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            stamp = str(int(time.time()))
            response = await client.post(
                "/lavepay",
                content=body,
                headers={"x-lavepay-timestamp": stamp, "x-lavepay-signature": "v1=nope"},
            )
    assert response.status_code == 401


async def test_emit_without_network():
    seen = []
    lp, http = make_client(lambda request: httpx.Response(404))

    @lp.invoice_paid()
    async def paid(got, order):
        seen.append((got.status, order))

    async with http:
        await lp.emit("invoice.paid", fake_invoice(), order="A")
    assert seen == [("paid", "A")]
