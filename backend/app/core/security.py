from datetime import datetime, timedelta, timezone
from functools import lru_cache

import bcrypt
from cryptography.fernet import Fernet
from jose import JWTError, jwt

from app.core.config import get_settings

# bcrypt solo usa los primeros 72 bytes del secreto; se trunca explícitamente
# para evitar que contraseñas largas lancen ValueError en vez de truncarse.
_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    truncated = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(truncated, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    truncated = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.checkpw(truncated, hashed_password.encode("utf-8"))


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError:
        return None
    return payload.get("sub")


@lru_cache
def _fernet() -> Fernet:
    settings = get_settings()
    if not settings.credentials_encryption_key:
        raise RuntimeError(
            "CREDENTIALS_ENCRYPTION_KEY no está configurada. Genera una con "
            "'python3 -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\"' y agrégala al .env."
        )
    return Fernet(settings.credentials_encryption_key.encode())


def encrypt_secret(plain_text: str) -> str:
    return _fernet().encrypt(plain_text.encode()).decode()


def decrypt_secret(cipher_text: str) -> str:
    return _fernet().decrypt(cipher_text.encode()).decode()
