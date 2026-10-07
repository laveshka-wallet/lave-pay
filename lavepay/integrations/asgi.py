from __future__ import annotations

import json
from typing import Any

from ..errors import BadSignature, StaleWebhook


def webhook_app(lp: Any):

    async def app(scope, receive, send):
        if scope["type"] != "http":
            return
        if scope["method"] != "POST":
            await _send(send, 405, {"ok": False, "error": "method"})
            return
        body = await _body(receive)
        headers = {key.decode().lower(): value.decode() for key, value in scope.get("headers", [])}
        try:
            from ..webhooks import verify_webhook

            event = verify_webhook(lp.webhook_secret, body, headers)
        except StaleWebhook:
            await _send(send, 400, {"ok": False, "error": "stale"})
            return
        except BadSignature:
            await _send(send, 401, {"ok": False, "error": "bad signature"})
            return
        lp.spawn(lp.dispatcher.dispatch_event(event))
        await _send(send, 200, {"ok": True})

    return app


async def _body(receive) -> bytes:
    chunks: list[bytes] = []
    while True:
        message = await receive()
        if message["type"] != "http.request":
            continue
        chunks.append(message.get("body", b""))
        if not message.get("more_body"):
            return b"".join(chunks)


async def _send(send, status: int, payload: dict) -> None:
    body = json.dumps(payload).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status,
            "headers": [(b"content-type", b"application/json")],
        },
    )
    await send({"type": "http.response.body", "body": body})
