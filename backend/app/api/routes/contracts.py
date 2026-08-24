import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.client import Client
from app.models.contract import Contract, ContractStatus, ContractTemplate
from app.models.plan import Plan
from app.models.user import User
from app.schemas.contract import (
    ContractCreate,
    ContractRead,
    ContractSignRequest,
    ContractTemplateCreate,
    ContractTemplateRead,
    ContractTemplateUpdate,
    ContractUpdate,
)
from app.services.contracts import render_contract_body

router = APIRouter(tags=["contracts"], dependencies=[Depends(get_current_user)])


def _get_template_or_404(db: Session, template_id: uuid.UUID) -> ContractTemplate:
    template = db.get(ContractTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return template


def _get_contract_or_404(db: Session, contract_id: uuid.UUID) -> Contract:
    contract = db.get(Contract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Contrato no encontrado.")
    return contract


@router.get("/contract-templates", response_model=list[ContractTemplateRead])
def list_contract_templates(db: Session = Depends(get_db)) -> list[ContractTemplate]:
    return db.query(ContractTemplate).order_by(ContractTemplate.name).all()


@router.post(
    "/contract-templates",
    response_model=ContractTemplateRead,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def create_contract_template(payload: ContractTemplateCreate, db: Session = Depends(get_db)) -> ContractTemplate:
    template = ContractTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


@router.patch(
    "/contract-templates/{template_id}",
    response_model=ContractTemplateRead,
    dependencies=[Depends(require_admin)],
)
def update_contract_template(
    template_id: uuid.UUID, payload: ContractTemplateUpdate, db: Session = Depends(get_db)
) -> ContractTemplate:
    template = _get_template_or_404(db, template_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete(
    "/contract-templates/{template_id}", status_code=204, dependencies=[Depends(require_admin)]
)
def delete_contract_template(template_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    template = _get_template_or_404(db, template_id)
    db.delete(template)
    db.commit()


@router.get("/contracts", response_model=list[ContractRead])
def list_contracts(db: Session = Depends(get_db)) -> list[Contract]:
    return db.query(Contract).order_by(Contract.created_at.desc()).all()


@router.post("/contracts", response_model=ContractRead, status_code=201)
def create_contract(
    payload: ContractCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
) -> Contract:
    client = db.get(Client, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    template = _get_template_or_404(db, payload.template_id)
    plan = db.get(Plan, client.plan_id) if client.plan_id else None

    contract = Contract(
        client_id=client.id,
        template_id=template.id,
        rendered_body=render_contract_body(template.body, client, plan),
        created_by_user_id=current_user.id,
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


@router.get("/contracts/{contract_id}", response_model=ContractRead)
def get_contract(contract_id: uuid.UUID, db: Session = Depends(get_db)) -> Contract:
    return _get_contract_or_404(db, contract_id)


@router.patch("/contracts/{contract_id}", response_model=ContractRead)
def update_contract(
    contract_id: uuid.UUID, payload: ContractUpdate, db: Session = Depends(get_db)
) -> Contract:
    contract = _get_contract_or_404(db, contract_id)
    if contract.status != ContractStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Solo se puede editar un contrato en borrador.")
    contract.rendered_body = payload.rendered_body
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/contracts/{contract_id}/sign", response_model=ContractRead)
def sign_contract(
    contract_id: uuid.UUID,
    payload: ContractSignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Contract:
    """Firma simple en pantalla, no firma digital certificada (ver
    app/models/contract.py). La IP capturada es la del dispositivo desde el
    que se llama esta ruta -- como no hay portal de autoservicio de
    clientes, en la práctica es la IP del staff que acompaña la firma, no
    necesariamente del cliente."""
    contract = _get_contract_or_404(db, contract_id)
    if contract.status != ContractStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Solo se puede firmar un contrato en borrador.")

    contract.signer_name = payload.signer_name
    contract.signer_identification = payload.signer_identification
    contract.signature_image = payload.signature_image
    contract.signed_at = datetime.now(timezone.utc)
    contract.signer_ip = request.client.host if request.client else None
    contract.witnessed_by_user_id = current_user.id
    contract.status = ContractStatus.SIGNED
    db.commit()
    db.refresh(contract)
    return contract


@router.post("/contracts/{contract_id}/void", status_code=204, dependencies=[Depends(require_admin)])
def void_contract(contract_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    contract = _get_contract_or_404(db, contract_id)
    if contract.status != ContractStatus.SIGNED:
        raise HTTPException(status_code=400, detail="Solo se puede anular un contrato firmado.")
    contract.status = ContractStatus.VOID
    db.commit()


@router.delete("/contracts/{contract_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_contract(contract_id: uuid.UUID, db: Session = Depends(get_db)) -> None:
    contract = _get_contract_or_404(db, contract_id)
    if contract.status != ContractStatus.DRAFT:
        raise HTTPException(status_code=400, detail="Solo se puede borrar un contrato en borrador.")
    db.delete(contract)
    db.commit()
