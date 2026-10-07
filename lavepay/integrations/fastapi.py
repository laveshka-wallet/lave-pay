from typing import Any

from ..errors import BadSignature, StaleWebhook
from ..webhooks import WebhookEvent, verify_webhook


def _missing() -> None:
    raise ImportError("Установите extra: pip install 'lavepay[fastapi]'")


def install(app: Any, lp: Any, *, path: str = "/lavepay") -> None:
    try:
        from fastapi import APIRouter, HTTPException, Request
    except ImportError:
        _missing()
    if not lp.webhook_secret:
        raise RuntimeError("для вебхука нужен webhook_secret")

    router = APIRouter()

    # без from __future__ import annotations: FastAPI иначе не видит Request
    @router.post(path)
    async def receive(request: Request):
        body = await request.body()
        try:
            event = verify_webhook(lp.webhook_secret, body, request.headers)
        except StaleWebhook as exc:
            raise HTTPException(400, "stale") from exc
        except BadSignature as exc:
            raise HTTPException(401, "bad signature") from exc
        lp.spawn(lp.dispatcher.dispatch_event(event))
        return {"ok": True}

    app.include_router(router)
    app.state.lavepay = lp
    app.router.add_event_handler("shutdown", lp.aclose)


def webhook_event(lp: Any):
    try:
        from fastapi import HTTPException, Request
    except ImportError:
        _missing()

    async def dependency(request: Request) -> WebhookEvent:
        body = await request.body()
        try:
            return verify_webhook(lp.webhook_secret, body, request.headers)
        except StaleWebhook as exc:
            raise HTTPException(400, "stale") from exc
        except BadSignature as exc:
            raise HTTPException(401, "bad signature") from exc

    return dependency
