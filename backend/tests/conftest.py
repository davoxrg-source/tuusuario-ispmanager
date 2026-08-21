import os

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ispmanager:changeme@localhost:5432/ispmanager_test"
)

# Limpia el cache de settings por si otro test ya lo llamó sin estas env vars.
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()
