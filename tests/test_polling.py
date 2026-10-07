from __future__ import annotations

import asyncio

import httpx

from lavepay import PollingConfig

from .conftest import cheque, envelope, invoice, make_client, page


def _client(handler, **config):
    polling = PollingConfig(delay=0, max_rps=0, qr_reverse_for=0, **config)
    return make_client(handler, polling=polling)


async def test_explicit_poll_injects_context_and_stops():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope(invoice(status="paid")))

    lp, http = _client(handler)
    seen = []

    @lp.invoice_paid()
    async def paid(got, message):
        seen.append((got.id, message))
        lp.stop_polling()

    async with http:
        created = await lp.invoices.get("inv_1")
        created.poll(message="hi")
        await asyncio.wait_for(lp.start_polling(), timeout=2)
    assert seen == [("inv_1", "hi")]


async def test_timeout_when_status_does_not_move():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope(invoice(status="active")))

    lp, http = _client(handler, timeout=0)
    seen = []

    @lp.invoice_timeout()
    async def timed_out(got):
        seen.append(got.status)
        lp.stop_polling()

    async with http:
        invoice_obj = await lp.invoices.get("inv_1")
        invoice_obj.poll()
        await asyncio.wait_for(lp.start_polling(), timeout=2)
    assert seen == ["active"]


async def test_cheque_activation_is_its_own_event():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=envelope(cheque(activations_used=1)))

    lp, http = _client(handler)
    seen = []

    @lp.cheque_activated()
    async def activated(got):
        seen.append(got.activations_used)
        lp.stop_polling()

    async with http:
        item = await lp.cheques.get("chq_1")
        item.activations_used = 0
        item.poll()
        await asyncio.wait_for(lp.start_polling(), timeout=2)
    assert seen == [1]


async def test_discover_does_not_replay_then_sees_payment():
    state = {"open": True}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.rstrip("/").endswith("/invoices"):
            if state["open"]:
                return httpx.Response(200, json=page([invoice(status="active")]))
            return httpx.Response(200, json=page([]))
        if "/invoices/" in path:
            return httpx.Response(200, json=envelope(invoice(status="paid")))
        return httpx.Response(200, json=page([]))

    lp, http = _client(handler, discover=True)
    seen = []

    @lp.invoice_paid()
    async def paid(got):
        seen.append(got.status)
        lp.stop_polling()

    async with http:
        await lp.dispatcher.sweep(discover=True)
        assert seen == []
        state["open"] = False
        await lp.dispatcher.sweep(discover=True)
    assert seen == ["paid"]
