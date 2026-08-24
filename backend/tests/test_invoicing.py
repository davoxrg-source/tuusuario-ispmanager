from datetime import date, datetime, timezone

from app.models.billing_settings import BillingSettings, ProrationTarget, ReconnectionFeeMode
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.plan import Plan
from app.services.billing.invoicing import (
    _month_bounds,
    apply_late_fees,
    apply_proration_if_needed,
    apply_reconnection_fee,
    generate_monthly_invoices,
    suspend_clients_with_overdue_invoices,
)


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


def _default_settings(**overrides) -> BillingSettings:
    settings = BillingSettings(
        # 31 por defecto (siempre abierta) -- salvo en el test dedicado a
        # esta ventana, no queremos que las demás pruebas dependan de en qué
        # día del mes cae `reference`.
        generate_invoice_days_before_due=31,
        suspend_days_after_due=5,
        proration_enabled=False,
        proration_min_days=1,
        proration_target=ProrationTarget.NEXT_INVOICE,
        late_fee_enabled=False,
        late_fee_amount=0,
        late_fee_apply_hour=0,
        reconnection_fee_mode=ReconnectionFeeMode.OFF,
        reconnection_fee_amount=0,
        invoice_folio_prefix="F-",
        invoice_folio_next_number=1,
    )
    for field, value in overrides.items():
        setattr(settings, field, value)
    return settings


def _make_client(db_session, **overrides) -> Client:
    plan = Plan(name=f"Plan-{overrides.get('_unique', 'x')}", download_speed_mbps=10, upload_speed_mbps=10, price=300)
    db_session.add(plan)
    db_session.commit()
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, plan_id=plan.id)
    for field, value in overrides.items():
        if field != "_unique":
            setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_generate_monthly_invoices_assigns_sequential_folios(db_session):
    client_a = _make_client(db_session, _unique="a")
    client_b = _make_client(db_session, _unique="b")
    settings = _default_settings()

    created = generate_monthly_invoices(db_session, settings, reference=date(2026, 3, 15))

    folios = sorted(inv.folio for inv in created)
    assert folios == ["F-000001", "F-000002"]
    assert settings.invoice_folio_next_number == 3


def test_generate_monthly_invoices_respects_days_before_due_window(db_session):
    _make_client(db_session, _unique="a")
    settings = _default_settings(generate_invoice_days_before_due=3)

    # 15 de marzo está a más de 3 días del fin de mes (31) -- todavía no se
    # abre la ventana de generación.
    created = generate_monthly_invoices(db_session, settings, reference=date(2026, 3, 15))
    assert created == []

    # 29 de marzo sí está dentro de la ventana (2 días antes del 31).
    created = generate_monthly_invoices(db_session, settings, reference=date(2026, 3, 29))
    assert len(created) == 1


def test_generate_monthly_invoices_consumes_pending_credit(db_session):
    client = _make_client(db_session, _unique="a", pending_credit=50)
    settings = _default_settings()

    created = generate_monthly_invoices(db_session, settings, reference=date(2026, 3, 15))

    assert len(created) == 1
    assert created[0].amount == 250  # 300 (precio del plan) - 50 de crédito
    db_session.refresh(client)
    assert client.pending_credit == 0


def test_generate_monthly_invoices_consumes_pending_reconnection_fee(db_session):
    client = _make_client(db_session, _unique="a", pending_reconnection_fee=True)
    settings = _default_settings(reconnection_fee_amount=20)

    created = generate_monthly_invoices(db_session, settings, reference=date(2026, 3, 15))

    assert len(created) == 1
    assert created[0].amount == 320  # 300 + 20 de reconexión pendiente
    db_session.refresh(client)
    assert client.pending_reconnection_fee is False


def test_apply_late_fees_adds_amount_once(db_session):
    client = _make_client(db_session, _unique="a")
    invoice = Invoice(
        client_id=client.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 31),
        amount=300,
        status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(late_fee_enabled=True, late_fee_amount=15, late_fee_apply_hour=0)
    now = datetime(2026, 4, 5, 10, tzinfo=timezone.utc)

    first_pass = apply_late_fees(db_session, now, settings)
    assert len(first_pass) == 1
    db_session.refresh(invoice)
    assert invoice.amount == 315
    assert invoice.late_fee_amount == 15

    # Segunda corrida del día siguiente: la guardia late_fee_applied_at no
    # deja que se vuelva a aplicar.
    second_pass = apply_late_fees(db_session, now, settings)
    assert second_pass == []
    db_session.refresh(invoice)
    assert invoice.amount == 315


def test_apply_late_fees_respects_apply_hour(db_session):
    client = _make_client(db_session, _unique="a")
    invoice = Invoice(
        client_id=client.id, period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 31), amount=300, status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(late_fee_enabled=True, late_fee_amount=15, late_fee_apply_hour=20)
    now = datetime(2026, 4, 5, 10, tzinfo=timezone.utc)  # antes de la hora configurada

    assert apply_late_fees(db_session, now, settings) == []


def test_apply_late_fees_disabled_is_noop(db_session):
    client = _make_client(db_session, _unique="a")
    invoice = Invoice(
        client_id=client.id, period_start=date(2026, 3, 1), period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 31), amount=300, status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(late_fee_enabled=False)
    now = datetime(2026, 4, 5, 10, tzinfo=timezone.utc)

    assert apply_late_fees(db_session, now, settings) == []


def test_proration_current_invoice_reduces_amount(db_session):
    client = _make_client(db_session, _unique="a")
    # Período de 30 días, plan $300 -- corte 10 días antes del fin de
    # período => crédito = 300/30*10 = 100, monto final 200.
    invoice = Invoice(
        client_id=client.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 30),
        due_date=date(2026, 3, 30),
        amount=300,
        status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(
        proration_enabled=True, proration_min_days=1, proration_target=ProrationTarget.CURRENT_INVOICE
    )
    apply_proration_if_needed(db_session, client, invoice, date(2026, 3, 20), settings)

    assert invoice.amount == 200


def test_proration_next_invoice_banks_credit_on_client(db_session):
    client = _make_client(db_session, _unique="a")
    invoice = Invoice(
        client_id=client.id, period_start=date(2026, 3, 1), period_end=date(2026, 3, 30),
        due_date=date(2026, 3, 30), amount=300, status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(
        proration_enabled=True, proration_min_days=1, proration_target=ProrationTarget.NEXT_INVOICE
    )
    apply_proration_if_needed(db_session, client, invoice, date(2026, 3, 20), settings)

    assert invoice.amount == 300  # sin cambios
    assert client.pending_credit == 100


def test_proration_skipped_below_min_days(db_session):
    client = _make_client(db_session, _unique="a")
    invoice = Invoice(
        client_id=client.id, period_start=date(2026, 3, 1), period_end=date(2026, 3, 30),
        due_date=date(2026, 3, 30), amount=300, status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    settings = _default_settings(proration_enabled=True, proration_min_days=15)
    # Solo 10 días sin usar, por debajo del mínimo configurado (15).
    apply_proration_if_needed(db_session, client, invoice, date(2026, 3, 20), settings)

    assert invoice.amount == 300
    assert client.pending_credit == 0


def test_reconnection_fee_on_suspend_creates_invoice(db_session):
    client = _make_client(db_session, _unique="a")
    settings = _default_settings(
        reconnection_fee_mode=ReconnectionFeeMode.ON_SUSPEND, reconnection_fee_amount=25
    )

    fee_invoice = apply_reconnection_fee(db_session, client, settings)

    assert fee_invoice is not None
    assert fee_invoice.amount == 25
    assert fee_invoice.status == InvoiceStatus.PENDING


def test_reconnection_fee_on_next_invoice_flags_client(db_session):
    client = _make_client(db_session, _unique="a")
    settings = _default_settings(reconnection_fee_mode=ReconnectionFeeMode.ON_NEXT_INVOICE)

    result = apply_reconnection_fee(db_session, client, settings)

    assert result is None
    assert client.pending_reconnection_fee is True


def test_reconnection_fee_off_is_noop(db_session):
    client = _make_client(db_session, _unique="a")
    settings = _default_settings(reconnection_fee_mode=ReconnectionFeeMode.OFF)

    assert apply_reconnection_fee(db_session, client, settings) is None
    assert client.pending_reconnection_fee is False


def test_suspend_uses_configurable_grace_days(db_session):
    client = _make_client(db_session, _unique="a", ip_address=None)
    today = date(2026, 4, 1)
    invoice = Invoice(
        client_id=client.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 20),  # vencida hace 12 días
        amount=300,
        status=InvoiceStatus.OVERDUE,
    )
    db_session.add(invoice)
    db_session.commit()

    # Con 15 días de gracia todavía no debería suspender (solo pasaron 12).
    settings_lenient = _default_settings(suspend_days_after_due=15)
    assert suspend_clients_with_overdue_invoices(db_session, settings_lenient, today) == []
    db_session.refresh(client)
    assert client.status == ClientStatus.ACTIVE

    # Con 5 días de gracia (el default histórico) sí debería suspender.
    settings_strict = _default_settings(suspend_days_after_due=5)
    suspended = suspend_clients_with_overdue_invoices(db_session, settings_strict, today)
    assert [c.id for c in suspended] == [client.id]
    db_session.refresh(client)
    assert client.status == ClientStatus.SUSPENDED
