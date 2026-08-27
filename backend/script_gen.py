"""Script generation via the Groq API."""
from groq import Groq

from config import CONFIG

# Chat model identifier available on the configured Groq account.
GROQ_MODEL = "qwen/qwen3.8-27b"

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

    client = Groq(api_key=CONFIG.groq_api_key)

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
