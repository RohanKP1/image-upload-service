from pydantic import BaseModel

class Token(BaseModel):
    """
    Pydantic model for the access token response.
    """
    access_token: str
    token_type: str
