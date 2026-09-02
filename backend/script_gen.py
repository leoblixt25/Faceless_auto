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

    Each prompt MUST directly visualize the corresponding section of the
    narration script. Prompts are safe to send over JSON.
    """
    n = max(1, int(n))

    system_prompt = (
        "You are a professional cinematographer. Your job is to convert a spoken "
        "narration script into SEQUENTIAL visual scene prompts for AI video generation.\n\n"
        "CRITICAL RULES:\n"
        "1. EACH prompt MUST directly visualize the corresponding section of the narration.\n"
        "   Read the script carefully — the visuals must MATCH what is being said.\n"
        "2. Split the script into {n} equal parts. Each prompt covers one part.\n"
        "3. Output EXACTLY {n} lines, one prompt per line. No numbering, no labels.\n\n"
        "EACH prompt must contain ALL of these elements:\n"
        "- SUBJECT: A specific, concrete person/place/object that relates to the narration\n"
        "  (e.g. 'a young woman typing on a laptop' not 'a person working')\n"
        "- ACTION: What the subject is doing — must match the narration content\n"
        "  (e.g. 'scrolling through job listings with a focused expression')\n"
        "- CAMERA: One specific shot type and movement\n"
        "  Options: slow dolly in, tracking shot, aerial drone shot, handheld close-up,\n"
        "  rack focus pull, steadicam orbit, static wide shot, slow zoom, POV shot\n"
        "- LIGHTING: One specific lighting setup\n"
        "  Options: golden hour sidelight, overcast soft light, neon night glow,\n"
        "  volumetric god rays, backlit silhouette, harsh midday sun, dim indoor warm light\n"
        "- MOOD: One emotional tone (e.g. hopeful, melancholic, intense, peaceful)\n\n"
        "FORMAT each prompt as:\n"
        "[SUBJECT] [ACTION], [CAMERA], [LIGHTING], [MOOD], photorealistic, vertical 9:16.\n\n"
        "EXAMPLE for script about 'Why most people fail at learning to code':\n"
        "1. A frustrated young adult staring at a laptop screen full of red error messages, "
        "slow dolly in, harsh overhead fluorescent light, defeated mood, photorealistic, vertical 9:16.\n"
        "2. Close-up of fingers hovering uncertainly over a keyboard, rack focus pull, "
        "dim warm desk lamp light, hesitant mood, photorealistic, vertical 9:16.\n"
        "3. A person watching a coding tutorial on their phone while lying in bed, "
        "tracking shot, blue screen glow in dark room, distracted mood, photorealistic, vertical 9:16.\n"
        "4. Hands typing confidently on a mechanical keyboard, steady orbit, "
        "golden hour window sidelight, determined mood, photorealistic, vertical 9:16.\n"
        "5. A terminal window showing successful code output, slow zoom in, "
        "bright screen glow, triumphant mood, photorealistic, vertical 9:16.\n"
        "6. Wide shot of a person working at a standing desk with multiple monitors, "
        "aerial establishing shot, natural daylight, focused mood, photorealistic, vertical 9:16.\n\n"
        "NEVER:\n"
        "- Use generic prompts like 'cinematic close-up' without a specific subject\n"
        "- Write prompts that don't relate to the narration content\n"
        "- Repeat the same subject/camera/lighting across multiple prompts\n"
        "- Include dialogue, narration, or text in the visual"
    )

    client = _client()

    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system_prompt.format(n=n)},
            {
                "role": "user",
                "content": (
                    f"TOPIC: {topic}\n\n"
                    f"NARRATION SCRIPT:\n{script}\n\n"
                    f"Write {n} scene prompts that DIRECTLY visualize each section of the script above."
                ),
            },
        ],
        temperature=0.8,
        max_tokens=1800,
    )

    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise RuntimeError("Groq returned no scene prompts.")

    scenes = []
    for line in content.splitlines():
        line = line.strip().lstrip("-0123456789. ")
        if line and line not in ("```",) and len(line) > 20:
            scenes.append(line)

    # Hard safety cap: never exceed the requested scene count.
    scenes = scenes[:n]
    if len(scenes) < n:
        # Pad with topic-specific cinematic continuations.
        pads = [
            f"Close-up of a person thinking deeply about {topic}, slow dolly in, "
            "natural window sidelight, contemplative mood, photorealistic, vertical 9:16.",
            f"Tracking shot through a workspace related to {topic}, "
            "soft ambient light, focused mood, photorealistic, vertical 9:16.",
            f"Hands working on something related to {topic}, rack focus pull, "
            "warm desk lamp light, determined mood, photorealistic, vertical 9:16.",
            f"Wide establishing shot of a location relevant to {topic}, "
            "golden hour sidelight, atmospheric mood, photorealistic, vertical 9:16.",
            f"Slow orbit around a key object from {topic}, "
            "dramatic rim light, mysterious mood, photorealistic, vertical 9:16.",
            f"POV shot experiencing {topic} firsthand, steady tracking, "
            "natural daylight, immersive mood, photorealistic, vertical 9:16.",
        ]
        for i in range(n - len(scenes)):
            scenes.append(pads[i % len(pads)])
    return scenes
