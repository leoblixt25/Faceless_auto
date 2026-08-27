"""Script generation via the Groq API (Llama 3)."""
from groq import Groq

from config import CONFIG

SYSTEM_PROMPT = (
    "You are a professional short-form video scriptwriter. Write a short, "
    "engaging, spoken-word script suitable for a 30-second vertical video "
    "(YouTube Shorts / TikTok / Instagram Reels). Use short punchy sentences, "
    "a hook in the first line, and a clear payoff at the end. Output ONLY the "
    "spoken narration text with no headings, no markdown, and no stage "
    "directions. Keep it between 60 and 80 words so it fits within ~30 seconds "
    "when spoken."
)


def generate_script(topic: str) -> str:
    """Generate a ~30 second spoken script about `topic` using Groq's Llama 3."""
    client = Groq(api_key=CONFIG.groq_api_key)

    response = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Write a 30-second faceless video script about: {topic}",
            },
        ],
        temperature=0.8,
        max_tokens=220,
    )

    script = response.choices[0].message.content or ""
    script = script.strip()
    if not script:
        raise RuntimeError("Groq returned an empty script.")
    return script
