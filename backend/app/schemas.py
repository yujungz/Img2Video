from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, List
from datetime import datetime
from app.models import TaskStatus, TaskType
import json


# User Schemas
class UserBase(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class EmailVerifyRequest(BaseModel):
    email: EmailStr
    code: Optional[str] = None


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    daily_image_quota: Optional[int] = None
    daily_video_quota: Optional[int] = None


class UserResponse(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    daily_image_quota: int
    daily_video_quota: int
    used_image_quota: int
    used_video_quota: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Reference Image Schemas
class ReferenceImageCreate(BaseModel):
    original_filename: str
    file_size: int
    mime_type: str


class ReferenceImageResponse(BaseModel):
    id: int
    filename: str
    original_filename: str
    file_size: int
    created_at: datetime
    url: Optional[str] = None

    class Config:
        from_attributes = True


# Task Schemas
class ImageGenerationRequest(BaseModel):
    prompt: str = Field(..., max_length=2000)
    negative_prompt: Optional[str] = Field(None, max_length=500)
    reference_image_ids: List[int] = []
    width: int = Field(1024, ge=256, le=2048)
    height: int = Field(1024, ge=256, le=2048)


class VideoGenerationRequest(BaseModel):
    image_id: int  # Source image (generated or uploaded)
    prompt: str = Field(..., max_length=1000)
    duration: float = Field(4.0, ge=1.0, le=10.0)
    region: Optional[dict] = None  # {x, y, width, height} for region control


class TaskCreate(BaseModel):
    task_type: TaskType
    input_data: dict


class TaskResponse(BaseModel):
    id: int
    user_id: int
    username: Optional[str] = None  # 用户名
    task_type: TaskType
    status: TaskStatus
    input_data: dict
    result_data: Optional[dict]
    error_message: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    @field_validator('input_data', 'result_data', mode='before')
    @classmethod
    def parse_json(cls, v):
        if isinstance(v, str):
            try:
                return json.loads(v)
            except:
                return {}
        return v

    class Config:
        from_attributes = True


# Generated Work Schemas
class GeneratedWorkResponse(BaseModel):
    id: int
    work_type: str
    filename: str
    prompt: Optional[str]
    created_at: datetime
    file_size: int
    url: Optional[str] = None  # Preview URL

    class Config:
        from_attributes = True


# Admin Schemas
class SystemConfigUpdate(BaseModel):
    key: str
    value: str


class SystemConfigResponse(BaseModel):
    id: int
    key: str
    value: str
    description: Optional[str]
    updated_at: datetime

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    total_users: int
    active_users: int
    total_tasks: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    total_images: int
    total_videos: int


# Common
class MessageResponse(BaseModel):
    message: str
    success: bool = True


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=6, max_length=100)
    new_password: str = Field(..., min_length=6, max_length=100)
