from __future__ import annotations

import asyncio
from collections import OrderedDict
from typing import Protocol


class Deduper(Protocol):
    async def claim(self, *keys: str) -> bool:
        """True, если эти ключи ещё не занимали."""


class MemoryDeduper:
    """Память процесса. Старые ключи вытесняет, между рестартами не живёт."""

    def __init__(self, max_size: int = 100_000) -> None:
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def claim(self, *keys: str) -> bool:
        if not keys:
            return True
        async with self._lock:
            if any(key in self._seen for key in keys):
                return False
            for key in keys:
                self._seen[key] = None
            while len(self._seen) > self._max_size:
                self._seen.popitem(last=False)
            return True
