"""Tests for live channel brightness interpolation (sensor._calculate_channel_brightness)."""

import datetime

from custom_components.aquable.domain.light.status import LightSchedule
from custom_components.aquable.sensor import _calculate_channel_brightness

# 2025-01-06 is a Monday.
MONDAY = datetime.date(2025, 1, 6)


def _at(hour: int, minute: int = 0, day: datetime.date = MONDAY) -> datetime.datetime:
    return datetime.datetime.combine(day, datetime.time(hour, minute))


def _schedule(**overrides) -> LightSchedule:
    values = {
        "sunrise_hour": 8,
        "sunrise_minute": 0,
        "sunset_hour": 18,
        "sunset_minute": 0,
        "ramp_up_minutes": 60,
        "weekday_mask": 127,
        "channel_brightness": [100, 50],
    }
    values.update(overrides)
    return LightSchedule(**values)


def test_zero_outside_window():
    sched = [_schedule()]
    assert _calculate_channel_brightness(sched, 0, _at(7, 59)) == 0
    assert _calculate_channel_brightness(sched, 0, _at(18, 0)) == 0


def test_ramp_up_midpoint():
    assert _calculate_channel_brightness([_schedule()], 0, _at(8, 30)) == 50
    assert _calculate_channel_brightness([_schedule()], 1, _at(8, 30)) == 25


def test_plateau_is_peak():
    assert _calculate_channel_brightness([_schedule()], 0, _at(12)) == 100


def test_ramp_down_midpoint():
    assert _calculate_channel_brightness([_schedule()], 0, _at(17, 30)) == 50


def test_no_ramp_jumps_to_peak():
    sched = [_schedule(ramp_up_minutes=0)]
    assert _calculate_channel_brightness(sched, 0, _at(8, 0)) == 100


def test_weekday_mask_respected():
    tuesday_only = [_schedule(weekday_mask=1 << 5)]
    assert _calculate_channel_brightness(tuesday_only, 0, _at(12)) == 0
    assert (
        _calculate_channel_brightness(tuesday_only, 0, _at(12, day=MONDAY + datetime.timedelta(1)))
        == 100
    )


def test_out_of_range_channel_is_zero():
    assert _calculate_channel_brightness([_schedule()], 5, _at(12)) == 0


def test_overlapping_schedules_take_max():
    sched = [_schedule(), _schedule(channel_brightness=[30, 30])]
    assert _calculate_channel_brightness(sched, 0, _at(12)) == 100
