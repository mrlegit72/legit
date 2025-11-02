"""Utilities for loading and generating phishing email datasets."""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

LOGGER = logging.getLogger(__name__)

DATA_COLUMNS = [
    "id",
    "subject",
    "body",
    "from_address",
    "to_address",
    "cc",
    "bcc",
    "received_at",
    "has_attachments",
    "num_links",
    "num_images",
    "domain_reputation",
    "spf_pass",
    "dkim_pass",
    "dmarc_pass",
    "label",
]

LABELS = ("phishing", "legit")


@dataclass
class Dataset:
    """Container for dataset splits."""

    train: pd.DataFrame
    valid: pd.DataFrame
    test: pd.DataFrame


def _random_datetime(start: datetime, end: datetime) -> datetime:
    delta = end - start
    random_seconds = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=random_seconds)


def _sample_from_addresses(n: int) -> list[str]:
    domains = [
        "paypal.com",
        "contoso.com",
        "secure-payments.net",
        "bankofspringfield.org",
        "cointrust.io",
        "it-support.local",
        "hr.company.com",
        "alerts-update.com",
    ]
    names = [
        "Alice",
        "Bob",
        "Finance Team",
        "Security",
        "HR",
        "IT Admin",
        "Payroll",
        "Support",
    ]
    addresses = []
    for _ in range(n):
        name = random.choice(names)
        domain = random.choice(domains)
        address = f"{name} <{name.lower().replace(' ', '')}@{domain}>"
        addresses.append(address)
    return addresses


def _generate_email_row(idx: int, start: datetime, end: datetime) -> dict:
    phishing_subjects = [
        "Urgent: Verify your account now",
        "Action required: Payroll update",
        "Security Alert - Password Reset Needed",
        "Payment pending confirmation",
        "Crypto wallet suspended",
    ]
    legit_subjects = [
        "Team meeting tomorrow",
        "Lunch order confirmation",
        "Weekly engineering newsletter",
        "Invoice processed",
        "Benefits enrollment reminder",
    ]
    phishing_bodies = [
        "Please login immediately using the secure link to avoid suspension.",
        "Your account has been compromised. Reset your password within 2 hours.",
        "Download the attached invoice and confirm payment to avoid penalties.",
        "We detected unusual login. Verify your credentials now at http://bit.ly/sec-login.",
        "Crypto payout waiting. Confirm your wallet details here.",
    ]
    legit_bodies = [
        "Here are the notes from today's meeting. Let me know if you have questions.",
        "Reminder about the company picnic this weekend. RSVP soon!",
        "The new HR policies are attached for review, thanks.",
        "Monthly sales numbers look good. Keep up the great work team.",
        "Agenda for next week's sprint planning is included below.",
    ]

    received_at = _random_datetime(start, end)
    is_phish = random.random() < 0.35
    if is_phish:
        subject = random.choice(phishing_subjects)
        body = random.choice(phishing_bodies)
        num_links = random.randint(1, 6)
        has_attachments = random.choice([0, 1])
        domain_reputation = round(random.uniform(0.0, 0.4), 2)
    else:
        subject = random.choice(legit_subjects)
        body = random.choice(legit_bodies)
        num_links = random.randint(0, 2)
        has_attachments = random.choice([0, 1]) if "attached" in body else 0
        domain_reputation = round(random.uniform(0.5, 1.0), 2)

    num_images = random.randint(0, 3)
    from_address = random.choice(_sample_from_addresses(1))
    to_address = "team@company.com"
    cc = "" if random.random() < 0.7 else "finance@company.com"
    bcc = "" if random.random() < 0.9 else "audit@company.com"

    urgency_keywords = ["urgent", "immediately", "penalty", "suspended"]
    if is_phish and random.random() < 0.6:
        body += " " + random.choice(urgency_keywords)

    label = "phishing" if is_phish else "legit"

    def sample_auth_status() -> int:
        if is_phish:
            return int(random.random() < 0.3)
        return int(random.random() < 0.85)

    return {
        "id": idx,
        "subject": subject,
        "body": body,
        "from_address": from_address,
        "to_address": to_address,
        "cc": cc,
        "bcc": bcc,
        "received_at": received_at.isoformat(),
        "has_attachments": has_attachments,
        "num_links": num_links,
        "num_images": num_images,
        "domain_reputation": domain_reputation,
        "spf_pass": sample_auth_status(),
        "dkim_pass": sample_auth_status(),
        "dmarc_pass": sample_auth_status(),
        "label": label,
    }


def generate_synthetic_dataset(path: Path, rows: int = 120) -> pd.DataFrame:
    """Generate a small but diverse synthetic phishing dataset."""
    LOGGER.info("Generating synthetic dataset at %s", path)
    path.parent.mkdir(parents=True, exist_ok=True)

    start = datetime.now() - timedelta(days=120)
    end = datetime.now()

    records = [_generate_email_row(i, start, end) for i in range(rows)]
    df = pd.DataFrame.from_records(records, columns=DATA_COLUMNS)
    df.to_csv(path, index=False)
    return df


def load_dataset(path: Path) -> pd.DataFrame:
    """Load dataset, generating a synthetic one if necessary."""
    if not path.exists():
        LOGGER.warning("Dataset %s missing. Generating synthetic data.", path)
        df = generate_synthetic_dataset(path)
    else:
        df = pd.read_csv(path)

    missing_cols = [col for col in DATA_COLUMNS if col not in df.columns]
    for col in missing_cols:
        if col == "label":
            continue
        LOGGER.info("Adding missing column %s with default values", col)
        if col in {"has_attachments", "spf_pass", "dkim_pass", "dmarc_pass"}:
            df[col] = 1
        elif col in {"num_links", "num_images"}:
            df[col] = 0
        elif col == "domain_reputation":
            df[col] = 0.5
        elif col == "received_at":
            df[col] = datetime.now().isoformat()
        else:
            df[col] = ""

    df = df.dropna(subset=["subject", "body", "from_address", "label"]).copy()
    df["label"] = df["label"].str.lower()
    df = df[df["label"].isin(LABELS)]
    LOGGER.info("Loaded dataset with %d rows", len(df))
    return df


def stratified_split(
    df: pd.DataFrame,
    train_size: float = 0.6,
    valid_size: float = 0.2,
    test_size: float = 0.2,
    random_state: int = 42,
) -> Dataset:
    """Split dataset into train/valid/test with stratification."""
    if not np.isclose(train_size + valid_size + test_size, 1.0):
        raise ValueError("train/valid/test sizes must sum to 1.0")

    from sklearn.model_selection import train_test_split

    temp_size = valid_size + test_size
    df_train, df_temp = train_test_split(
        df,
        test_size=temp_size,
        stratify=df["label"],
        random_state=random_state,
    )
    relative_valid_size = valid_size / temp_size
    df_valid, df_test = train_test_split(
        df_temp,
        test_size=(test_size / temp_size),
        stratify=df_temp["label"],
        random_state=random_state,
    )

    LOGGER.info(
        "Split dataset into train=%d, valid=%d, test=%d",
        len(df_train),
        len(df_valid),
        len(df_test),
    )
    return Dataset(train=df_train, valid=df_valid, test=df_test)
