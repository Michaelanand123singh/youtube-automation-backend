from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from enum import Enum

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid objectid")
        return ObjectId(v)

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(type="string")

class VideoStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    PUBLISHED = "published"
    FAILED = "failed"
    DELETED = "deleted"

class VideoPrivacy(str, Enum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"

class VideoBase(BaseModel):
    title: str
    description: Optional[str] = ""
    tags: List[str] = []
    privacy: VideoPrivacy = VideoPrivacy.PRIVATE
    thumbnail_url: Optional[str] = None

class VideoCreate(VideoBase):
    file_path: str
    file_size: int
    duration: Optional[int] = None
    mime_type: str

class VideoUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    privacy: Optional[VideoPrivacy] = None
    thumbnail_url: Optional[str] = None

class VideoSchedule(BaseModel):
    upload_scheduled_at: Optional[datetime] = None
    delete_scheduled_at: Optional[datetime] = None
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    upload_job_id: Optional[str] = None
    delete_job_id: Optional[str] = None

class Video(VideoBase):
    id: PyObjectId = None
    user_id: PyObjectId
    file_path: str
    file_size: int
    duration: Optional[int] = None
    mime_type: str
    status: VideoStatus = VideoStatus.UPLOADING
    google_drive_file_id: Optional[str] = None
    schedule: VideoSchedule = VideoSchedule()
    created_at: datetime = None
    updated_at: datetime = None
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "title": "My Awesome Video",
                "description": "This is a great video",
                "tags": ["tutorial", "programming"],
                "privacy": "private",
                "file_size": 10485760,
                "duration": 300,
                "mime_type": "video/mp4",
                "status": "uploaded"
            }
        }
