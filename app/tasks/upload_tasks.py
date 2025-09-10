from celery import Celery
from app.config import settings
from app.services.youtube_service import youtube_service
from app.services.drive_service import drive_service
from app.database import get_database
from app.models.video import VideoStatus
from typing import Dict, Any
from datetime import datetime
import logging
import os

logger = logging.getLogger(__name__)

# Initialize Celery
celery_app = Celery(
    "youtube_scheduler",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

@celery_app.task(bind=True)
def upload_video_to_youtube(self, video_id: str, user_id: str, youtube_channel_id: str):
    """Upload video to YouTube as a background task"""
    try:
        db = get_database()
        
        # Get video and channel info
        video_doc = db.videos.find_one({"_id": video_id})
        channel_doc = db.youtube_channels.find_one({"_id": youtube_channel_id})
        
        if not video_doc or not channel_doc:
            raise Exception("Video or channel not found")
        
        # Update video status to processing
        db.videos.update_one(
            {"_id": video_id},
            {"$set": {"status": VideoStatus.PROCESSING}}
        )
        
        # Get credentials
        credentials = youtube_service.get_credentials_from_token(
            channel_doc['access_token'],
            channel_doc['refresh_token']
        )
        
        # Refresh credentials if needed
        credentials = youtube_service.refresh_credentials(credentials)
        if not credentials:
            raise Exception("Failed to refresh credentials")
        
        # Upload video to YouTube
        video_data = {
            "title": video_doc['title'],
            "description": video_doc.get('description', ''),
            "tags": video_doc.get('tags', []),
            "privacy": video_doc.get('privacy', 'private')
        }
        
        result = youtube_service.upload_video(
            video_doc['file_path'],
            video_data,
            credentials
        )
        
        # Update video with YouTube info
        db.videos.update_one(
            {"_id": video_id},
            {
                "$set": {
                    "status": VideoStatus.PUBLISHED,
                    "schedule.youtube_video_id": result['video_id'],
                    "schedule.youtube_url": result['video_url'],
                    "updated_at": datetime.utcnow()
                }
            }
        )
        
        logger.info(f"Video {video_id} uploaded successfully to YouTube")
        return {"status": "success", "video_id": result['video_id']}
        
    except Exception as e:
        logger.error(f"Error uploading video {video_id}: {e}")
        
        # Update video status to failed
        db.videos.update_one(
            {"_id": video_id},
            {"$set": {"status": VideoStatus.FAILED}}
        )
        
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task(bind=True)
def delete_video_from_youtube(self, video_id: str, youtube_video_id: str, user_id: str, youtube_channel_id: str):
    """Delete video from YouTube as a background task"""
    try:
        db = get_database()
        
        # Get channel info
        channel_doc = db.youtube_channels.find_one({"_id": youtube_channel_id})
        
        if not channel_doc:
            raise Exception("Channel not found")
        
        # Get credentials
        credentials = youtube_service.get_credentials_from_token(
            channel_doc['access_token'],
            channel_doc['refresh_token']
        )
        
        # Refresh credentials if needed
        credentials = youtube_service.refresh_credentials(credentials)
        if not credentials:
            raise Exception("Failed to refresh credentials")
        
        # Delete video from YouTube
        success = youtube_service.delete_video(youtube_video_id, credentials)
        
        if success:
            # Update video status
            db.videos.update_one(
                {"_id": video_id},
                {
                    "$set": {
                        "status": VideoStatus.DELETED,
                        "schedule.youtube_video_id": None,
                        "schedule.youtube_url": None,
                        "updated_at": datetime.utcnow()
                    }
                }
            )
            
            logger.info(f"Video {video_id} deleted successfully from YouTube")
            return {"status": "success"}
        else:
            raise Exception("Failed to delete video from YouTube")
        
    except Exception as e:
        logger.error(f"Error deleting video {video_id}: {e}")
        raise self.retry(exc=e, countdown=60, max_retries=3)

@celery_app.task
def cleanup_expired_videos():
    """Clean up videos that are scheduled for deletion"""
    try:
        db = get_database()
        current_time = datetime.utcnow()
        
        # Find videos scheduled for deletion
        videos_to_delete = db.videos.find({
            "schedule.delete_scheduled_at": {"$lte": current_time},
            "status": {"$in": [VideoStatus.PUBLISHED, VideoStatus.SCHEDULED]}
        })
        
        for video in videos_to_delete:
            if video['schedule'].get('youtube_video_id'):
                # Schedule deletion task
                delete_video_from_youtube.delay(
                    str(video['_id']),
                    video['schedule']['youtube_video_id'],
                    str(video['user_id']),
                    str(video.get('youtube_channel_id', ''))
                )
        
        logger.info(f"Cleaned up {len(list(videos_to_delete))} expired videos")
        
    except Exception as e:
        logger.error(f"Error in cleanup_expired_videos: {e}")
