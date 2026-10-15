"""Experiment tool for light schedules: set the clock, write/clear slots, read back.

Used to find out how the firmware interprets auto-schedule slots and point curves (see #10).
Hardware behaviour that is not confirmed by a capture is an assumption.

IMPORTANT: disable the AquaBle integration in Home Assistant while experimenting, it re-syncs
the device clock on every connect and would undo a deliberately jumped clock.

Usage:
    uv run scripts/light_schedule_lab.py --address <MAC> set-time "2026-08-27 11:58"
    uv run scripts/light_schedule_lab.py --address <MAC> write slots.json
    uv run scripts/light_schedule_lab.py --address <MAC> read
    uv run scripts/light_schedule_lab.py --address <MAC> sync-time
    uv run scripts/light_schedule_lab.py --address <MAC> clear
    uv run scripts/light_schedule_lab.py --address <MAC> points curve.json
    uv run scripts/light_schedule_lab.py --address <MAC> raw "05 FF FF" --cmd 0x5A --mode 0x05

Only set-time / sync-time touch the clock; write, clear and points never sync it.
Add `--log lab.log` to append every sent/received frame (hex, timestamped) to a file.

write.json (channels 0-100 or 255, max 8; weekdays: names, "everyday" or an int mask):
    [{"sunrise": "06:00", "sunset": "18:00", "ramp": 30,
      "weekdays": ["monday", "tuesday"], "channels": [30, 0, 20]}]

points.json (list index = channel, null = no frame for that channel, levels 0-100).
The 0x5A/0x05 [05 FF FF] reset + 0x5A/0x06 [channel, hour, minute, level] frames follow
TheMicDiet/chihiros-led-control docs/protocol.md and are NOT confirmed on our hardware:
    [{"time": "06:00", "channels": [6, null, 6]}]
"""

from __future__ import annotations

import argparse
import asyncio
import datetime
import importlib
import json
import sys
import types
from collections.abc import Sequence
from pathlib import Path

_INTEGRATION_DIR = Path(__file__).resolve().parent.parent / "custom_components" / "aquable"


def _load_integration_package() -> types.ModuleType:
    """Register the integration dir as a bare package, skipping its HA-dependent __init__."""
    name = "aquable_lab"
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [str(_INTEGRATION_DIR)]
        sys.modules[name] = pkg
    return sys.modules[name]


_load_integration_package()
encoder = importlib.import_module("aquable_lab.commands.encoder")
parsers = importlib.import_module("aquable_lab.commands.parsers")

# Nordic UART Service (NUS) characteristics
UART_RX_CHAR_UUID = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # we write here
UART_TX_CHAR_UUID = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # we get notifications here

_POINT_DELAY = 0.03  # reference repo sends curve points ~30 ms apart (assumption)
_FRAME_DELAY = 0.2


class MessageIds:
    """Hands out consecutive message ids, skipping reserved values."""

    def __init__(self, start: tuple[int, int] = (0, 0)) -> None:
        self._current = start

    def next(self) -> tuple[int, int]:
        self._current = encoder.next_message_id(self._current)
        return self._current


# ─── Frame building (pure, no BLE) ────────────────────────────────────────────


def parse_clock_time(text: str) -> datetime.time:
    return datetime.datetime.strptime(text, "%H:%M").time()


def parse_datetime(text: str) -> datetime.datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Expected 'YYYY-MM-DD HH:MM[:SS]', got {text!r}")


def build_set_time(ids: MessageIds, when: datetime.datetime | None = None) -> list[bytearray]:
    return [encoder.create_set_time_command(ids.next(), when=when)]


def build_clear(ids: MessageIds) -> list[bytearray]:
    return [encoder.create_reset_auto_settings_command(ids.next())]


def _weekday_mask(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool):
        if not 0 <= value <= 127:
            raise ValueError(f"Weekday mask must be 0-127, got {value}")
        return value
    return encoder.encode_weekdays(value)  # type: ignore[arg-type]


def build_write(ids: MessageIds, slots: Sequence[dict]) -> list[bytearray]:
    """Reset, one 0xA5/0x19 frame per slot, then switch to auto mode."""
    frames = build_clear(ids)
    for slot in slots:
        frames.append(
            encoder.create_add_auto_setting_command(
                ids.next(),
                parse_clock_time(slot["sunrise"]),
                parse_clock_time(slot["sunset"]),
                tuple(slot["channels"]),
                int(slot["ramp"]),
                _weekday_mask(slot.get("weekdays", "everyday")),
            )
        )
    frames.append(encoder.create_switch_to_auto_mode_command(ids.next()))
    return frames


def build_points(ids: MessageIds, points: Sequence[dict]) -> list[bytearray]:
    """0x5A/0x05 [05 FF FF] reset, then a 0x5A/0x06 frame per point per channel."""
    frames = build_clear(ids)
    for point in points:
        when = parse_clock_time(point["time"])
        for channel, level in enumerate(point["channels"]):
            if level is None:
                continue
            if not 0 <= level <= 100:
                raise ValueError(f"Level must be 0-100, got {level}")
            frames.append(
                encoder._encode_uart_command(
                    0x5A, 0x06, ids.next(), [channel, when.hour, when.minute, level]
                )
            )
    return frames


def build_raw(ids: MessageIds, cmd: int, mode: int, params: bytes) -> tuple[bytearray, list[int]]:
    """Build a raw frame; also return indexes of 0x5A params the encoder replaces."""
    substituted = [i for i, b in enumerate(params) if b == 0x5A]
    return encoder._encode_uart_command(cmd, mode, ids.next(), list(params)), substituted


# ─── Decoding ─────────────────────────────────────────────────────────────────

_TRIPLES_OFFSET = 25


def decode_fe(payload: bytes) -> list[str]:
    """Decode a 0xFE snapshot as AquaBle schedule blocks and as the reference repo's triples."""
    lines: list[str] = []
    status = parsers.parse_light_payload(payload, num_channels=4)
    if status is None:
        return ["not a 0x5B/0xFE light status frame"]
    lines.append(
        f"header: weekday={status.weekday} time={status.hour}:{status.minute:02d}"
        if status.hour is not None
        else "header: incomplete"
    )
    lines.append("as 13-byte schedule blocks (AquaBle):")
    if not status.schedules:
        lines.append("  (none)")
    for s in status.schedules:
        lines.append(
            f"  {s.sunrise_hour:02d}:{s.sunrise_minute:02d} -> "
            f"{s.sunset_hour:02d}:{s.sunset_minute:02d} ramp={s.ramp_up_minutes} "
            f"mask={s.weekday_mask:#04x} channels={s.channel_brightness}"
        )
    lines.append(
        f"as hour,minute,level triples from offset {_TRIPLES_OFFSET} (chihiros-led-control):"
    )
    body = payload[_TRIPLES_OFFSET:-1]  # last byte is the checksum
    triples = [body[i : i + 3] for i in range(0, len(body) - len(body) % 3, 3)]
    if not triples:
        lines.append("  (payload too short)")
    for t in triples:
        plausible = t[0] <= 23 and t[1] <= 59 and t[2] <= 100
        lines.append(f"  {t[0]:02d}:{t[1]:02d} level={t[2]}{'' if plausible else '  ?'}")
    return lines


# ─── BLE I/O ──────────────────────────────────────────────────────────────────


class Recorder:
    def __init__(self, log_path: Path | None) -> None:
        self._log = log_path
        self.saw_fe = False

    def emit(self, direction: str, data: bytes) -> None:
        stamp = datetime.datetime.now().isoformat(timespec="milliseconds")
        line = f"{stamp} {direction} {data.hex(' ')}"
        print(line)
        if self._log:
            with self._log.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def note(self, text: str) -> None:
        print(text)
        if self._log:
            with self._log.open("a", encoding="utf-8") as fh:
                fh.write(text + "\n")


async def run_session(
    address: str,
    frames: Sequence[bytes],
    recorder: Recorder,
    delay: float,
    wait: float,
    decode: bool = False,
) -> None:
    from bleak import BleakClient  # imported lazily so --help and tests need no BLE stack

    def on_notify(_sender, data: bytearray) -> None:
        payload = bytes(data)
        recorder.emit("RX", payload)
        if len(payload) > 5 and payload[0] == 0x5B and payload[5] == 0xFE:
            recorder.saw_fe = True
            if decode:
                for line in decode_fe(payload):
                    recorder.note("    " + line)

    async with BleakClient(address) as client:
        await client.start_notify(UART_TX_CHAR_UUID, on_notify)
        for frame in frames:
            recorder.emit("TX", bytes(frame))
            await client.write_gatt_char(UART_RX_CHAR_UUID, bytes(frame), response=False)
            await asyncio.sleep(delay)
        await asyncio.sleep(wait)
        await client.stop_notify(UART_TX_CHAR_UUID)

    if decode and not recorder.saw_fe:
        recorder.note("No 0x5B/0xFE status notification received.")


# ─── CLI ──────────────────────────────────────────────────────────────────────


def _parse_int(text: str) -> int:
    return int(text, 0)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experiment tool for Chihiros light schedules. Disable the AquaBle "
        "integration while using it (it re-syncs the device clock on connect)."
    )
    parser.add_argument("--address", "-a", required=True, help="Device MAC / UUID.")
    parser.add_argument("--log", type=Path, help="Append all frames to this file.")
    parser.add_argument("--wait", type=float, default=3.0, help="Seconds to listen afterwards.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("set-time", help="Set the device clock to a given date/time.")
    p.add_argument("when", help="YYYY-MM-DD HH:MM[:SS]")
    sub.add_parser("sync-time", help="Set the device clock to the host's current time.")
    p = sub.add_parser("write", help="Clear all slots, write slots from JSON, enable auto mode.")
    p.add_argument("file", type=Path)
    sub.add_parser("clear", help="Clear all auto slots.")
    p = sub.add_parser("points", help="Write a point curve from JSON (unconfirmed protocol).")
    p.add_argument("file", type=Path)
    sub.add_parser("read", help="Handshake and print/decode every notification.")
    p = sub.add_parser("raw", help="Send a frame with arbitrary parameter bytes.")
    p.add_argument("params", help="Parameter bytes as hex, e.g. '05 FF FF'.")
    p.add_argument("--cmd", type=_parse_int, required=True, choices=[0x5A, 0xA5])
    p.add_argument("--mode", type=_parse_int, required=True)
    return parser


def frames_for(args: argparse.Namespace, ids: MessageIds, recorder: Recorder) -> list[bytearray]:
    match args.command:
        case "set-time":
            return build_set_time(ids, parse_datetime(args.when))
        case "sync-time":
            return build_set_time(ids)
        case "clear":
            return build_clear(ids)
        case "write":
            return build_write(ids, json.loads(args.file.read_text(encoding="utf-8")))
        case "points":
            return build_points(ids, json.loads(args.file.read_text(encoding="utf-8")))
        case "read":
            return [encoder.create_handshake_command(ids.next())]
        case "raw":
            frame, substituted = build_raw(
                ids, args.cmd, args.mode, bytes.fromhex(args.params.replace(",", " "))
            )
            if substituted:
                recorder.note(
                    f"WARNING: parameter byte(s) at index {substituted} were 0x5A; "
                    "the encoder replaces them with 0x59."
                )
            return [frame]
    raise AssertionError(args.command)


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    recorder = Recorder(args.log)
    frames = frames_for(args, MessageIds(), recorder)
    delay = _POINT_DELAY if args.command == "points" else _FRAME_DELAY
    asyncio.run(
        run_session(args.address, frames, recorder, delay, args.wait, decode=args.command == "read")
    )


if __name__ == "__main__":
    main()
