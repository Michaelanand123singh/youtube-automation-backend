from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime
from bson import ObjectId

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

class YouTubeChannelBase(BaseModel):
    channel_id: str
    title: str
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: Optional[int] = None
    view_count: Optional[int] = None
    video_count: Optional[int] = None

class YouTubeChannelCreate(YouTubeChannelBase):
    access_token: str
    refresh_token: str
    token_expires_at: datetime

class YouTubeChannelUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail_url: Optional[str] = None
    subscriber_count: Optional[int] = None
    view_count: Optional[int] = None
    video_count: Optional[int] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None

class YouTubeChannel(YouTubeChannelBase):
    id: PyObjectId = None
    user_id: PyObjectId
    access_token: str
    refresh_token: str
    token_expires_at: datetime
    is_active: bool = True
    created_at: datetime = None
    updated_at: datetime = None
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "channel_id": "UC1234567890",
                "title": "My YouTube Channel",
                "description": "Welcome to my channel!",
                "thumbnail_url": "https://example.com/channel_thumb.jpg",
                "subscriber_count": 1000,
                "view_count": 50000,
                "video_count": 100,
                "is_active": True
            }
        }
