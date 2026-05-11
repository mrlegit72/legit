from osint_trader.markets.condition_index import _decode_token_ids


def test_handles_json_string_list():
    assert _decode_token_ids('["123","456"]') == ["123", "456"]


def test_handles_python_list():
    assert _decode_token_ids(["a", "b"]) == ["a", "b"]


def test_handles_none_and_garbage():
    assert _decode_token_ids(None) == []
    assert _decode_token_ids("not a list") == []
    assert _decode_token_ids(42) == []
