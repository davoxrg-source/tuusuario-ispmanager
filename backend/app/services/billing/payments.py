from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.client import ClientStatus
from app.models.invoice import Invoice, InvoiceStatus
from app.models.payment import Payment
from app.schemas.billing import PaymentCreate
from app.services.clients.status import reactivate_client_service


def mark_invoice_paid(db: Session, invoice: Invoice, payment: PaymentCreate) -> Invoice:
    """Crea el Payment, marca la Invoice pagada, y reactiva al cliente si
    corresponde -- compartida entre pay_invoice/confirm_payment_report
    (staff marca o confirma un pago) y el webhook de Wompi (un pago en
    línea verificado por firma). Asume que ya se validó que la factura no
    estaba pagada."""
    db.add(Payment(invoice_id=invoice.id, **payment.model_dump()))
    invoice.status = InvoiceStatus.PAID
    invoice.paid_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(invoice)

    # Reactivación automática: si el cliente estaba suspendido y esta era su
    # última factura pendiente/vencida (incluida una factura de reconexión,
    # si el modo de cobro es "al suspender" -- es solo otra fila más acá),
    # se reactiva sin que nadie tenga que hacerlo a mano.
    client = invoice.client
    if client.status == ClientStatus.SUSPENDED:
        other_unpaid = (
            db.query(Invoice)
            .filter(
                Invoice.client_id == client.id,
                Invoice.status.in_([InvoiceStatus.PENDING, InvoiceStatus.OVERDUE]),
            )
            .count()
        )
        if other_unpaid == 0:
            reactivate_client_service(db, client)

    return invoice
