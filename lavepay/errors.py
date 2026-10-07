from __future__ import annotations


class LavePayError(Exception):
    """Ошибка API. ``code`` — тот же, что в ответе."""

    code = "error"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        details: dict | None = None,
    ) -> None:
        self.message = message
        self.code = code or type(self).code
        self.status = status
        self.details = dict(details or {})
        super().__init__(message)

    @property
    def retry_after(self) -> float | None:
        value = self.details.get("retry_after")
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class NetworkError(LavePayError):
    code = "network"


class UnauthorizedError(LavePayError):
    code = "unauthorized"


class ForbiddenError(LavePayError):
    code = "forbidden"


class NotFoundError(LavePayError):
    code = "not_found"


class DuplicateOperationError(LavePayError):
    code = "duplicate_operation"


class InsufficientFundsError(LavePayError):
    code = "insufficient_funds"


class LimitExceededError(LavePayError):
    code = "limit_exceeded"


class QuoteExpiredError(LavePayError):
    code = "quote_expired"


class RateChangedError(LavePayError):
    code = "rate_changed"


class PayoutUnavailableError(LavePayError):
    code = "payout_unavailable"


class IdempotencyConflictError(LavePayError):
    code = "idempotency_conflict"


class BuyBlockedError(LavePayError):
    code = "buy_blocked"


class ValidationError(LavePayError):
    code = "validation_error"


class SteamAccountRejectedError(LavePayError):
    code = "steam_account_rejected"


class RateLimitedError(LavePayError):
    code = "rate_limited"


class ProviderError(LavePayError):
    code = "provider_error"


class SteamUnavailableError(LavePayError):
    code = "steam_unavailable"


class SteamPausedError(LavePayError):
    code = "steam_paused"


class BuyUnavailableError(LavePayError):
    code = "buy_unavailable"


class ProviderNotConfiguredError(LavePayError):
    code = "provider_not_configured"


class WebhookError(LavePayError):
    code = "webhook"


class StaleWebhook(WebhookError):
    code = "webhook_stale"


class BadSignature(WebhookError):
    code = "webhook_signature"


BY_CODE: dict[str, type[LavePayError]] = {
    "unauthorized": UnauthorizedError,
    "forbidden": ForbiddenError,
    "not_found": NotFoundError,
    "duplicate_operation": DuplicateOperationError,
    "insufficient_funds": InsufficientFundsError,
    "limit_exceeded": LimitExceededError,
    "quote_expired": QuoteExpiredError,
    "rate_changed": RateChangedError,
    "payout_unavailable": PayoutUnavailableError,
    "idempotency_conflict": IdempotencyConflictError,
    "buy_blocked": BuyBlockedError,
    "validation_error": ValidationError,
    "steam_account_rejected": SteamAccountRejectedError,
    "rate_limited": RateLimitedError,
    "provider_error": ProviderError,
    "steam_unavailable": SteamUnavailableError,
    "steam_paused": SteamPausedError,
    "buy_unavailable": BuyUnavailableError,
    "provider_not_configured": ProviderNotConfiguredError,
}


_HINTS = {
    "unauthorized": "Ключ API не принят. Проверьте его в настройках мерчанта.",
    "forbidden": "Это действие сейчас закрыто у мерчанта.",
    "not_found": "Такого счёта или получателя нет.",
    "duplicate_operation": "Заказ с этим номером уже выставлен на другую сумму.",
    "insufficient_funds": "На балансе мерчанта не хватает средств.",
    "limit_exceeded": "Превышен лимит. Подождите или уменьшите сумму.",
    "quote_expired": "Цена устарела. Запросите её заново.",
    "rate_changed": "Курс изменился. Проверьте сумму и повторите.",
    "payout_unavailable": "Эта выплата сейчас недоступна. Деньги не списаны.",
    "idempotency_conflict": "Этот ключ уже использован для другого платежа.",
    "buy_blocked": "Покупка временно закрыта. Попробуйте позже.",
    "validation_error": "Проверьте введённые данные.",
    "steam_account_rejected": "Этот логин Steam нельзя пополнить.",
    "rate_limited": "Слишком много запросов. Подождите немного.",
    "provider_error": "Поставщик не ответил. Деньги не списаны.",
    "steam_unavailable": "Пополнение Steam сейчас недоступно.",
    "steam_paused": "Пополнение Steam на паузе.",
    "buy_unavailable": "Покупка USDT сейчас недоступна.",
    "provider_not_configured": "Этот способ оплаты сейчас выключен.",
    "network": "Нет связи с Lave Pay. Повторите запрос.",
}


def explain(error: BaseException) -> str:
    """Текст для покупателя. Сообщение сервера сюда не попадает."""
    if isinstance(error, LavePayError):
        return _HINTS.get(error.code, "Платёж сейчас не пройти. Попробуйте ещё раз.")
    return "Платёж сейчас не пройти. Попробуйте ещё раз."


def error_from_payload(payload: dict, status: int) -> LavePayError:
    raw = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raw = {}
    code = str(raw.get("code") or "error")
    message = str(raw.get("message") or code)
    details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
    cls = BY_CODE.get(code, LavePayError)
    return cls(message, code=code, status=status, details=details)
