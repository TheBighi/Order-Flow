from pydantic import BaseModel

class UserCreate(BaseModel):
    username: str
    email: str
    hashed_password: str
    
#class UserResponse(BaseModel):
#    id: int
#    username: str
#    email: str

#    model_config = {"from_attributes": True}  # lets pydantic read SQLAlchemy objects