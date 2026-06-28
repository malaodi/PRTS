from pydantic import BaseModel
from app.models.space import SpaceType


class SpaceCreate(BaseModel):
    name: str
    type: SpaceType = SpaceType.TEAM
    team_context: str | None = None


class SpaceUpdate(BaseModel):
    name: str | None = None
    team_context: str | None = None


class SpaceOut(BaseModel):
    id: str
    name: str
    type: str
    owner_id: str
    team_context: str | None
    member_count: int

    model_config = {"from_attributes": True}


class MemberOut(BaseModel):
    id: str
    user_id: str
    username: str | None
    email: str | None
    display_name: str | None
    role: str
    joined_at: str | None

    model_config = {"from_attributes": True}


class MemberRoleUpdate(BaseModel):
    role: str


class MemberInvite(BaseModel):
    email: str
    role: str = "member"
