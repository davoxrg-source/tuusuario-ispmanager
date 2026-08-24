import uuid
from datetime import date

import pytest
from pydantic import ValidationError

from app.schemas.billing import BulkInvoiceCharge, PaymentCreate, PromiseToPayCreate
from app.schemas.client import BulkClientAction


def test_promise_to_pay_create_parses_until_date():
    payload = PromiseToPayCreate(until=date(2026, 9, 1))
    assert payload.until == date(2026, 9, 1)


def test_bulk_client_action_parses_uuid_list():
    ids = [uuid.uuid4(), uuid.uuid4()]
    payload = BulkClientAction(client_ids=ids)
    assert payload.client_ids == ids


def test_bulk_invoice_charge_parses():
    payload = BulkInvoiceCharge(invoice_ids=[uuid.uuid4()], amount=15.5)
    assert payload.amount == 15.5


def test_bulk_invoice_charge_rejects_non_positive_amount():
    with pytest.raises(ValidationError):
        BulkInvoiceCharge(invoice_ids=[uuid.uuid4()], amount=0)


def test_payment_create_accepts_optional_account_id():
    payload = PaymentCreate(amount=100, method="efectivo")
    assert payload.payment_account_id is None

    account_id = uuid.uuid4()
    payload_with_account = PaymentCreate(amount=100, method="efectivo", payment_account_id=account_id)
    assert payload_with_account.payment_account_id == account_id
