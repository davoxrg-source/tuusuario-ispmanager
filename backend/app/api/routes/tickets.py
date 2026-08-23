import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.ticket import Ticket, TicketCategory, TicketPriority, TicketReply, TicketStatus
from app.models.user import User
from app.schemas.ticket import (
    TicketCreate,
    TicketMeta,
    TicketRead,
    TicketReplyCreate,
    TicketReplyRead,
    TicketUpdate,
)

router = APIRouter(prefix="/tickets", tags=["tickets"], dependencies=[Depends(get_current_user)])


def _get_ticket_or_404(db: Session, ticket_id: uuid.UUID) -> Ticket:
    ticket = db.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket no encontrado.")
    return ticket


@router.get("/meta", response_model=TicketMeta)
def get_ticket_meta() -> TicketMeta:
    """Valores válidos de status/priority/category -- para que el frontend
    (o cualquier integración externa) no tenga que hardcodear los enums."""
    return TicketMeta(
        statuses=[s.value for s in TicketStatus],
        priorities=[p.value for p in TicketPriority],
        categories=[c.value for c in TicketCategory],
    )


@router.get("", response_model=list[TicketRead])
def list_tickets(
    status: TicketStatus | None = Query(default=None),
    priority: TicketPriority | None = Query(default=None),
    category: TicketCategory | None = Query(default=None),
    client_id: uuid.UUID | None = Query(default=None),
    assigned_to: uuid.UUID | None = Query(default=None),
    db: Session = Depends(get_db),
) -> list[Ticket]:
    query = db.query(Ticket)
    if status is not None:
        query = query.filter(Ticket.status == status)
    if priority is not None:
        query = query.filter(Ticket.priority == priority)
    if category is not None:
        query = query.filter(Ticket.category == category)
    if client_id is not None:
        query = query.filter(Ticket.client_id == client_id)
    if assigned_to is not None:
        query = query.filter(Ticket.assigned_to_user_id == assigned_to)
    return query.order_by(Ticket.created_at.desc()).all()


@router.post("", response_model=TicketRead, status_code=201)
def create_ticket(
    payload: TicketCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Ticket:
    ticket = Ticket(**payload.model_dump(), created_by_user_id=current_user.id)
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}", response_model=TicketRead)
def get_ticket(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> Ticket:
    return _get_ticket_or_404(db, ticket_id)


@router.patch("/{ticket_id}", response_model=TicketRead)
def update_ticket(ticket_id: uuid.UUID, payload: TicketUpdate, db: Session = Depends(get_db)) -> Ticket:
    ticket = _get_ticket_or_404(db, ticket_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)
    db.commit()
    db.refresh(ticket)
    return ticket


@router.get("/{ticket_id}/replies", response_model=list[TicketReplyRead])
def list_ticket_replies(ticket_id: uuid.UUID, db: Session = Depends(get_db)) -> list[TicketReply]:
    _get_ticket_or_404(db, ticket_id)
    return (
        db.query(TicketReply)
        .filter(TicketReply.ticket_id == ticket_id)
        .order_by(TicketReply.created_at)
        .all()
    )


@router.post("/{ticket_id}/reply", response_model=TicketReplyRead, status_code=201)
def reply_to_ticket(
    ticket_id: uuid.UUID,
    payload: TicketReplyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TicketReply:
    _get_ticket_or_404(db, ticket_id)
    reply = TicketReply(ticket_id=ticket_id, author_user_id=current_user.id, body=payload.body)
    db.add(reply)
    db.commit()
    db.refresh(reply)
    return reply
