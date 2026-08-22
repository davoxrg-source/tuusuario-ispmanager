from pydantic import BaseModel


class InterfaceRead(BaseModel):
    id: str
    name: str
    type: str
    running: bool
    disabled: bool
    mac_address: str | None = None
    mtu: int | None = None


class IpAddressRead(BaseModel):
    id: str
    address: str
    network: str | None = None
    interface: str
    disabled: bool = False


class IpAddressCreate(BaseModel):
    interface: str
    address: str  # formato CIDR, ej. "192.168.1.1/24"


class BridgeRead(BaseModel):
    id: str
    name: str
    disabled: bool = False


class BridgeCreate(BaseModel):
    name: str


class BridgePortRead(BaseModel):
    id: str
    interface: str
    bridge: str


class BridgePortCreate(BaseModel):
    interface: str


class PppoeServerSetupRequest(BaseModel):
    interface: str
    service_name: str
    pool_start: str
    pool_end: str
    profile_name: str
    local_address: str
