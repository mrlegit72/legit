from pathlib import Path

import pytest

pytest.importorskip("pandas")
np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("joblib")

from phishguard import data, model


def test_train_and_evaluate(tmp_path):
    csv_path = tmp_path / "emails.csv"
    data.generate_synthetic_dataset(csv_path, rows=80)
    artifacts, eval_result = model.train_model(csv_path)
    assert artifacts.model_name in {"logistic_regression", "gradient_boosting", "LogisticRegression", "GradientBoostingClassifier"}
    assert eval_result.confusion.shape == (2, 2)
    # Evaluate using saved model
    result = model.evaluate_model(csv_path)
    assert 0 <= result.accuracy <= 1
    assert not np.isnan(result.roc_auc)
