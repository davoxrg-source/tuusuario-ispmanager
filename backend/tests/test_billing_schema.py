from datetime import date

from app.schemas.billing import PromiseToPayCreate


def test_promise_to_pay_create_parses_until_date():
    payload = PromiseToPayCreate(until=date(2026, 9, 1))
    assert payload.until == date(2026, 9, 1)
