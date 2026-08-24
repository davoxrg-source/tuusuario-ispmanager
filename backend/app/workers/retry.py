"""Reintento con backoff exponencial para llamadas de red de un solo intento
lógico (ej. consultar un Mikrotik). Puro -- sin dependencias de DB/app -- para
poder reusarlo fuera de los workers si hace falta."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class AttemptOutcome:
    attempt_number: int
    max_attempts: int
    succeeded: bool
    error: Exception | None
    duration_ms: int


def run_with_retries(
    fn: Callable[[], T],
    *,
    max_attempts: int,
    backoff_base_seconds: float,
    backoff_max_seconds: float,
    on_attempt: Callable[[AttemptOutcome], None],
) -> T:
    """Llama a fn() hasta max_attempts veces. Después de CADA intento (éxito o
    fallo) invoca on_attempt -- así quien llama puede persistir el intento de
    inmediato, sin esperar al resultado final. Si se agotan los intentos,
    relanza la última excepción."""
    delay = backoff_base_seconds
    last_error: Exception | None = None

    for attempt_number in range(1, max_attempts + 1):
        start = time.monotonic()
        try:
            result = fn()
        except Exception as exc:  # noqa: BLE001
            duration_ms = int((time.monotonic() - start) * 1000)
            last_error = exc
            on_attempt(
                AttemptOutcome(
                    attempt_number=attempt_number,
                    max_attempts=max_attempts,
                    succeeded=False,
                    error=exc,
                    duration_ms=duration_ms,
                )
            )
            if attempt_number < max_attempts:
                time.sleep(delay)
                delay = min(delay * 2, backoff_max_seconds)
            continue

        duration_ms = int((time.monotonic() - start) * 1000)
        on_attempt(
            AttemptOutcome(
                attempt_number=attempt_number,
                max_attempts=max_attempts,
                succeeded=True,
                error=None,
                duration_ms=duration_ms,
            )
        )
        return result

    assert last_error is not None
    raise last_error
