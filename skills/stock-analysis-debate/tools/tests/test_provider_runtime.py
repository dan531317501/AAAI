import requests

import provider_runtime
from provider_runtime import RetryPolicy, retry_call


def test_retry_call_retries_transient_error_then_succeeds():
    calls = []
    sleeps = []

    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise requests.ConnectionError("connection reset")
        return {"ok": True}

    result = retry_call(
        operation,
        provider="test",
        operation="transient",
        policy=RetryPolicy(max_attempts=4, base_delay_seconds=1, jitter_seconds=0),
        sleep=sleeps.append,
    )

    assert result == {"ok": True}
    assert len(calls) == 3
    assert sleeps == [1, 2]


def test_retry_call_does_not_retry_non_transient_http_400():
    calls = []
    response = requests.Response()
    response.status_code = 400

    def operation():
        calls.append(1)
        raise requests.HTTPError("bad request", response=response)

    try:
        retry_call(
            operation,
            provider="test",
            operation="bad_request",
            sleep=lambda _: None,
        )
    except requests.HTTPError:
        pass
    else:
        raise AssertionError("HTTP 400 must propagate")

    assert len(calls) == 1


def test_retry_call_retries_http_429_and_records_trace():
    provider_runtime.clear_retry_events()
    response = requests.Response()
    response.status_code = 429
    calls = []

    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise requests.HTTPError("rate limited", response=response)
        return "ok"

    assert retry_call(
        operation,
        provider="test",
        operation="rate_limit",
        sleep=lambda _: None,
        random_uniform=lambda *_: 0,
    ) == "ok"
    events = provider_runtime.get_retry_events()
    assert events[-2]["http_status"] == 429
    assert events[-2]["retryable"] is True
    assert events[-1]["status"] == "success"


def test_retry_call_retries_empty_or_invalid_response():
    responses = [{}, {"data": [1]}]

    result = retry_call(
        lambda: responses.pop(0),
        provider="test",
        operation="schema_validation",
        validator=lambda value: bool(value.get("data")),
        sleep=lambda _: None,
        random_uniform=lambda *_: 0,
    )

    assert result == {"data": [1]}
