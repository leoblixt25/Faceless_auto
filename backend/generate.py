#!/usr/bin/env python3
"""Faceless video generator — Phase 3 core pipeline.

Flow:
  1. Read CLI args (userId, topic, platform) + optional documentId.
  2. Generate a script via Groq.
  3. Convert script to MP3 via edge-tts.
  4. Fetch + download vertical stock videos via Pexels.
  5. Assemble the 1080x1920 MP4 with MoviePy (audio + captions).
  6. Upload the MP4 to Firebase Storage.
  7. Update the Firestore document status -> "completed" with the video URL.

The GitHub Actions workflow (`video_builder.yml`) runs this file, passing the
repository_dispatch `client_payload` fields as arguments.
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path

import firebase_store
import release_store

import publish as publisher
from assets import fetch_assets
from assemble import assemble_video
from script_gen import generate_script
from tts import text_to_speech

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("generate")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Generate a faceless short video.")
    parser.add_argument("--userId", "--user_id", dest="userId", required=True)
    parser.add_argument("--topic", default=os.environ.get("TOPIC", ""),
                        help="Video topic/prompt (may be supplied via the TOPIC env var).")
    parser.add_argument("--platform", required=True,
                        help="youtube_shorts | tiktok | instagram_reels")
    parser.add_argument("--documentId", "--document_id", dest="documentId", default=None)
    parser.add_argument("--duration", type=int, default=30,
                        help="Target video length in seconds (30|60|90).")
    args = parser.parse_args(argv)
    if not args.topic or not args.topic.strip():
        parser.error("a non-empty --topic (or TOPIC env var) is required")
    return args


def build_video(topic, work_dir, duration=30):
    """Run the display pipeline and return (script, audio_path, video_path)."""
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    logger.info("Generating script...")
    script = generate_script(topic, duration)

    logger.info("Generating audio (edge-tts)...")
    audio_path = text_to_speech(script, str(work / "narration.mp3"))

    # Fetch enough vertical clips to cover the requested length (~10s each).
    clip_count = max(3, -(-duration // 10))
    logger.info("Fetching stock assets (Pexels)...")
    video_paths = fetch_assets(topic, count=clip_count, work_dir=str(work))

    logger.info("Assembling video (MoviePy)...")
    output_path = str(work / "final_video.mp4")
    video_path = assemble_video(video_paths, audio_path, script, output_path)

    return script, audio_path, video_path


def main(argv=None):
    args = parse_args(argv)
    started = time.time()

    # --- Phase 3: render the video -------------------------------------
    script, audio_path, video_path = build_video(args.topic, "assets", args.duration)
    logger.info("Rendered video at %s (%.1fs)", video_path, time.time() - started)

    # Upload the video (GitHub Releases — free, public URL) + status update.
    video_url = release_store.upload_video(
        video_path, args.userId, args.documentId or ""
    )
    firebase_store.update_status(
        args.documentId,
        "completed",
        videoUrl=video_url,
        platform=args.platform,
    )
    logger.info("Status updated -> completed. URL: %s", video_url)

    # --- Phase 4/5: publish to the target platform ---------------------
    # Publishing is BEST-EFFORT: the video is already rendered and stored, so
    # a publishing failure must NOT fail the whole pipeline. If publishing
    # succeeds we mark the doc posted; otherwise we keep it completed and
    # record the error, but still exit 0 so the GitHub Action is green.
    try:
        link = publisher.publish(
            platform=args.platform,
            video_url=video_url,
            video_path=video_path,
            title=script[:80],
            description=f"Faceless video about: {args.topic}",
            caption=script[:2200],
        )
        firebase_store.update_status(
            args.documentId,
            "posted",
            socialLink=link,
            platform=args.platform,
        )
        logger.info("Status updated -> posted. Link: %s", link)
    except Exception as exc:
        logger.warning("Publishing to %s failed (video still produced): %s", args.platform, exc)
        firebase_store.update_status(
            args.documentId, "completed", publishError=f"publish: {exc}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
