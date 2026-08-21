import struct

from app.services.mikrotik.discovery import parse_mndp_packet


def _tlv(tlv_type: int, value: bytes) -> bytes:
    return struct.pack(">HH", tlv_type, len(value)) + value


def test_parse_mndp_packet_extracts_mac_identity_and_version():
    payload = (
        b"\x00\x00"  # header, ignorado
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
    payload = b"\x00\x00" + _tlv(0x0005, b"sin-mac")
    assert parse_mndp_packet(payload) is None


def test_parse_mndp_packet_ignores_unknown_tlv_types():
    payload = (
        b"\x00\x00"
        + _tlv(0x00FF, b"tipo-desconocido-cualquier-cosa")
        + _tlv(0x0001, bytes.fromhex("AABBCCDDEEFF"))
    )

    result = parse_mndp_packet(payload)

    assert result is not None
    assert result["mac_address"] == "AA:BB:CC:DD:EE:FF"


def test_parse_mndp_packet_truncated_tlv_does_not_crash():
    payload = b"\x00\x00" + struct.pack(">HH", 0x0001, 6) + b"\x01\x02"  # dice 6 bytes pero trae 2
    assert parse_mndp_packet(payload) is None
