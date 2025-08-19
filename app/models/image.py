from pydantic import BaseModel, HttpUrl
from typing import Optional, List
from datetime import datetime
from enum import Enum

class ImageBase(BaseModel):
    id: str
    filename: str
    uploaded_at: datetime
    embedding: Optional[List[float]] = None
    description: Optional[str] = None
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
    embedding: List[float]
    description: Optional[str] = None


class ClusteringAlgorithm(str, Enum):
    KMEANS = "kmeans"
    HIERARCHICAL = "hierarchical"


class ClusterRequest(BaseModel):
    algorithm: ClusteringAlgorithm = ClusteringAlgorithm.KMEANS
    n_clusters: Optional[int] = None
    generate_names: bool = False


class ImageCluster(BaseModel):
    cluster_id: int
    name: Optional[str] = None
    images: List[ImageResponse]


class ClusterResponse(BaseModel):
    clusters: List[ImageCluster]
    unclustered: List[ImageResponse] = []
