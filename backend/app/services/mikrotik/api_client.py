"""Wrapper delgado sobre librouteros (API binaria RouterOS, puertos 8728/8729)."""

from __future__ import annotations

import ssl
from contextlib import contextmanager
from typing import Any, Iterator

from librouteros import connect
from librouteros.exceptions import TrapError, FatalError, ConnectionClosed


class RouterOsApiError(Exception):
    pass


@contextmanager
def api_connection(
    host: str,
    username: str,
    password: str,
    port: int = 8728,
    use_tls: bool = False,
    timeout: float = 8.0,
) -> Iterator[Any]:
    """Abre una conexión API RouterOS y la cierra al salir del bloque `with`."""
    kwargs: dict[str, Any] = {
        "host": host,
        "username": username,
        "password": password,
        "port": port,
        "timeout": timeout,
    }
    if use_tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        kwargs["ssl_wrapper"] = ctx.wrap_socket

    try:
        api = connect(**kwargs)
    except (TrapError, FatalError, ConnectionClosed, OSError) as exc:
        raise RouterOsApiError(str(exc)) from exc

    try:
        yield api
    except (TrapError, FatalError, ConnectionClosed) as exc:
        raise RouterOsApiError(str(exc)) from exc
    finally:
        try:
            api.close()
        except Exception:
            pass


def get_identity(api: Any) -> str:
    rows = list(api("/system/identity/print"))
    return rows[0]["name"] if rows else ""


def get_system_resource(api: Any) -> dict[str, Any]:
    rows = list(api("/system/resource/print"))
    return rows[0] if rows else {}


def get_interfaces(api: Any) -> list[dict[str, Any]]:
    return list(api("/interface/print"))


def get_active_ppp_sessions(api: Any) -> list[dict[str, Any]]:
    return list(api("/ppp/active/print"))


def list_ppp_secrets(api: Any) -> list[dict[str, Any]]:
    return list(api("/ppp/secret/print"))


def find_ppp_secret_id(api: Any, pppoe_username: str) -> str | None:
    for row in list_ppp_secrets(api):
        if row.get("name") == pppoe_username:
            return row.get(".id")
    return None


def create_ppp_secret(
    api: Any,
    name: str,
    password: str,
    profile: str | None = None,
    service: str = "pppoe",
) -> None:
    kwargs: dict[str, Any] = {"name": name, "password": password, "service": service}
    if profile:
        kwargs["profile"] = profile
    list(api("/ppp/secret/add", **kwargs))


def set_ppp_secret_enabled(api: Any, pppoe_username: str, enabled: bool) -> bool:
    secret_id = find_ppp_secret_id(api, pppoe_username)
    if secret_id is None:
        return False
    list(api("/ppp/secret/set", **{".id": secret_id, "disabled": "no" if enabled else "yes"}))
    return True


def remove_ppp_secret(api: Any, pppoe_username: str) -> bool:
    secret_id = find_ppp_secret_id(api, pppoe_username)
    if secret_id is None:
        return False
    list(api("/ppp/secret/remove", **{".id": secret_id}))
    return True


def reboot(api: Any) -> None:
    list(api("/system/reboot"))
