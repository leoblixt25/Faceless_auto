"""Assembly of AI-generated Seedance clips into the final video.

Unlike the Pexels path (assemble.py) the Seedance clips are already 9:16 and
10s each, so this module concatenates them in order, adds the TTS narration as
the audio track, overlays captions, and exports the final vertical MP4.
"""
from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    VideoFileClip,
    concatenate_videoclips,
)

from captions import build_caption_clips, resolve_font, split_script_for_captions

WIDTH = 1080
HEIGHT = 1920
FPS = 30


def _fit_vertical(clip):
    """Resize/cover a 9:16-friendly clip to exactly 1080x1920."""
    w, h = clip.size
    if (w, h) == (WIDTH, HEIGHT):
        return clip
    target_ratio = WIDTH / HEIGHT
    clip_ratio = w / h

    if clip_ratio > target_ratio:
        clip = clip.resized(height=HEIGHT)
        new_w = int(clip.size[0])
        excess = new_w - WIDTH
        clip = clip.cropped(x1=excess // 2, x2=excess // 2 + WIDTH)
    else:
        clip = clip.resized(width=WIDTH)
        new_h = int(clip.size[1])
        excess = new_h - HEIGHT
        top = max(0, (new_h - HEIGHT) // 2)
        clip = clip.cropped(y1=top, y2=top + HEIGHT)
    return clip


def assemble_seedance(
    scene_video_paths,
    audio_path,
    script,
    output_path,
):
    """Concatenate Seedance clips in order + TTS audio + captions -> final MP4."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not scene_video_paths:
        raise RuntimeError("assemble_seedance called with no scene videos.")

    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration or 30

    clips = []
    for path in scene_video_paths:
        clip = VideoFileClip(str(path))
        clip = _fit_vertical(clip)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    # Trim to audio length if scenes are longer than the narration.
    if video.duration > audio_duration + 0.5:
        video = video.subclipped(0, audio_duration)
    video = video.with_audio(audio)

    font = resolve_font()
    if font:
        chunks = split_script_for_captions(script)
        captions = build_caption_clips(chunks, audio_duration, font)
        if captions:
            video = CompositeVideoClip([video, *captions], size=(WIDTH, HEIGHT))

    video.write_videofile(
        str(output),
        fps=FPS,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        bitrate="5000k",
        threads=2,
        logger="bar",
    )

    for clip in clips:
        try:
            clip.close()
        except Exception:
            pass
    audio.close()
    video.close()

    return str(output)