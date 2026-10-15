"""Tests for BLE frame encoding (custom_components/aquable/commands/encoder.py)."""

import datetime

import pytest

from custom_components.aquable.commands.encoder import (
    _calculate_checksum,
    _encode_uart_command,
    create_add_auto_setting_command,
    create_delete_auto_setting_command,
    create_handshake_command,
    encode_weekdays,
    next_message_id,
)

# Delete frame captured in BLE_Protocol.md ("Schedule Deletion").
DOC_DELETE_FRAME = bytes.fromhex("A5 01 13 00 17 19 02 1E 05 0A 01 7F FF FF FF FF FF FF FF FF 71")


class TestWeekdays:
    @pytest.mark.parametrize(
        ("days", "mask"),
        [
            (["monday"], 64),
            (["sunday"], 1),
            (["monday", "wednesday"], 80),
            (["Saturday", "SUNDAY"], 3),
            (["monday", "tuesday", "wednesday", "thursday", "friday"], 124),
            ("everyday", 127),
            ("daily", 127),
            (["everyday"], 127),
            (None, 127),
            ([], 127),
            ("friday", 4),
        ],
    )
    def test_encode(self, days, mask):
        assert encode_weekdays(days) == mask

    def test_invalid_day(self):
        with pytest.raises(ValueError, match="Invalid weekday"):
            encode_weekdays(["funday"])


class TestChecksum:
    def test_xor_from_length_byte(self):
        frame = bytes([0x5A, 0x01, 0x06, 0x00, 0x01, 0x04, 0x01])
        assert _calculate_checksum(frame) == 0x01 ^ 0x06 ^ 0x00 ^ 0x01 ^ 0x04 ^ 0x01

    def test_frame_ends_with_checksum(self):
        frame = create_handshake_command((0, 1))
        assert frame[-1] == _calculate_checksum(frame[:-1])

    def test_checksum_never_0x5a(self):
        # Every encoded frame must avoid the reserved 0x5A in the checksum position.
        for lo in range(1, 255):
            if lo == 0x5A:
                continue
            assert _encode_uart_command(0x5A, 0x04, (0, lo), [0x01])[-1] != 0x5A

    def test_reserved_byte_in_params_is_sanitised(self):
        frame = _encode_uart_command(0x5A, 0x07, (0, 1), [0x5A, 0x10])
        assert frame[6] == 0x59


class TestMessageId:
    def test_increment(self):
        assert next_message_id((0, 1)) == (0, 2)

    def test_skips_reserved_lower(self):
        assert next_message_id((0, 89)) == (0, 91)

    def test_carry_and_skip_reserved_higher(self):
        assert next_message_id((0, 255)) == (1, 0)
        assert next_message_id((89, 255)) == (91, 0)

    def test_wrap(self):
        assert next_message_id((255, 255)) == (0, 1)

    def test_rejects_reserved(self):
        with pytest.raises(ValueError):
            next_message_id((0, 90))


class TestAutoSettingCommands:
    def test_add_layout(self):
        frame = create_add_auto_setting_command(
            (0, 7),
            datetime.time(8, 30),
            datetime.time(18, 0),
            (100, 80, 60, 40),
            ramp_up_minutes=15,
            weekdays=127,
        )
        assert len(frame) == 21  # 6 header + 14 params + checksum
        assert frame[0] == 165  # 0xA5
        assert frame[1] == 0x01
        assert frame[2] == 19  # 14 params + 5
        assert (frame[3], frame[4]) == (0, 7)
        assert frame[5] == 25  # mode
        params = [8, 30, 18, 0, 15, 127, 100, 80, 60, 40, 255, 255, 255, 255]
        assert list(frame[6:-1]) == params
        assert frame[-1] == _calculate_checksum(frame[:-1])

    def test_add_rejects_bad_brightness(self):
        with pytest.raises(ValueError):
            create_add_auto_setting_command(
                (0, 1), datetime.time(8), datetime.time(18), (101,), 0, 127
            )
        with pytest.raises(ValueError):
            create_add_auto_setting_command((0, 1), datetime.time(8), datetime.time(18), (), 0, 127)

    def test_delete_pads_with_0xff(self):
        frame = create_delete_auto_setting_command(
            (0, 7), datetime.time(8, 30), datetime.time(18, 0), 15, 127
        )
        assert list(frame[6:12]) == [8, 30, 18, 0, 15, 127]
        assert list(frame[12:-1]) == [255] * 8

    def test_delete_matches_documented_capture(self):
        frame = create_delete_auto_setting_command(
            (0x00, 0x17),
            datetime.time(2, 30),
            datetime.time(5, 10),
            ramp_up_minutes=1,
            weekdays=0x7F,
        )
        assert bytes(frame) == DOC_DELETE_FRAME
