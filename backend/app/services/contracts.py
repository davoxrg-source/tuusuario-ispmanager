from datetime import date

from app.models.client import Client
from app.models.plan import Plan


class _BlankOnMissing(dict):
    """dict que devuelve "" para una clave que no existe, en vez de lanzar
    KeyError -- así un placeholder sin dato (ej. {identification} en un
    cliente sin documento cargado) queda en blanco en el texto en vez de
    romper la creación del contrato."""

    def __missing__(self, key: str) -> str:
        return ""


def render_contract_body(template_body: str, client: Client, plan: Plan | None) -> str:
    """Reemplaza placeholders con los datos del cliente/plan. El resultado
    se guarda congelado en Contract.rendered_body -- no se vuelve a
    renderizar si la plantilla o el cliente cambian después."""
    values = _BlankOnMissing(
        full_name=client.full_name or "",
        identification=client.identification or "",
        address=client.address or "",
        phone=client.phone or "",
        email=client.email or "",
        plan_name=plan.name if plan else "",
        plan_price=f"{plan.price} {plan.currency}" if plan else "",
        today=date.today().isoformat(),
    )
    return template_body.format_map(values)
