"""Las dos únicas piezas de criptografía que exige Wompi -- documentación
real revisada el 2026-08-24 en docs.wompi.co (Environments and Keys,
Widget & Checkout Web, Events), no de memoria, porque un contrato de pagos
mal calculado es plata real mal manejada."""

import hashlib
from typing import Any


def build_integrity_signature(reference: str, amount_in_cents: int, currency: str, integrity_secret: str) -> str:
    """Firma que exige el link de checkout hospedado (data-signature:integrity
    en el widget, o el campo "signature:integrity" del form de redirect).
    Orden de concatenación exacto (sin espacios, sin separadores):
    referencia + monto_en_centavos + moneda + secreto de integridad."""
    concat = f"{reference}{amount_in_cents}{currency}{integrity_secret}"
    return hashlib.sha256(concat.encode()).hexdigest()


def _get_nested(data: dict[str, Any], dotted_path: str) -> Any:
    """"transaction.id" -> data["transaction"]["id"]. Las properties del
    webhook siempre son relativas a payload["data"], no a la raíz."""
    value: Any = data
    for key in dotted_path.split("."):
        value = value[key]
    return value


def verify_webhook_checksum(payload: dict[str, Any], events_secret: str) -> bool:
    """Verifica signature.checksum de un webhook de Wompi antes de creer
    una palabra de lo que dice el payload -- NUNCA se procesa un webhook
    sin pasar esto primero. Concatenación: valores de signature.properties
    (en el orden dado, resueltos contra payload["data"]) + timestamp
    (como está, sin convertir) + events_secret."""
    try:
        properties: list[str] = payload["signature"]["properties"]
        expected_checksum: str = payload["signature"]["checksum"]
        timestamp = payload["timestamp"]
        data = payload["data"]
    except (KeyError, TypeError):
        return False

    values = [str(_get_nested(data, prop)) for prop in properties]
    concat = "".join(values) + str(timestamp) + events_secret
    computed = hashlib.sha256(concat.encode()).hexdigest()
    return computed.lower() == str(expected_checksum).lower()
