from fastapi import APIRouter, HTTPException, status, Depends
from app.routers.auth import get_current_user_dependency
from app.models.user import User
from app.models.youtube_channel import YouTubeChannel, YouTubeChannelCreate, YouTubeChannelUpdate
from app.services.youtube_service import youtube_service
from app.database import get_database
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class YouTubeAuthRequest(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: datetime

@router.get("/channels", response_model=List[YouTubeChannel])
async def get_youtube_channels(
    current_user: User = Depends(get_current_user_dependency)
):
    """Get user's YouTube channels"""
    try:
        db = get_database()
        channels = []
        
        async for channel_doc in db.youtube_channels.find(
            {"user_id": current_user.id, "is_active": True}
        ).sort("created_at", -1):
            channels.append(YouTubeChannel(**channel_doc))
        
        return channels
        
    except Exception as e:
        logger.error(f"Error getting YouTube channels: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get YouTube channels"
        )

@router.post("/authenticate", response_model=YouTubeChannel)
async def authenticate_youtube_channel(
    auth_request: YouTubeAuthRequest,
    current_user: User = Depends(get_current_user_dependency)
):
    """Authenticate and connect YouTube channel"""
    try:
        # Get credentials
        credentials = youtube_service.get_credentials_from_token(
            auth_request.access_token,
            auth_request.refresh_token
        )
        
        # Refresh credentials if needed
        credentials = youtube_service.refresh_credentials(credentials)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to refresh credentials"
            )
        
        # Get channel info
        channel_info = await youtube_service.get_channel_info(credentials)
        if not channel_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get channel information"
            )
        
        # Check if channel already exists
        db = get_database()
        existing_channel = await db.youtube_channels.find_one({
            "channel_id": channel_info["channel_id"],
            "user_id": current_user.id
        })
        
        if existing_channel:
            # Update existing channel
            update_data = YouTubeChannelUpdate(
                title=channel_info["title"],
                description=channel_info["description"],
                thumbnail_url=channel_info["thumbnail_url"],
                subscriber_count=channel_info["subscriber_count"],
                view_count=channel_info["view_count"],
                video_count=channel_info["video_count"],
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=credentials.expiry
            )
            
            update_dict = update_data.dict(exclude_unset=True)
            update_dict["updated_at"] = datetime.utcnow()
            
            await db.youtube_channels.update_one(
                {"_id": existing_channel["_id"]},
                {"$set": update_dict}
            )
            
            # Get updated channel
            updated_channel_doc = await db.youtube_channels.find_one(
                {"_id": existing_channel["_id"]}
            )
            return YouTubeChannel(**updated_channel_doc)
        
        else:
            # Create new channel
            channel_data = YouTubeChannelCreate(
                channel_id=channel_info["channel_id"],
                title=channel_info["title"],
                description=channel_info["description"],
                thumbnail_url=channel_info["thumbnail_url"],
                subscriber_count=channel_info["subscriber_count"],
                view_count=channel_info["view_count"],
                video_count=channel_info["video_count"],
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_expires_at=credentials.expiry
            )
            
            channel_dict = channel_data.dict()
            channel_dict.update({
                "user_id": current_user.id,
                "is_active": True,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            result = await db.youtube_channels.insert_one(channel_dict)
            
            # Get created channel
            channel_doc = await db.youtube_channels.find_one({"_id": result.inserted_id})
            return YouTubeChannel(**channel_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error authenticating YouTube channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to authenticate YouTube channel"
        )

@router.put("/channels/{channel_id}", response_model=YouTubeChannel)
async def update_youtube_channel(
    channel_id: str,
    channel_update: YouTubeChannelUpdate,
    current_user: User = Depends(get_current_user_dependency)
):
    """Update YouTube channel information"""
    try:
        db = get_database()
        
        # Check if channel exists and belongs to user
        channel_doc = await db.youtube_channels.find_one({
            "_id": ObjectId(channel_id),
            "user_id": current_user.id
        })
        
        if not channel_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found"
            )
        
        # Update channel
        update_data = channel_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        await db.youtube_channels.update_one(
            {"_id": ObjectId(channel_id)},
            {"$set": update_data}
        )
        
        # Get updated channel
        updated_channel_doc = await db.youtube_channels.find_one({"_id": ObjectId(channel_id)})
        return YouTubeChannel(**updated_channel_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating YouTube channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update YouTube channel"
        )

@router.delete("/channels/{channel_id}")
async def delete_youtube_channel(
    channel_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    """Delete YouTube channel connection"""
    try:
        db = get_database()
        
        # Check if channel exists and belongs to user
        channel_doc = await db.youtube_channels.find_one({
            "_id": ObjectId(channel_id),
            "user_id": current_user.id
        })
        
        if not channel_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found"
            )
        
        # Soft delete (set is_active to False)
        await db.youtube_channels.update_one(
            {"_id": ObjectId(channel_id)},
            {
                "$set": {
                    "is_active": False,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        return {"message": "Channel disconnected successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting YouTube channel: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete YouTube channel"
        )

@router.get("/channels/{channel_id}/info")
async def get_channel_info(
    channel_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get detailed channel information from YouTube API"""
    try:
        db = get_database()
        
        # Get channel from database
        channel_doc = await db.youtube_channels.find_one({
            "_id": ObjectId(channel_id),
            "user_id": current_user.id,
            "is_active": True
        })
        
        if not channel_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Channel not found"
            )
        
        # Get credentials
        credentials = youtube_service.get_credentials_from_token(
            channel_doc["access_token"],
            channel_doc["refresh_token"]
        )
        
        # Refresh credentials if needed
        credentials = youtube_service.refresh_credentials(credentials)
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to refresh credentials"
            )
        
        # Get fresh channel info from YouTube
        channel_info = await youtube_service.get_channel_info(credentials)
        if not channel_info:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to get channel information"
            )
        
        return channel_info
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting channel info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get channel information"
        )
