from typing import Literal

from pydantic import BaseModel, model_validator

WanConnectionType = Literal["static", "dhcp", "pppoe"]


class WanLinkInput(BaseModel):
    interface: str
    connection_type: WanConnectionType = "static"
    distance: int = 1

    # Solo para connection_type == "static"
    gateway: str | None = None
    address: str | None = None  # IP/CIDR, ej. "10.10.1.2/30"

    # Solo para connection_type == "pppoe"
    pppoe_username: str | None = None
    pppoe_password: str | None = None
    pppoe_service_name: str | None = None

    @model_validator(mode="after")
    def _validate_fields_for_type(self) -> "WanLinkInput":
        if self.connection_type == "static" and not self.gateway:
            raise ValueError(f"La WAN '{self.interface}' es de tipo IP fija y necesita un gateway.")
        if self.connection_type == "pppoe" and not (self.pppoe_username and self.pppoe_password):
            raise ValueError(
                f"La WAN '{self.interface}' es de tipo PPPoE y necesita usuario y contraseña."
            )
        return self

    @property
    def pppoe_client_name(self) -> str:
        return f"pppoe-{self.interface}"


class PublicBlockPin(BaseModel):
    cidr: str
    wan_interface: str


class WanBalancingRequest(BaseModel):
    lan_interface: str
    wans: list[WanLinkInput]
    public_blocks: list[PublicBlockPin] = []


class WanCommandResult(BaseModel):
    description: str
    path: str
    params: dict[str, str]
    executed: bool = False
    error: str | None = None


class WanBalancingResponse(BaseModel):
    commands: list[WanCommandResult]
    applied: bool
