from fastapi import APIRouter, HTTPException, status

from app.auth.demo_users import DEMO_USERS
from app.auth.security import create_access_token
from app.schemas.auth import LoginRequest, LoginResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest) -> LoginResponse:
    role = DEMO_USERS.get(payload.username)
    if role is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username")

    token = create_access_token(username=payload.username, role=role)
    return LoginResponse(token=token, role=role)
