"""
YouTube OAuth upload module for Swarm.
Handles OAuth 2.0 authentication via refresh token and video upload via YouTube Data API v3.

The upload flow:
    refresh_token (GitHub secret)
        ↓
    Credentials(refresh_token, client_id, client_secret)
        ↓
    google-api-python-client → service.videos().insert()
        ↓
    video uploaded (private until project passes Google audit)
"""

import os
from pathlib import Path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = ['https://www.googleapis.com/auth/youtube.upload']


def get_service():
    """Create authenticated YouTube API service from GitHub secret env vars."""
    refresh_token = os.environ.get('YOUTUBE_REFRESH_TOKEN', '')
    client_id = os.environ.get('YOUTUBE_CLIENT_ID', '')
    client_secret = os.environ.get('YOUTUBE_CLIENT_SECRET', '')

    if not all([refresh_token, client_id, client_secret]):
        return None

    try:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES
        )
        return build('youtube', 'v3', credentials=creds)
    except Exception as e:
        print(f"[YOUTUBE] Authentication failed: {e}")
        return None


def upload_video(file_path, title, description, tags, category_id='22',
                 privacy_status='private', thumbnail_path=None):
    """Upload a video to YouTube via OAuth.

    Args:
        file_path: Path to video file (MP4 recommended)
        title: Video title (max 100 chars)
        description: Video description
        tags: List of tag strings
        category_id: YouTube category ID (default '22' = People & Blogs)
        privacy_status: 'private' | 'unlisted' | 'public'
        thumbnail_path: Optional path to custom thumbnail image

    Returns:
        Dict with status, video_id, url, privacy, or error
    """
    service = get_service()
    if not service:
        return {
            'status': 'failed',
            'error': 'Authentication failed — missing YOUTUBE_REFRESH_TOKEN, CLIENT_ID, or CLIENT_SECRET'
        }

    video_file = Path(file_path)
    if not video_file.exists():
        return {'status': 'failed', 'error': f'Video file not found: {file_path}'}

    try:
        body = {
            'snippet': {
                'title': title[:100],
                'description': description,
                'tags': tags[:500] if tags else [],
                'categoryId': category_id
            },
            'status': {
                'privacyStatus': privacy_status
            }
        }

        media = MediaFileUpload(str(video_file), chunksize=-1, resumable=True)

        print(f"[YOUTUBE] Uploading: {title}")
        print(f"[YOUTUBE] File: {file_path} ({video_file.stat().st_size / 1024 / 1024:.1f} MB)")

        response = service.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media
        ).execute()

        video_id = response.get('id')

        result = {
            'status': 'published',
            'video_id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'privacy': privacy_status,
            'title': title
        }

        # Upload custom thumbnail if provided
        if thumbnail_path and Path(thumbnail_path).exists():
            try:
                service.thumbnails().set(
                    videoId=video_id,
                    body={'snippet': {'thumbnails': {'default': {'url': ''}}}},
                    media_body=MediaFileUpload(str(thumbnail_path))
                ).execute()
                result['thumbnail'] = thumbnail_path
            except Exception as e:
                print(f"[YOUTUBE] Thumbnail upload skipped: {e}")

        print(f"[YOUTUBE] Uploaded: https://www.youtube.com/watch?v={video_id}")
        return result

    except HttpError as e:
        error_details = e.content.decode() if e.content else str(e)
        if 'quota' in error_details.lower():
            return {'status': 'failed', 'error': 'API quota exceeded — wait 24h'}
        if 'invalid' in error_details.lower() and 'refresh' in error_details.lower():
            return {'status': 'failed', 'error': 'Refresh token expired or revoked'}
        return {'status': 'failed', 'error': f'Upload failed: {error_details[:200]}'}
    except Exception as e:
        return {'status': 'failed', 'error': f'Unexpected error: {str(e)[:200]}'}


def authenticate_locally():
    """One-time local OAuth flow — run this ONCE to get refresh token.

    Prerequisites:
        pip install google-auth-oauthlib
        Create OAuth 2.0 Client ID in Google Cloud Console
        Download as client_secrets.json in the swarm directory

    Output:
        Prints refresh token + client ID + client secret
        → Add these three as GitHub repository secrets
        → Delete client_secrets.json from local machine
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    client_secrets_path = Path('client_secrets.json')
    if not client_secrets_path.exists():
        print("=" * 60)
        print("ERROR: client_secrets.json not found")
        print("=" * 60)
        print()
        print("Setup steps:")
        print("1. Go to https://console.cloud.google.com/apis/credentials")
        print("2. Create OAuth 2.0 Client ID (Application type: Desktop app)")
        print("3. Download as client_secrets.json")
        print("4. Place it in the swarm directory")
        print("5. Run: python youtube_oauth.py")
        print("6. Copy the printed secrets to GitHub repo secrets")
        print("7. Delete client_secrets.json from local machine")
        return

    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets_path),
        SCOPES
    )

    print("Opening browser for OAuth consent...")
    print("Grant permission for 'YouTube Data API v3' → 'Upload videos to your YouTube channel'")
    creds = flow.run_local_server(port=0)

    print("\n" + "=" * 60)
    print("AUTHENTICATION COMPLETE")
    print("=" * 60)
    print()
    print("Add these THREE values as GitHub repository secrets:")
    print("-" * 40)
    print(f"YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print(f"YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    print("-" * 40)
    print()
    print("Then delete client_secrets.json from your local machine.")
    print("The refresh token allows CI to get new access tokens automatically.")
    print("Token expires after 24h but refresh_token is long-lived.")
