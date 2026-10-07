from __future__ import annotations

import httpx
import pytest

from lavepay import LavePay, PollingConfig


def envelope(data):
    return {"ok": True, "data": data}


def invoice(**overrides):
    data = {
        "id": "inv_1",
        "merchant_id": 1,
        "status": "active",
        "amount": "12.34",
        "fee": "0.13",
        "net": "12.21",
        "currency": "USD",
        "order_id": "ord-1",
        "payload": "",
        "pay_url": "https://t.me/laveshka?startapp=lpay_x",
        "created_at": "2026-08-22T09:10:00+00:00",
    }
    data.update(overrides)
    return data


def cheque(**overrides):
    data = {
        "id": "chq_1",
        "public_id": "CQ1",
        "status": "active",
        "amount": "5.00",
        "total": "5.00",
        "currency": "USD",
        "activations_total": 1,
        "activations_used": 0,
        "url": "https://t.me/laveshka_robot?startapp=chq_x",
        "idempotency_key": "payout-1",
    }
    data.update(overrides)
    return data


def page(items, cursor=None):
    return envelope({"items": items, "next_cursor": cursor})


@pytest.fixture
def polling_config():
    return PollingConfig(delay=0, max_rps=0, timeout=None, qr_reverse_for=0)


def make_client(handler, **kwargs) -> tuple[LavePay, httpx.AsyncClient]:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    lp = LavePay(
        "LAVE-1-test",
        base_url="https://api.test/merchant/v1",
        http_client=http,
        polling=kwargs.pop("polling", PollingConfig(delay=0, max_rps=0)),
        **kwargs,
    )
    return lp, http
