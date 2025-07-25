from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

class ImageBase(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    original_url: Optional[HttpUrl] = None
    thumbnail_url: Optional[HttpUrl] = None

class ImageResponse(ImageBase):
    """
    Response model for listing images and getting image details.
    """
    pass

class ImageUploadResponse(BaseModel):
    """
    Response model after a successful image upload.
    """
    id: str
    filename: str
    original_url: HttpUrl
    thumbnail_url: HttpUrl
