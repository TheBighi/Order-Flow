from passlib.context import CryptContext
from typing import Optional
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify plain password against hashed password
    """
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    """
    Generate password hash from plain password
    """
    return pwd_context.hash(password)