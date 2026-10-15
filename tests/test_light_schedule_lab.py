"""Tests for scripts/light_schedule_lab.py frame building and decoding (no BLE needed)."""

import datetime
import importlib.util
from pathlib import Path

import pytest

from custom_components.aquable.commands.encoder import create_set_time_command

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "light_schedule_lab.py"
_spec = importlib.util.spec_from_file_location("light_schedule_lab", _SCRIPT)
lab = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lab)

FIXTURE = Path(__file__).parent / "fixtures" / "light_fe_status.hex"


def test_set_time_with_explicit_datetime_matches_capture():
    when = datetime.datetime(2026, 8, 27, 11, 30, 15)
    frame = create_set_time_command((0, 7), when=when)
    # BLE_Protocol.md lists the checksum as 33, but XOR over bytes 1..n-2 gives 08
    assert frame.hex(" ").upper() == "5A 01 0B 00 07 09 1A 08 04 0B 1E 0F 08"


def test_set_time_default_uses_now():
    frame = create_set_time_command((0, 7))
    assert frame[5] == 9 and frame[6] == datetime.datetime.now().year - 2000


def test_parse_datetime_formats():
    assert lab.parse_datetime("2026-08-27 11:30") == datetime.datetime(2026, 8, 27, 11, 30)
    assert lab.parse_datetime("2026-08-27 11:30:15").second == 15
    with pytest.raises(ValueError):
        lab.parse_datetime("27.08.2026")


def test_raw_checksum_and_warning_for_0x5a():
    frame, substituted = lab.build_raw(lab.MessageIds((0, 0)), 0x5A, 0x05, bytes([5, 255, 255]))
    assert frame.hex(" ").upper() == "5A 01 08 00 01 05 05 FF FF 08"
    assert substituted == []
    _, substituted = lab.build_raw(lab.MessageIds(), 0x5A, 0x05, bytes([0x5A, 1]))
    assert substituted == [0]


def test_write_builds_reset_slots_and_auto_mode():
    slots = [
        {
            "sunrise": "06:00",
            "sunset": "18:00",
            "ramp": 30,
            "weekdays": ["monday", "tuesday"],
            "channels": [30, 0, 20],
        }
    ]
    frames = lab.build_write(lab.MessageIds(), slots)
    assert len(frames) == 3
    assert list(frames[0][5:9]) == [5, 5, 255, 255]  # reset: mode 5, params [05 FF FF]
    slot = frames[1]
    assert (slot[0], slot[5]) == (0xA5, 0x19)
    assert list(slot[6:-1]) == [6, 0, 18, 0, 30, 0x60, 30, 0, 20, 255, 255, 255, 255, 255]
    assert list(frames[2][5:9]) == [5, 18, 255, 255]  # auto mode


def test_points_builds_reset_and_point_frames():
    frames = lab.build_points(
        lab.MessageIds((0, 0xC8)),
        [{"time": "08:00", "channels": [10, None, 20]}],
    )
    assert len(frames) == 3  # reset + 2 points (null skipped)
    # Reference capture (chihiros-led-control A2): ch 0, 08:00, 10% with msg id 0x00CA
    assert frames[1].hex(" ") == "5a 01 09 00 ca 06 00 08 00 0a c6"
    assert list(frames[2][6:-1]) == [2, 8, 0, 20]


def test_points_rejects_out_of_range_level():
    with pytest.raises(ValueError):
        lab.build_points(lab.MessageIds(), [{"time": "08:00", "channels": [101]}])


# fixture is a synthetic frame (not a device capture); replace with a real one after #10
def test_decode_fe_both_interpretations():
    payload = bytes.fromhex(FIXTURE.read_text().strip())
    text = "\n".join(lab.decode_fe(payload))
    assert "06:00 -> 18:00 ramp=30" in text
    assert "channels=[30, 0, 20, 255]" in text
    assert "triples from offset 25" in text
    assert "06:00 level=30" in text
    assert "14:00 level=20" in text


def test_decode_fe_rejects_other_frames():
    assert lab.decode_fe(bytes([0x5B, 1, 6, 0, 1, 0x0A, 0, 0])) == [
        "not a 0x5B/0xFE light status frame"
    ]


def test_help_works_without_ble(capsys):
    with pytest.raises(SystemExit) as exc:
        lab.main(["--help"])
    assert exc.value.code == 0
    assert "set-time" in capsys.readouterr().out
