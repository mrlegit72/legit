"""Feature engineering utilities for phishing detection."""
from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Iterable, List

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

LOGGER = logging.getLogger(__name__)

SUSPICIOUS_TLDS = {
    "zip",
    "xyz",
    "top",
    "loan",
    "click",
    "country",
    "mom",
    "work",
    "support",
    "online",
}

URL_SHORTENERS = re.compile(r"\b(bit\.ly|goo\.gl|tinyurl\.com|ow\.ly|t\.co|is\.gd)\b", re.I)
CREDENTIAL_KEYWORDS = re.compile(
    r"\b(password|verify|account|login|bank|crypto|wallet|pin|credential)\b", re.I
)
URGENCY_KEYWORDS = re.compile(
    r"\b(urgent|immediately|asap|suspend|suspension|minutes|now|important)\b", re.I
)
PUNYCODE_PATTERN = re.compile(r"xn--", re.I)


class HeuristicFeatureTransformer(BaseEstimator, TransformerMixin):
    """Generate heuristic features from email metadata and content."""

    feature_names_: List[str]

    def fit(self, X: pd.DataFrame, y: Iterable[str] | None = None):
        self.feature_names_ = [
            "num_links",
            "num_images",
            "has_attachments",
            "domain_reputation",
            "domain_display_mismatch",
            "suspicious_tld",
            "urgency_keyword_count",
            "credential_keyword_count",
            "shortener_count",
            "unicode_homograph",
            "new_sender",
            "spf_pass",
            "dkim_pass",
            "dmarc_pass",
            "hour_of_day",
            "is_weekend",
        ]
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        df = X.copy()
        df["num_links"] = pd.to_numeric(df.get("num_links", 0)).fillna(0)
        df["num_images"] = pd.to_numeric(df.get("num_images", 0)).fillna(0)
        df["has_attachments"] = pd.to_numeric(df.get("has_attachments", 0)).fillna(0)
        df["domain_reputation"] = pd.to_numeric(df.get("domain_reputation", 0.5)).fillna(0.5)

        def extract_domain(address: str) -> str:
            if not isinstance(address, str):
                return ""
            if "<" in address and ">" in address:
                address = address.split("<", 1)[1].split(">", 1)[0]
            return address.split("@")[-1].lower() if "@" in address else address.lower()

        df["from_domain"] = df.get("from_address", "").apply(extract_domain)
        df["display_name"] = df.get("from_address", "").str.extract(r"^([^<]+)")
        df["display_name"] = df["display_name"].fillna("").str.strip().str.lower()

        df["domain_display_mismatch"] = (
            df["display_name"].apply(lambda x: bool(x))
            & ~df.apply(lambda row: row["display_name"] in row["from_domain"], axis=1)
        ).astype(int)

        df["suspicious_tld"] = df["from_domain"].str.split(".").str[-1].isin(SUSPICIOUS_TLDS).astype(int)

        text = (df.get("subject", "") + " " + df.get("body", "")).fillna("")
        df["urgency_keyword_count"] = text.str.count(URGENCY_KEYWORDS)
        df["credential_keyword_count"] = text.str.count(CREDENTIAL_KEYWORDS)
        df["shortener_count"] = text.str.count(URL_SHORTENERS)
        df["unicode_homograph"] = text.apply(lambda x: int(any(ord(ch) > 126 for ch in x)))

        df["spf_pass"] = pd.to_numeric(df.get("spf_pass", 1)).fillna(1)
        df["dkim_pass"] = pd.to_numeric(df.get("dkim_pass", 1)).fillna(1)
        df["dmarc_pass"] = pd.to_numeric(df.get("dmarc_pass", 1)).fillna(1)

        timestamps = pd.to_datetime(df.get("received_at", datetime.utcnow()), errors="coerce")
        timestamps = timestamps.ffill().bfill()
        df["received_at"] = timestamps
        df["hour_of_day"] = timestamps.dt.hour.fillna(0)
        df["is_weekend"] = timestamps.dt.dayofweek.isin([5, 6]).astype(int)

        # Determine if sender is new within a 14-day window.
        df_sorted = df.sort_values("received_at")
        first_seen = df_sorted.groupby("from_domain")["received_at"].transform("first")
        first_seen_dt = pd.to_datetime(first_seen, errors="coerce")
        received_dt = pd.to_datetime(df_sorted["received_at"], errors="coerce")
        delta = (received_dt - first_seen_dt).dt.total_seconds().fillna(0)
        df_sorted["new_sender"] = (delta <= 14 * 24 * 3600).astype(int)
        df = df_sorted.sort_index()

        features = df[self.feature_names_].fillna(0).astype(float)
        return features.to_numpy(dtype=float)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.array(self.feature_names_)


def build_feature_pipeline() -> ColumnTransformer:
    """Create the full feature extraction pipeline."""
    text_combiner = FunctionTransformer(
        lambda df: (df["subject"].fillna("") + " " + df["body"].fillna("")),
        validate=False,
    )
    body_extractor = FunctionTransformer(lambda df: df["body"].fillna(""), validate=False)

    text_word = Pipeline(
        steps=[
            ("combine", text_combiner),
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    max_features=8000,
                    min_df=2,
                    strip_accents="unicode",
                ),
            ),
        ]
    )

    text_char = Pipeline(
        steps=[
            ("body", body_extractor),
            (
                "tfidf",
                TfidfVectorizer(
                    analyzer="char_wb",
                    ngram_range=(3, 5),
                    max_features=4000,
                ),
            ),
        ]
    )

    heuristics = Pipeline(
        steps=[
            ("heuristic", HeuristicFeatureTransformer()),
            ("scaler", StandardScaler(with_mean=False)),
        ]
    )

    transformer = ColumnTransformer(
        transformers=[
            ("text_word", text_word, ["subject", "body"]),
            ("text_char", text_char, ["subject", "body"]),
            ("heuristics", heuristics, [
                "subject",
                "body",
                "num_links",
                "num_images",
                "has_attachments",
                "domain_reputation",
                "from_address",
                "received_at",
                "spf_pass",
                "dkim_pass",
                "dmarc_pass",
            ]),
        ],
        remainder="drop",
    )
    return transformer


def get_feature_names(transformer: ColumnTransformer) -> List[str]:
    """Retrieve feature names from a fitted ColumnTransformer."""
    feature_names: List[str] = []
    for name, trans, columns in transformer.transformers_:
        if name == "remainder":
            continue
        if hasattr(trans, "get_feature_names_out"):
            names = trans.get_feature_names_out()
        elif hasattr(trans, "named_steps") and "tfidf" in trans.named_steps:
            names = trans.named_steps["tfidf"].get_feature_names_out()
        else:
            names = []
        if isinstance(names, np.ndarray):
            names = names.tolist()
        # Prefix feature group for clarity
        feature_names.extend([f"{name}__{feat}" for feat in names])
    return feature_names
