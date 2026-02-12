from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
from datetime import datetime

class ImageJobType(str, Enum):
    TXT2IMG = "txt2img"
    IMG2IMG = "img2img"
    INPAINT = "inpaint"
    DESCRIBE = "describe"
    UPSCALE = "upscale"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="Positive prompt")
    negative_prompt: Optional[str] = Field(None, description="Negative prompt")
    width: Optional[int] = Field(512, ge=64, le=2048)
    height: Optional[int] = Field(512, ge=64, le=2048)
    steps: Optional[int] = Field(20, ge=1, le=100)
    cfg_scale: Optional[float] = Field(7.0, ge=1.0, le=30.0)
    seed: Optional[int] = Field(None, description="Random seed")
    model_id: Optional[str] = Field("default", description="Model checkpoint to use")
    preset: Optional[str] = Field("default", description="Configuration preset (quality, fast)")
    batch_size: Optional[int] = Field(1, ge=1, le=4)

class ImageFileResponse(BaseModel):
    file_id: str
    job_id: str
    role: str
    url: str
    mime_type: str
    size_bytes: int

class JobResponse(BaseModel):
    job_id: str
    type: ImageJobType
    status: JobStatus
    provider: str
    created_at: float
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    files: List[ImageFileResponse] = []
    
class JobCreatedResponse(BaseModel):
    job_id: str
    status: JobStatus
    eta_seconds: Optional[float] = None
