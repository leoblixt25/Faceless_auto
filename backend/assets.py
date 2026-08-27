"""Stock asset fetching + download via the Pexels API."""
import re
from pathlib import Path

import requests

from config import CONFIG

PEXELS_SEARCH_URL = "https://api.pexels.com/videos/search"
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920


def _clean_query(topic: str, n: int = 3) -> str:
    """Shorten the topic into a usable search query."""
    words = re.findall(r"[a-zA-Z0-9']+", topic.lower())
    # Drop stopwords to get a tighter visual subject.
    stopwords = {
        "the", "a", "an", "of", "to", "and", "for", "in", "on", "with",
        "that", "is", "are", "top", "facts", "about", "how", "why", "what",
    }
    keywords = [w for w in words if w not in stopwords][:n]
    return " ".join(keywords) if keywords else topic


def _pick_video_file(video_files):
    """Pick the most suitable video file for a 9:16 (1080x1920) vertical."""
    portrait = [f for f in video_files if f.get("width") and f.get("height")
                and f["width"] < f["height"]]
    pool = portrait or video_files

    def score(f):
        w = f.get("width") or 0
        h = f.get("height") or 0
        # Prefer closest to 1080 wide and vertical.
        return abs(w - TARGET_WIDTH) + (10000 if h > w else 0)

    pool.sort(key=score)
    return pool[0] if pool else None


def search_videos(topic: str, count: int = 3):
    """Search Pexels for `count` vertical videos matching `topic`."""
    headers = {"Authorization": CONFIG.pexels_api_key}
    params = {
        "query": _clean_query(topic),
        "orientation": "portrait",
        "per_page": count,
    }
    response = requests.get(PEXELS_SEARCH_URL, headers=headers, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    return data.get("videos", [])[:count]


def download_video(url: str, dest_path: str) -> str:
    """Download a video file to `dest_path` and return the local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return str(dest)


def fetch_assets(topic: str, count: int = 3, work_dir: str = "assets") -> list:
    """Fetch and download `count` vertical videos for `topic`.

    Returns a list of paths to the downloaded video files.
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)
    videos = search_videos(topic, count=count)

    paths = []
    for idx, video in enumerate(videos):
        file_info = _pick_video_file(video.get("video_files", []))
        if not file_info:
            continue
        link = file_info.get("link")
        if not link:
            continue
        extension = Path(link.split("?")[0]).suffix or ".mp4"
        dest = str(work / f"asset_{idx + 1}{extension}")
        download_video(link, dest)
        paths.append(dest)

    if not paths:
        raise RuntimeError("No usable stock videos were found for the topic.")
    return paths
