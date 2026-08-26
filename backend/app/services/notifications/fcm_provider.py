"""Envío de push nativo (FCM) para las apps móviles -- HTTP v1 API de
Firebase Cloud Messaging llamada directo vía httpx, mismo estilo que
services/wompi/client.py: sin el SDK completo de firebase-admin, que trae
grpc/protobuf/firestore/storage de más solo para mandar un push (probado y
descartado -- ver requirements.txt). La autenticación usa el flujo
JWT-bearer de OAuth2 para service accounts de Google (RFC 7523): armar y
firmar un JWT con la private key de la service account, canjearlo por un
access token en el endpoint de token de Google -- las mismas piezas que usa
`firebase-admin`/`google-auth` internamente, sin la dependencia pesada.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import httpx
from google.auth import crypt
from google.auth import jwt as google_jwt

from app.core.config import get_settings

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
TOKEN_URL = "https://oauth2.googleapis.com/token"
GRANT_TYPE = "urn:ietf:params:oauth:grant-type:jwt-bearer"

# Cachea el access token en memoria del proceso -- vive ~1h (lo que
# Google le da), evita re-autenticar contra Google en cada push individual.
_cached_token: tuple[str, float] | None = None


@dataclass
class PushResult:
    success: bool
    error: str | None
    # Un token no registrado (app desinstalada, etc.) no tiene sentido
    # reintentarlo -- el llamador lo borra, mismo criterio que una
    # suscripción Web Push expirada (ver push_provider.py).
    expired: bool = False


def _get_access_token(credentials_info: dict) -> str:
    global _cached_token
    if _cached_token and _cached_token[1] > time.time() + 60:
        return _cached_token[0]

    signer = crypt.RSASigner.from_service_account_info(credentials_info)
    now = int(time.time())
    payload = {
        "iss": credentials_info["client_email"],
        "scope": FCM_SCOPE,
        "aud": TOKEN_URL,
        "iat": now,
        "exp": now + 3600,
    }
    assertion = google_jwt.encode(signer, payload)
    response = httpx.post(
        TOKEN_URL,
        data={"grant_type": GRANT_TYPE, "assertion": assertion},
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()
    _cached_token = (data["access_token"], time.time() + data.get("expires_in", 3600))
    return _cached_token[0]


def send_fcm(token: str, title: str, body: str) -> PushResult:
    settings = get_settings()
    if not settings.firebase_project_id or not settings.firebase_credentials_json:
        return PushResult(success=False, error="Firebase no está configurado.")

    try:
        credentials_info = json.loads(settings.firebase_credentials_json)
        access_token = _get_access_token(credentials_info)
    except Exception as exc:  # noqa: BLE001
        return PushResult(success=False, error=f"No se pudo autenticar con Firebase: {exc}"[:2000])

    url = f"https://fcm.googleapis.com/v1/projects/{settings.firebase_project_id}/messages:send"
    payload = {"message": {"token": token, "notification": {"title": title, "body": body}}}
    try:
        response = httpx.post(
            url, json=payload, headers={"Authorization": f"Bearer {access_token}"}, timeout=10.0
        )
    except httpx.HTTPError as exc:
        return PushResult(success=False, error=str(exc)[:2000])

    if response.status_code == 200:
        return PushResult(success=True, error=None)

    try:
        error_status = response.json().get("error", {}).get("status")
    except ValueError:
        error_status = None
    if error_status == "UNREGISTERED" or response.status_code == 404:
        return PushResult(success=False, error="Token expirado.", expired=True)
    return PushResult(success=False, error=response.text[:2000])
