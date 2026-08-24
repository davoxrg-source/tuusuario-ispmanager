import json
import logging
import secrets
from urllib.parse import urlencode

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.invoice import Invoice, InvoiceStatus
from app.models.wompi_transaction import WompiTransaction, WompiTransactionStatus
from app.schemas.billing import PaymentCreate
from app.services.billing.payments import mark_invoice_paid
from app.services.wompi.signing import build_integrity_signature, verify_webhook_checksum

logger = logging.getLogger(__name__)

CURRENCY = "COP"
CHECKOUT_URL = "https://checkout.wompi.co/p/"

# Wompi manda el status en mayúsculas ("APPROVED") -- este dict lo traduce
# a nuestro enum en minúsculas; cualquier valor no reconocido cae a ERROR
# en vez de romper el webhook.
_STATUS_MAP = {
    "PENDING": WompiTransactionStatus.PENDING,
    "APPROVED": WompiTransactionStatus.APPROVED,
    "DECLINED": WompiTransactionStatus.DECLINED,
    "VOIDED": WompiTransactionStatus.VOIDED,
    "ERROR": WompiTransactionStatus.ERROR,
}


def create_checkout(db: Session, invoice: Invoice, redirect_url: str) -> tuple[WompiTransaction, str]:
    """Crea el registro del intento de pago y arma el link de checkout
    hospedado de Wompi -- el cliente paga en el dominio de Wompi, nuestro
    backend nunca ve un número de tarjeta."""
    settings = get_settings()
    if not settings.wompi_public_key or not settings.wompi_integrity_secret:
        raise ValueError("Wompi no está configurado.")

    amount_in_cents = int(round(float(invoice.amount) * 100))
    # Única por INTENTO, no por factura -- un reintento tras un pago
    # fallido genera una referencia nueva (ver docs de Wompi).
    reference = f"INV-{invoice.id.hex}-{secrets.token_hex(4)}"

    transaction = WompiTransaction(
        invoice_id=invoice.id,
        reference=reference,
        amount_in_cents=amount_in_cents,
        status=WompiTransactionStatus.PENDING,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    signature = build_integrity_signature(reference, amount_in_cents, CURRENCY, settings.wompi_integrity_secret)
    params = {
        "public-key": settings.wompi_public_key,
        "currency": CURRENCY,
        "amount-in-cents": amount_in_cents,
        "reference": reference,
        "signature:integrity": signature,
        "redirect-url": redirect_url,
    }
    checkout_url = f"{CHECKOUT_URL}?{urlencode(params)}"
    return transaction, checkout_url


def handle_webhook(db: Session, payload: dict) -> None:
    """Verifica la firma ANTES de tocar cualquier dato -- si no valida, se
    descarta sin procesar. Idempotente: reprocesar el mismo evento (Wompi
    reintenta hasta 3 veces en 24h si no respondemos 200) no duplica nada."""
    settings = get_settings()
    if not settings.wompi_events_secret or not verify_webhook_checksum(payload, settings.wompi_events_secret):
        raise ValueError("Firma de webhook inválida.")

    # No basta con que el checksum general valide -- el campo reference
    # específicamente tiene que estar DENTRO de lo firmado (signature.properties),
    # si no un atacante podría reusar el checksum de un evento real cambiando
    # solo a qué factura apunta. No es hipotético: el ejemplo de la
    # documentación de Wompi para transaction.updated no incluye
    # "transaction.reference" en properties, así que hay que chequearlo
    # nosotros en vez de asumirlo.
    if "transaction.reference" not in payload.get("signature", {}).get("properties", []):
        raise ValueError("El campo reference no está firmado en este webhook.")

    transaction_data = payload["data"]["transaction"]
    reference = transaction_data["reference"]

    wompi_tx = db.query(WompiTransaction).filter(WompiTransaction.reference == reference).first()
    if wompi_tx is None:
        logger.warning("Webhook de Wompi para una referencia desconocida: %s", reference)
        return

    wompi_tx.wompi_transaction_id = transaction_data.get("id")
    wompi_tx.raw_webhook_payload = json.dumps(payload)
    wompi_tx.status = _STATUS_MAP.get(transaction_data.get("status", ""), WompiTransactionStatus.ERROR)
    db.commit()

    if wompi_tx.status != WompiTransactionStatus.APPROVED:
        return

    invoice = wompi_tx.invoice
    if invoice.status == InvoiceStatus.PAID:
        return  # ya se procesó (reintento del webhook) -- idempotente, no duplica el Payment

    mark_invoice_paid(
        db,
        invoice,
        PaymentCreate(
            amount=wompi_tx.amount_in_cents / 100,
            method="wompi",
            reference=wompi_tx.wompi_transaction_id or reference,
        ),
    )
