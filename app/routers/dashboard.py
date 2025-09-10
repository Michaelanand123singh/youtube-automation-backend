from fastapi import APIRouter, HTTPException, status, Depends
from app.routers.auth import get_current_user_dependency
from app.models.user import User
from app.models.video import VideoStatus
from app.database import get_database
from typing import Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/stats")
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user_dependency)
):
    """Get dashboard statistics"""
    try:
        db = get_database()
        
        # Get video counts by status
        video_stats = {}
        for status in VideoStatus:
            count = await db.videos.count_documents({
                "user_id": current_user.id,
                "status": status.value
            })
            video_stats[status.value] = count
        
        # Get total videos
        total_videos = await db.videos.count_documents({"user_id": current_user.id})
        
        # Get scheduled uploads count
        scheduled_uploads = await db.videos.count_documents({
            "user_id": current_user.id,
            "schedule.upload_scheduled_at": {"$exists": True, "$gt": datetime.utcnow()}
        })
        
        # Get scheduled deletions count
        scheduled_deletions = await db.videos.count_documents({
            "user_id": current_user.id,
            "schedule.delete_scheduled_at": {"$exists": True, "$gt": datetime.utcnow()}
        })
        
        # Get YouTube channels count
        youtube_channels = await db.youtube_channels.count_documents({
            "user_id": current_user.id,
            "is_active": True
        })
        
        # Get storage usage (sum of file sizes)
        storage_pipeline = [
            {"$match": {"user_id": current_user.id}},
            {"$group": {"_id": None, "total_size": {"$sum": "$file_size"}}}
        ]
        storage_result = await db.videos.aggregate(storage_pipeline).to_list(1)
        total_storage = storage_result[0]["total_size"] if storage_result else 0
        
        return {
            "total_videos": total_videos,
            "video_stats": video_stats,
            "scheduled_uploads": scheduled_uploads,
            "scheduled_deletions": scheduled_deletions,
            "youtube_channels": youtube_channels,
            "total_storage_bytes": total_storage,
            "total_storage_mb": round(total_storage / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get dashboard statistics"
        )

@router.get("/recent")
async def get_recent_activities(
    limit: int = 10,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get recent activities"""
    try:
        db = get_database()
        activities = []
        
        # Get recent videos
        async for video_doc in db.videos.find(
            {"user_id": current_user.id}
        ).sort("updated_at", -1).limit(limit):
            activity = {
                "type": "video",
                "id": str(video_doc["_id"]),
                "title": video_doc["title"],
                "status": video_doc["status"],
                "created_at": video_doc["created_at"],
                "updated_at": video_doc["updated_at"]
            }
            
            # Add scheduling info if available
            if video_doc.get("schedule", {}).get("upload_scheduled_at"):
                activity["upload_scheduled_at"] = video_doc["schedule"]["upload_scheduled_at"]
            
            if video_doc.get("schedule", {}).get("delete_scheduled_at"):
                activity["delete_scheduled_at"] = video_doc["schedule"]["delete_scheduled_at"]
            
            activities.append(activity)
        
        # Get recent YouTube channel connections
        async for channel_doc in db.youtube_channels.find(
            {"user_id": current_user.id}
        ).sort("created_at", -1).limit(5):
            activities.append({
                "type": "youtube_channel",
                "id": str(channel_doc["_id"]),
                "title": channel_doc["title"],
                "channel_id": channel_doc["channel_id"],
                "created_at": channel_doc["created_at"],
                "updated_at": channel_doc["updated_at"]
            })
        
        # Sort all activities by updated_at
        activities.sort(key=lambda x: x["updated_at"], reverse=True)
        
        return activities[:limit]
        
    except Exception as e:
        logger.error(f"Error getting recent activities: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent activities"
        )

@router.get("/upcoming")
async def get_upcoming_schedules(
    days: int = 7,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get upcoming scheduled uploads and deletions"""
    try:
        db = get_database()
        upcoming = []
        
        # Get upcoming uploads
        uploads = []
        async for video_doc in db.videos.find({
            "user_id": current_user.id,
            "schedule.upload_scheduled_at": {
                "$exists": True,
                "$gte": datetime.utcnow(),
                "$lte": datetime.utcnow() + timedelta(days=days)
            }
        }).sort("schedule.upload_scheduled_at", 1):
            uploads.append({
                "type": "upload",
                "video_id": str(video_doc["_id"]),
                "title": video_doc["title"],
                "scheduled_at": video_doc["schedule"]["upload_scheduled_at"],
                "status": video_doc["status"]
            })
        
        # Get upcoming deletions
        deletions = []
        async for video_doc in db.videos.find({
            "user_id": current_user.id,
            "schedule.delete_scheduled_at": {
                "$exists": True,
                "$gte": datetime.utcnow(),
                "$lte": datetime.utcnow() + timedelta(days=days)
            }
        }).sort("schedule.delete_scheduled_at", 1):
            deletions.append({
                "type": "delete",
                "video_id": str(video_doc["_id"]),
                "title": video_doc["title"],
                "scheduled_at": video_doc["schedule"]["delete_scheduled_at"],
                "youtube_video_id": video_doc["schedule"].get("youtube_video_id")
            })
        
        # Combine and sort
        upcoming = uploads + deletions
        upcoming.sort(key=lambda x: x["scheduled_at"])
        
        return upcoming
        
    except Exception as e:
        logger.error(f"Error getting upcoming schedules: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get upcoming schedules"
        )

@router.get("/calendar")
async def get_calendar_data(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user_dependency)
):
    """Get calendar data for a specific month"""
    try:
        from datetime import date
        import calendar
        
        # Get start and end of month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        db = get_database()
        calendar_data = {}
        
        # Get uploads for the month
        async for video_doc in db.videos.find({
            "user_id": current_user.id,
            "schedule.upload_scheduled_at": {
                "$exists": True,
                "$gte": start_date,
                "$lt": end_date
            }
        }):
            scheduled_date = video_doc["schedule"]["upload_scheduled_at"].date()
            if scheduled_date not in calendar_data:
                calendar_data[scheduled_date] = {"uploads": [], "deletions": []}
            
            calendar_data[scheduled_date]["uploads"].append({
                "video_id": str(video_doc["_id"]),
                "title": video_doc["title"],
                "scheduled_at": video_doc["schedule"]["upload_scheduled_at"]
            })
        
        # Get deletions for the month
        async for video_doc in db.videos.find({
            "user_id": current_user.id,
            "schedule.delete_scheduled_at": {
                "$exists": True,
                "$gte": start_date,
                "$lt": end_date
            }
        }):
            scheduled_date = video_doc["schedule"]["delete_scheduled_at"].date()
            if scheduled_date not in calendar_data:
                calendar_data[scheduled_date] = {"uploads": [], "deletions": []}
            
            calendar_data[scheduled_date]["deletions"].append({
                "video_id": str(video_doc["_id"]),
                "title": video_doc["title"],
                "scheduled_at": video_doc["schedule"]["delete_scheduled_at"]
            })
        
        return calendar_data
        
    except Exception as e:
        logger.error(f"Error getting calendar data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get calendar data"
        )
