from fastapi import HTTPException, status
from google.auth.transport import requests
from google.oauth2 import id_token
from google_auth_oauthlib.flow import Flow
from app.config import settings
from app.models.user import User, UserCreate
from app.database import get_database
from typing import Optional, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.db = get_database()
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
    
    def get_google_flow(self) -> Flow:
        """Create Google OAuth flow"""
        flow = Flow.from_client_config(
            self.client_config,
            scopes=[
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/userinfo.profile",
                "https://www.googleapis.com/auth/drive.file",
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube"
            ]
        )
        flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
        return flow
    
    async def verify_google_token(self, token: str) -> Dict[str, Any]:
        """Verify Google ID token and return user info"""
        try:
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                settings.GOOGLE_CLIENT_ID
            )
            
            if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
                raise ValueError('Wrong issuer.')
            
            return {
                "google_id": idinfo['sub'],
                "email": idinfo['email'],
                "name": idinfo['name'],
                "picture": idinfo.get('picture')
            }
        except ValueError as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google token"
            )
    
    async def get_or_create_user(self, user_data: Dict[str, Any]) -> User:
        """Get existing user or create new one"""
        try:
            # Try to find existing user
            user_doc = await self.db.users.find_one({"google_id": user_data["google_id"]})
            
            if user_doc:
                # Update user info
                await self.db.users.update_one(
                    {"google_id": user_data["google_id"]},
                    {
                        "$set": {
                            "email": user_data["email"],
                            "name": user_data["name"],
                            "picture": user_data.get("picture"),
                            "updated_at": datetime.utcnow()
                        }
                    }
                )
                user_doc = await self.db.users.find_one({"google_id": user_data["google_id"]})
            else:
                # Create new user
                user_create = UserCreate(
                    email=user_data["email"],
                    name=user_data["name"],
                    google_id=user_data["google_id"],
                    picture=user_data.get("picture")
                )
                
                user_dict = user_create.dict()
                user_dict.update({
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow(),
                    "is_active": True,
                    "youtube_channels": []
                })
                
                result = await self.db.users.insert_one(user_dict)
                user_doc = await self.db.users.find_one({"_id": result.inserted_id})
            
            return User(**user_doc)
            
        except Exception as e:
            logger.error(f"Error in get_or_create_user: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to process user authentication"
            )
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            from bson import ObjectId
            user_doc = await self.db.users.find_one({"_id": ObjectId(user_id)})
            if user_doc:
                return User(**user_doc)
            return None
        except Exception as e:
            logger.error(f"Error getting user by ID: {e}")
            return None

auth_service = AuthService()
