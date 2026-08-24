from unittest.mock import patch

import pytest

from app.workers.retry import run_with_retries


def test_succeeds_on_first_try():
    calls = []
    attempts = []

    def fn():
        calls.append(1)
        return "ok"

    with patch("app.workers.retry.time.sleep") as sleep_mock:
        result = run_with_retries(
            fn,
            max_attempts=3,
            backoff_base_seconds=1,
            backoff_max_seconds=10,
            on_attempt=attempts.append,
        )

    assert result == "ok"
    assert len(calls) == 1
    assert len(attempts) == 1
    assert attempts[0].succeeded is True
    sleep_mock.assert_not_called()


def test_fails_twice_then_succeeds_with_backoff():
    calls = []
    attempts = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise RuntimeError("timeout")
        return "ok"

    with patch("app.workers.retry.time.sleep") as sleep_mock:
        result = run_with_retries(
            fn,
            max_attempts=3,
            backoff_base_seconds=5,
            backoff_max_seconds=30,
            on_attempt=attempts.append,
        )

    assert result == "ok"
    assert len(calls) == 3
    assert [a.succeeded for a in attempts] == [False, False, True]
    # Backoff exponencial: 5s tras el primer fallo, 10s tras el segundo.
    sleep_mock.assert_any_call(5)
    sleep_mock.assert_any_call(10)
    assert sleep_mock.call_count == 2


def test_exhausts_attempts_and_raises_last_error():
    calls = []
    attempts = []

    def fn():
        calls.append(1)
        raise RuntimeError(f"fallo {len(calls)}")

    with patch("app.workers.retry.time.sleep"):
        with pytest.raises(RuntimeError, match="fallo 3"):
            run_with_retries(
                fn,
                max_attempts=3,
                backoff_base_seconds=1,
                backoff_max_seconds=10,
                on_attempt=attempts.append,
            )

    assert len(calls) == 3
    assert all(not a.succeeded for a in attempts)
    assert len(attempts) == 3
