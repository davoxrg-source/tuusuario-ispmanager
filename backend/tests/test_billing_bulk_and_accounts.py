import uuid
from datetime import date

from app.api.routes.billing import balance_by_account, bulk_charge_invoices, pay_invoice
from app.api.routes.clients import bulk_reactivate_clients, bulk_suspend_clients
from app.models.client import Client, ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.models.payment_account import PaymentAccount
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.billing import BulkInvoiceCharge, PaymentCreate
from app.schemas.client import BulkClientAction

_ADMIN = User(role=UserRole.ADMIN)  # ADMIN sin restricción de zona -- ver ensure_zone_access


def _make_client(db_session, **overrides) -> Client:
    plan = Plan(name=f"Plan-{uuid.uuid4()}", download_speed_mbps=10, upload_speed_mbps=10, price=300)
    db_session.add(plan)
    db_session.commit()
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, plan_id=plan.id, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _make_invoice(db_session, client: Client, **overrides) -> Invoice:
    invoice = Invoice(
        client_id=client.id,
        period_start=date(2026, 3, 1),
        period_end=date(2026, 3, 31),
        due_date=date(2026, 3, 31),
        amount=300,
        status=InvoiceStatus.PENDING,
    )
    for field, value in overrides.items():
        setattr(invoice, field, value)
    db_session.add(invoice)
    db_session.commit()
    db_session.refresh(invoice)
    return invoice


def test_balance_by_account_aggregates_payments_per_account(db_session):
    account_with_payments = PaymentAccount(name="Nequi *1234", kind="digital_wallet")
    account_without_payments = PaymentAccount(name="Cuenta vacía", kind="bank")
    db_session.add_all([account_with_payments, account_without_payments])
    db_session.commit()

    client = _make_client(db_session)
    invoice_1 = _make_invoice(db_session, client, status=InvoiceStatus.PAID)
    invoice_2 = _make_invoice(db_session, client, status=InvoiceStatus.PAID)
    db_session.add_all(
        [
            Payment(
                invoice_id=invoice_1.id, amount=100, method="nequi",
                payment_account_id=account_with_payments.id,
            ),
            Payment(
                invoice_id=invoice_2.id, amount=50, method="nequi",
                payment_account_id=account_with_payments.id,
            ),
        ]
    )
    db_session.commit()

    balances = {row.id: row for row in balance_by_account(db_session)}

    assert balances[account_with_payments.id].total == 150
    assert balances[account_without_payments.id].total == 0


def test_bulk_suspend_partial_failure_returns_per_item_results(db_session):
    client_1 = _make_client(db_session)
    client_2 = _make_client(db_session)
    bad_id = uuid.uuid4()

    result = bulk_suspend_clients(
        BulkClientAction(client_ids=[client_1.id, client_2.id, bad_id]), db_session
    )

    ok_ids = {item.id for item in result.results if item.ok}
    failed_ids = {item.id for item in result.results if not item.ok}
    assert ok_ids == {client_1.id, client_2.id}
    assert failed_ids == {bad_id}

    db_session.refresh(client_1)
    db_session.refresh(client_2)
    assert client_1.status == ClientStatus.SUSPENDED
    assert client_2.status == ClientStatus.SUSPENDED


def test_bulk_reactivate_clients(db_session):
    client = _make_client(db_session, status=ClientStatus.SUSPENDED)

    result = bulk_reactivate_clients(BulkClientAction(client_ids=[client.id]), db_session)

    assert result.results[0].ok is True
    db_session.refresh(client)
    assert client.status == ClientStatus.ACTIVE


def test_bulk_charge_invoices_rejects_already_paid(db_session):
    client = _make_client(db_session)
    invoice_pending = _make_invoice(db_session, client, status=InvoiceStatus.PENDING)
    invoice_paid = _make_invoice(db_session, client, status=InvoiceStatus.PAID)

    result = bulk_charge_invoices(
        BulkInvoiceCharge(invoice_ids=[invoice_pending.id, invoice_paid.id], amount=10), db_session
    )

    results_by_id = {item.id: item for item in result.results}
    assert results_by_id[invoice_pending.id].ok is True
    assert results_by_id[invoice_paid.id].ok is False

    db_session.refresh(invoice_pending)
    assert invoice_pending.amount == 310


def test_pay_invoice_triggers_auto_reactivation_when_no_other_overdue(db_session):
    client = _make_client(db_session, status=ClientStatus.SUSPENDED)
    invoice = _make_invoice(db_session, client, status=InvoiceStatus.OVERDUE)

    pay_invoice(invoice.id, PaymentCreate(amount=300, method="manual"), db_session, _ADMIN)

    db_session.refresh(client)
    assert client.status == ClientStatus.ACTIVE


def test_pay_invoice_does_not_reactivate_with_other_overdue_invoice(db_session):
    client = _make_client(db_session, status=ClientStatus.SUSPENDED)
    invoice_1 = _make_invoice(db_session, client, status=InvoiceStatus.OVERDUE)
    _make_invoice(db_session, client, status=InvoiceStatus.OVERDUE, period_start=date(2026, 4, 1))

    pay_invoice(invoice_1.id, PaymentCreate(amount=300, method="manual"), db_session, _ADMIN)

    db_session.refresh(client)
    assert client.status == ClientStatus.SUSPENDED
