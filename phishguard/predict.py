"""Prediction utilities for the phishing detector."""
from __future__ import annotations

import email
import html
import html.parser
import json
import logging
import re
from email.message import Message
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .model import load_artifacts
from .rules import evaluate_rules, normalize_rule_score

LOGGER = logging.getLogger(__name__)

REQUIRED_FIELDS = [
    "subject",
    "body",
    "from_address",
    "to_address",
    "received_at",
    "has_attachments",
    "num_links",
    "num_images",
    "domain_reputation",
    "spf_pass",
    "dkim_pass",
    "dmarc_pass",
]


def sanitize_html(html_text: str) -> str:
    """Safely strip HTML to plain text without executing scripts."""

    class _HTMLStripper(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.result: List[str] = []

        def handle_data(self, data: str) -> None:  # pragma: no cover - simple
            if data:
                self.result.append(data)

        def handle_entityref(self, name: str) -> None:  # pragma: no cover - simple
            try:
                self.result.append(html.unescape(f"&{name};"))
            except Exception:
                self.result.append(f"&{name};")

        def get_data(self) -> str:
            return " ".join(self.result)

    stripper = _HTMLStripper()
    try:
        stripper.feed(html_text)
    except Exception:  # pragma: no cover - defensive
        return re.sub(r"\s+", " ", html_text)
    text = stripper.get_data()
    return re.sub(r"\s+", " ", text).strip()


def extract_body(message: Message) -> str:
    """Extract a safe text body from an email message."""
    if message.is_multipart():
        parts = []
        for part in message.walk():
            if part.get_content_maintype() == "multipart":
                continue
            content_type = part.get_content_type()
            try:
                payload = part.get_payload(decode=True)
            except Exception:  # pragma: no cover - defensive
                payload = None
            if not payload:
                continue
            charset = part.get_content_charset("utf-8")
            text = payload.decode(charset, errors="replace")
            if content_type == "text/html":
                parts.append(sanitize_html(text))
            elif content_type.startswith("text"):
                parts.append(text)
        return "\n".join(parts)
    payload = message.get_payload(decode=True)
    if not payload:
        return ""
    charset = message.get_content_charset("utf-8")
    text = payload.decode(charset, errors="replace")
    if message.get_content_type() == "text/html":
        return sanitize_html(text)
    return text


def parse_eml(path: Path) -> Dict[str, Any]:
    """Parse an .eml file into the fields required for prediction."""
    with path.open("rb") as f:
        msg = email.message_from_binary_file(f)

    body = extract_body(msg)
    subject = msg.get("subject", "")
    from_address = msg.get("from", "")
    to_address = msg.get("to", "")
    cc = msg.get("cc", "")
    bcc = msg.get("bcc", "")
    received_at = msg.get("date", "")

    has_attachments = any(part.get_filename() for part in msg.walk() if part.get_filename())

    urls = re.findall(r"https?://[^\s]+", body)

    record = {
        "subject": subject,
        "body": body,
        "from_address": from_address,
        "to_address": to_address,
        "cc": cc,
        "bcc": bcc,
        "received_at": received_at,
        "has_attachments": int(has_attachments),
        "num_links": len(urls),
        "num_images": sum(1 for part in msg.walk() if part.get_content_maintype() == "image"),
        "domain_reputation": 0.5,
        "spf_pass": 1,
        "dkim_pass": 1,
        "dmarc_pass": 1,
    }
    return record


def _ensure_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    defaults = {
        "subject": "",
        "body": "",
        "from_address": "unknown@unknown",
        "to_address": "",
        "cc": "",
        "bcc": "",
        "received_at": "",
        "has_attachments": 0,
        "num_links": 0,
        "num_images": 0,
        "domain_reputation": 0.5,
        "spf_pass": 1,
        "dkim_pass": 1,
        "dmarc_pass": 1,
    }
    for key, value in defaults.items():
        data.setdefault(key, value)
    return data


def _prepare_dataframe(payloads: List[Dict[str, Any]]) -> pd.DataFrame:
    records = [_ensure_fields(dict(payload)) for payload in payloads]
    df = pd.DataFrame(records)
    df["has_attachments"] = pd.to_numeric(df["has_attachments"]).fillna(0).astype(int)
    df["num_links"] = pd.to_numeric(df["num_links"]).fillna(0).astype(int)
    df["num_images"] = pd.to_numeric(df["num_images"]).fillna(0).astype(int)
    df["domain_reputation"] = pd.to_numeric(df["domain_reputation"]).fillna(0.5)
    df["spf_pass"] = pd.to_numeric(df["spf_pass"]).fillna(1)
    df["dkim_pass"] = pd.to_numeric(df["dkim_pass"]).fillna(1)
    df["dmarc_pass"] = pd.to_numeric(df["dmarc_pass"]).fillna(1)
    return df


def explain_prediction(pipeline, feature_names: List[str], df: pd.DataFrame) -> List[List[Dict[str, Any]]]:
    """Return top positive and negative feature contributions for each prediction."""
    explanations: List[List[Dict[str, Any]]] = []
    features = pipeline.named_steps["features"]
    transformed = features.transform(df)
    clf = pipeline.named_steps["clf"]

    if hasattr(clf, "coef_"):
        coefficients = clf.coef_[0]
        if hasattr(transformed, "toarray"):
            transformed = transformed.toarray()
        for row in transformed:
            contributions = coefficients * row
            top_indices = np.argsort(contributions)[-5:][::-1]
            bottom_indices = np.argsort(contributions)[:5]
            reasons = []
            for idx in top_indices:
                if idx >= len(feature_names):
                    continue
                score = contributions[idx]
                if score <= 0:
                    continue
                reasons.append({"feature": feature_names[idx], "weight": float(score)})
            for idx in bottom_indices:
                if idx >= len(feature_names):
                    continue
                score = contributions[idx]
                if score >= 0:
                    continue
                reasons.append({"feature": feature_names[idx], "weight": float(score)})
            explanations.append(reasons)
    elif hasattr(clf, "feature_importances_"):
        importances = clf.feature_importances_
        top_indices = np.argsort(importances)[-10:][::-1]
        reasons = [
            {"feature": feature_names[idx], "weight": float(importances[idx])}
            for idx in top_indices
            if idx < len(feature_names)
        ]
        for _ in range(len(df)):
            explanations.append(reasons)
    else:  # pragma: no cover - fallback
        for _ in range(len(df)):
            explanations.append([])
    return explanations


def predict(payloads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    artifacts = load_artifacts()
    pipeline = artifacts.pipeline
    feature_pipeline = artifacts.feature_pipeline
    feature_names = feature_pipeline.get_feature_names_out()
    if not isinstance(feature_names, list):
        feature_names = feature_names.tolist()

    df = _prepare_dataframe(payloads)
    if hasattr(pipeline[-1], "predict_proba"):
        ml_probs = pipeline.predict_proba(df)[:, 1]
    else:
        preds = pipeline.predict(df)
        ml_probs = np.where(np.array(preds) == "phishing", 1.0, 0.0)

    explanations = explain_prediction(pipeline, feature_names, df)
    results: List[Dict[str, Any]] = []
    for row, prob, reasons in zip(df.to_dict(orient="records"), ml_probs, explanations):
        rule_result = evaluate_rules(row.get("subject", ""), row.get("body", ""))
        final_score = normalize_rule_score(rule_result.score, float(prob))
        label = "phishing" if final_score >= 0.5 else "legit"
        reason_strings = [
            f"ML: {item['feature']} ({item['weight']:+.3f})" for item in reasons[:3]
        ] + [f"Rule: {name} (+{weight:.2f})" for name, weight in rule_result.triggers.items()]
        results.append(
            {
                "label": label,
                "ml_prob": float(prob),
                "rule_score": float(rule_result.score),
                "final_score": float(final_score),
                "top_reasons": reason_strings,
            }
        )
    return results


def predict_json(payloads: List[Dict[str, Any]]) -> str:
    return json.dumps(predict(payloads), indent=2)


def predict_from_file(path: Path) -> Dict[str, Any]:
    record = parse_eml(path)
    return predict([record])[0]
