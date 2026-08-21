from datetime import date

from app.services.billing.invoicing import _month_bounds


def test_month_bounds_mid_month():
    start, end = _month_bounds(date(2026, 2, 15))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_month_bounds_leap_year_february():
    start, end = _month_bounds(date(2028, 2, 10))
    assert start == date(2028, 2, 1)
    assert end == date(2028, 2, 29)


def test_month_bounds_december():
    start, end = _month_bounds(date(2026, 12, 5))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)
