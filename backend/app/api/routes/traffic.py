import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.client import Client
from app.models.client_traffic_usage import ClientTrafficUsage
from app.schemas.traffic import TrafficUsageRead

router = APIRouter(prefix="/clients", tags=["traffic"], dependencies=[Depends(get_current_user)])


@router.get("/{client_id}/traffic-usage", response_model=list[TrafficUsageRead])
def get_client_traffic_usage(
    client_id: uuid.UUID,
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    granularity: str = Query(default="hour", pattern="^(hour|day)$"),
    db: Session = Depends(get_db),
) -> list[TrafficUsageRead]:
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    base = db.query(ClientTrafficUsage).filter(ClientTrafficUsage.client_id == client_id)
    if since:
        base = base.filter(ClientTrafficUsage.bucket_start >= since)
    if until:
        base = base.filter(ClientTrafficUsage.bucket_start <= until)

    if granularity == "hour":
        rows = base.order_by(ClientTrafficUsage.bucket_start).all()
        return [TrafficUsageRead.model_validate(row) for row in rows]

    # granularity == "day": rollup en la query, no se guarda una segunda tabla.
    bucket = func.date_trunc("day", ClientTrafficUsage.bucket_start).label("bucket_start")
    rows = (
        base.with_entities(
            bucket,
            func.sum(ClientTrafficUsage.bytes_in).label("bytes_in"),
            func.sum(ClientTrafficUsage.bytes_out).label("bytes_out"),
            func.sum(ClientTrafficUsage.packets_in).label("packets_in"),
            func.sum(ClientTrafficUsage.packets_out).label("packets_out"),
        )
        .group_by(bucket)
        .order_by(bucket)
        .all()
    )
    return [
        TrafficUsageRead(
            client_id=client_id,
            bucket_start=row.bucket_start,
            bytes_in=int(row.bytes_in or 0),
            bytes_out=int(row.bytes_out or 0),
            packets_in=int(row.packets_in or 0),
            packets_out=int(row.packets_out or 0),
        )
        for row in rows
    ]
