from datetime import datetime, timedelta, timezone

from osint_trader.risk.cooldown import CooldownTracker, _Last


def test_first_signal_passes():
    cd = CooldownTracker(minutes=30)
    ok, _ = cd.allow("market-x", "yes", 0.10)
    assert ok


def test_second_signal_blocked_inside_window():
    cd = CooldownTracker(minutes=30, edge_widening_required=0.05)
    cd.record("market-x", "yes", 0.10)
    ok, why = cd.allow("market-x", "yes", 0.11)
    assert not ok
    assert "cooldown_active" in why


def test_signal_passes_after_window():
    cd = CooldownTracker(minutes=30)
    cd.record("market-x", "yes", 0.10)
    cd._last[("market-x", "yes")] = _Last(
        when=datetime.now(timezone.utc) - timedelta(minutes=31), edge=0.10,
    )
    ok, _ = cd.allow("market-x", "yes", 0.10)
    assert ok


def test_signal_passes_when_edge_widens_materially():
    cd = CooldownTracker(minutes=30, edge_widening_required=0.05)
    cd.record("market-x", "yes", 0.05)
    ok, why = cd.allow("market-x", "yes", 0.12)
    assert ok
    assert "edge_widened" in why


def test_other_side_unaffected():
    cd = CooldownTracker(minutes=30)
    cd.record("market-x", "yes", 0.10)
    ok, _ = cd.allow("market-x", "no", 0.10)
    assert ok
