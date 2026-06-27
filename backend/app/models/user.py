from pydantic import BaseModel

from app.auth.roles import UserRole


class AuthenticatedUser(BaseModel):
    username: str
    role: UserRole
