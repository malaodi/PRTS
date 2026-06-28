from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str
    display_name: str | None = None


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    username: str
    display_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class UserSpace(BaseModel):
    space_id: str
    space_name: str
    role: str

    model_config = {"from_attributes": True}
