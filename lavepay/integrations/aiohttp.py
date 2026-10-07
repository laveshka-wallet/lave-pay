from __future__ import annotations

from typing import Any

from ..errors import BadSignature, StaleWebhook


def mount(app: Any, lp: Any, path: str = "/lavepay") -> None:
    try:
        from aiohttp import web
    except ImportError as exc:
        raise ImportError("Установите extra: pip install 'lavepay[aiohttp]'") from exc

    async def handle(request):
        body = await request.read()
        try:
            await lp.feed(body, request.headers)
        except StaleWebhook:
            return web.json_response({"ok": False, "error": "stale"}, status=400)
        except BadSignature:
            return web.json_response({"ok": False, "error": "bad signature"}, status=401)
        return web.json_response({"ok": True})

    app.router.add_post(path, handle)
