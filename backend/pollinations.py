"""Pollinations free-tier AI image -> Ken Burns video engine.

This engine needs NO API key: it generates a vertical (9:16) AI image per
scene prompt through the public anonymous endpoint of image.pollinations.ai,
then animates each image with an ffmpeg Ken Burns zoom/pan and concatenates
the shots into a single MP4 clip. Audio + captions are layered on later by
assemble_seedance.

Because the free tier is rate-limited (roughly one request every 15s), the
module sleeps between image calls and retries transient failures. It sits in
the engine chain between the paid AI engines (Replicate / Magic Hour /
Seedance) and the Pexels stock-footage fallback, and is always available.
"""
import logging
import os
import subprocess
import time
from pathlib import Path

import requests

logger = logging.getLogger("pollinations")

IMAGE_BASE_URL = "https://image.pollinations.ai"
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
FPS = 30
RATE_LIMIT_SECONDS = 15.0
MAX_ATTEMPTS = 4
SHOT_DURATION = 10


class PollinationsError(RuntimeError):
    """Raised when the free-tier image endpoint cannot be used."""


def _ffmpeg_path() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def _generate_image(prompt: str, dest_path: str, seed: int, timeout: int = 120) -> str:
    """Download one vertical AI image for a scene prompt."""
    import urllib.parse

    query = urllib.parse.quote(prompt)
    url = (
        f"{IMAGE_BASE_URL}/prompt/{query}"
        f"?width={DEFAULT_WIDTH}&height={DEFAULT_HEIGHT}"
        f"&nologo=true&seed={seed}"
    )

    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, timeout=timeout)
            if resp.status_code == 429:
                raise PollinationsError(f"free tier rate limited (HTTP 429)")
            if resp.status_code >= 400:
                raise PollinationsError(
                    f"image failed ({resp.status_code}): {resp.text[:200]}"
                )
            if len(resp.content) < 5000:
                raise PollinationsError(f"image response suspiciously small ({len(resp.content)} bytes)")
            Path(dest_path).write_bytes(resp.content)
            logger.info("Pollinations image %s seed=%s (%d bytes)", dest_path, seed, len(resp.content))
            return dest_path
        except PollinationsError as exc:
            last_error = exc
            if attempt < MAX_ATTEMPTS:
                time.sleep(RATE_LIMIT_SECONDS * attempt)
    raise PollinationsError(f"Pollinations image failed after retries: {last_error}")


def _kenburns_clip(
    image_path: str,
    dest_path: str,
    duration: float,
    zoom_direction: str = "in",
) -> str:
    """Animate a still image with a slow Ken Burns move -> MP4 clip."""
    ffmpeg = _ffmpeg_path()
    frames = max(1, int(round(duration * FPS)))
    if zoom_direction == "out":
        zexpr = "max(1.12-0.0004*(on-1),1.0)"
    else:
        zexpr = "min(1.0+0.0004*(on-1),1.12)"
    vf = (
        f"scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
        f"zoompan=z='{zexpr}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:fps={FPS}"
    )
    cmd = [
        ffmpeg, "-y", "-i", image_path,
        "-vf", vf,
        "-frames:v", str(frames),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        "-r", str(FPS),
        dest_path,
    ]
    logger.info("Pollinations Ken Burns: %s -> %s (%.1fs)", image_path, dest_path, duration)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PollinationsError(
            f"ffmpeg Ken Burns failed: {proc.stderr[-500:]}"
        )
    return dest_path


def generate_one(
    prompt: str,
    dest_path: str,
    duration: int = SHOT_DURATION,
    images_per_scene: int = 0,
) -> str:
    """Render one scene into an MP4: AI image(s) + Ken Burns + concat."""
    shots = max(1, int(duration))
    duration = max(1, min(shots, SHOT_DURATION))

    images_per_scene = images_per_scene or int(
        os.getenv("POLLINATIONS_IMAGES_PER_SCENE", "2")
    )
    shot_len = duration / images_per_scene

    image_dir = Path(dest_path).parent / f"poll_{Path(dest_path).stem}_img"
    image_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for idx in range(images_per_scene):
        img = str(image_dir / f"scene_{idx}.jpg")
        _generate_image(prompt, img, seed=idx)
        clip = str(image_dir / f"clip_{idx}.mp4")
        direction = "out" if idx % 2 == 1 else "in"
        _kenburns_clip(img, clip, shot_len, direction)
        clips.append(clip)
        if idx < images_per_scene - 1:
            time.sleep(RATE_LIMIT_SECONDS)

    if len(clips) == 1:
        Path(clips[0]).replace(dest_path)
        return dest_path

    list_file = image_dir / "concat.txt"
    with open(list_file, "w", encoding="utf-8") as f:
        for clip in clips:
            f.write(f"file '{Path(clip).as_posix()}'\n")

    ffmpeg = _ffmpeg_path()
    cmd = [
        ffmpeg, "-y", "-f", "concat", "-safe", "0",
        "-i", str(list_file), "-c", "copy", dest_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise PollinationsError(f"ffmpeg concat failed: {proc.stderr[-500:]}")

    return dest_path