"""Deterministic provider retries, response validation, and audit traces."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import random
import time
from typing import Any, Callable

import requests


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 8.0
    jitter_seconds: float = 0.25


_EVENTS: list[dict[str, Any]] = []


class ResponseValidationError(ValueError):
    """Provider returned an empty or structurally unusable response."""


def clear_retry_events() -> None:
    _EVENTS.clear()


def get_retry_events() -> list[dict[str, Any]]:
    return [dict(event) for event in _EVENTS]


def _status_code(error: BaseException) -> int | None:
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    return int(status) if isinstance(status, int) else None


def is_retryable(error: BaseException) -> bool:
    """Retry only transient transport failures, throttling, and server errors."""
    status = _status_code(error)
    if status is not None:
        return status in (408, 425, 429) or 500 <= status <= 599
    if isinstance(error, ResponseValidationError):
        return True
    if isinstance(
        error,
        (
            TimeoutError,
            ConnectionError,
            requests.Timeout,
            requests.ConnectionError,
        ),
    ):
        return True
    name = type(error).__name__.casefold()
    message = str(error).casefold()
    return (
        any(token in name for token in ("timeout", "connection", "ratelimit"))
        or any(token in message for token in (
            "connection reset", "connection aborted", "timed out",
            "too many requests", "rate limit", "http 429",
        ))
    )


def retry_call(
    func: Callable[[], Any],
    *,
    provider: str,
    operation: str,
    policy: RetryPolicy | None = None,
    validator: Callable[[Any], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    random_uniform: Callable[[float, float], float] = random.uniform,
) -> Any:
    """Call a provider with classified exponential backoff and an audit trail."""
    policy = policy or RetryPolicy()
    if policy.max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")

    for attempt in range(1, policy.max_attempts + 1):
        started_at = datetime.now(timezone.utc).isoformat()
        try:
            value = func()
            if validator is not None and not validator(value):
                raise ResponseValidationError(
                    "provider response failed schema/empty validation"
                )
            _EVENTS.append({
                "provider": provider,
                "operation": operation,
                "attempt": attempt,
                "started_at": started_at,
                "status": "success",
            })
            return value
        except Exception as error:
            retryable = is_retryable(error)
            final = attempt >= policy.max_attempts or not retryable
            event = {
                "provider": provider,
                "operation": operation,
                "attempt": attempt,
                "started_at": started_at,
                "status": "failed",
                "retryable": retryable,
                "error_type": type(error).__name__,
                "error": str(error)[:500],
                "http_status": _status_code(error),
            }
            _EVENTS.append(event)
            if final:
                raise
            delay = min(
                policy.max_delay_seconds,
                policy.base_delay_seconds * (2 ** (attempt - 1)),
            ) + random_uniform(0.0, policy.jitter_seconds)
            event["next_delay_seconds"] = round(delay, 3)
            sleep(delay)
    raise RuntimeError("retry loop exhausted")


def request_json(
    method: str,
    url: str,
    *,
    provider: str,
    operation: str,
    policy: RetryPolicy | None = None,
    session: Any = requests,
    validator: Callable[[Any], bool] | None = None,
    **kwargs: Any,
) -> Any:
    """Issue an HTTP request and validate that the decoded JSON is usable."""
    def call() -> Any:
        response = session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    return retry_call(
        call,
        provider=provider,
        operation=operation,
        policy=policy,
        validator=validator or (lambda value: value is not None),
    )
