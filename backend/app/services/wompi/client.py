import httpx

from app.core.config import get_settings


def get_transaction(wompi_transaction_id: str) -> dict | None:
    """Consulta el estado de una transacción directo contra la API de
    Wompi (Bearer con la private key) -- el flujo normal no la necesita,
    el webhook ya trae todo, pero sirve para resincronizar a mano si hiciera
    falta. Devuelve None si Wompi no está configurado o la consulta falla."""
    settings = get_settings()
    if not settings.wompi_private_key:
        return None
    try:
        response = httpx.get(
            f"{settings.wompi_api_base_url}/transactions/{wompi_transaction_id}",
            headers={"Authorization": f"Bearer {settings.wompi_private_key}"},
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("data")
    except httpx.HTTPError:
        return None
