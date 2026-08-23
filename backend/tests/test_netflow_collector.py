import struct
from datetime import datetime, timezone

from app.services.netflow.collector import _bucket_start, parse_v5


def _build_v5_packet(src_addr: str, dst_addr: str, packets: int, octets: int) -> bytes:
    header = struct.pack("!HHIIIIBBH", 5, 1, 0, 0, 0, 0, 0, 0, 0)
    record = struct.pack(
        "!IIIHHIIIIHHBBBBHHBBH",
        int.from_bytes(bytes(int(o) for o in src_addr.split(".")), "big"),
        int.from_bytes(bytes(int(o) for o in dst_addr.split(".")), "big"),
        0,  # nexthop
        0,  # input
        0,  # output
        packets,
        octets,
        0,  # first
        0,  # last
        1234,  # srcport
        80,  # dstport
        0,  # pad1
        0,  # tcp_flags
        6,  # prot (tcp)
        0,  # tos
        0,  # src_as
        0,  # dst_as
        0,  # src_mask
        0,  # dst_mask
        0,  # pad2
    )
    return header + record


def test_parse_v5_decodes_addresses_and_counters():
    packet = _build_v5_packet("10.0.0.5", "8.8.8.8", packets=10, octets=1500)
    records = parse_v5(packet)
    assert len(records) == 1
    assert records[0]["src_addr"] == "10.0.0.5"
    assert records[0]["dst_addr"] == "8.8.8.8"
    assert records[0]["packets"] == 10
    assert records[0]["bytes"] == 1500


def test_parse_v5_ignores_non_v5_packets():
    header = struct.pack("!HHIIIIBBH", 9, 1, 0, 0, 0, 0, 0, 0, 0)
    assert parse_v5(header) == []


def test_parse_v5_ignores_truncated_packets():
    assert parse_v5(b"\x00") == []


def test_parse_v5_stops_at_declared_count_even_with_trailing_garbage():
    packet = _build_v5_packet("10.0.0.5", "8.8.8.8", packets=10, octets=1500) + b"\x00" * 10
    records = parse_v5(packet)
    assert len(records) == 1


def test_bucket_start_truncates_to_the_hour():
    now = datetime(2026, 8, 23, 14, 37, 52, tzinfo=timezone.utc)
    bucket = _bucket_start(now)
    assert bucket == datetime(2026, 8, 23, 14, 0, 0, tzinfo=timezone.utc)
