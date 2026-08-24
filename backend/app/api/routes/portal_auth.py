from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_client
from app.core.security import create_access_token, hash_password, verify_password
from app.db.session import get_db
from app.models.client import Client
from app.schemas.portal import ChangePasswordRequest, ClientPortalRead
from app.schemas.user import Token

router = APIRouter(prefix="/portal/auth", tags=["portal"])


@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> Token:
    # "username" es el nombre fijo del campo de OAuth2PasswordRequestForm --
    # acá se usa para mandar la identificación (cédula/NIT), no un email.
    client = db.query(Client).filter(Client.identification == form_data.username).first()
    if (
        client is None
        or client.hashed_password is None
        or not verify_password(form_data.password, client.hashed_password)
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas.")
    # Sin chequeo de ClientStatus a propósito -- ver docstring de
    # get_current_client: un cliente suspendido tiene que poder entrar.
    token = create_access_token(subject=str(client.id))
    return Token(access_token=token)


@router.get("/me", response_model=ClientPortalRead)
def me(current_client: Client = Depends(get_current_client)) -> Client:
    return current_client


@router.post("/change-password", status_code=204)
def change_password(
    payload: ChangePasswordRequest,
    current_client: Client = Depends(get_current_client),
    db: Session = Depends(get_db),
) -> None:
    if not verify_password(payload.current_password, current_client.hashed_password):
        raise HTTPException(status_code=400, detail="La contraseña actual no es correcta.")
    current_client.hashed_password = hash_password(payload.new_password)
    db.commit()
