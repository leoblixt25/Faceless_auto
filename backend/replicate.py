"""Replicate API client for AI video generation.

Creates a text-to-video prediction on Replicate (Kling v3 Omni for cinematic
quality with multi-shot support), polls until complete, then downloads the MP4.

Reference: https://replicate.com/kwaivgi/kling-v3-omni-video
  POST   /v1/predictions          -> { id, status, ... }
  GET    /v1/predictions/:id      -> { status, output, error, ... }

Engine selection is handled upstream in generate.py: if REPLICATE_API_TOKEN
is set this engine is tried FIRST (Kling v3 Omni multi-shot = cinematic), then
Magic Hour, Seedance, then Pexels fallback.
"""
import logging
import os
import time
from pathlib import Path

import requests

from config import CONFIG

logger = logging.getLogger("replicate")

DEFAULT_BASE_URL = "https://api.replicate.com"
DEFAULT_MODEL = "kwaivgi/kling-v3-omni-video"
DEFAULT_MAX_SHOTS = 6
DEFAULT_SHOT_DURATION = 10
TARGET_DURATION = 10
PAGE_SIZE = 8192


def _headers() -> dict:
    token = CONFIG.replicate_api_token
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is not configured.")
    return {
        "Authorization": f"Token {token}",
        "accept": "application/json",
        "Content-Type": "application/json",
    }


def _base_url() -> str:
    return os.getenv("REPLICATE_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class ReplicateError(RuntimeError):
    """Generic Replicate API error."""


class ReplicateNoCreditsError(RuntimeError):
    """Raised when the Replicate account has no credits (HTTP 402)."""


def _normalise_prompt(prompt: str) -> str:
    """Collapse whitespace/newlines so prompts survive JSON transport."""
    return " ".join(str(prompt).split())


def create_prediction(
    prompts: list[str],
    model: str | None = None,
    shot_duration: int = DEFAULT_SHOT_DURATION,
    aspect_ratio: str = "9:16",
    mode: str = "standard",
    timeout: int = 30,
) -> str:
    """Submit a prediction and return its prediction id.

    Uses Kling v3 Omni multi-shot mode: one API call produces up to
    `max_shots` connected scenes.

    Raises ReplicateNoCreditsError on 402 (no balance).
    """
    model = model or os.getenv("REPLICATE_MODEL", DEFAULT_MODEL)
    max_shots = int(os.getenv("REPLICATE_MAX_SHOTS", str(DEFAULT_MAX_SHOTS)))
    prompts = prompts[:max_shots]

    payload = {
        "version": model,
        "input": {
            "multi_prompt": [
                {"prompt": _normalise_prompt(p), "duration": shot_duration}
                for p in prompts
            ],
            "mode": mode,
            "aspect_ratio": aspect_ratio,
            "generate_audio": False,
        },
    }

    logger.info(
        "Replicate create_prediction: model=%s shots=%d duration=%ss mode=%s",
        model,
        len(prompts),
        shot_duration,
        mode,
    )

    response = requests.post(
        f"{_base_url()}/v1/predictions",
        headers=_headers(),
        json=payload,
        timeout=timeout,
    )
    logger.info("Replicate create_prediction HTTP %s", response.status_code)

    if response.status_code == 402:
        raise ReplicateNoCreditsError(
            "Replicate account has no credits (402). "
            "Top up at https://replicate.com/account/billing."
        )
    if response.status_code >= 400:
        raise ReplicateError(
            f"Replicate create_prediction failed ({response.status_code}): "
            f"{response.text[:300]}"
        )

    data = response.json()
    prediction_id = data.get("id")
    if not prediction_id:
        raise ReplicateError(f"Replicate response had no id: {data}")
    return str(prediction_id)


def get_prediction(prediction_id: str, timeout: int = 30) -> dict:
    """Return the prediction payload: {status, output, error, ...}."""
    response = requests.get(
        f"{_base_url()}/v1/predictions/{prediction_id}",
        headers=_headers(),
        timeout=timeout,
    )
    if response.status_code >= 400:
        raise ReplicateError(
            f"Replicate get_prediction failed ({response.status_code}): "
            f"{response.text[:300]}"
        )
    return response.json()


def wait_for_prediction(
    prediction_id: str,
    poll_interval: float = 5.0,
    max_wait: float = 1800.0,
) -> str:
    """Poll until the job succeeds; return the first download URL."""
    waited = 0.0
    while waited < max_wait:
        info = get_prediction(prediction_id)
        status = (info.get("status") or "").lower()
        logger.info("Replicate job %s status=%s (waited %.0fs)", prediction_id, status, waited)

        if status == "succeeded":
            output = info.get("output")
            if output:
                if isinstance(output, list):
                    urls = [u for u in output if u]
                    if urls:
                        return str(urls[0])
                return str(output)
            raise ReplicateError(
                f"Replicate job {prediction_id} succeeded but no output URL."
            )

        if status in ("failed", "canceled", "error"):
            error = info.get("error") or "unknown error"
            raise ReplicateError(
                f"Replicate job {prediction_id} ended with status '{status}': {error}"
            )

        time.sleep(poll_interval)
        waited += poll_interval

    raise ReplicateError(f"Replicate job {prediction_id} timed out after {max_wait}s.")


def download_video(url: str, dest_path: str) -> str:
    """Download a Replicate result MP4 to `dest_path` and return the local path."""
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Downloading Replicate video...")
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=PAGE_SIZE):
                if chunk:
                    f.write(chunk)

    if not dest.exists() or dest.stat().st_size == 0:
        raise ReplicateError(f"Replicate download {dest_path} is empty/missing.")
    return str(dest)


def generate_one(
    prompts: list[str],
    dest_path: str,
    shot_duration: int = TARGET_DURATION,
    poll_interval: float = 5.0,
    max_wait: float = 1800.0,
) -> str:
    """High-level helper: create -> poll -> download in one call."""
    prediction_id = create_prediction(prompts, shot_duration=shot_duration)
    url = wait_for_prediction(prediction_id, poll_interval=poll_interval, max_wait=max_wait)
    return download_video(url, dest_path)