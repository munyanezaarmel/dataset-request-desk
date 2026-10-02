from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import User
from .security import decode_access_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """Authentication: who is calling? Runs on every protected endpoint."""
    unauthorized = HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    user_id = decode_access_token(credentials.credentials)
    user = db.get(User, user_id) if user_id else None
    # Loading the user from the DB on every request means a deactivated
    # user or changed role takes effect immediately, not when the token expires.
    if user is None or not user.is_active:
        raise unauthorized
    request.state.user_id = user.id  # picked up by the logging middleware
    return user


def require_roles(*roles: str):
    """Authorization: is this caller allowed? Use as Depends(require_roles(...))."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="You do not have permission")
        return user

    return checker
