import time

import pytest
from jose import jwt

from app.core.security import (
    ALGORITHM,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import settings


# ── Password hashing ──────────────────────────────────────────────────────────

def test_hash_password_returns_string():
    hashed = hash_password("mysecretpassword")
    assert isinstance(hashed, str)


def test_hash_password_is_not_plaintext():
    password = "mysecretpassword"
    hashed = hash_password(password)
    # The hash must never equal the original password
    assert hashed != password


def test_hash_password_produces_different_hashes():
    """
    bcrypt uses a random salt each time so the same password
    produces a different hash on every call. This is intentional
    and important for security.
    """
    hashed1 = hash_password("samepassword")
    hashed2 = hash_password("samepassword")
    assert hashed1 != hashed2


def test_verify_password_correct():
    password = "mysecretpassword"
    hashed = hash_password(password)
    assert verify_password(password, hashed) is True


def test_verify_password_wrong_password():
    hashed = hash_password("correctpassword")
    assert verify_password("wrongpassword", hashed) is False


def test_verify_password_empty_string():
    hashed = hash_password("somepassword")
    assert verify_password("", hashed) is False


# ── JWT access tokens ─────────────────────────────────────────────────────────

def test_create_access_token_returns_string():
    token = create_access_token(subject="user-123", tenant_id="tenant-456")
    assert isinstance(token, str)
    # JWT tokens have exactly 3 parts separated by dots
    assert len(token.split(".")) == 3


def test_access_token_contains_correct_claims():
    """
    Decode the token manually and verify the payload has exactly
    the fields we expect — subject, tenant_id, type, and expiry.
    """
    token = create_access_token(subject="user-123", tenant_id="tenant-456")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])

    assert payload["sub"] == "user-123"
    assert payload["tenant_id"] == "tenant-456"
    assert payload["type"] == "access"
    assert "exp" in payload


def test_access_token_expires_in_future():
    token = create_access_token(subject="user-123", tenant_id="tenant-456")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    # exp must be in the future (greater than current time)
    assert payload["exp"] > time.time()


# ── JWT refresh tokens ────────────────────────────────────────────────────────

def test_refresh_token_type_is_refresh():
    token = create_refresh_token(subject="user-123", tenant_id="tenant-456")
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    assert payload["type"] == "refresh"


def test_access_and_refresh_tokens_are_different():
    """
    Even with the same inputs, access and refresh tokens must differ
    because they have different type claims and different TTLs.
    """
    access = create_access_token(subject="user-123", tenant_id="tenant-456")
    refresh = create_refresh_token(subject="user-123", tenant_id="tenant-456")
    assert access != refresh


# ── decode_token ──────────────────────────────────────────────────────────────

def test_decode_token_returns_payload():
    token = create_access_token(subject="user-123", tenant_id="tenant-456")
    payload = decode_token(token)
    assert payload["sub"] == "user-123"
    assert payload["tenant_id"] == "tenant-456"


def test_decode_token_raises_on_invalid_token():
    with pytest.raises(ValueError, match="Invalid or expired token"):
        decode_token("this.is.not.a.valid.jwt")


def test_decode_token_raises_on_tampered_token():
    """
    Take a valid token and change the last character.
    The signature verification should fail.
    """
    token = create_access_token(subject="user-123", tenant_id="tenant-456")
    tampered = token[:-1] + ("A" if token[-1] != "A" else "B")
    with pytest.raises(ValueError):
        decode_token(tampered)


def test_decode_token_raises_on_wrong_secret():
    """
    Sign a token with a different secret — our app should reject it.
    """
    payload = {"sub": "user-123", "tenant_id": "t-1", "type": "access", "exp": int(time.time()) + 900}
    bad_token = jwt.encode(payload, "wrong_secret", algorithm=ALGORITHM)
    with pytest.raises(ValueError):
        decode_token(bad_token)