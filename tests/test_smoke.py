from pathlib import Path

import pytest

pytest.importorskip("pandas")
pytest.importorskip("numpy")
pytest.importorskip("sklearn")
pytest.importorskip("joblib")

from phishguard import data, model


def test_generate_and_train(tmp_path):
    csv_path = tmp_path / "emails.csv"
    df = data.generate_synthetic_dataset(csv_path, rows=60)
    assert len(df) == 60
    artifacts, evaluation = model.train_model(csv_path)
    assert artifacts.pipeline is not None
    assert 0 <= evaluation.accuracy <= 1
