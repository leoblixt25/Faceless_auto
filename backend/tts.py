"""Text-to-speech using edge-tts (free, no external API)."""
import asyncio
from pathlib import Path

import edge_tts

# A clear, engaging English voice available in edge-tts.
DEFAULT_VOICE = "en-US-JennyNeural"


def text_to_speech(text: str, output_path: str, voice: str = DEFAULT_VOICE) -> str:
    """Convert `text` to an MP3 file at `output_path` using edge-tts."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    async def _run():
        communicate = edge_tts.Communicate(text, voice=voice)
        await communicate.save(str(output))

    asyncio.run(_run())

    if not output.exists():
        raise RuntimeError(f"TTS failed: {output_path} was not created.")
    return str(output)
