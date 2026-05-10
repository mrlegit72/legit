from osint_trader.credibility import CredibilityTracker


def test_seeded_prior_returns_yaml_value():
    t = CredibilityTracker(prior_strength=20)
    t.seed_prior("reuters", 0.92)
    # mean of Beta(α, β) = α / (α+β) = 18.4 / 20 = 0.92
    assert abs(t.credibility("reuters") - 0.92) < 1e-9


def test_unknown_source_uses_fallback():
    t = CredibilityTracker()
    assert t.credibility("nobody", fallback=0.31) == 0.31


def test_wins_pull_credibility_up_losses_pull_down():
    t = CredibilityTracker(prior_strength=4)
    t.seed_prior("rumor_channel", 0.40)
    start = t.credibility("rumor_channel")
    for _ in range(10):
        t.update("rumor_channel", won=True)
    end = t.credibility("rumor_channel")
    assert end > start
    # Now flood with losses
    for _ in range(20):
        t.update("rumor_channel", won=False)
    final = t.credibility("rumor_channel")
    assert final < start


def test_hydrate_from_outcomes_is_idempotent_in_count():
    t = CredibilityTracker(prior_strength=10)
    t.seed_prior("src", 0.5)
    t.hydrate_from_outcomes([("src", True), ("src", False), ("src", True)])
    # 2 wins + 1 loss on a 5/5 prior → α=7, β=6 → mean ≈ 0.538
    assert abs(t.credibility("src") - 7 / 13) < 1e-9
