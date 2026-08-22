from pydantic import BaseModel

from app.schemas.wan_balancing import WanCommandResult


class QosPlanBootstrapRequest(BaseModel):
    """Arma la infraestructura QoS de UN plan (address-list + PCQ + mangle +
    queue tree) — se aplica una sola vez por plan por equipo, no por
    cliente. Ver services/mikrotik/qos.py."""

    lan_interface: str
    wan_interface: str
    priority_tcp_ports: list[int] = []
    priority_udp_ports: list[int] = []
    realtime_tcp_max_size: int = 128
    realtime_udp_max_size: int = 200


class QosPlanBootstrapResponse(BaseModel):
    commands: list[WanCommandResult]
    applied: bool
