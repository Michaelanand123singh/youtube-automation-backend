from fastapi import APIRouter, HTTPException, status, Depends, UploadFile, File, Form
from app.routers.auth import get_current_user_dependency
from app.models.user import User
from app.models.video import Video, VideoCreate, VideoUpdate, VideoStatus, VideoPrivacy
from app.services.drive_service import drive_service
from app.database import get_database
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
import logging
import os
import tempfile

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/upload", response_model=Video)
async def upload_video(
    file: UploadFile = File(...),
    title: str = Form(...),
    description: str = Form(""),
    tags: str = Form(""),
    privacy: str = Form("private"),
    current_user: User = Depends(get_current_user_dependency)
):
    """Upload video to Google Drive"""
    try:
        # Validate file type
        if file.content_type not in settings.allowed_video_types_list:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only video files are allowed."
            )
        
        # Validate file size (100MB limit)
        file_size = 0
        content = await file.read()
        file_size = len(content)
        
        if file_size > settings.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File too large. Maximum size is 100MB."
            )
        
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # Get user's Google credentials (you'll need to implement this)
            # For now, we'll create a placeholder
            credentials = None  # This should be retrieved from user's stored tokens
            
            if not credentials:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Google Drive authentication required. Please connect your Google account."
                )
            
            # Upload to Google Drive
            drive_result = await drive_service.upload_video(
                temp_file_path,
                file.filename,
                credentials
            )
            
            # Parse tags
            tag_list = [tag.strip() for tag in tags.split(",") if tag.strip()]
            
            # Create video document
            video_data = VideoCreate(
                title=title,
                description=description,
                tags=tag_list,
                privacy=VideoPrivacy(privacy),
                file_path=temp_file_path,
                file_size=file_size,
                mime_type=file.content_type
            )
            
            video_dict = video_data.dict()
            video_dict.update({
                "user_id": current_user.id,
                "google_drive_file_id": drive_result["file_id"],
                "status": VideoStatus.UPLOADED,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            })
            
            # Save to database
            db = get_database()
            result = await db.videos.insert_one(video_dict)
            
            # Get created video
            video_doc = await db.videos.find_one({"_id": result.inserted_id})
            video = Video(**video_doc)
            
            return video
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload video"
        )

@router.get("/", response_model=List[Video])
async def get_videos(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get user's videos"""
    try:
        db = get_database()
        videos = []
        
        async for video_doc in db.videos.find(
            {"user_id": current_user.id}
        ).skip(skip).limit(limit).sort("created_at", -1):
            videos.append(Video(**video_doc))
        
        return videos
        
    except Exception as e:
        logger.error(f"Error getting videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get videos"
        )

@router.get("/{video_id}", response_model=Video)
async def get_video(
    video_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get specific video"""
    try:
        db = get_database()
        video_doc = await db.videos.find_one({
            "_id": ObjectId(video_id),
            "user_id": current_user.id
        })
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        return Video(**video_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get video"
        )

@router.put("/{video_id}", response_model=Video)
async def update_video(
    video_id: str,
    video_update: VideoUpdate,
    current_user: User = Depends(get_current_user_dependency)
):
    """Update video metadata"""
    try:
        db = get_database()
        
        # Check if video exists and belongs to user
        video_doc = await db.videos.find_one({
            "_id": ObjectId(video_id),
            "user_id": current_user.id
        })
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Update video
        update_data = video_update.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()
        
        await db.videos.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": update_data}
        )
        
        # Get updated video
        updated_video_doc = await db.videos.find_one({"_id": ObjectId(video_id)})
        return Video(**updated_video_doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update video"
        )

@router.delete("/{video_id}")
async def delete_video(
    video_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    """Delete video"""
    try:
        db = get_database()
        
        # Check if video exists and belongs to user
        video_doc = await db.videos.find_one({
            "_id": ObjectId(video_id),
            "user_id": current_user.id
        })
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Delete from Google Drive if exists
        if video_doc.get("google_drive_file_id"):
            # You'll need to implement this with proper credentials
            pass
        
        # Delete from database
        await db.videos.delete_one({"_id": ObjectId(video_id)})
        
        return {"message": "Video deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete video"
        )

@router.post("/{video_id}/schedule-upload")
async def schedule_upload(
    video_id: str,
    scheduled_at: datetime,
    youtube_channel_id: str,
    current_user: User = Depends(get_current_user_dependency)
):
    """Schedule video upload to YouTube"""
    try:
        db = get_database()
        
        # Check if video exists and belongs to user
        video_doc = await db.videos.find_one({
            "_id": ObjectId(video_id),
            "user_id": current_user.id
        })
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        # Update video with schedule
        await db.videos.update_one(
            {"_id": ObjectId(video_id)},
            {
                "$set": {
                    "schedule.upload_scheduled_at": scheduled_at,
                    "schedule.youtube_channel_id": ObjectId(youtube_channel_id),
                    "status": VideoStatus.SCHEDULED,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Schedule Celery task
        from app.tasks.upload_tasks import upload_video_to_youtube
        task = upload_video_to_youtube.apply_async(
            args=[str(video_doc["_id"]), str(current_user.id), youtube_channel_id],
            eta=scheduled_at
        )
        
        # Update video with job ID
        await db.videos.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {"schedule.upload_job_id": task.id}}
        )
        
        return {"message": "Video scheduled for upload", "job_id": task.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling upload: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule upload"
        )

@router.post("/{video_id}/schedule-delete")
async def schedule_delete(
    video_id: str,
    scheduled_at: datetime,
    current_user: User = Depends(get_current_user_dependency)
):
    """Schedule video deletion from YouTube"""
    try:
        db = get_database()
        
        # Check if video exists and belongs to user
        video_doc = await db.videos.find_one({
            "_id": ObjectId(video_id),
            "user_id": current_user.id
        })
        
        if not video_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Video not found"
            )
        
        if not video_doc.get("schedule", {}).get("youtube_video_id"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Video not uploaded to YouTube yet"
            )
        
        # Update video with delete schedule
        await db.videos.update_one(
            {"_id": ObjectId(video_id)},
            {
                "$set": {
                    "schedule.delete_scheduled_at": scheduled_at,
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        # Schedule Celery task
        from app.tasks.upload_tasks import delete_video_from_youtube
        task = delete_video_from_youtube.apply_async(
            args=[
                str(video_doc["_id"]),
                video_doc["schedule"]["youtube_video_id"],
                str(current_user.id),
                str(video_doc["schedule"].get("youtube_channel_id", ""))
            ],
            eta=scheduled_at
        )
        
        # Update video with job ID
        await db.videos.update_one(
            {"_id": ObjectId(video_id)},
            {"$set": {"schedule.delete_job_id": task.id}}
        )
        
        return {"message": "Video scheduled for deletion", "job_id": task.id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error scheduling deletion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to schedule deletion"
        )

@router.get("/scheduled", response_model=List[Video])
async def get_scheduled_videos(
    current_user: User = Depends(get_current_user_dependency)
):
    """Get scheduled videos"""
    try:
        db = get_database()
        videos = []
        
        async for video_doc in db.videos.find({
            "user_id": current_user.id,
            "$or": [
                {"schedule.upload_scheduled_at": {"$exists": True}},
                {"schedule.delete_scheduled_at": {"$exists": True}}
            ]
        }).sort("created_at", -1):
            videos.append(Video(**video_doc))
        
        return videos
        
    except Exception as e:
        logger.error(f"Error getting scheduled videos: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get scheduled videos"
        )
