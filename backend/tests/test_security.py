from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cr3t!")
    assert hashed != "s3cr3t!"
    assert verify_password("s3cr3t!", hashed)
    assert not verify_password("wrong", hashed)


def test_credentials_encryption_roundtrip():
    cipher = encrypt_secret("mikrotik-admin-password")
    assert cipher != "mikrotik-admin-password"
    assert decrypt_secret(cipher) == "mikrotik-admin-password"


def test_jwt_roundtrip():
    token = create_access_token(subject="user-123")
    assert decode_access_token(token) == "user-123"


def test_jwt_invalid_token_returns_none():
    assert decode_access_token("not-a-real-token") is None
