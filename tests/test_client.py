from __future__ import annotations

from decimal import Decimal

import httpx
import pytest

from lavepay import InsufficientFundsError, LavePayError, RateLimitedError, explain, idempotency_key
from lavepay.money import as_amount

from .conftest import cheque, envelope, invoice, make_client, page


def test_amount_rejects_float():
    with pytest.raises(TypeError):
        as_amount(1.5)


def test_idempotency_key_is_stable():
    assert idempotency_key("order", 1042) == idempotency_key("order", 1042)
    assert idempotency_key("order", 1042) != idempotency_key("order", 1043)
    assert len(idempotency_key()) == 32


def test_explain_hides_server_text():
    error = InsufficientFundsError("balance 0.01 merchant 12", code="insufficient_funds", status=409)
    assert "0.01" not in explain(error)
    assert "баланс" in explain(error).lower()


async def test_create_invoice_sends_decimal_string_and_key():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["key"] = request.headers["x-api-key"]
        seen["body"] = request.read()
        return httpx.Response(200, json=envelope(invoice()))

    lp, http = make_client(handler)
    async with http:
        created = await lp.invoices.create(Decimal("12.34"), order_id="ord-1", description="Набор")
    assert seen["key"] == "LAVE-1-test"
    assert b'"12.34"' in seen["body"]
    assert created.amount == Decimal("12.34")
    assert created.pay_url.startswith("https://t.me/")


async def test_float_amount_never_leaves_the_client():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("запрос не должен уйти")

    lp, http = make_client(handler)
    async with http:
        with pytest.raises(TypeError):
            await lp.invoices.create(12.34)


async def test_error_code_becomes_typed_exception():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "ok": False,
                "data": None,
                "error": {"code": "insufficient_funds", "message": "Insufficient funds", "details": {}},
            },
        )

    lp, http = make_client(handler)
    async with http:
        with pytest.raises(InsufficientFundsError) as caught:
            await lp.invoices.refund("inv_1")
    assert caught.value.status == 409


async def test_unknown_code_stays_base_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={"ok": False, "error": {"code": "future_code", "message": "later", "details": {"a": 1}}},
        )

    lp, http = make_client(handler)
    async with http:
        with pytest.raises(LavePayError) as caught:
            await lp.me()
    assert caught.value.code == "future_code"
    assert type(caught.value) is LavePayError


async def test_rate_limit_is_retried():
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={
                    "ok": False,
                    "error": {"code": "rate_limited", "message": "Too many", "details": {"retry_after": 0}},
                },
            )
        return httpx.Response(200, json=envelope(invoice(status="paid")))

    lp, http = make_client(handler)
    async with http:
        loaded = await lp.invoices.get("inv_1")
    assert calls["n"] == 2
    assert loaded.status == "paid"
    assert isinstance(RateLimitedError("x", code="rate_limited", status=429, details={"retry_after": 0}), RateLimitedError)


async def test_pagination_walks_cursor():
    def handler(request: httpx.Request) -> httpx.Response:
        before = request.url.params.get("before")
        if before is None:
            return httpx.Response(200, json=page([invoice(id="inv_1")], cursor=10))
        assert before == "10"
        return httpx.Response(200, json=page([invoice(id="inv_2", order_id="ord-2")]))

    lp, http = make_client(handler)
    async with http:
        ids = [item.id async for item in lp.invoices.iter()]
    assert ids == ["inv_1", "inv_2"]


async def test_card_payout_requires_one_amount():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("запрос не должен уйти")

    lp, http = make_client(handler)
    async with http:
        with pytest.raises(ValueError):
            await lp.card.payout("2200700000000000", idempotency_key="k")


async def test_matches_checks_paid_amount_and_order():
    from lavepay import fake_invoice

    paid = fake_invoice(amount="12.34", order_id="ord-1", currency="USD")
    assert paid.matches(amount="12.34", currency="usd", order_id="ord-1")
    assert not paid.matches(amount="12.35", order_id="ord-1")
    assert not fake_invoice(status="active").matches(order_id="ord-1")
    assert paid.payload_json() is None
    paid.payload = '{"cart": 7}'
    assert paid.payload_json() == {"cart": 7}


async def test_cheque_shortcut_cancel_path():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        return httpx.Response(200, json=envelope(cheque(status="cancelled")))

    lp, http = make_client(handler)
    async with http:
        created = (await lp.cheques.get("chq_1"))
        cancelled = await created.cancel()
    assert seen["path"].endswith("/cheques/chq_1/cancel")
    assert cancelled.status == "cancelled"
