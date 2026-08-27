"""Video assembly with MoviePy.

Concatenates stock clips, cover-crops them to 1080x1920, adds the TTS audio,
overlays simple caption subtitles, and exports a final MP4.
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

# Possible true-type font file paths (Pillow needs a file, not a family name).
_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_resolved_font: str | None = None


def _resolve_font() -> str | None:
    """Return the first existing font file path, or None if none is found."""
    global _resolved_font
    if _resolved_font is not None:
        return _resolved_font or None
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            _resolved_font = candidate
            return candidate
    # Try resolving by name via Pillow's default font as a last resort.
    _resolved_font = ""
    return None


def _cover_resize(clip):
    """Resize + crop a clip so it fully covers the 1080x1920 frame."""
    clip_w, clip_h = clip.size
    target_ratio = WIDTH / HEIGHT
    clip_ratio = clip_w / clip_h

    if clip_ratio > target_ratio:
        # Too wide -> scale by height, then crop width.
        clip = clip.resized(height=HEIGHT)
        new_w = int(clip.size[0])
        excess = new_w - WIDTH
        clip = clip.cropped(x1=excess // 2, x2=excess // 2 + WIDTH)
    else:
        # Too tall -> scale by width, then crop height.
        clip = clip.resized(width=WIDTH)
        new_h = int(clip.size[1])
        excess = new_h - HEIGHT
        top = max(0, (new_h - HEIGHT) // 2)  # prefer center; keep content
        clip = clip.cropped(y1=top, y2=top + HEIGHT)

    return clip


def _mirror_if_landscape_fallback(clip):
    """No-op in Phase 3; reserved for future enhancement."""
    return clip


def build_subtitle_clips(script_chunks, total_duration):
    """Create a list of caption TextClips timed across the video duration."""
    clips = []
    n = len(script_chunks)
    if n == 0:
        return clips

    font = _resolve_font()
    if not font:
        # No usable font file -> render without captions rather than crash.
        return clips

    per_chunk = total_duration / n
    font_size = 52
    for i, chunk in enumerate(script_chunks):
        start = i * per_chunk
        duration = min(per_chunk, total_duration - start)
        txt = TextClip(
            text=chunk,
            font_size=font_size,
            color="white",
            stroke_color="black",
            stroke_width=3,
            font=font,
            method="caption",
            size=(WIDTH - 160, None),
        )
        # Position centrally, slightly above the bottom.
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


def assemble_video(video_paths, audio_path, script, output_path):
    """Build the final 1080x1920 video with audio + captions."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    audio = AudioFileClip(audio_path)
    audio_duration = audio.duration or 30

    clips = []
    for path in video_paths:
        clip = VideoFileClip(path)
        clip = _cover_resize(clip)
        clips.append(clip)

    video = concatenate_videoclips(clips, method="compose")

    # Match the video duration to the narration length.
    if video.duration > audio_duration + 0.5:
        video = video.subclipped(0, audio_duration)
    video = video.with_audio(audio)

    # Build captions.
    chunks = split_script_for_captions(script)
    captions = build_subtitle_clips(chunks, audio_duration)

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

    # Cleanup raw clips.
    for clip in clips:
        try:
            clip.close()
        except Exception:
            pass
    audio.close()
    video.close()

    return str(output)
