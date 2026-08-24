import os
from pathlib import Path

from cryptography.fernet import Fernet

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("CREDENTIALS_ENCRYPTION_KEY", Fernet.generate_key().decode())
os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://ispmanager:changeme@localhost:5432/ispmanager_test"
)

# Limpia el cache de settings por si otro test ya lo llamó sin estas env vars.
from app.core.config import get_settings  # noqa: E402

get_settings.cache_clear()

import subprocess  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _migrated_test_db():
    """Deja la BD de pruebas (ispmanager_test) al día antes de correr
    cualquier test que use db_session -- corre las migraciones reales (no
    Base.metadata.create_all) para que las pruebas vean el mismo esquema
    (enums, backfills, etc.) que producción. Se corre como subproceso, no
    con la API de Python de alembic (alembic.command.upgrade): env.py hace
    logging.config.fileConfig() al importarse, que resetea/deshabilita los
    loggers existentes -- llamarlo in-process rompía caplog en otros tests."""
    backend_dir = Path(__file__).resolve().parent.parent
    subprocess.run(
        ["alembic", "upgrade", "head"], cwd=str(backend_dir), check=True, capture_output=True
    )


@pytest.fixture
def db_session():
    """Sesión real contra la BD de pruebas, para lógica que hace consultas
    de verdad (facturación) -- no todo se puede probar con mocks sin volverse
    frágil. El código bajo prueba hace sus propios db.commit(); por eso la
    limpieza acá es un DELETE explícito al final, no solo un rollback."""
    from app.db.session import SessionLocal
    from app.models.billing_settings import BillingSettings
    from app.models.client import Client
    from app.models.inventory import InventoryItem, InventoryMovement, Supplier
    from app.models.mikrotik_device import MikrotikDevice
    from app.models.invoice import Invoice
    from app.models.payment import Payment
    from app.models.payment_account import PaymentAccount
    from app.models.plan import Plan
    from app.models.user import User
    from app.models.zone import Zone

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # InventoryMovement antes que Item/Supplier/User/Client -- referencia
        # a los 4 sin ondelete=CASCADE, así que tiene que irse primero.
        session.query(InventoryMovement).delete()
        session.query(InventoryItem).delete()
        session.query(Supplier).delete()
        session.query(Payment).delete()
        session.query(Invoice).delete()
        session.query(Client).delete()
        session.query(PaymentAccount).delete()
        session.query(Plan).delete()
        session.query(MikrotikDevice).delete()
        # User antes que Zone: borrar un User limpia sus filas de
        # user_zones solo (ondelete=CASCADE ahí), pero Client/MikrotikDevice
        # ya se borraron arriba, así que Zone queda libre para borrarse.
        session.query(User).delete()
        session.query(Zone).delete()
        # Reestablece el invariante "siempre hay exactamente una fila" que
        # espera get_billing_settings(), por si algún test la borró/creó otra.
        session.query(BillingSettings).delete()
        session.add(BillingSettings())
        session.commit()
        session.close()
