from __future__ import annotations

import asyncio
from typing import Any

from ..tools import payment_url

_PREFIX = "lavepay:check:"
_STATUS = {
    "active": "Счёт ещё ждёт оплату",
    "paid": "Счёт оплачен",
    "expired": "Срок счёта вышел",
    "cancelled": "Счёт отменён",
    "refunded": "Оплата возвращена",
}


def _aiogram():
    try:
        from aiogram import BaseMiddleware, Router
        from aiogram.filters import Filter
        from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
    except ImportError as exc:
        raise ImportError("Установите extra: pip install 'lavepay[aiogram]'") from exc
    return BaseMiddleware, Router, Filter, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup


def pay_keyboard(invoice: Any, *, pay: str = "Оплатить", check: str | None = None):
    _, _, _, _, InlineKeyboardButton, InlineKeyboardMarkup = _aiogram()
    rows = [[InlineKeyboardButton(text=pay, url=payment_url(invoice))]]
    if check:
        rows.append(
            [InlineKeyboardButton(text=check, callback_data=f"{_PREFIX}{invoice.id}")],
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def check_text(status: str) -> str:
    return _STATUS.get(status, "Статус счёта обновлён")


async def invoice_check_text(lp: Any, invoice_id: str) -> str:
    invoice = await lp.invoices.get(invoice_id)
    return check_text(invoice.status)


def install(
    dp: Any,
    lp: Any,
    *,
    poll: bool = True,
    aiohttp_app: Any = None,
    webhook_path: str = "/lavepay",
) -> None:
    """Поллинг поднимается вместе с ботом. Кнопка «проверить» заказ не выдаёт."""
    BaseMiddleware, Router, Filter, CallbackQuery, _, _ = _aiogram()
    if aiohttp_app is not None:
        from .aiohttp import mount

        mount(aiohttp_app, lp, webhook_path)
        poll = False

    class _Middleware(BaseMiddleware):
        async def __call__(self, handler, event, data):
            data["lavepay"] = lp
            return await handler(event, data)

    dp.update.middleware(_Middleware())

    class _Check(Filter):
        async def __call__(self, query: CallbackQuery) -> bool:
            return bool(query.data and query.data.startswith(_PREFIX))

    router = Router()

    @router.callback_query(_Check())
    async def on_check(query: CallbackQuery):
        invoice_id = (query.data or "").removeprefix(_PREFIX)
        text = await invoice_check_text(lp, invoice_id)
        await query.answer(text, show_alert=True)

    dp.include_router(router)

    if not poll:
        return

    task: asyncio.Task | None = None

    async def _startup() -> None:
        nonlocal task
        task = asyncio.create_task(lp.start_polling())

    async def _shutdown() -> None:
        lp.stop_polling()
        if task is None:
            return
        try:
            await asyncio.wait_for(task, timeout=5)
        except TimeoutError:
            task.cancel()

    dp.startup.register(_startup)
    dp.shutdown.register(_shutdown)
