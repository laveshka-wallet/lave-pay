from __future__ import annotations

import asyncio
import time

import httpx
import pytest
from fastapi import FastAPI

from lavepay import fake_invoice, sign
from lavepay.integrations.aiogram import check_text, install, pay_keyboard
from lavepay.integrations.fastapi import install as install_fastapi
from lavepay.integrations.qr import payment_png

from .conftest import invoice, make_client

SECRET = "whsec_test"


def _body() -> bytes:
    import json

    return json.dumps(
        {
            "id": "evt_web",
            "type": "invoice.paid",
            "created_at": "2026-08-22T09:15:02+00:00",
            "merchant_id": 1,
            "data": invoice(status="paid"),
        },
        separators=(",", ":"),
    ).encode()


def _headers(body: bytes) -> dict[str, str]:
    stamp = str(int(time.time()))
    return {
        "x-lavepay-timestamp": stamp,
        "x-lavepay-signature": sign(SECRET, stamp, body),
        "content-type": "application/json",
    }


async def test_fastapi_answers_before_the_handler_finishes():
    lp, http = make_client(lambda request: httpx.Response(404), webhook_secret=SECRET)
    started = asyncio.Event()

    @lp.invoice_paid()
    async def paid(got):
        started.set()
        await asyncio.Event().wait()

    app = FastAPI()
    install_fastapi(app, lp)
    body = _body()
    async with http:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await asyncio.wait_for(
                client.post("/lavepay", content=body, headers=_headers(body)),
                timeout=2,
            )
        await asyncio.wait_for(started.wait(), timeout=2)
        assert response.status_code == 200
        assert response.json() == {"ok": True}
        await lp.aclose()


def test_keyboard_and_check_text():
    from aiogram import Dispatcher

    invoice_obj = fake_invoice()
    markup = pay_keyboard(invoice_obj, check="Проверить оплату")
    assert markup.inline_keyboard[0][0].url == invoice_obj.pay_url
    assert markup.inline_keyboard[1][0].callback_data == f"lavepay:check:{invoice_obj.id}"
    assert check_text("expired") == "Срок счёта вышел"

    lp, _http = make_client(lambda request: httpx.Response(404))
    dp = Dispatcher()
    install(dp, lp, poll=True)
    assert dp.startup.handlers
    assert dp.shutdown.handlers


def test_payment_png_is_a_png():
    blob = payment_png("https://t.me/laveshka?startapp=lpay_x")
    assert blob.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_check_callback_reads_status():
    from lavepay.integrations.aiogram import invoice_check_text

    def handler(request: httpx.Request) -> httpx.Response:
        from .conftest import envelope

        return httpx.Response(200, json=envelope(invoice(status="paid")))

    lp, http = make_client(handler)
    async with http:
        text = await invoice_check_text(lp, "inv_1")
    assert text == "Счёт оплачен"
