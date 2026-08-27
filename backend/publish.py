"""Publishing module (Phase 4 + 5).

Uploads the rendered MP4 to the target social platform and returns the live
link. Supports:
  - YouTube Shorts (via YouTube Data API v3, google-api-python-client)
  - Instagram Reels (via Meta Graph API, two-step media/publish)
  - TikTok (via the Content Posting API, init + status polling)
"""
import json
import logging
import time

import requests

from config import CONFIG

logger = logging.getLogger("publish")

CATEGORY_ID = "22"  # YouTube "People & Blogs"

# ---------------------------------------------------------------------------
# YouTube (Phase 4)
# ---------------------------------------------------------------------------


def _load_google_credentials():
    """Load OAuth2 credentials from the stored token (and client secrets).

    Requires env:
      GOOGLE_CLIENT_SECRETS - path to the downloaded client_secret_*.json
      GOOGLE_TOKEN          - path to the stored token JSON (access+refresh)
    """
    from google.oauth2.credentials import Credentials

    token_path = CONFIG.google_token_path
    with open(token_path, "r", encoding="utf-8") as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
    return creds


def upload_to_youtube(video_path, title, description, tags=None, privacy="public"):
    """Upload a local MP4 to YouTube Shorts and return the video URL.

    YouTube infers "Short" automatically for videos under 60 seconds that use
    the vertical (9:16) format, so no explicit indicator is required.
    """
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = _load_google_credentials()
    service = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "categoryId": CATEGORY_ID,
            "tags": tags or ["shorts", "vertical", "faceless"],
            "defaultAudioLanguage": "en",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }

    media = MediaFileUpload(
        video_path, chunksize=1024 * 1024 * 8, resumable=True, mimetype="video/mp4"
    )
    request = service.videos().insert(
        part="snippet,status", body=body, media_body=media
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info("YouTube upload progress: %d%%", int(status.progress() * 100))

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("YouTube upload did not return a video id.")
    return f"https://www.youtube.com/shorts/{video_id}"


# ---------------------------------------------------------------------------
# Instagram Reels (Phase 4)
# ---------------------------------------------------------------------------

GRAPH_API = "https://graph.facebook.com/v20.0"


def upload_to_instagram(video_url, caption, access_token=None, business_account_id=None):
    """Publish a Reels video using the two-step Media/Media_publish flow."""
    token = access_token or CONFIG.instagram_access_token
    account_id = business_account_id or CONFIG.instagram_business_account_id
    if not token or not account_id:
        raise RuntimeError(
            "Instagram publishing requires INSTAGRAM_ACCESS_TOKEN and "
            "INSTAGRAM_BUSINESS_ACCOUNT_ID."
        )

    # Step A: create the media container.
    create_resp = requests.post(
        f"{GRAPH_API}/{account_id}/media",
        params={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": token,
        },
        timeout=60,
    )
    create_resp.raise_for_status()
    creation_id = create_resp.json().get("id")
    if not creation_id:
        raise RuntimeError(f"Instagram media creation failed: {create_resp.text}")

    # Step B: publish the created media container.
    publish_resp = requests.post(
        f"{GRAPH_API}/{account_id}/media_publish",
        params={"creation_id": creation_id, "access_token": token},
        timeout=60,
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json().get("id")
    if not media_id:
        raise RuntimeError(f"Instagram publish failed: {publish_resp.text}")

    return f"https://www.instagram.com/reel/{media_id}"


# ---------------------------------------------------------------------------
# TikTok (Phase 5)
# ---------------------------------------------------------------------------

TIKTOK_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


def tiktok_publish(video_url, access_token, title, privacy_level="SELF_ONLY", timeout=300):
    """Publish a video to TikTok via URL pull + status polling.

    Returns the TikTok item id URL on success.
    """
    init_resp = requests.post(
        TIKTOK_INIT_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={
            "source_info": {
                "source": "PULL_FROM_URL",
                "video_url": video_url,
            },
            "post_info": {
                "title": title,
                "privacy_level": privacy_level,
            },
        },
        timeout=60,
    )
    if init_resp.status_code != 200:
        raise RuntimeError(f"TikTok init failed ({init_resp.status_code}): {init_resp.text}")
    init_data = init_resp.json().get("data", {})
    publish_id = init_data.get("publish_id")
    if not publish_id:
        raise RuntimeError(f"TikTok init did not return publish_id: {init_resp.text}")

    # Poll every 10 seconds until complete/failed or timeout.
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(10)
        status_resp = requests.post(
            TIKTOK_STATUS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"publish_id": publish_id},
            timeout=60,
        )
        status_resp.raise_for_status()
        status_info = status_resp.json().get("data", {})
        status = status_info.get("status")
        logger.info("TikTok publish status: %s", status)

        if status == "PUBLISH_COMPLETE":
            item_id = (status_info.get("post") or {}).get("link") or publish_id
            logger.info("TikTok publish complete: %s", item_id)
            return f"https://www.tiktok.com/@{'video'}/video/{publish_id}"
        if status in ("PUBLISH_FAILED", "FAILED"):
            raise RuntimeError(f"TikTok publish failed: {status_info}")

    raise TimeoutError("Timed out waiting for TikTok publish to complete.")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def publish(platform, video_url, title, description, caption, **kwargs):
    """Route to the correct platform publisher based on `platform`."""
    platform = (platform or "").lower()
    if platform == "youtube_shorts":
        return upload_to_youtube(kwargs.get("video_path", ""), title, description)
    if platform == "instagram_reels":
        return upload_to_instagram(video_url, caption, **kwargs)
    if platform in ("tiktok",):
        return tiktok_publish(
            video_url,
            CONFIG.tiktok_access_token,
            title,
            privacy_level=kwargs.get("privacy_level", "SELF_ONLY"),
        )
    raise ValueError(f"Unsupported platform: {platform}")
