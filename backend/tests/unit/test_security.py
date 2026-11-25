from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.infrastructure.security.passwords import hash_password, verify_password
from app.infrastructure.security.tokens import TokenError, TokenService

NOW = datetime(2026, 10, 5, 9, 0, tzinfo=UTC)
SECRET = "s" * 64


def test_hash_is_not_plaintext_and_is_salted():
    h1, h2 = hash_password("correct horse"), hash_password("correct horse")
    assert "correct horse" not in h1
    assert h1 != h2
    assert h1.startswith("$argon2id$")


def test_verify_accepts_right_and_rejects_wrong_password():
    h = hash_password("correct horse")
    assert verify_password("correct horse", h) is True
    assert verify_password("wrong", h) is False


def test_verify_returns_false_for_malformed_hash():
    assert verify_password("anything", "not-a-hash") is False


def test_token_round_trips_to_user_id():
    svc = TokenService(SECRET, ttl=timedelta(minutes=30))
    uid = uuid4()
    assert svc.verify(svc.issue(uid, now=NOW), now=NOW + timedelta(minutes=5)) == uid


def test_expired_token_is_rejected():
    svc = TokenService(SECRET, ttl=timedelta(minutes=30))
    token = svc.issue(uuid4(), now=NOW)
    with pytest.raises(TokenError):
        svc.verify(token, now=NOW + timedelta(minutes=31))


def test_token_signed_with_other_secret_is_rejected():
    token = TokenService("o" * 64, ttl=timedelta(minutes=30)).issue(uuid4(), now=NOW)
    with pytest.raises(TokenError):
        TokenService(SECRET, ttl=timedelta(minutes=30)).verify(token, now=NOW)


def test_tampered_token_is_rejected():
    svc = TokenService(SECRET, ttl=timedelta(minutes=30))
    token = svc.issue(uuid4(), now=NOW)
    with pytest.raises(TokenError):
        svc.verify(token[:-2] + ("AA" if token[-2:] != "AA" else "BB"), now=NOW)


def test_unsigned_alg_none_token_is_rejected():
    forged = jwt.encode(
        {"sub": str(uuid4()), "exp": int((NOW + timedelta(hours=1)).timestamp())},
        key=None,
        algorithm="none",
    )
    with pytest.raises(TokenError):
        TokenService(SECRET, ttl=timedelta(minutes=30)).verify(forged, now=NOW)


def test_garbage_token_is_rejected():
    with pytest.raises(TokenError):
        TokenService(SECRET, ttl=timedelta(minutes=30)).verify("garbage", now=NOW)
