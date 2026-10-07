from __future__ import annotations

import asyncio
import inspect
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from .config import PollingConfig
from .kinds import KINDS, OPEN_STATUSES, events_for, kind_of

logger = logging.getLogger("lavepay.polling")

_RESOURCES = {
    "invoice": "invoices",
    "cheque": "cheques",
    "qr_payment": "qr",
    "card_payout": "card",
    "steam_order": "steam",
    "telegram_order": "telegram",
    "buy_order": "buy",
}


@dataclass
class _Task:
    kind: str
    id: str
    snapshot: Any
    data: dict[str, Any]
    arm: bool
    explicit: bool
    started: float
    reverse_until: float | None = None


@dataclass
class Dispatcher:

    client: Any
    config: PollingConfig
    deduper: Any
    defaults: dict[str, Any] = field(default_factory=dict)
    _handlers: dict[str, list[tuple[Any, Any]]] = field(default_factory=dict)
    _explicit: dict[tuple[str, str], _Task] = field(default_factory=dict)
    _known: dict[tuple[str, str], _Task] = field(default_factory=dict)
    _stop: asyncio.Event = field(default_factory=asyncio.Event)
    _running: bool = False
    _next_request: float = 0.0

    @property
    def running(self) -> bool:
        return self._running

    def on(self, event: str, handler: Any = None, *, filter: Any = None):

        def deco(fn):
            self._handlers.setdefault(event, []).append((fn, filter))
            return fn

        if callable(handler):
            return deco(handler)
        return deco

    def watch(self, obj: Any, **data: Any) -> None:
        kind = kind_of(obj)
        self._explicit[(kind, obj.id)] = _Task(
            kind=kind,
            id=obj.id,
            snapshot=obj,
            data=data,
            arm=True,
            explicit=True,
            started=time.monotonic(),
        )

    def unwatch(self, obj: Any) -> None:
        kind = kind_of(obj)
        self._explicit.pop((kind, obj.id), None)

    async def emit(
        self,
        event: str,
        obj: Any,
        *,
        extra: dict[str, Any] | None = None,
        event_id: str | None = None,
    ) -> bool:
        keys = _keys(event, obj, event_id)
        if not await self.deduper.claim(*keys):
            logger.debug("событие %s уже обработано", event)
            return False
        merged = {**self.defaults, **(extra or {})}
        called = False
        for fn, predicate in self._handlers.get(event, []):
            if predicate is not None and not await _truthy(predicate(obj)):
                continue
            try:
                await _call(fn, obj, merged, self.client)
            except Exception:
                logger.exception("обработчик %s упал", event)
            called = True
        if not called:
            logger.debug("на %s нет обработчика", event)
        return called

    async def dispatch_event(self, event: Any) -> bool:
        obj = event.cast()
        if hasattr(obj, "bind"):
            obj.bind(self.client)
        return await self.emit(event.type, obj, event_id=event.id)

    async def sweep(self, *, discover: bool | None = None) -> None:
        await self._sweep_explicit()
        use_discover = self.config.discover if discover is None else discover
        if use_discover:
            await self._sweep_discover()

    async def run(self, *, discover: bool | None = None) -> None:
        if self._running:
            raise RuntimeError("поллинг уже запущен")
        self._stop.clear()
        self._running = True
        logger.info("поллинг запущен")
        try:
            while not self._stop.is_set():
                await self.sweep(discover=discover)
                if self._stop.is_set():
                    break
                if self.config.delay <= 0:
                    await asyncio.sleep(0)
                    continue
                try:
                    await asyncio.wait_for(self._stop.wait(), self.config.delay)
                except TimeoutError:
                    pass
        finally:
            self._running = False
            logger.info("поллинг остановлен")

    def stop(self) -> None:
        self._stop.set()

    async def _sweep_explicit(self) -> None:
        tasks = list(self._explicit.values())
        if not tasks:
            return
        sem = asyncio.Semaphore(max(1, self.config.concurrency))

        async def one(task: _Task) -> None:
            async with sem:
                try:
                    fresh = await self._fetch(task.kind, task.id)
                except Exception:
                    logger.exception("не удалось дочитать %s %s", task.kind, task.id)
                    return
                await self._apply(task, fresh, self._explicit)

        await asyncio.gather(*(one(task) for task in tasks))

    async def _sweep_discover(self) -> None:
        explicit = set(self._explicit)
        for kind in KINDS:
            try:
                opened = await self._list_open(kind)
            except Exception:
                logger.exception("не удалось прочитать открытые %s", kind)
                continue
            current: set[tuple[str, str]] = set()
            for obj in opened:
                key = (kind, obj.id)
                current.add(key)
                if key in explicit:
                    continue
                task = self._known.get(key)
                if task is None:
                    self._known[key] = _Task(
                        kind=kind,
                        id=obj.id,
                        snapshot=obj,
                        data={},
                        arm=False,
                        explicit=False,
                        started=time.monotonic(),
                    )
                    continue
                await self._apply(task, obj, self._known)
            for key, task in list(self._known.items()):
                if key[0] != kind or key in current or key in explicit:
                    continue
                try:
                    fresh = await self._fetch(kind, key[1])
                except Exception:
                    logger.exception("не удалось дочитать %s %s", kind, key[1])
                    continue
                await self._apply(task, fresh, self._known)

    async def _apply(self, task: _Task, fresh: Any, store: dict[tuple[str, str], _Task]) -> None:
        if task.arm:
            events = events_for(task.kind, None, fresh, announce=True)
            task.arm = False
        else:
            events = events_for(task.kind, task.snapshot, fresh, announce=False)
        task.snapshot = fresh
        for event in events:
            await self.emit(event, fresh, extra=task.data)
        key = (task.kind, task.id)
        if self._finished(task, fresh):
            store.pop(key, None)
            return
        if self.config.timeout is not None and time.monotonic() >= task.started + self.config.timeout:
            await self.emit(f"{task.kind}.timeout", fresh, extra=task.data)
            store.pop(key, None)

    def _finished(self, task: _Task, obj: Any) -> bool:
        if task.kind == "qr_payment" and obj.status == "completed" and not obj.returned:
            if self.config.qr_reverse_for <= 0:
                return True
            if task.reverse_until is None:
                task.reverse_until = time.monotonic() + self.config.qr_reverse_for
            return time.monotonic() >= task.reverse_until
        if task.kind == "qr_payment" and obj.returned:
            return True
        if task.kind == "buy_order" and obj.status == "overdue":
            return False
        if obj.status in {"active", "pending", "processing", "awaiting_payment"}:
            return False
        return obj.status in {"paid", "expired", "cancelled", "refunded", "completed", "failed"}

    async def _fetch(self, kind: str, obj_id: str) -> Any:
        await self._pace()
        return await getattr(self.client, _RESOURCES[kind]).get(obj_id)

    async def _list_open(self, kind: str) -> list[Any]:
        resource = getattr(self.client, _RESOURCES[kind])
        found: list[Any] = []
        cap = self.config.page_limit * self.config.max_pages
        for status in OPEN_STATUSES[kind]:
            before = None
            for _ in range(self.config.max_pages):
                await self._pace()
                page = await resource.list(status=status, limit=self.config.page_limit, before=before)
                found.extend(page.items)
                if page.next_cursor is None or len(found) >= cap:
                    break
                before = page.next_cursor
            if len(found) >= cap:
                break
        return found

    async def _pace(self) -> None:
        if self.config.max_rps <= 0:
            return
        gap = 1 / self.config.max_rps
        now = time.monotonic()
        wait = self._next_request - now
        self._next_request = max(now, self._next_request) + gap
        if wait > 0:
            await asyncio.sleep(wait)


def _keys(event: str, obj: Any, event_id: str | None) -> list[str]:
    keys: list[str] = []
    if event_id:
        keys.append(f"webhook:{event_id}")
    object_id = getattr(obj, "id", None)
    if object_id:
        suffix = ""
        if event == "cheque.activated":
            suffix = f":{getattr(obj, 'activations_used', 0)}"
        keys.append(f"state:{event}:{object_id}{suffix}")
    return keys


async def _truthy(value: Any) -> bool:
    if inspect.isawaitable(value):
        value = await value
    return bool(value)


async def _call(fn: Any, obj: Any, extra: dict[str, Any], client: Any) -> None:
    sig = inspect.signature(fn)
    params = [
        param
        for param in sig.parameters.values()
        if param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    ]
    args: list[Any] = []
    kwargs: dict[str, Any] = {}
    if params and params[0].kind is not inspect.Parameter.KEYWORD_ONLY:
        args.append(obj)
        rest = params[1:]
    elif params:
        kwargs[params[0].name] = obj
        rest = params[1:]
    else:
        rest = []
    has_var_kw = any(param.kind is inspect.Parameter.VAR_KEYWORD for param in sig.parameters.values())
    for param in rest:
        if param.name in extra:
            kwargs[param.name] = extra[param.name]
        elif param.name == "lavepay":
            kwargs["lavepay"] = client
    if has_var_kw:
        used = set(kwargs)
        if params:
            used.add(params[0].name)
        for key, value in extra.items():
            if key not in used:
                kwargs[key] = value
    result = fn(*args, **kwargs)
    if inspect.isawaitable(result):
        await result
