from pydantic import BaseModel

from app.auth.roles import UserRole


class CollectionsResponse(BaseModel):
    role: UserRole
    collections: list[str]
