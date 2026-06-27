from pydantic import BaseModel, Field

from app.auth.roles import UserRole


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=120)


class LoginResponse(BaseModel):
    token: str
    role: UserRole
