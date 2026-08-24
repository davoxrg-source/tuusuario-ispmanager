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
    from app.models.api_key import ApiKey
    from app.models.billing_settings import BillingSettings
    from app.models.client import Client
    from app.models.contract import Contract, ContractTemplate
    from app.models.hotspot import HotspotProfile, HotspotVoucher
    from app.models.installation import Installation
    from app.models.inventory import InventoryItem, InventoryMovement, Supplier
    from app.models.mikrotik_device import MikrotikDevice
    from app.models.invoice import Invoice
    from app.models.notification import Notification
    from app.models.payment import Payment
    from app.models.payment_account import PaymentAccount
    from app.models.payment_report import PaymentReport
    from app.models.plan import Plan
    from app.models.push_subscription import PushSubscription
    from app.models.ticket import Ticket, TicketReply
    from app.models.user import User
    from app.models.wompi_transaction import WompiTransaction
    from app.models.zone import Zone

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        # ApiKey antes que User -- created_by_user_id es FK a users sin
        # ondelete=CASCADE.
        session.query(ApiKey).delete()
        # Contract antes que User -- created_by_user_id/witnessed_by_user_id
        # son FK a users sin ondelete=CASCADE.
        session.query(Contract).delete()
        session.query(ContractTemplate).delete()
        # HotspotVoucher antes que HotspotProfile/User -- profile_id y
        # sold_by_user_id son FK sin ondelete=CASCADE.
        session.query(HotspotVoucher).delete()
        session.query(HotspotProfile).delete()
        # InventoryMovement antes que Item/Supplier/User/Client -- referencia
        # a los 4 sin ondelete=CASCADE, así que tiene que irse primero.
        session.query(InventoryMovement).delete()
        session.query(InventoryItem).delete()
        session.query(Supplier).delete()
        # Installation antes que Client -- el DELETE en bloque de acá abajo
        # es un DELETE crudo, no pasa por el cascade del ORM (Client.installations).
        session.query(Installation).delete()
        # TicketReply antes que Ticket (FK ticket_id) -- ambos referencian
        # User/Client sin ondelete, así que también tienen que irse antes.
        session.query(TicketReply).delete()
        session.query(Ticket).delete()
        # PaymentReport antes que Invoice/Client -- referencia a ambos sin
        # ondelete (la cascada real es Invoice.payment_reports, que no
        # aplica acá por ser un DELETE en bloque, no vía ORM).
        session.query(PaymentReport).delete()
        # Notification/PushSubscription antes que Client -- mismo motivo,
        # sin ondelete propio (la cascada de PushSubscription también es
        # solo a nivel ORM, no aplica en un DELETE en bloque).
        session.query(Notification).delete()
        session.query(PushSubscription).delete()
        session.query(WompiTransaction).delete()
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
