from __future__ import annotations

import io


def payment_png(url: str, *, scale: int = 6) -> bytes:
    try:
        import segno
    except ImportError as exc:
        raise ImportError("Установите extra: pip install 'lavepay[qr]'") from exc
    buffer = io.BytesIO()
    segno.make(url).save(buffer, kind="png", scale=scale)
    return buffer.getvalue()
