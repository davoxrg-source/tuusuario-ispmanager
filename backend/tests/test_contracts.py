import uuid

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes.contracts import (
    create_contract,
    create_contract_template,
    sign_contract,
    update_contract,
    update_contract_template,
    void_contract,
)
from app.models.client import Client, ClientStatus
from app.models.contract import ContractStatus
from app.models.plan import Plan
from app.models.user import User, UserRole
from app.schemas.contract import ContractCreate, ContractSignRequest, ContractTemplateCreate, ContractTemplateUpdate, ContractUpdate
from app.services.contracts import render_contract_body


def _make_admin(db_session) -> User:
    admin = User(
        full_name="Admin", email=f"{uuid.uuid4()}@compusoft-isp.com", hashed_password="x",
        role=UserRole.ADMIN,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


def _make_client(db_session, **overrides) -> Client:
    client = Client(full_name="Cliente Test", status=ClientStatus.ACTIVE, ip_address=None)
    for field, value in overrides.items():
        setattr(client, field, value)
    db_session.add(client)
    db_session.commit()
    db_session.refresh(client)
    return client


def _fake_request() -> Request:
    scope = {
        "type": "http",
        "client": ("10.0.0.5", 12345),
        "headers": [],
    }
    return Request(scope)


def test_render_contract_body_fills_known_placeholders():
    client = Client(full_name="Juan Perez", identification="123456", address="Calle 1")
    body = render_contract_body("Cliente: {full_name}, doc: {identification}, plan: {plan_name}", client, None)
    assert body == "Cliente: Juan Perez, doc: 123456, plan: "


def test_render_contract_body_blank_on_missing_field_does_not_raise():
    client = Client(full_name="Juan Perez")  # sin identification/address
    body = render_contract_body("Doc: {identification}, dir: {address}, otro: {unknown_field}", client, None)
    assert body == "Doc: , dir: , otro: "


def test_create_contract_freezes_text_from_template(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session, full_name="Cliente Congelado")
    template = create_contract_template(
        ContractTemplateCreate(name="Plantilla Base", body="Contrato de {full_name}"), db_session
    )

    contract = create_contract(ContractCreate(client_id=client.id, template_id=template.id), db_session, admin)

    assert contract.rendered_body == "Contrato de Cliente Congelado"
    assert contract.status == ContractStatus.DRAFT

    # cambiar la plantilla después no debe afectar el contrato ya creado
    update_contract_template(template.id, ContractTemplateUpdate(body="Otro texto {full_name}"), db_session)
    db_session.refresh(contract)
    assert contract.rendered_body == "Contrato de Cliente Congelado"


def test_sign_contract_transitions_to_signed(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    template = create_contract_template(
        ContractTemplateCreate(name="Plantilla", body="Texto {full_name}"), db_session
    )
    contract = create_contract(ContractCreate(client_id=client.id, template_id=template.id), db_session, admin)

    signed = sign_contract(
        contract.id,
        ContractSignRequest(signer_name="Juan Perez", signer_identification="123", signature_image="data:image/png;base64,AAAA"),
        _fake_request(),
        db_session,
        admin,
    )

    assert signed.status == ContractStatus.SIGNED
    assert signed.signer_name == "Juan Perez"
    assert signed.signature_image == "data:image/png;base64,AAAA"
    assert signed.signer_ip == "10.0.0.5"
    assert signed.witnessed_by_user_id == admin.id
    assert signed.signed_at is not None


def test_sign_already_signed_contract_rejected(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    template = create_contract_template(ContractTemplateCreate(name="P", body="T"), db_session)
    contract = create_contract(ContractCreate(client_id=client.id, template_id=template.id), db_session, admin)
    sign_contract(
        contract.id,
        ContractSignRequest(signer_name="X", signature_image="data:image/png;base64,AAAA"),
        _fake_request(), db_session, admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        sign_contract(
            contract.id,
            ContractSignRequest(signer_name="Y", signature_image="data:image/png;base64,BBBB"),
            _fake_request(), db_session, admin,
        )
    assert exc_info.value.status_code == 400


def test_update_signed_contract_rejected(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    template = create_contract_template(ContractTemplateCreate(name="P2", body="T"), db_session)
    contract = create_contract(ContractCreate(client_id=client.id, template_id=template.id), db_session, admin)
    sign_contract(
        contract.id,
        ContractSignRequest(signer_name="X", signature_image="data:image/png;base64,AAAA"),
        _fake_request(), db_session, admin,
    )

    with pytest.raises(HTTPException) as exc_info:
        update_contract(contract.id, ContractUpdate(rendered_body="otro texto"), db_session)
    assert exc_info.value.status_code == 400


def test_void_requires_signed_status(db_session):
    admin = _make_admin(db_session)
    client = _make_client(db_session)
    template = create_contract_template(ContractTemplateCreate(name="P3", body="T"), db_session)
    contract = create_contract(ContractCreate(client_id=client.id, template_id=template.id), db_session, admin)

    with pytest.raises(HTTPException) as exc_info:
        void_contract(contract.id, db_session)
    assert exc_info.value.status_code == 400

    sign_contract(
        contract.id,
        ContractSignRequest(signer_name="X", signature_image="data:image/png;base64,AAAA"),
        _fake_request(), db_session, admin,
    )
    void_contract(contract.id, db_session)
    db_session.refresh(contract)
    assert contract.status == ContractStatus.VOID
