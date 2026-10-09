"""Tests for small tools: echo, current_time, date_calc, weather metadata."""

import asyncio

from sunnyware.tools.current_time import CurrentTimeTool
from sunnyware.tools.date_calc import DateCalcTool
from sunnyware.tools.echo import EchoTool
from sunnyware.tools.weather import WeatherTool


def run(tool, args):
    return asyncio.run(tool.run(args))


# ── echo ──
def test_echo_basic():
    r = run(EchoTool(), {"text": "hello"})
    assert r["echoed"] == "hello"
    assert r["length"] == 5


def test_echo_empty():
    r = run(EchoTool(), {})
    assert r["echoed"] == ""


# ── current_time ──
def test_current_time_fields():
    r = run(CurrentTimeTool(), {})
    assert "utc_iso" in r
    assert "utc_human" in r
    assert "epoch_seconds" in r
    assert r["day_of_week"] in {
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    }


def test_current_time_epoch_positive():
    r = run(CurrentTimeTool(), {})
    assert r["epoch_seconds"] > 1_700_000_000


# ── date_calc ──
def test_date_add():
    r = run(DateCalcTool(), {"action": "add", "date": "2026-01-01", "days": 30})
    assert r["result"] == "2026-01-31"


def test_date_add_negative():
    r = run(DateCalcTool(), {"action": "add", "date": "2026-01-31", "days": -30})
    assert r["result"] == "2026-01-01"


def test_date_diff():
    r = run(DateCalcTool(), {"action": "diff", "date": "2026-01-01", "date2": "2026-01-31"})
    assert r["days_between"] == 30
    assert r["absolute_days"] == 30


def test_date_diff_reversed():
    r = run(DateCalcTool(), {"action": "diff", "date": "2026-02-01", "date2": "2026-01-01"})
    assert r["days_between"] == -31


def test_date_weekday():
    r = run(DateCalcTool(), {"action": "weekday", "date": "2026-01-01"})
    assert r["weekday"] == "Thursday"


def test_date_invalid_format():
    r = run(DateCalcTool(), {"action": "add", "date": "not-a-date", "days": 1})
    assert "error" in r


def test_date_unknown_action():
    r = run(DateCalcTool(), {"action": "zorp", "date": "2026-01-01"})
    assert "error" in r


def test_date_add_out_of_range():
    r = run(DateCalcTool(), {"action": "add", "date": "2026-01-01", "days": 999_999_999})
    assert "error" in r


def test_date_missing_args():
    r = run(DateCalcTool(), {"action": "add", "date": "2026-01-01"})
    # days defaults to 0 — same date
    assert r.get("result") == "2026-01-01" or "error" in r


# ── weather (metadata only — no network) ──
def test_weather_name():
    assert WeatherTool.name == "weather"


def test_weather_has_city_param():
    assert "city" in WeatherTool.parameters


def test_weather_rejects_empty_city():
    r = run(WeatherTool(), {"city": ""})
    assert "error" in r
