"""Rule-based heuristics for phishing detection."""
from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple

LOGGER = logging.getLogger(__name__)

RULES: List[Tuple[str, re.Pattern[str], float]] = [
    ("credential_request", re.compile(r"\b(password|verify|login|account)\b", re.I), 0.25),
    ("financial_threat", re.compile(r"\b(invoice|bank|payment|crypto|wallet)\b", re.I), 0.2),
    (
        "urgency_language",
        re.compile(r"\b(urgent|immediately|minutes|suspend|limited|now)\b", re.I),
        0.2,
    ),
    ("link_shortener", re.compile(r"\b(bit\.ly|tinyurl|ow\.ly|t\.co)\b", re.I), 0.15),
    ("punycode_url", re.compile(r"https?://[^\s]*xn--", re.I), 0.1),
    (
        "credential_form",
        re.compile(r"https?://[^\s]*(office|microsoft|paypa1|secure-update)", re.I),
        0.1,
    ),
]


@dataclass
class RuleResult:
    score: float
    triggers: Dict[str, float]


def evaluate_rules(subject: str, body: str) -> RuleResult:
    """Evaluate heuristic rules against email content."""
    text = f"{subject}\n{body}" if body else subject or ""
    triggers: Dict[str, float] = {}

    for name, pattern, weight in RULES:
        if pattern.search(text):
            triggers[name] = weight
            LOGGER.debug("Rule %s triggered (weight %.2f)", name, weight)

    raw_score = sum(triggers.values())
    score = max(0.0, min(1.0, raw_score))
    return RuleResult(score=score, triggers=triggers)


def normalize_rule_score(rule_score: float, ml_prob: float) -> float:
    """Combine rule score with ML probability into a calibrated risk."""
    # Blend using logistic-like smoothing to avoid extremes.
    combined = 1 - math.exp(-(0.7 * ml_prob + 0.6 * rule_score))
    return max(0.0, min(1.0, combined))
