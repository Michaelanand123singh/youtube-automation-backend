from pydantic_settings import BaseSettings
from typing import List, Optional
import os

class Settings(BaseSettings):
    # Database
    MONGODB_URL: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = "youtube_scheduler"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = "http://localhost:3000/auth/callback"
    
    # Google APIs
    GOOGLE_DRIVE_API_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # CORS - Parse comma-separated values
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"
    
    # File upload
    MAX_FILE_SIZE: int = 100 * 1024 * 1024  # 100MB
    ALLOWED_VIDEO_TYPES: str = "video/mp4,video/avi,video/mov,video/wmv,video/flv,video/webm"
    
    # YouTube
    YOUTUBE_SCOPES: str = "https://www.googleapis.com/auth/youtube.upload,https://www.googleapis.com/auth/youtube,https://www.googleapis.com/auth/drive.file"
    
    # Timezone
    DEFAULT_TIMEZONE: str = "UTC"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
    @property
    def allowed_video_types_list(self) -> List[str]:
        return [video_type.strip() for video_type in self.ALLOWED_VIDEO_TYPES.split(",")]
    
    @property
    def youtube_scopes_list(self) -> List[str]:
        return [scope.strip() for scope in self.YOUTUBE_SCOPES.split(",")]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
