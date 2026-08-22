from pydantic import BaseModel


class WanLinkInput(BaseModel):
    interface: str
    gateway: str
    distance: int = 1


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
