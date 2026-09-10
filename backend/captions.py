"""Shared Pillow-based caption rendering for the video assemblers.

MoviePy's TextClip (Pillow backend) sizes its canvas to exactly the text
metrics, which crops descenders/apostrophes off the bottom edge. Here we
render word-wrapped captions directly with Pillow, using the tight bounding
box PLUS explicit padding on every side, so nothing is ever sliced, and an
optionally semi-transparent rounded backdrop is drawn behind the text.

Used by both assemble.py (Pexels montage) and assemble_seedance.py (AI
engine clips).
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from moviepy import CompositeVideoClip, ImageClip

import numpy as np

WIDTH = 1080
HEIGHT = 1920

CAPTION_FONT_SIZE = 58
CAPTION_COLOR = (255, 255, 255, 255)
CAPTION_STROKE = (0, 0, 0, 255)
CAPTION_STROKE_WIDTH = 4
CAPTION_MARGIN_X = 160
CAPTION_PAD_X = 36
CAPTION_PAD_Y = 26
CAPTION_BG_OPACITY = 0.5
CAPTION_RADIUS = 28
CAPTION_Y = 0.8

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]

_resolved_font: str | None = None


def resolve_font() -> str | None:
    """Return the first existing TrueType font path, or None if none found."""
    global _resolved_font
    if _resolved_font is not None:
        return _resolved_font or None
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            _resolved_font = candidate
            return candidate
    _resolved_font = ""
    return None


def _wrap_lines(text: str, font):
    """Wrap into <=2 lines that fit WIDTH - CAPTION_MARGIN_X pixels."""
    words = text.split()
    if not words:
        return []
    max_width = WIDTH - CAPTION_MARGIN_X
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if font.getlength(trial) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _text_image(chunk: str, font_path: str) -> Image.Image:
    """Render the caption text onto a transparent RGBA canvas, padded."""
    font = ImageFont.truetype(font_path, CAPTION_FONT_SIZE)
    lines = _wrap_lines(chunk, font)

    max_width = WIDTH - CAPTION_MARGIN_X
    asc, desc = font.getmetrics()
    line_height = asc + desc
    # Pad top AND bottom so glyph bowls/descenders are never cropped.
    text_h = len(lines) * line_height + 2 * CAPTION_PAD_Y
    img = Image.new("RGBA", (max_width, text_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        x = (max_width - line_w) // 2 - bbox[0]
        y = CAPTION_PAD_Y + i * line_height - bbox[1]
        draw.text(
            (x, y),
            line,
            font=font,
            fill=CAPTION_COLOR,
            stroke_width=CAPTION_STROKE_WIDTH,
            stroke_fill=CAPTION_STROKE,
        )
    return img


def make_caption(chunk: str, font_path: str, duration: float):
    """Render + style one caption chunk as a positioned MoviePy clip."""
    text_img = _text_image(chunk, font_path)
    tw, th = text_img.size

    bg_w = tw + CAPTION_PAD_X * 2
    bg_h = th + CAPTION_PAD_Y * 2
    bg = Image.new("RGBA", (bg_w, bg_h), (0, 0, 0, 0))
    bg_draw = ImageDraw.Draw(bg)
    bg_draw.rounded_rectangle(
        (0, 0, bg_w - 1, bg_h - 1),
        radius=CAPTION_RADIUS,
        fill=(0, 0, 0, int(255 * CAPTION_BG_OPACITY)),
    )
    bg.paste(text_img, (CAPTION_PAD_X, CAPTION_PAD_Y), text_img)

    arr = np.array(bg)
    rgb = arr[:, :, :3].copy()
    alpha = arr[:, :, 3].copy()
    clip = ImageClip(rgb).with_mask(ImageClip(alpha, is_mask=True))
    return (
        clip.with_position(("center", CAPTION_Y), relative=True)
        .with_duration(duration)
    )


def split_script_for_captions(script: str, max_words: int = 4, max_chars: int = 28):
    """Split a script into short caption chunks that fit on <= two lines."""
    words = script.split()
    chunks = []
    current = []
    for w in words:
        current.append(w)
        joined = " ".join(current)
        if len(current) >= max_words or len(joined) >= max_chars:
            chunks.append(joined)
            current = []
    if current:
        chunks.append(" ".join(current))
    return chunks


def build_caption_clips(script_chunks, total_duration, font_path):
    """Create timed, positioned caption clips spanning the video duration."""
    clips = []
    n = len(script_chunks)
    if n == 0:
        return clips
    per_chunk = total_duration / n
    for i, chunk in enumerate(script_chunks):
        start = i * per_chunk
        duration = min(per_chunk, total_duration - start)
        clips.append(make_caption(chunk, font_path, duration).with_start(start))
    return clips