"""Per-source credibility learner using Beta-Bernoulli posterior.

Idea: each source's credibility is a probability that a signal it triggers
ultimately wins (positive PnL on resolution). We treat the YAML credibility
as a Beta(α₀, β₀) prior and update it from realised outcomes:
    α = α₀ + wins
    β = β₀ + losses
The posterior mean replaces the static credibility on startup and gets
refreshed whenever a settlement lands.

The prior is anchored at the YAML weight × strength (default 20 pseudo-counts)
so the system doesn't lurch on the first few outcomes.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..observability import get_logger

logger = get_logger(__name__)


@dataclass
class _Posterior:
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / max(self.alpha + self.beta, 1e-6)


class CredibilityTracker:
    def __init__(self, prior_strength: float = 20.0) -> None:
        self.prior_strength = prior_strength
        self._posteriors: dict[str, _Posterior] = {}

    def seed_prior(self, source_handle: str, prior_credibility: float) -> None:
        alpha = max(0.5, prior_credibility * self.prior_strength)
        beta = max(0.5, (1.0 - prior_credibility) * self.prior_strength)
        self._posteriors[source_handle] = _Posterior(alpha, beta)

    def credibility(self, source_handle: str, fallback: float = 0.5) -> float:
        post = self._posteriors.get(source_handle)
        return post.mean if post else fallback

    def update(self, source_handle: str, won: bool) -> float:
        post = self._posteriors.get(source_handle)
        if post is None:
            self.seed_prior(source_handle, 0.5)
            post = self._posteriors[source_handle]
        if won:
            post.alpha += 1.0
        else:
            post.beta += 1.0
        logger.info("credibility_updated", source=source_handle, won=won, mean=round(post.mean, 3))
        return post.mean

    def hydrate_from_outcomes(self, outcomes: list[tuple[str, bool]]) -> None:
        """Apply a batch of (source, won) outcomes — used at startup."""
        for source, won in outcomes:
            if source not in self._posteriors:
                self.seed_prior(source, 0.5)
            self.update(source, won)
