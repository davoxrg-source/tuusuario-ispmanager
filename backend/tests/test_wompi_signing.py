import hashlib

from app.services.wompi.signing import build_integrity_signature, verify_webhook_checksum


def test_build_integrity_signature_matches_documented_formula():
    # Orden documentado en docs.wompi.co: referencia + monto + moneda + secreto,
    # sin separadores, SHA256.
    expected = hashlib.sha256("REF-1450000COPtest_integrity_secret".encode()).hexdigest()
    assert build_integrity_signature("REF-1", 450000, "COP", "test_integrity_secret") == expected


def test_build_integrity_signature_changes_with_any_input():
    base = build_integrity_signature("REF-1", 450000, "COP", "secret")
    assert base != build_integrity_signature("REF-2", 450000, "COP", "secret")
    assert base != build_integrity_signature("REF-1", 450001, "COP", "secret")
    assert base != build_integrity_signature("REF-1", 450000, "COP", "other-secret")


def _make_payload(secret: str, *, tamper: bool = False) -> dict:
    properties = ["transaction.id", "transaction.status", "transaction.amount_in_cents"]
    data = {"transaction": {"id": "01-123", "status": "APPROVED", "amount_in_cents": 45000}}
    timestamp = 1530291411
    concat = "01-123" + "APPROVED" + "45000" + str(timestamp) + secret
    checksum = hashlib.sha256(concat.encode()).hexdigest()
    if tamper:
        data["transaction"]["amount_in_cents"] = 1  # el atacante cambia el monto sin recalcular el checksum
    return {
        "event": "transaction.updated",
        "data": data,
        "signature": {"properties": properties, "checksum": checksum},
        "timestamp": timestamp,
        "sent_at": "2026-08-24T00:00:00.000Z",
    }


def test_verify_webhook_checksum_valid_signature_accepted():
    payload = _make_payload("test_events_secret")
    assert verify_webhook_checksum(payload, "test_events_secret") is True


def test_verify_webhook_checksum_wrong_secret_rejected():
    payload = _make_payload("test_events_secret")
    assert verify_webhook_checksum(payload, "otro_secreto") is False


def test_verify_webhook_checksum_tampered_payload_rejected():
    payload = _make_payload("test_events_secret", tamper=True)
    assert verify_webhook_checksum(payload, "test_events_secret") is False


def test_verify_webhook_checksum_missing_fields_returns_false_not_raises():
    assert verify_webhook_checksum({}, "secret") is False
    assert verify_webhook_checksum({"signature": {}}, "secret") is False
