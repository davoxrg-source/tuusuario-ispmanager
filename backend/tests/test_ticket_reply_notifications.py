import uuid

from app.api.routes.tickets import create_ticket, reply_to_ticket
from app.models.client import Client, ClientStatus
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.schemas.ticket import TicketCreate, TicketReplyCreate


def _make_staff(db_session) -> User:
    user = User(
        full_name="Tecnico", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x",
        role=UserRole.TECHNICIAN,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def test_staff_reply_to_clients_ticket_notifies_the_client(db_session):
    staff = _make_staff(db_session)
    client = _make_client(db_session, email="cliente@compusoft-isp.com")
    ticket = create_ticket(
        TicketCreate(client_id=client.id, subject="Sin señal", description="No hay internet"),
        db_session,
        staff,
    )

    reply_to_ticket(ticket.id, TicketReplyCreate(body="Ya lo estamos revisando"), db_session, staff)

    notifications = db_session.query(Notification).filter(Notification.client_id == client.id).all()
    assert len(notifications) == 1
    assert notifications[0].event_type == "ticket_reply"


def test_reply_to_ticket_without_client_sends_no_notification(db_session):
    staff = _make_staff(db_session)
    ticket = create_ticket(
        TicketCreate(subject="Nota interna", description="Sin cliente asociado"), db_session, staff
    )

    reply_to_ticket(ticket.id, TicketReplyCreate(body="ok"), db_session, staff)

    assert db_session.query(Notification).count() == 0
