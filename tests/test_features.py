import pytest

pd = pytest.importorskip("pandas")
pytest.importorskip("numpy")
pytest.importorskip("sklearn")

from phishguard.features import HeuristicFeatureTransformer, build_feature_pipeline


def test_heuristic_features_basic():
    transformer = HeuristicFeatureTransformer()
    df = pd.DataFrame(
        {
            "subject": ["Urgent action required"],
            "body": ["Please verify your account now at http://bit.ly/fake"],
            "num_links": [2],
            "num_images": [0],
            "has_attachments": [1],
            "domain_reputation": [0.2],
            "from_address": ["Support <support@alerts-update.com>"],
            "received_at": ["2023-01-01T10:00:00"],
            "spf_pass": [0],
            "dkim_pass": [0],
            "dmarc_pass": [0],
        }
    )
    transformer.fit(df)
    values = transformer.transform(df)
    assert values.shape[1] == len(transformer.feature_names_)
    # Suspicious TLD and urgency keywords should be flagged
    suspicious_tld_idx = transformer.feature_names_.index("suspicious_tld")
    urgency_idx = transformer.feature_names_.index("urgency_keyword_count")
    assert values[0, suspicious_tld_idx] == 1
    assert values[0, urgency_idx] >= 1


def test_feature_pipeline_output_shape():
    pipeline = build_feature_pipeline()
    df = pd.DataFrame(
        {
            "subject": ["Hello team"],
            "body": ["Meeting agenda"],
            "num_links": [0],
            "num_images": [0],
            "has_attachments": [0],
            "domain_reputation": [0.9],
            "from_address": ["Alice <alice@company.com>"],
            "received_at": ["2023-01-01T10:00:00"],
            "spf_pass": [1],
            "dkim_pass": [1],
            "dmarc_pass": [1],
        }
    )
    pipeline.fit(df, ["legit"])
    transformed = pipeline.transform(df)
    assert transformed.shape[0] == 1
