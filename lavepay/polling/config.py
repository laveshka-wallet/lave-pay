from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class PollingConfig:
    delay: float = 2.0
    # Пусто — ждём, пока статус закроет само API. Свой предел шлёт ``*.timeout``.
    timeout: float | None = None
    concurrency: int = 5
    max_rps: float = 2.0
    discover: bool = False
    page_limit: int = 100
    max_pages: int = 5
    qr_reverse_for: float = 3600.0
