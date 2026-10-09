"""Tests for API key auth + rate limiting."""

from sunnyware import auth


def test_auth_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SUNNYWARE_API_KEYS", raising=False)
    auth.load_keys(reload=True)
    assert auth.auth_enabled() is False


def test_auth_enabled_with_keys(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_API_KEYS", "k1,k2,k3")
    auth.load_keys(reload=True)
    assert auth.auth_enabled() is True
    assert auth.is_valid_key("k1")
    assert auth.is_valid_key("k3")
    assert not auth.is_valid_key("k4")
    assert not auth.is_valid_key("")


def test_auth_whitespace_tolerance(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_API_KEYS", "  k1 , k2 , k3  ")
    auth.load_keys(reload=True)
    assert auth.is_valid_key("k1")
    assert auth.is_valid_key("k2")


def test_extract_key_from_x_api_key():
    headers = [(b"x-api-key", b"secret")]
    assert auth.extract_key_from_headers(headers) == "secret"


def test_extract_key_from_bearer():
    headers = [(b"authorization", b"Bearer topsecret")]
    assert auth.extract_key_from_headers(headers) == "topsecret"


def test_extract_key_missing():
    assert auth.extract_key_from_headers([]) is None
    assert auth.extract_key_from_headers([(b"content-type", b"application/json")]) is None


def test_mask_key():
    assert auth.mask_key("abcdefgh") == "abc...fgh"
    assert auth.mask_key("ab") == "***"
    assert auth.mask_key("") == "***"


def test_rate_limit_disabled_by_default(monkeypatch):
    monkeypatch.delenv("SUNNYWARE_RATE_LIMIT_PER_MINUTE", raising=False)
    auth.reset_rate_limits()
    assert auth.rate_limit_enabled() is False
    r = auth.check_rate_limit("any")
    assert r["ok"] is True


def test_rate_limit_blocks_after_limit(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_RATE_LIMIT_PER_MINUTE", "3")
    auth.reset_rate_limits()
    assert auth.rate_limit_per_minute() == 3
    for _ in range(3):
        assert auth.check_rate_limit("k").get("ok") is True
    r = auth.check_rate_limit("k")
    assert r["ok"] is False
    assert r["retry_after"] > 0


def test_rate_limit_separate_buckets(monkeypatch):
    monkeypatch.setenv("SUNNYWARE_RATE_LIMIT_PER_MINUTE", "2")
    auth.reset_rate_limits()
    auth.check_rate_limit("k1")
    auth.check_rate_limit("k1")
    # k1 exhausted, k2 still has room
    assert auth.check_rate_limit("k1")["ok"] is False
    assert auth.check_rate_limit("k2")["ok"] is True
