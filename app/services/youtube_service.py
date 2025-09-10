from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from app.config import settings
from typing import Optional, Dict, Any, List
import logging
import os

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self):
        pass
    
    def get_credentials_from_token(self, access_token: str, refresh_token: str) -> Credentials:
        """Create credentials from stored tokens"""
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=settings.youtube_scopes_list
        )
        return creds
    
    def get_youtube_service(self, credentials: Credentials):
        """Get YouTube service instance"""
        return build('youtube', 'v3', credentials=credentials)
    
    async def upload_video(self, file_path: str, video_data: Dict[str, Any], credentials: Credentials) -> Dict[str, Any]:
        """Upload video to YouTube"""
        try:
            service = self.get_youtube_service(credentials)
            
            # Prepare video metadata
            body = {
                'snippet': {
                    'title': video_data.get('title', 'Untitled Video'),
                    'description': video_data.get('description', ''),
                    'tags': video_data.get('tags', []),
                    'categoryId': '22'  # People & Blogs category
                },
                'status': {
                    'privacyStatus': video_data.get('privacy', 'private'),
                    'selfDeclaredMadeForKids': False
                }
            }
            
            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype='video/*',
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Upload video
            insert_request = service.videos().insert(
                part=','.join(body.keys()),
                body=body,
                media_body=media
            )
            
            # Execute upload
            response = None
            while response is None:
                status, response = insert_request.next_chunk()
                if status:
                    logger.info(f"Upload progress: {int(status.progress() * 100)}%")
            
            if 'id' in response:
                video_id = response['id']
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                
                logger.info(f"Video uploaded successfully: {video_id}")
                
                return {
                    "video_id": video_id,
                    "video_url": video_url,
                    "title": response['snippet']['title'],
                    "status": response['status']['privacyStatus']
                }
            else:
                raise Exception("Upload failed - no video ID returned")
                
        except Exception as e:
            logger.error(f"Error uploading video to YouTube: {e}")
            raise Exception(f"Failed to upload video to YouTube: {str(e)}")
    
    async def delete_video(self, video_id: str, credentials: Credentials) -> bool:
        """Delete video from YouTube"""
        try:
            service = self.get_youtube_service(credentials)
            service.videos().delete(id=video_id).execute()
            logger.info(f"Video deleted successfully from YouTube: {video_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting video from YouTube: {e}")
            return False
    
    async def get_video_info(self, video_id: str, credentials: Credentials) -> Optional[Dict[str, Any]]:
        """Get video information from YouTube"""
        try:
            service = self.get_youtube_service(credentials)
            response = service.videos().list(
                part='snippet,status,statistics',
                id=video_id
            ).execute()
            
            if not response['items']:
                return None
            
            video = response['items'][0]
            snippet = video['snippet']
            status = video['status']
            statistics = video.get('statistics', {})
            
            return {
                "video_id": video_id,
                "title": snippet['title'],
                "description": snippet['description'],
                "tags": snippet.get('tags', []),
                "privacy_status": status['privacyStatus'],
                "view_count": statistics.get('viewCount', 0),
                "like_count": statistics.get('likeCount', 0),
                "comment_count": statistics.get('commentCount', 0),
                "published_at": snippet['publishedAt'],
                "thumbnail_url": snippet['thumbnails']['default']['url']
            }
        except Exception as e:
            logger.error(f"Error getting video info from YouTube: {e}")
            return None
    
    async def get_channel_info(self, credentials: Credentials) -> Optional[Dict[str, Any]]:
        """Get authenticated user's channel information"""
        try:
            service = self.get_youtube_service(credentials)
            response = service.channels().list(
                part='snippet,statistics',
                mine=True
            ).execute()
            
            if not response['items']:
                return None
            
            channel = response['items'][0]
            snippet = channel['snippet']
            statistics = channel['statistics']
            
            return {
                "channel_id": channel['id'],
                "title": snippet['title'],
                "description": snippet['description'],
                "thumbnail_url": snippet['thumbnails']['default']['url'],
                "subscriber_count": int(statistics.get('subscriberCount', 0)),
                "view_count": int(statistics.get('viewCount', 0)),
                "video_count": int(statistics.get('videoCount', 0))
            }
        except Exception as e:
            logger.error(f"Error getting channel info: {e}")
            return None
    
    async def refresh_credentials(self, credentials: Credentials) -> Optional[Credentials]:
        """Refresh expired credentials"""
        try:
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                return credentials
            return credentials
        except Exception as e:
            logger.error(f"Error refreshing credentials: {e}")
            return None

youtube_service = YouTubeService()
