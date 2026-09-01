"""Assembly of AI-generated Seedance clips into the final video.

Unlike the Pexels path (assemble.py) the Seedance clips are already 9:16 and
10s each, so this module concatenates them in order, adds the TTS narration as
the audio track, overlays captions, and exports the final vertical MP4.
"""
from pathlib import Path

from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    TextClip,
    VideoFileClip,
    concatenate_videoclips,
)

WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Keep the same font resolution as assemble.py.
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_resolved_font: str | None = None


def _resolve_font() -> str | None:
    global _resolved_font
    if _resolved_font is not None:
        return _resolved_font or None
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            _resolved_font = candidate
            return candidate
    _resolved_font = ""
    return None


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


def _subtitle_clips(script_chunks, total_duration):
    clips = []
    n = len(script_chunks)
    if n == 0:
        return clips

    font = _resolve_font()
    if not font:
        return clips

    per_chunk = total_duration / n
    for i, chunk in enumerate(script_chunks):
        start = i * per_chunk
        duration = min(per_chunk, total_duration - start)
        txt = TextClip(
            text=chunk,
            font_size=52,
            color="white",
            stroke_color="black",
            stroke_width=3,
            font=font,
            method="caption",
            size=(WIDTH - 160, None),
        )
        txt = txt.with_position(("center", 0.78), relative=True).with_duration(
            duration
        ).with_start(start)
        clips.append(txt)
    return clips


def split_script_for_captions(script: str, max_words: int = 5):
    """Split a script into short caption chunks of <= max_words words."""
    words = script.split()
    chunks = []
    current = []
    for w in words:
        current.append(w)
        if len(current) >= max_words or (len(" ".join(current)) >= 45):
            chunks.append(" ".join(current))
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


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

    chunks = split_script_for_captions(script)
    captions = _subtitle_clips(chunks, audio_duration)
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