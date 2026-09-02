"""Script generation via the Groq API."""
from groq import Groq

from config import CONFIG

# Chat model identifier available on the configured Groq account.
GROQ_MODEL = "qwen/qwen3.8-27b"


def _client() -> Groq:
    return Groq(api_key=CONFIG.groq_api_key)


def generate_script(topic: str, duration: int = 30) -> str:
    """Generate a spoken script sized for a `duration`-second vertical video."""
    target_words = max(40, int(duration * 2.2))
    # Generous headroom so the model doesn't cut off mid-sentence.
    max_tokens = int(target_words * 1.6) + 60

    system_prompt = (
        f"You are a professional short-form video scriptwriter. Write an engaging, "
        f"spoken-word script suitable for a {duration}-second vertical video "
        f"(YouTube Shorts / TikTok / Instagram Reels). Use short punchy sentences, "
        f"a hook in the first line, and a clear payoff at the end. Output ONLY the "
        f"spoken narration text with no headings, no markdown, and no stage "
        f"directions. Keep it around {target_words} words so it fits within "
        f"{duration} seconds when spoken (roughly 2.2 words per second)."
    )

    client = _client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Write a {duration}-second faceless video script about: {topic}",
            },
        ],
        temperature=0.8,
        max_tokens=max_tokens,
    )

    script = response.choices[0].message.content or ""
    script = script.strip()
    if not script:
        raise RuntimeError("Groq returned an empty script.")
    return script


def generate_scenes(script: str, topic: str, n: int = 6) -> list[str]:
    """Break a spoken script into `n` visual scene prompts for AI video gen.

    Each returned string is a self-contained, detailed cinematic prompt that
    describes the visuals for one ~10-second chunk of the narration: subject,
    action, camera movement, lighting, and mood. Prompts are safe to send over JSON.
    """
    n = max(1, int(n))

    system_prompt = (
        "You are a professional cinematographer converting narration scripts into "
        "cinematic text-to-video prompts. Given a script and scene count, split it "
        f"into {n} sequential visual scenes. For each scene output EXACTLY ONE line "
        "with ONLY the visual prompt (no numbering, no labels, no quotes).\n\n"
        "Each prompt must be a detailed, photorealistic cinematic description:\n"
        "- SUBJECT: Specific person/object/environment (e.g. 'a weathered fisherman' not 'a person')\n"
        "- ACTION: What is happening with natural, fluid movement\n"
        "- CAMERA: Specific shot type and movement (slow dolly in, tracking shot, "
        "aerial establishing shot, handheld close-up, rack focus, steadicam orbit)\n"
        "- LIGHTING: Natural/dramatic (golden hour sidelight, overcast soft light, "
        "neon-lit night scene, volumetric god rays, backlit silhouette)\n"
        "- MOOD/ATMOSPHERE: Emotional tone (melancholic, triumphant, intimate, mysterious)\n"
        "- STYLE: Photorealistic, cinematic color grading, shallow depth of field\n\n"
        "NEVER use generic descriptions like 'cinematic close-up' alone. "
        "Each prompt must be visually distinct from the others. "
        "Write for a vertical 9:16 format. Do not write narration or dialogue."
    )

    client = _client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Script:\n{script}\n\n"
                    f"Topic: {topic}\n\n"
                    f"Write {n} detailed, photorealistic cinematic scene prompts, one per line."
                ),
            },
        ],
        temperature=0.85,
        max_tokens=1600,
    )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Groq returned no scene prompts.")

    scenes = []
    for line in content.splitlines():
        line = line.strip().lstrip("-0123456789. ")
        if line and line not in ("```",):
            scenes.append(line)

    # Hard safety cap: never exceed the requested scene count.
    scenes = scenes[:n]
    if len(scenes) < n:
        # Pad with specific cinematic continuations so assembly always has enough clips.
        pads = [
            "Slow dolly through a misty forest at dawn, volumetric light filtering through trees, "
            "photorealistic, cinematic color grading, vertical 9:16 composition.",
            "Aerial establishing shot of a sprawling city at golden hour, warm sidelight, "
            "shallow depth of field, photorealistic, vertical 9:16 composition.",
            "Close-up of hands working with careful precision, shallow depth of field, "
            "natural window light, intimate atmosphere, photorealistic, vertical 9:16.",
            "Tracking shot following someone walking through a crowded market, "
            "warm ambient light, vibrant colors, photorealistic, vertical 9:16 composition.",
            "Wide shot of a dramatic landscape at sunset, golden hour backlight, "
            "silhouettes against the sky, photorealistic, cinematic, vertical 9:16.",
            "Slow orbit around a detailed subject, soft diffused lighting, "
            "bokeh background, photorealistic, intimate mood, vertical 9:16 composition.",
        ]
        for i in range(n - len(scenes)):
            scenes.append(pads[i % len(pads)])
    return scenes
