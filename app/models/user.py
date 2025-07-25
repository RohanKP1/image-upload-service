from pydantic import BaseModel, EmailStr

class User(BaseModel):
    """
    Represents a user authenticated via Firebase.
    """
    id: str
    email: EmailStr
