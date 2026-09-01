"""Magic Hour AI video generation client.

Creates a text-to-video job on the Magic Hour API, polls until the job is
complete, then downloads the generated MP4.

API reference: https://docs.magichour.ai/api-reference/video-projects/text-to-video
  POST /v1/text-to-video      -> { id, credits_charged, ... }
  GET  /v1/video-projects/:id -> { status, error, downloads: [{url, expires_at}], ... }

Engine selection is handled upstream in generate.py: if MAGIC_HOUR_API_KEY is
set this module is used first (favouring free-tier cinematic models like
ltx-2.3 / seedance-2.5), then Seedance, then the Pexels stock-footage path.
"""
import logging
import os
import time
from pathlib import Path

import requests

from config import CONFIG

logger = logging.getLogger("magichour")

DEFAULT_BASE_URL = "https://api.magichour.ai"
# Free tier defaults: fastest/cheapest model, 480p (576px) output.
DEFAULT_MODEL = "ltx-2.3"
DEFAULT_RESOLUTION = "480p"
DEFAULT_ASPECT_RATIO = "9:16"
# Conservative per-clip cap; ltx-2.3 supports up to 30s.
MAX_DURATION = 30
TARGET_DURATION = 10
PAGE_SIZE = 8192


def _headers() -> dict:
    api_key = CONFIG.magic_hour_api_key
    if not api_key:
        raise RuntimeError("MAGIC_HOUR_API_KEY is not configured.")
    return {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return os.getenv("MAGIC_HOUR_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _normalise_prompt(prompt: str) -> str:
    """Collapse whitespace/newlines so prompts survive JSON transport."""
    return " ".join(str(prompt).split())


class MagicHourCreditError(RuntimeError):
    """Raised when the Magic Hour account is out of credits."""


class MagicHourError(RuntimeError):
    """Generic Magic Hour API error."""


def create_video(
    prompt: str,
    duration: int = TARGET_DURATION,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str | None = None,
    model: str | None = None,
    name: str = "Faceless video scene",
    timeout: int = 30,
) -> str:
    """Create a text-to-video job and return its project id.

    Raises MagicHourCreditError on 402 (insufficient credits).
    """
    model = model or os.getenv("MAGIC_HOUR_MODEL", DEFAULT_MODEL)
    resolution = resolution or os.getenv("MAGIC_HOUR_RESOLUTION", DEFAULT_RESOLUTION)

    duration = int(duration)
    if duration > MAX_DURATION:
        duration = MAX_DURATION
    if duration < 1:
        duration = 1

    payload = {
        "name": name or "Faceless video scene",
        "end_seconds": duration,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "model": model,
        "audio": False,  # narration/voiceover is layered in later by MoviePy
        "style": {"prompt": _normalise_prompt(prompt)},
    }

    logger.info(
        "MagicHour create_video: model=%s duration=%ss aspect=%s resolution=%s",
        model,
        duration,
        aspect_ratio,
        resolution,
    )

    response = requests.post(
        f"{_base_url()}/v1/text-to-video",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    logger.info("MagicHour create_video HTTP %s", response.status_code)

    if response.status_code == 402:
        text = response.text or "insufficient credits"
        raise MagicHourCreditError(f"Magic Hour has no credits ({text}).")
    if response.status_code >= 400:
        raise MagicHourError(
            f"MagicHour create_video failed ({response.status_code}): "
            f"{response.text[:300]}"
        )

    data = response.json()
    project_id = data.get("id")
    if not project_id:
        raise MagicHourError(f"MagicHour response had no project id: {data}")
    return str(project_id)


def get_video_details(project_id: str, timeout: int = 30) -> dict:
    """Return the project payload: {status, error, downloads, credits_charged}."""
    response = requests.get(
        f"{_base_url()}/v1/video-projects/{project_id}",
        headers=_headers(),
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise MagicHourError(
            f"MagicHour status failed ({response.status_code}): {response.text[:300]}"
        )
    return response.json()


def wait_for_video(
    project_id: str,
    poll_interval: float = 5.0,
    max_wait: float = 900.0,
) -> str:
    """Poll until the job succeeds; return the first download URL."""
    waited = 0.0
    while waited < max_wait:
        info = get_video_details(project_id)
        status = (info.get("status") or "").lower()
        logger.info("MagicHour job %s status=%s (waited %.0fs)", project_id, status, waited)

        if status == "complete":
            downloads = info.get("downloads") or []
            if downloads and downloads[0].get("url"):
                return str(downloads[0]["url"])
            raise MagicHourError(
                f"MagicHour job {project_id} complete but no download URL."
            )

        if status in ("error", "canceled", "draft"):
            error = info.get("error") or {}
            message = error.get("message") if isinstance(error, dict) else str(error)
            raise MagicHourError(
                f"MagicHour job {project_id} ended with status '{status}': {message}"
            )

        time.sleep(poll_interval)
        waited += poll_interval

    raise MagicHourError(f"MagicHour job {project_id} timed out after {max_wait}s.")


def download_video(url: str, dest_path: str) -> str:
    """Download a Magic Hour result MP4 to `dest_path` and return the local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading MagicHour video...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=PAGE_SIZE):
                if chunk:
                    f.write(chunk)

    if not dest.exists() or dest.stat().st_size == 0:
        raise MagicHourError(f"MagicHour download {dest_path} is empty/missing.")
    return str(dest)


def generate_one(
    prompt: str,
    dest_path: str,
    duration: int = TARGET_DURATION,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    poll_interval: float = 5.0,
    max_wait: float = 900.0,
) -> str:
    """High-level helper: create -> poll -> download in one call."""
    project_id = create_video(
        prompt=prompt,
        duration=duration,
        aspect_ratio=aspect_ratio,
    )
    url = wait_for_video(project_id, poll_interval=poll_interval, max_wait=max_wait)
    return download_video(url, dest_path)