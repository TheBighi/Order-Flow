from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from typing import Optional, List
from app.models.token import TokenPayload
from app.core.config import settings
from app.auth.jwt_handler import decode_token

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Validates token and returns the username
    """
    try:
        payload = decode_token(token)
        token_data = TokenPayload(**payload)
        # Check token expiration
        if datetime.fromtimestamp(token_data.exp) < datetime.now():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return token_data.sub
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
def get_current_user_with_roles(
    required_roles: Optional[List[str]] = None
) -> callable:
    """
    Creates a dependency that checks if the current user has the required roles
    """
    if required_roles is None:
        required_roles = []
    def _inner(token: str = Depends(oauth2_scheme)) -> str:
        try:
            payload = decode_token(token)
            token_data = TokenPayload(**payload)
            # Check token expiration
            if datetime.fromtimestamp(token_data.exp) < datetime.now():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            # If no specific roles required, just authentication is enough
            if not required_roles:
                return token_data.sub
            # Check if user has at least one of the required roles
            user_roles = set(token_data.roles)
            if not any(role in user_roles for role in required_roles) and "admin" not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return token_data.sub
        except (JWTError, ValidationError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return _inner