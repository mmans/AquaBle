"""Tests for telemetry parsing (custom_components/aquable/commands/parsers.py)."""

from custom_components.aquable.commands.encoder import _calculate_checksum
from custom_components.aquable.commands.parsers import parse_light_payload


def _status_frame(blocks: list[list[int]]) -> bytes:
    header = [0x5B, 0x06, 0, 0x00, 0x01, 0xFE, 0x05, 0x16, 0x2B]  # Fri 22:43
    body = [b for block in blocks for b in block]
    tail = [0, 0, 0, 0, 0]
    frame = bytearray(header + body + tail)
    frame[2] = len(frame) - 3 + 1
    frame.append(_calculate_checksum(frame))
    return bytes(frame)


def test_parses_schedule_blocks():
    payload = _status_frame(
        [
            [8, 30, 18, 0, 15, 127, 100, 80, 60, 255, 255, 255, 255],
            [20, 0, 22, 30, 10, 0x40, 30, 30, 30, 255, 255, 255, 255],
        ]
    )
    status = parse_light_payload(payload, num_channels=3)

    assert status is not None
    assert (status.weekday, status.hour, status.minute) == (5, 22, 43)
    assert len(status.schedules) == 2

    first, second = status.schedules
    assert first.sunrise() == "08:30"
    assert first.sunset() == "18:00"
    assert first.ramp_up_minutes == 15
    assert first.weekday_mask == 127
    assert first.channel_brightness == [100, 80, 60]
    assert second.weekdays() == ["monday"]
    assert second.channel_brightness == [30, 30, 30]


def test_skips_empty_slots():
    payload = _status_frame(
        [
            [255] * 13,
            [0] * 13,
            [6, 0, 12, 0, 0, 127, 50, 255, 255, 255, 255, 255, 255],
        ]
    )
    status = parse_light_payload(payload, num_channels=1)

    assert status is not None
    assert [s.sunrise() for s in status.schedules] == ["06:00"]
    assert status.schedules[0].channel_brightness == [50]


def test_rejects_non_status_frames():
    assert parse_light_payload(b"") is None
    assert parse_light_payload(bytes([0x5B, 0x06, 0x08, 0, 1, 0x0A, 0, 0])) is None
    assert parse_light_payload(bytes([0x5A, 0x06, 0x08, 0, 1, 0xFE, 0, 0, 0])) is None
