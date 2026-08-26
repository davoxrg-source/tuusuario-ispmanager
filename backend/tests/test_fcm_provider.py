import json
import time
from unittest.mock import MagicMock, patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import get_settings
from app.services.notifications import fcm_provider
from app.services.notifications.fcm_provider import PushResult, _get_access_token, send_fcm


def _generate_test_credentials_info() -> dict:
    """Par de llaves RSA descartable, generado en el momento -- nunca sale
    de este proceso ni se usa contra Google de verdad (la llamada de red
    está mockeada), solo sirve para probar que _get_access_token arma y
    firma el JWT correctamente."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    return {
        "client_email": "svc@test-project.iam.gserviceaccount.com",
        "private_key": pem,
        "token_uri": "https://oauth2.googleapis.com/token",
    }


def test_send_fcm_without_firebase_configured_fails_with_gracia(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "firebase_project_id", "")
    monkeypatch.setattr(settings, "firebase_credentials_json", "")

    result = send_fcm("token-123", "Título", "Cuerpo")

    assert result.success is False
    assert "Firebase" in result.error


def test_get_access_token_signs_jwt_and_calls_token_endpoint(monkeypatch):
    fcm_provider._cached_token = None
    credentials_info = _generate_test_credentials_info()

    fake_response = MagicMock(status_code=200)
    fake_response.json.return_value = {"access_token": "real-token-abc", "expires_in": 3600}
    fake_response.raise_for_status = MagicMock()

    with patch("app.services.notifications.fcm_provider.httpx.post", return_value=fake_response) as mock_post:
        token = _get_access_token(credentials_info)

    assert token == "real-token-abc"
    assert mock_post.call_args.args[0] == fcm_provider.TOKEN_URL
    body = mock_post.call_args.kwargs["data"]
    assert body["grant_type"] == fcm_provider.GRANT_TYPE
    assert isinstance(body["assertion"], (str, bytes)) and len(body["assertion"]) > 20


def test_get_access_token_uses_cache_within_expiry(monkeypatch):
    fcm_provider._cached_token = ("cached-token", time.time() + 3000)

    with patch("app.services.notifications.fcm_provider.httpx.post") as mock_post:
        token = _get_access_token(_generate_test_credentials_info())

    assert token == "cached-token"
    mock_post.assert_not_called()
    fcm_provider._cached_token = None


def test_send_fcm_success(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "firebase_project_id", "test-project")
    monkeypatch.setattr(settings, "firebase_credentials_json", json.dumps(_generate_test_credentials_info()))

    fake_response_ok = MagicMock(status_code=200)
    with (
        patch.object(fcm_provider, "_get_access_token", return_value="fake-access-token"),
        patch("app.services.notifications.fcm_provider.httpx.post", return_value=fake_response_ok) as mock_post,
    ):
        result = send_fcm("token-123", "Título", "Cuerpo")

    assert result == PushResult(success=True, error=None)
    called_url = mock_post.call_args.args[0]
    assert called_url == "https://fcm.googleapis.com/v1/projects/test-project/messages:send"
    assert mock_post.call_args.kwargs["headers"]["Authorization"] == "Bearer fake-access-token"


def test_send_fcm_unregistered_token_marks_expired(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "firebase_project_id", "test-project")
    monkeypatch.setattr(settings, "firebase_credentials_json", "{}")

    fake_response = MagicMock(status_code=404)
    fake_response.json.return_value = {"error": {"status": "UNREGISTERED"}}
    with (
        patch.object(fcm_provider, "_get_access_token", return_value="fake-access-token"),
        patch("app.services.notifications.fcm_provider.httpx.post", return_value=fake_response),
    ):
        result = send_fcm("token-123", "Título", "Cuerpo")

    assert result.success is False
    assert result.expired is True


def test_send_fcm_auth_failure_does_not_crash(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "firebase_project_id", "test-project")
    monkeypatch.setattr(settings, "firebase_credentials_json", "not-valid-json")

    result = send_fcm("token-123", "Título", "Cuerpo")

    assert result.success is False
    assert "Firebase" in result.error
