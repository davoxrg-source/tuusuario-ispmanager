from app.api.routes.tickets import get_ticket_meta
from app.models.ticket import TicketCategory, TicketPriority, TicketStatus
from app.schemas.ticket import TicketCreate


def test_ticket_create_defaults_to_medium_priority_and_other_category():
    ticket = TicketCreate(subject="No hay señal", description="El cliente reporta que no navega.")
    assert ticket.priority == TicketPriority.MEDIUM
    assert ticket.category == TicketCategory.OTHER
    assert ticket.client_id is None


def test_ticket_meta_lists_every_enum_value():
    meta = get_ticket_meta()
    assert set(meta.statuses) == {s.value for s in TicketStatus}
    assert set(meta.priorities) == {p.value for p in TicketPriority}
    assert set(meta.categories) == {c.value for c in TicketCategory}
