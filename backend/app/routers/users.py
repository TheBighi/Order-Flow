from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from app.auth.jwt_bearer import get_current_user, get_current_user_with_roles
from app.models.user import User
# For demonstration
fake_users_db = {
    "john@example.com": {
        "id": 1,
        "email": "john@example.com",
        "full_name": "John Doe",
        "roles": ["user"],
        "is_active": True
    },
    "admin@example.com": {
        "id": 2,
        "email": "admin@example.com",
        "full_name": "Admin User",
        "roles": ["user", "admin"],
        "is_active": True
    }
}
router = APIRouter(prefix="/users", tags=["users"])
@router.get("/me", response_model=User)
async def read_users_me(current_user: str = Depends(get_current_user)):
    """
    Get current user
    """
    user = fake_users_db.get(current_user)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user
@router.get("/", response_model=List[User])
async def read_users(
    current_user: str = Depends(get_current_user_with_roles(required_roles=["admin"]))
):
    """
    Get all users - only for admins
    """
    # Convert dict to list for response
    users = list(fake_users_db.values())
    return users