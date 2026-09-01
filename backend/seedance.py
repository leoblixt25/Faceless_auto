"""Seedance 2.0 AI video generation client.

Creates a text-to-video generation task on the Seedance API (proxy/gateway),
polls until the video is ready, then downloads the resulting MP4.

API reference: https://seedanceapi.org/docs/v2
  Base URL:  https://seedanceapi.org/v2
  POST /v2/generate  -> { code, message, data: { task_id, status, ... } }
  GET  /v2/status?task_id=... -> { data: { status, response: [url] } }

Engine selection is handled upstream in generate.py: if SEEDANCE_API_KEY is
set this module is used, otherwise the Pexels stock-footage path is used.
"""
import logging
import os
import time
from pathlib import Path

import requests

from config import CONFIG

logger = logging.getLogger("seedance")

DEFAULT_MODEL = "seedance-2.0"
# 9:16 vertical videos for TikTok / Shorts / Reels.
DEFAULT_ASPECT_RATIO = "9:16"
DEFAULT_RESOLUTION = "720p"
DEFAULT_BASE_URL = "https://seedanceapi.org/v2"
MAX_DURATION = 15  # hard per-clip cap from the Seedance API
TARGET_DURATION = 10  # our default per-scene clip length
PAGE_SIZE = 8192


def _headers() -> dict:
    api_key = CONFIG.seedance_api_key
    if not api_key:
        raise RuntimeError("SEEDANCE_API_KEY is not configured.")
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return os.getenv("SEEDANCE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


def _normalise_prompt(prompt: str) -> str:
    """Clean up a scene prompt so it survives JSON transport on the GitHub runner."""
    return " ".join(str(prompt).split())


class SeedanceCreditError(RuntimeError):
    """Raised when the Seedance account is out of credits."""


class SeedanceError(RuntimeError):
    """Generic Seedance API error."""


def create_video(
    prompt: str,
    duration: int = TARGET_DURATION,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str = DEFAULT_RESOLUTION,
    model: str = DEFAULT_MODEL,
    timeout: int = 30,
) -> str:
    """Create a generation task and return its task_id.

    Raises SeedanceCreditError on 402 (insufficient credits) so callers can
    fall back to the stock-footage engine.
    """
    duration = int(duration)
    if duration > MAX_DURATION:
        duration = MAX_DURATION
    if duration < 5:
        duration = 5

    payload = {
        "prompt": _normalise_prompt(prompt),
        "aspect_ratio": aspect_ratio,
        "duration": duration,
        "model": model,
    }
    if resolution:
        payload["resolution"] = resolution

    logger.info(
        "Seedance create_video: model=%s duration=%ss aspect=%s resolution=%s",
        model,
        duration,
        aspect_ratio,
        resolution,
    )

    response = requests.post(
        f"{_base_url()}/generate",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    logger.info("Seedance create_video HTTP %s", response.status_code)

    if response.status_code == 402:
        text = response.text or "insufficient credits"
        raise SeedanceCreditError(
            f"Seedance account has no credits ({text}). "
            "Top up at https://seedanceapi.org/pricing."
        )
    if response.status_code >= 400:
        raise SeedanceError(
            f"Seedance create_video failed ({response.status_code}): "
            f"{response.text[:300]}"
        )

    data = response.json()
    task_info = data.get("data") or {}
    task_id = task_info.get("task_id") or data.get("task_id")
    if not task_id:
        raise SeedanceError(f"Seedance response had no task_id: {data}")
    return str(task_id)


def get_task_status(task_id: str, timeout: int = 30) -> dict:
    """Return the task payload: {status, response, error_message, ...}."""
    response = requests.get(
        f"{_base_url()}/status",
        headers=_headers(),
        params={"task_id": task_id},
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise SeedanceError(
            f"Seedance status failed ({response.status_code}): {response.text[:300]}"
        )
    data = response.json()
    return data.get("data") or {}


def wait_for_video(
    task_id: str,
    poll_interval: float = 12.0,
    max_wait: float = 900.0,
) -> str:
    """Poll until the task SUCCEEDS/FAILS; return the first video URL.

    Raises SeedanceError when the task fails or times out.
    """
    waited = 0.0
    while waited < max_wait:
        info = get_task_status(task_id)
        status = (info.get("status") or "").upper()
        logger.info("Seedance task %s status=%s (waited %.0fs)", task_id, status, waited)

        if status in ("SUCCESS", "COMPLETED", "DONE"):
            response_urls = info.get("response") or []
            if isinstance(response_urls, str):
                response_urls = [response_urls]
            urls = [u for u in response_urls if u]
            if urls:
                return urls[0]
            raise SeedanceError(
                f"Seedance task {task_id} SUCCESS but no video URL in response."
            )

        if status in ("FAILED", "FAILURE", "CANCELLED", "ERROR"):
            error_msg = info.get("error_message") or info.get("error") or "unknown error"
            raise SeedanceError(f"Seedance task {task_id} failed: {error_msg}")

        time.sleep(poll_interval)
        waited += poll_interval

    raise SeedanceError(f"Seedance task {task_id} timed out after {max_wait}s.")


def download_video(url: str, dest_path: str) -> str:
    """Download a Seedance result MP4 to `dest_path` and return the local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading Seedance video: %s", url)
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=PAGE_SIZE):
                if chunk:
                    f.write(chunk)

    if not dest.exists() or dest.stat().st_size == 0:
        raise SeedanceError(f"Seedance download {dest_path} is empty/missing.")
    return str(dest)


def generate_one(
    prompt: str,
    dest_path: str,
    duration: int = TARGET_DURATION,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    resolution: str = DEFAULT_RESOLUTION,
    model: str = DEFAULT_MODEL,
    poll_interval: float = 12.0,
    max_wait: float = 900.0,
) -> str:
    """High-level helper: create -> poll -> download in one call."""
    task_id = create_video(
        prompt=prompt,
        duration=duration,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        model=model,
    )
    url = wait_for_video(
        task_id,
        poll_interval=poll_interval,
        max_wait=max_wait,
    )
    return download_video(url, dest_path)