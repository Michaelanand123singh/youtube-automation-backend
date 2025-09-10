from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from app.config import settings
from typing import Optional, Dict, Any
import logging
import os
import mimetypes

logger = logging.getLogger(__name__)

class DriveService:
    def __init__(self):
        self.client_config = {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI]
            }
        }
    
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
    
    def get_drive_service(self, credentials: Credentials):
        """Get Google Drive service instance"""
        return build('drive', 'v3', credentials=credentials)
    
    async def upload_video(self, file_path: str, file_name: str, credentials: Credentials) -> Dict[str, Any]:
        """Upload video to Google Drive"""
        try:
            service = self.get_drive_service(credentials)
            
            # Get file metadata
            file_size = os.path.getsize(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            # Create file metadata
            file_metadata = {
                'name': file_name,
                'parents': ['root']  # Upload to root folder
            }
            
            # Create media upload
            media = MediaFileUpload(
                file_path,
                mimetype=mime_type,
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Upload file
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id,name,size,mimeType,webViewLink'
            ).execute()
            
            logger.info(f"Video uploaded successfully: {file.get('id')}")
            
            return {
                "file_id": file.get('id'),
                "name": file.get('name'),
                "size": file.get('size'),
                "mime_type": file.get('mimeType'),
                "web_view_link": file.get('webViewLink')
            }
            
        except Exception as e:
            logger.error(f"Error uploading video to Drive: {e}")
            raise Exception(f"Failed to upload video: {str(e)}")
    
    async def delete_video(self, file_id: str, credentials: Credentials) -> bool:
        """Delete video from Google Drive"""
        try:
            service = self.get_drive_service(credentials)
            service.files().delete(fileId=file_id).execute()
            logger.info(f"Video deleted successfully: {file_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting video from Drive: {e}")
            return False
    
    async def get_video_info(self, file_id: str, credentials: Credentials) -> Optional[Dict[str, Any]]:
        """Get video information from Google Drive"""
        try:
            service = self.get_drive_service(credentials)
            file = service.files().get(
                fileId=file_id,
                fields='id,name,size,mimeType,webViewLink,createdTime,modifiedTime'
            ).execute()
            
            return {
                "file_id": file.get('id'),
                "name": file.get('name'),
                "size": file.get('size'),
                "mime_type": file.get('mimeType'),
                "web_view_link": file.get('webViewLink'),
                "created_time": file.get('createdTime'),
                "modified_time": file.get('modifiedTime')
            }
        except Exception as e:
            logger.error(f"Error getting video info from Drive: {e}")
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

drive_service = DriveService()
