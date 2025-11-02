"""Model training and evaluation utilities."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from .data import load_dataset, stratified_split
from .features import build_feature_pipeline, get_feature_names

LOGGER = logging.getLogger(__name__)

ARTIFACT_DIR = Path("artifacts")
MODEL_PATH = ARTIFACT_DIR / "model.joblib"
VECTORIZER_PATH = ARTIFACT_DIR / "vectorizer.joblib"
METRICS_PATH = ARTIFACT_DIR / "metrics.json"


@dataclass
class ModelArtifacts:
    pipeline: Pipeline
    feature_pipeline: object
    model_name: str


@dataclass
class EvaluationResult:
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    confusion: np.ndarray


RANDOM_STATE = 42


def _build_models() -> Dict[str, Pipeline]:
    feature_pipeline = build_feature_pipeline()
    lr_pipeline = Pipeline(
        steps=[
            ("features", feature_pipeline),
            (
                "clf",
                LogisticRegression(
                    max_iter=1000,
                    n_jobs=None,
                    class_weight="balanced",
                    solver="saga",
                    random_state=RANDOM_STATE,
                ),
            ),
        ]
    )

    gb_pipeline = Pipeline(
        steps=[
            ("features", build_feature_pipeline()),
            (
                "clf",
                GradientBoostingClassifier(random_state=RANDOM_STATE),
            ),
        ]
    )

    return {"logistic_regression": lr_pipeline, "gradient_boosting": gb_pipeline}


def select_model(train_df: pd.DataFrame) -> Tuple[str, Pipeline]:
    """Select the best model using cross-validation on the training set."""
    X_train = train_df.drop(columns=["label"])
    y_train = train_df["label"]

    models = _build_models()
    best_score = -np.inf
    best_name = ""
    best_pipeline: Pipeline | None = None

    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=RANDOM_STATE)

    for name, pipeline in models.items():
        LOGGER.info("Evaluating model %s via cross-validation", name)
        scores = cross_val_score(
            pipeline,
            X_train,
            y_train,
            cv=cv,
            scoring="f1",
            n_jobs=None,
        )
        mean_score = scores.mean()
        LOGGER.info("Model %s F1 score: %.3f", name, mean_score)
        if mean_score > best_score:
            best_score = mean_score
            best_name = name
            best_pipeline = pipeline

    assert best_pipeline is not None
    return best_name, best_pipeline


def train_model(data_path: Path) -> Tuple[ModelArtifacts, EvaluationResult]:
    """Train the best model and evaluate it on the hold-out test set."""
    df = load_dataset(data_path)
    dataset = stratified_split(df)

    best_name, pipeline = select_model(dataset.train)

    # Fit on combined train+valid for final model
    train_valid = pd.concat([dataset.train, dataset.valid]).reset_index(drop=True)
    X_tv = train_valid.drop(columns=["label"])
    y_tv = train_valid["label"]

    LOGGER.info("Training best model %s on train+valid set", best_name)
    pipeline.fit(X_tv, y_tv)

    X_test = dataset.test.drop(columns=["label"])
    y_test = dataset.test["label"]
    y_prob = pipeline.predict_proba(X_test)[:, 1] if hasattr(pipeline[-1], "predict_proba") else None
    y_pred = pipeline.predict(X_test)

    accuracy = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary", pos_label="phishing"
    )
    roc_auc = roc_auc_score(y_test.map({"legit": 0, "phishing": 1}), y_prob) if y_prob is not None else float("nan")
    conf = confusion_matrix(y_test, y_pred, labels=["phishing", "legit"])

    evaluation = EvaluationResult(
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=roc_auc,
        confusion=conf,
    )

    feature_pipeline = pipeline.named_steps["features"]
    feature_names = get_feature_names(feature_pipeline)

    ARTIFACT_DIR.mkdir(exist_ok=True)
    joblib.dump(pipeline, MODEL_PATH)
    joblib.dump(feature_pipeline, VECTORIZER_PATH)
    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": best_name,
                "accuracy": accuracy,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "roc_auc": roc_auc,
                "confusion_matrix": conf.tolist(),
                "feature_count": len(feature_names),
            },
            f,
            indent=2,
        )

    LOGGER.info("Saved model artifacts to %s", ARTIFACT_DIR)
    artifacts = ModelArtifacts(pipeline=pipeline, feature_pipeline=feature_pipeline, model_name=best_name)
    return artifacts, evaluation


def load_artifacts() -> ModelArtifacts:
    """Load trained model artifacts from disk."""
    if not MODEL_PATH.exists() or not VECTORIZER_PATH.exists():
        raise FileNotFoundError("Model artifacts not found. Train the model first.")

    pipeline: Pipeline = joblib.load(MODEL_PATH)
    feature_pipeline = joblib.load(VECTORIZER_PATH)
    model_name = pipeline.named_steps["clf"].__class__.__name__
    return ModelArtifacts(pipeline=pipeline, feature_pipeline=feature_pipeline, model_name=model_name)


def evaluate_model(data_path: Path) -> EvaluationResult:
    """Evaluate the saved model on the test split of the dataset."""
    artifacts = load_artifacts()
    df = load_dataset(data_path)
    dataset = stratified_split(df)
    X_test = dataset.test.drop(columns=["label"])
    y_test = dataset.test["label"]

    pipeline = artifacts.pipeline
    y_pred = pipeline.predict(X_test)
    y_prob = pipeline.predict_proba(X_test)[:, 1] if hasattr(pipeline[-1], "predict_proba") else None

    accuracy = accuracy_score(y_test, y_pred)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_test, y_pred, average="binary", pos_label="phishing"
    )
    roc_auc = roc_auc_score(y_test.map({"legit": 0, "phishing": 1}), y_prob) if y_prob is not None else float("nan")
    conf = confusion_matrix(y_test, y_pred, labels=["phishing", "legit"])

    result = EvaluationResult(
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1=f1,
        roc_auc=roc_auc,
        confusion=conf,
    )
    LOGGER.info("Evaluation metrics: %s", result)
    return result
