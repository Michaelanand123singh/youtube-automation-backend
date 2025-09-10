from pydantic import BaseModel, EmailStr
from typing import Optional, List
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

class UserBase(BaseModel):
    email: EmailStr
    name: str
    google_id: str
    picture: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    name: Optional[str] = None
    picture: Optional[str] = None

class User(UserBase):
    id: PyObjectId = None
    created_at: datetime = None
    updated_at: datetime = None
    is_active: bool = True
    youtube_channels: List[PyObjectId] = []
    
    class Config:
        allow_population_by_field_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}
        schema_extra = {
            "example": {
                "email": "user@example.com",
                "name": "John Doe",
                "google_id": "123456789",
                "picture": "https://example.com/photo.jpg",
                "is_active": True
            }
        }
