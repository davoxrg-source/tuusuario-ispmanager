import struct

from app.services.mikrotik.discovery import parse_mndp_packet

# Header real de MNDP: 2 bytes tipo de paquete + 2 bytes secuencia (ninguno se usa).
_HEADER = b"\x00\x00\x00\x00"


def _tlv(tlv_type: int, value: bytes) -> bytes:
    return struct.pack(">HH", tlv_type, len(value)) + value


def test_parse_mndp_packet_extracts_mac_identity_and_version():
    payload = (
        _HEADER
        + _tlv(0x0001, bytes.fromhex("000C42010203"))  # MAC (6 bytes)
        + _tlv(0x0005, b"lab-router")
        + _tlv(0x0007, b"7.15")
        + _tlv(0x0008, b"CHR")
    )

    result = parse_mndp_packet(payload)

    assert result is not None
    assert result["mac_address"] == "00:0C:42:01:02:03"
    assert result["identity"] == "lab-router"
    assert result["version"] == "7.15"
    assert result["platform"] == "CHR"


def test_parse_mndp_packet_without_mac_returns_none():
    payload = _HEADER + _tlv(0x0005, b"sin-mac")
    assert parse_mndp_packet(payload) is None


def test_parse_mndp_packet_ignores_unknown_tlv_types():
    payload = (
        _HEADER
        + _tlv(0x00FF, b"tipo-desconocido-cualquier-cosa")
        + _tlv(0x0001, bytes.fromhex("AABBCCDDEEFF"))
    )

    result = parse_mndp_packet(payload)

    assert result is not None
    assert result["mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_parse_mndp_packet_truncated_tlv_does_not_crash():
    payload = _HEADER + struct.pack(">HH", 0x0001, 6) + b"\x01\x02"  # dice 6 bytes pero trae 2
    assert parse_mndp_packet(payload) is None


def test_parse_mndp_packet_matches_real_mikrotik_capture():
    """Paquete real capturado de un MikroTik RB962UiGS-5HacT2HnT en la red
    (RouterOS 7.19.3), para no depender solo de paquetes construidos a mano."""
    payload = bytes.fromhex(
        "000003d400010006c4ad34de9efd000500084d696b726f54696b00070023372e"
        "31392e332028737461626c652920323032352d30372d30332031313a32333a30"
        "34000800084d696b726f54696b000a000482640000000b0009553931542d534b"
        "4c4d000c00135242393632556947532d354861635432486e54000e0001010"
        "00f0010fe80000000000000c6ad34fffede9efd0010000665746865723500"
        "1100040a640901"
    )

    result = parse_mndp_packet(payload)

    assert result is not None
    assert result["mac_address"] == "C4:AD:34:DE:9E:FD"
    assert result["identity"] == "MikroTik"
    assert result["version"] == "7.19.3 (stable) 2025-07-03 11:23:04"
    assert result["platform"] == "MikroTik"
