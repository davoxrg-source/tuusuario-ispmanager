from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.wompi.service import handle_webhook

# Sin ninguna dependencia de auth -- es la única ruta de esta app que no
# requiere sesión. Se protege exclusivamente verificando la firma del
# payload contra el events secret (ver services/wompi/signing.py) antes de
# tocar cualquier dato.
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/wompi", status_code=200)
def wompi_webhook(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict:
    try:
        handle_webhook(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}
