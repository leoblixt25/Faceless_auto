"""Script generation via the Groq API."""
import re

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


def _split_script_into_chunks(script: str, n: int) -> list[str]:
    """Split a script into `n` balanced chunks, preferring sentence boundaries.

    Chunk i is guaranteed to align with the i-th equal time segment of the
    final video, so the scene visual matches what the narration says in the
    same moment the viewer hears it.
    """
    script = (script or "").strip()
    if not script:
        return [" "] * n

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if not sentences:
        sentences = [script]

    total_len = sum(len(s) for s in sentences)
    target = total_len / n

    chunks = []
    current = []
    current_len = 0
    for s in sentences:
        current.append(s)
        current_len += len(s)
        if current_len >= target and len(chunks) < n - 1:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
    if current:
        chunks.append(" ".join(current))

    # If the script has fewer sentences than chunks, split the longest chunk
    # at a word boundary until we reach the requested count.
    guard = 0
    while len(chunks) < n and guard < n * 4:
        guard += 1
        idx = max(range(len(chunks)), key=lambda i: len(chunks[i]))
        longest = chunks[idx]
        words = longest.split()
        if len(words) < 6:
            break
        half = sum(len(w) + 1 for w in words[: len(words) // 2])
        left = longest[:half].rstrip()
        right = longest[half:].lstrip()
        if not left or not right:
            break
        chunks[idx : idx + 1] = [left, right]

    return chunks[:n]


def _clean_scene_prompt(text: str, topic: str) -> str:
    """Collapse one LLM response into a single clean scene prompt line."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`").strip()
    # Strip one leading numbering/label such as "1.", "2)", "-".
    text = re.sub(r"^(?:\d+[.)]|\d+\s*[:=]|-)\s*", "", text)
    text = " ".join(text.split())
    if len(text) < 25:
        return (
            f"Close-up of a subject directly related to {topic}, slow dolly in, "
            "natural window sidelight, contemplative mood, photorealistic, vertical 9:16."
        )
    return text


def generate_scenes(
    script: str, topic: str, n: int = 6, cinematic: str | None = None
) -> list[str]:
    """Generate `n` visual scene prompts, ONE per narration chunk.

    The narration script is split into `n` balanced chunks deterministically.
    Each chunk gets its OWN Groq call, so scene i ALWAYS visualizes the exact
    narration spoken during time-segment i — no cross-page confusion. Each
    prompt is safe to send over JSON.

    `cinematic`: optional global visual scenario/director's note applied to
    every scene (e.g. "arri alexa footage, shallow depth of field, warm grade,
    slow motion").
    """
    n = max(1, int(n))
    chunks = _split_script_into_chunks(script, n)

    system_prompt = (
        "You are a cinematographer directing AI video generation. Convert ONE "
        "narration chunk into EXACTLY ONE scene prompt.\n"
        "The SUBJECT and the ACTION MUST be drawn DIRECTLY from the narration "
        "chunk's content: the visual must show what the narration is talking "
        "about, not a generic unrelated shot.\n"
        "Every prompt must include:\n"
        "- SUBJECT: a specific, concrete person/place/object tied to the chunk "
        "('a young woman typing on a laptop' not 'a person working')\n"
        "- ACTION: what the subject is doing, matching the narration content\n"
        "- CAMERA: one shot type + movement (slow dolly in, tracking shot, "
        "aerial drone shot, handheld close-up, rack focus pull, steadicam "
        "orbit, static wide shot, slow zoom, POV shot)\n"
        "- LIGHTING: one setup (golden hour sidelight, overcast soft light, "
        "neon night glow, volumetric god rays, backlit silhouette, dim indoor "
        "warm light)\n"
        "- MOOD: one emotional tone matching the narration\n"
        "FORMAT: [SUBJECT] [ACTION], [CAMERA], [LIGHTING], [MOOD], "
        "photorealistic, vertical 9:16.\n"
        "NEVER include dialogue, narration text, captions or watermarks in the visual."
    )

    client = _client()

    scenes = []
    for i, chunk in enumerate(chunks):
        prev = " ".join(chunks[i - 1].split()[:6]) if i > 0 else "this is the first chunk"
        nxt = (
            " ".join(chunks[i + 1].split()[:6])
            if i + 1 < len(chunks)
            else "this is the final chunk"
        )
        user = (
            f"TOPIC: {topic}\n"
            + (
                f"CINEMATIC SCENARIO (apply this global visual style): {cinematic}\n"
                if cinematic
                else ""
            )
            + f"NARRATION CHUNK {i + 1} of {n} — visualize ONLY this:\n{chunk}\n\n"
            f"PREVIOUS CHUNK (continuity): {prev}\n"
            f"NEXT CHUNK (continuity): {nxt}\n\n"
            "Write EXACTLY ONE scene prompt in the required format."
        )
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user},
            ],
            temperature=0.8,
            max_tokens=220,
        )
        text = (response.choices[0].message.content or "").strip()
        scenes.append(_clean_scene_prompt(text, topic))

    return scenes[:n]
