from datetime import datetime, timedelta, timezone

from osint_trader.analysis.regime import RegimeDetector


def test_no_events_is_normal():
    rd = RegimeDetector()
    label, adj = rd.regime()
    assert label in ("calm", "normal")


def test_burst_in_recent_window_triggers_crisis():
    rd = RegimeDetector(short_window_min=60, long_window_hours=24)
    base = datetime.now(timezone.utc) - timedelta(hours=23, minutes=59)
    # 1 baseline event 24h ago, 200 events in the last hour → crisis
    rd.record(base)
    for i in range(200):
        rd.record(datetime.now(timezone.utc) - timedelta(seconds=i))
    label, adj = rd.regime()
    assert label == "crisis"
    assert adj < 0


def test_calm_when_recent_below_baseline():
    rd = RegimeDetector(short_window_min=60, long_window_hours=24)
    # Many old events, none recent
    for i in range(48):
        rd.record(datetime.now(timezone.utc) - timedelta(hours=i))
    label, adj = rd.regime()
    assert label in ("calm", "normal")
