from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.roles import ROLE_COLLECTIONS, UserRole
from app.auth.security import get_current_user
from app.models.collection import CollectionsResponse
from app.models.user import AuthenticatedUser

router = APIRouter()


@router.get("/collections/{role}", response_model=CollectionsResponse)
def get_collections_for_role(role: UserRole, user: AuthenticatedUser = Depends(get_current_user)) -> CollectionsResponse:
    if user.role != role and user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access collections for your own role",
        )

    return CollectionsResponse(role=role, collections=ROLE_COLLECTIONS[role])
