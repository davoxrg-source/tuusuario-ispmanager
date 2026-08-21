import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.plan import Plan
from app.schemas.plan import PlanCreate, PlanRead, PlanUpdate

router = APIRouter(prefix="/plans", tags=["plans"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[PlanRead])
def list_plans(db: Session = Depends(get_db)) -> list[Plan]:
    return db.query(Plan).order_by(Plan.name).all()


@router.post("", response_model=PlanRead, status_code=201)
def create_plan(payload: PlanCreate, db: Session = Depends(get_db)) -> Plan:
    plan = Plan(**payload.model_dump())
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.get("/{plan_id}", response_model=PlanRead)
def get_plan(plan_id: uuid.UUID, db: Session = Depends(get_db)) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    return plan


@router.patch("/{plan_id}", response_model=PlanRead)
def update_plan(plan_id: uuid.UUID, payload: PlanUpdate, db: Session = Depends(get_db)) -> Plan:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=204)
def delete_plan(plan_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    plan = db.get(Plan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    db.delete(plan)
    db.commit()
