from osint_trader.risk import Bankroll
from osint_trader.risk.scenarios import Scenario, ScenarioRegistry


def test_remaining_capacity_unbucketed_market_is_unbounded():
    reg = ScenarioRegistry([])
    bk = Bankroll(starting_usdc=1000)
    assert reg.remaining_capacity_usdc("anything", bk) == float("inf")


def test_scenario_caps_aggregate_exposure():
    reg = ScenarioRegistry([
        Scenario(id="iran_de_escalation", markets=["a", "b"], max_exposure_pct=0.10),
    ])
    bk = Bankroll(starting_usdc=1000)
    assert reg.remaining_capacity_usdc("a", bk) == 100.0
    bk.add_exposure("a", 70.0)
    assert reg.remaining_capacity_usdc("a", bk) == 30.0
    bk.add_exposure("b", 25.0)
    assert reg.remaining_capacity_usdc("a", bk) == 5.0
    bk.add_exposure("a", 10.0)  # over-cap; clamps at 0
    assert reg.remaining_capacity_usdc("a", bk) == 0.0


def test_market_in_two_scenarios_takes_smallest_cap():
    reg = ScenarioRegistry([
        Scenario(id="big", markets=["a"], max_exposure_pct=0.20),
        Scenario(id="small", markets=["a"], max_exposure_pct=0.05),
    ])
    bk = Bankroll(starting_usdc=1000)
    assert reg.remaining_capacity_usdc("a", bk) == 50.0
