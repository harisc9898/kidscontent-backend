"""
KidsContent.ai — Backend v3.0 — UNLIMITED FREE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LLM Stack (Triple Fallback — Completely Free):
  1. Google Gemini 2.5 Flash  → 500 req/day FREE (primary)
  2. Groq Llama 3.3 70B       → 1000 req/day FREE (backup)
  3. OpenRouter (free models)  → unlimited FREE (emergency)

Image Stack:
  1. ModelsLab FREE tier       → 100 calls/day, 10,000+ models
  2. Pollinations.AI           → unlimited FREE fallback

Voice: Edge TTS (Microsoft Neural — FREE forever)
Music: Pollinations Audio (FREE forever)
Video: FFmpeg Ken Burns (FREE forever)
Upload: YouTube Data API v3 (FREE, 6/day)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, json, time, random, asyncio, subprocess, re, shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── ENV VARS (set in Render dashboard) ───────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY          = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.environ.get("OPENROUTER_API_KEY", "")
MODELSLAB_API_KEY     = os.environ.get("MODELSLAB_API_KEY", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(title="KidsContent.ai API", version="3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

WORK_DIR = Path("/tmp/kidscontent")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

pipeline_status: dict = {
    "running": False, "step": "", "step_index": 0,
    "total_steps": 7, "last_result": None, "error": None,
    "llm_used": None, "image_source": None,
}

# ── DEFAULT CONTENT PRESETS (used when no custom topic is given) ──────────────
DEFAULT_TOPICS = [
    # Kids / nursery
    "nursery rhyme about farm animals",
    "original lullaby about stars and moon",
    "counting song 1 to 10 for toddlers",
    "ABC alphabet learning song",
    "colors and shapes learning song",
    "dinosaurs going on an adventure",
    # Bedtime
    "bedtime story about a brave little bunny",
    "gentle bedtime story about a sleepy cloud",
    "short bedtime story about a magical forest",
    # Animal facts
    "amazing facts about elephants for kids",
    "fun facts about penguins for children",
    "wow facts about blue whales for kids",
    # Seasonal
    "Christmas song for toddlers",
    "Eid celebration song for children",
    "Halloween fun song for kids",
    # Broad educational
    "vegetables and fruits song for kids",
    "weather song about rain sunshine and rainbows",
    "ocean animals swimming and dancing",
    "space adventure song about planets",
    "kindness and sharing values song for children",
]

CONTENT_TYPES = {
    "rhyme":   {"label": "Nursery Rhyme",   "icon": "🎵"},
    "story":   {"label": "Bedtime Story",   "icon": "🌙"},
    "facts":   {"label": "Facts for Kids",  "icon": "🦁"},
    "learning":{"label": "Learning Song",   "icon": "🔤"},
    "custom":  {"label": "Custom",          "icon": "✨"},
}

# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    topic: Optional[str] = Field(default=None,
        description="Custom topic e.g. 'dinosaurs for kids' or 'Eid song'. Leave empty for auto.")
    content_type: Optional[str] = Field(default=None,
        description="rhyme | story | facts | learning | auto")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — TRIPLE-STACKED FREE LLM CONTENT GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def build_prompt(topic: str, content_type: str) -> str:
    """Build a killer content generation prompt for any topic."""

    type_instructions = {
        "rhyme": f"""Create a VIRAL original nursery rhyme for toddlers (age 1-5) about: {topic}
- 4 verses × 4 lines, AABB or ABAB rhyme scheme
- Catchy 2-line chorus repeated after every verse
- Fun sound effects (moo! splash! zoom! giggle!)
- Educational element woven in naturally (counting, colors, animals)
- Upbeat, happy, highly singable""",

        "story": f"""Create a magical 60-second bedtime story for young children (age 2-6) about: {topic}
- Warm peaceful opening that sets a cozy mood
- Simple gentle adventure (problem solved kindly)
- Happy peaceful ending with a moral
- Soothing repetitive phrases children love
- End with a sweet "goodnight / sweet dreams" closing
- Under 200 words, calm gentle tone""",

        "facts": f"""Create an exciting facts video script for kids (age 4-8) about: {topic}
- Hook opening: "Did you know..." or "WOW! Get ready to be amazed!"
- 5 incredible age-appropriate facts with fun comparisons kids understand
- Enthusiasm and energy throughout
- Mind-blowing closing fact
- Under 180 words, fast-paced and exciting""",

        "learning": f"""Create an original educational song for toddlers (age 2-5) about: {topic}
- Fun catchy intro line
- 3-4 educational verses × 4 lines each
- Simple repeating chorus children can memorize
- Clear learning objective per verse
- Repetition of key concepts
- Upbeat and memorable""",
    }

    instruction = type_instructions.get(content_type, type_instructions["rhyme"])

    return instruction + """

Also generate KILLER YouTube Shorts SEO optimised for maximum virality.
Return ONLY valid JSON with zero markdown, zero backticks, zero explanation:
{
  "title": "YouTube title max 70 chars, start with emoji, make it irresistible to click",
  "content": "full script/rhyme/story/facts here",
  "description": "170 word YouTube Shorts description. First 2 sentences are the search hook. Include keywords parents search for. End with subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "hashtags": "#Shorts #KidsSongs #NurseryRhymes #ChildrensMusic #ToddlerSongs",
  "scenes": [
    "vivid colorful scene description 1 for image generation, max 15 words",
    "scene 2",
    "scene 3",
    "scene 4",
    "scene 5"
  ],
  "voice_style": "cheerful|gentle|energetic|soothing",
  "content_type": "rhyme|story|facts|learning"
}"""


def call_gemini(prompt: str) -> Optional[str]:
    """Google Gemini 2.5 Flash — 500 req/day FREE, best reasoning."""
    if not GEMINI_API_KEY:
        return None
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.9, "maxOutputTokens": 1500}},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini failed: {e}")
    return None


def call_groq(prompt: str) -> Optional[str]:
    """Groq Llama 3.3 70B — 1000 req/day FREE, ultra fast 300+ tok/s."""
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.9, "max_tokens": 1500},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq failed: {e}")
    return None


def call_openrouter(prompt: str) -> Optional[str]:
    """OpenRouter free models — emergency fallback, always available."""
    if not OPENROUTER_API_KEY:
        # Try without key (some models work without auth)
        headers = {"Content-Type": "application/json",
                   "HTTP-Referer": "https://kidscontent-api.onrender.com"}
    else:
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                   "Content-Type": "application/json",
                   "HTTP-Referer": "https://kidscontent-api.onrender.com"}

    # Try multiple free models in order
    free_models = [
        "meta-llama/llama-3.3-70b-instruct:free",
        "google/gemma-3-27b-it:free",
        "mistralai/mistral-7b-instruct:free",
        "qwen/qwen3-8b:free",
    ]
    for model in free_models:
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.9, "max_tokens": 1500},
                timeout=90)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                if text and len(text) > 100:
                    print(f"  OpenRouter used model: {model}")
                    return text
        except Exception as e:
            print(f"OpenRouter {model} failed: {e}")
            continue
    return None


def generate_content(topic: Optional[str], content_type: Optional[str]) -> dict:
    """Generate killer content using triple-stacked free LLMs."""

    # Auto-select topic if not provided
    if not topic:
        topic = random.choice(DEFAULT_TOPICS)
        print(f"🎲 Auto-selected topic: {topic}")
    else:
        print(f"🎯 Custom topic: {topic}")

    # Auto-detect content type from topic
    if not content_type or content_type == "auto":
        topic_lower = topic.lower()
        if any(w in topic_lower for w in ["story", "tale", "bedtime", "night", "sleep"]):
            content_type = "story"
        elif any(w in topic_lower for w in ["fact", "amazing", "did you know", "wow"]):
            content_type = "facts"
        elif any(w in topic_lower for w in ["abc", "123", "learn", "count", "alphabet", "color", "shape", "number"]):
            content_type = "learning"
        else:
            content_type = "rhyme"

    print(f"📝 Content type: {content_type}")
    prompt = build_prompt(topic, content_type)

    # Try LLMs in order: Gemini → Groq → OpenRouter
    raw = None
    llm_used = None

    print("🧠 Trying Gemini 2.5 Flash...")
    raw = call_gemini(prompt)
    if raw:
        llm_used = "Gemini 2.5 Flash"
    else:
        print("⚡ Trying Groq Llama 3.3 70B...")
        raw = call_groq(prompt)
        if raw:
            llm_used = "Groq Llama 3.3 70B"
        else:
            print("🔄 Trying OpenRouter free models...")
            raw = call_openrouter(prompt)
            if raw:
                llm_used = "OpenRouter (free)"

    if not raw:
        raise Exception("All 3 LLM providers failed. Check API keys.")

    print(f"✅ Content generated via {llm_used}")
    pipeline_status["llm_used"] = llm_used

    # Parse JSON response — robust cleaning pipeline
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip()).rstrip("`").strip()

    # Extract JSON block if LLM added extra text before/after
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        raw = json_match.group(0)

    # Remove ALL invalid control characters (the main cause of this error)
    # Keep only: tab(\t), newline(\n), carriage return(\r) — remove everything else 0x00-0x1f
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', raw)

    # Fix common LLM JSON mistakes
    raw = raw.replace('\r\n', '\\n').replace('\r', '\\n')

    # Remove trailing commas before } or ] (invalid JSON)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        # Last resort: use ast-style aggressive cleaning
        raw_clean = raw.encode('utf-8', errors='ignore').decode('utf-8')
        data = json.loads(raw_clean)
    data["topic"] = topic
    data["content_type"] = content_type
    data["llm_used"] = llm_used
    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 — EDGE TTS VOICE (Microsoft Neural — FREE forever, no key)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
VOICE_PROFILES = {
    "cheerful":  {"voice": "en-US-AriaNeural",    "rate": "+8%",  "pitch": "+10Hz"},
    "gentle":    {"voice": "en-GB-SoniaNeural",   "rate": "-8%",  "pitch": "-2Hz"},
    "energetic": {"voice": "en-US-GuyNeural",     "rate": "+10%", "pitch": "+5Hz"},
    "soothing":  {"voice": "en-GB-LibbyNeural",   "rate": "-12%", "pitch": "-4Hz"},
    "default":   {"voice": "en-US-JennyNeural",   "rate": "+3%",  "pitch": "+3Hz"},
}


async def _tts_async(text, voice, rate, pitch, audio_out, srt_out):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    sub = edge_tts.SubMaker()
    with open(audio_out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                sub.feed(chunk)
    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(sub.get_srt())


def generate_voice(content: str, voice_style: str, audio_path: str, srt_path: str):
    profile = VOICE_PROFILES.get(voice_style, VOICE_PROFILES["default"])
    asyncio.run(_tts_async(
        text=content,
        voice=profile["voice"],
        rate=profile["rate"],
        pitch=profile["pitch"],
        audio_out=audio_path,
        srt_out=srt_path,
    ))
    print(f"✅ Voice: {profile['voice']} ({voice_style})")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION (ModelsLab FREE → Pollinations fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MODELSLAB_KIDS_MODELS = [
    "flux",              # Best quality, fast
    "sdxl",              # High quality
    "dreamshaper-xl",    # Great for illustrations
    "realistic-vision-v6", # Vivid realistic
]


def generate_image_modelslab(scene: str, output_path: str) -> bool:
    """ModelsLab FREE tier — 100 calls/day, 10,000+ models, best quality."""
    if not MODELSLAB_API_KEY:
        return False
    try:
        prompt = (
            f"{scene}, children's book illustration style, "
            f"bright vibrant colors, cute characters, safe for kids, "
            f"no text, no watermarks, vertical 9:16 composition, "
            f"ultra detailed, high quality, colorful, joyful"
        )
        payload = {
            "key": MODELSLAB_API_KEY,
            "model_id": random.choice(MODELSLAB_KIDS_MODELS),
            "prompt": prompt,
            "negative_prompt": "ugly, blurry, text, watermark, adult, violence, scary, dark",
            "width": "576",
            "height": "1024",
            "samples": "1",
            "num_inference_steps": "20",
            "guidance_scale": 7.5,
            "safety_checker": "yes",
            "enhance_prompt": "yes",
        }
        resp = requests.post(
            "https://modelslab.com/api/v6/realtime/text2img",
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=120,
        )
        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "success" and result.get("output"):
                img_url = result["output"][0]
                img_resp = requests.get(img_url, timeout=60)
                if img_resp.status_code == 200 and len(img_resp.content) > 5000:
                    Path(output_path).write_bytes(img_resp.content)
                    return True
    except Exception as e:
        print(f"  ModelsLab failed: {e}")
    return False


def generate_image_pollinations(scene: str, output_path: str) -> bool:
    """Pollinations.AI — unlimited FREE fallback, no key needed."""
    try:
        prompt = (
            f"{scene}, bright vibrant children's illustration, "
            f"colorful cartoon style, cute, joyful, no text, no watermarks"
        )
        encoded = requests.utils.quote(prompt)
        url = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width=1080&height=1920&nologo=true&model=flux"
            f"&seed={random.randint(1000, 99999)}"
        )
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 5000:
            Path(output_path).write_bytes(r.content)
            return True
    except Exception as e:
        print(f"  Pollinations failed: {e}")
    return False


def generate_image(scene: str, output_path: str) -> str:
    """Try ModelsLab first, fall back to Pollinations."""
    # Try ModelsLab (best quality)
    if MODELSLAB_API_KEY and generate_image_modelslab(scene, output_path):
        pipeline_status["image_source"] = "ModelsLab"
        return "modelslab"
    # Fallback to Pollinations (unlimited free)
    if generate_image_pollinations(scene, output_path):
        pipeline_status["image_source"] = "Pollinations"
        return "pollinations"
    return None


def build_scene_clip(scene: str, duration: float, output_path: str) -> bool:
    """Generate image then animate with Ken Burns motion effect."""
    img_path = output_path.replace(".mp4", ".jpg")
    source = generate_image(scene, img_path)
    if not source:
        return False

    frames = int(duration * 25)
    kb_effects = [
        "zoompan=z='zoom+0.0015':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "zoompan=z='zoom+0.001':x='min(max(0,iw/2-(iw/zoom/2)+4*on),iw-iw/zoom)':y='ih/2-(ih/zoom/2)'",
        "zoompan=z='zoom+0.001':x='max(0,iw/2-(iw/zoom/2)-4*on)':y='ih/2-(ih/zoom/2)'",
    ]
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x1a1a2e,"
            f"{random.choice(kb_effects)}:d={frames}:s=1080x1920:fps=25"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180)
    Path(img_path).unlink(missing_ok=True)
    return result.returncode == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — BACKGROUND MUSIC (Pollinations Audio — FREE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUSIC_STYLES = {
    "rhyme":    "cheerful upbeat children piano xylophone melody",
    "story":    "soft gentle lullaby piano bedtime peaceful music",
    "facts":    "adventurous exciting kids nature documentary music",
    "learning": "fun educational bouncy children tune xylophone",
    "default":  "bright cheerful children background music loop",
}


def generate_music(content_type: str, music_path: str) -> bool:
    style = MUSIC_STYLES.get(content_type, MUSIC_STYLES["default"])
    url = f"https://audio.pollinations.ai/{requests.utils.quote(style)}"
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            return True
    except Exception as e:
        print(f"Music gen failed: {e}")
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — VIDEO ASSEMBLY (FFmpeg — FREE)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 10.0


def srt_to_drawtext(srt_path: str) -> Optional[str]:
    try:
        content = Path(srt_path).read_text(encoding="utf-8")
    except Exception:
        return None
    filters = []
    for block in re.split(r"\n\n+", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            times = lines[1].replace(",", ".").split(" --> ")
            start = _t2s(times[0].strip())
            end = _t2s(times[1].strip())
            text = " ".join(lines[2:]).strip()
            text = (text.replace("'", "\\'").replace(":", "\\:")
                       .replace("[", "\\[").replace("]", "\\]"))
            if len(text) > 32:
                text = text[:32] + "..."
            filters.append(
                f"drawtext=text='{text}'"
                f":fontsize=72:fontcolor=white:borderw=5:bordercolor=black"
                f":x=(w-text_w)/2:y=(h-220)"
                f":enable='between(t,{start:.2f},{end:.2f})'"
            )
        except Exception:
            continue
    return ",".join(filters) if filters else None


def _t2s(t: str) -> float:
    h, m, rest = t.split(":")
    s, ms = rest.split(".")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000


def assemble_video(clips: list, voice_p: str, music_p: Optional[str],
                   srt_p: str, output_p: str):
    ts = str(int(time.time()))

    # Concat clips
    txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", txt, "-c", "copy", concat_out],
                   capture_output=True, timeout=120)

    # Trim to voice + 0.5s padding, max 59s for Shorts
    voice_dur = min(get_duration(voice_p) + 0.5, 59.0)
    trimmed = str(WORK_DIR / f"trimmed_{ts}.mp4")
    subprocess.run(["ffmpeg", "-y", "-i", concat_out, "-t", str(voice_dur),
                    "-c:v", "libx264", "-crf", "22", "-preset", "fast",
                    "-pix_fmt", "yuv420p", trimmed],
                   capture_output=True, timeout=180)

    # Burn subtitles
    sub_filter = srt_to_drawtext(srt_p)
    subbed = str(WORK_DIR / f"subbed_{ts}.mp4")
    if sub_filter:
        r = subprocess.run(["ffmpeg", "-y", "-i", trimmed, "-vf", sub_filter,
                            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
                            "-pix_fmt", "yuv420p", subbed],
                           capture_output=True, timeout=300)
        subbed = subbed if r.returncode == 0 else trimmed
    else:
        subbed = trimmed

    # Mix voice + optional background music
    if music_p and Path(music_p).exists():
        filt = ("[1:a]volume=1.5[voice];"
                "[2:a]volume=0.20,aloop=loop=-1:size=2e+09[music];"
                "[voice][music]amix=inputs=2:duration=first[afinal]")
        subprocess.run(["ffmpeg", "-y",
                        "-i", subbed, "-i", voice_p, "-i", music_p,
                        "-filter_complex", filt,
                        "-map", "0:v", "-map", "[afinal]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", output_p],
                       capture_output=True, timeout=300)
    else:
        subprocess.run(["ffmpeg", "-y", "-i", subbed, "-i", voice_p,
                        "-map", "0:v", "-map", "1:a",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
                        "-shortest", "-movflags", "+faststart", output_p],
                       capture_output=True, timeout=300)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 6 — YOUTUBE UPLOAD WITH FULL SEO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def get_yt_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID, "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN, "grant_type": "refresh_token",
    })
    if r.status_code != 200:
        raise Exception(f"Token refresh failed: {r.text[:200]}")
    return r.json()["access_token"]


def upload_youtube(video_path: str, data: dict) -> str:
    token = get_yt_token()
    description = (
        f"{data['description']}\n\n"
        f"🔔 Subscribe for new videos every day!\n"
        f"👍 Like if your little one enjoyed this!\n"
        f"💬 Tell us what topic you want next!\n\n"
        f"{data.get('hashtags', '#Shorts #KidsSongs #NurseryRhymes')}"
    )
    tags = list(dict.fromkeys(
        data.get("tags", []) +
        ["kids songs", "children music", "toddler", "nursery rhymes",
         "educational", "shorts", "youtube shorts", "kids tv",
         data.get("content_type", "rhyme")]
    ))[:15]

    metadata = {
        "snippet": {"title": data["title"][:100], "description": description[:4900],
                    "tags": tags, "categoryId": "22", "defaultLanguage": "en"},
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": True,
                   "madeForKids": True},
    }
    init_r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4"},
        json=metadata)
    if init_r.status_code != 200:
        raise Exception(f"YouTube init {init_r.status_code}: {init_r.text[:200]}")

    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(init_r.headers["Location"],
                        headers={"Content-Type": "video/mp4",
                                 "Content-Length": str(len(video_bytes))},
                        data=video_bytes, timeout=600)
    if up_r.status_code not in (200, 201):
        raise Exception(f"Upload {up_r.status_code}: {up_r.text[:200]}")
    return up_r.json().get("id", "unknown")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def full_pipeline(topic: Optional[str], content_type: Optional[str]):
    if pipeline_status["running"]:
        return
    pipeline_status["running"] = True
    pipeline_status["error"] = None
    pipeline_status["llm_used"] = None
    pipeline_status["image_source"] = None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = WORK_DIR / ts
    session.mkdir(exist_ok=True)

    try:
        # 1 — Generate content
        pipeline_status["step"] = "Generating killer content with AI..."
        pipeline_status["step_index"] = 1
        data = generate_content(topic, content_type)
        print(f"✅ Title: {data['title']}")

        # 2 — Voice synthesis
        pipeline_status["step"] = "Synthesizing voice with Edge TTS..."
        pipeline_status["step_index"] = 2
        voice_p = str(session / "voice.mp3")
        srt_p = str(session / "subs.srt")
        voice_style = data.get("voice_style", "cheerful")
        generate_voice(data["content"], voice_style, voice_p, srt_p)
        audio_dur = get_duration(voice_p)
        scene_dur = min(audio_dur / max(len(data["scenes"]), 1), 12.0)

        # 3 — Scene images + Ken Burns animation
        pipeline_status["step"] = "Generating scene images..."
        pipeline_status["step_index"] = 3
        clips = []
        for i, scene in enumerate(data["scenes"]):
            out = str(session / f"scene_{i}.mp4")
            if build_scene_clip(scene, scene_dur, out):
                clips.append(out)
                print(f"  ✅ Scene {i+1}/5 ({pipeline_status['image_source']})")
        if not clips:
            raise Exception("All scene generation failed")

        # 4 — Music
        pipeline_status["step"] = "Generating background music..."
        pipeline_status["step_index"] = 4
        music_p = str(session / "music.mp3")
        if not generate_music(data.get("content_type", "rhyme"), music_p):
            music_p = None

        # 5 — Assemble video
        pipeline_status["step"] = "Assembling final video..."
        pipeline_status["step_index"] = 5
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, srt_p, final_p)

        # 6 — Upload to YouTube
        pipeline_status["step"] = "Uploading to YouTube with full SEO..."
        pipeline_status["step_index"] = 6
        video_id = upload_youtube(final_p, data)
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Live: {url}")

        # 7 — Log
        pipeline_status["step"] = "Done! 🎉"
        pipeline_status["step_index"] = 7
        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp": ts, "video_id": video_id,
            "title": data["title"], "topic": data.get("topic", ""),
            "content_type": data.get("content_type", ""),
            "llm_used": data.get("llm_used", ""),
            "url": url,
        }
        log.append(entry)
        LOG_FILE.write_text(json.dumps(log, indent=2))
        pipeline_status["last_result"] = entry

    except Exception as e:
        pipeline_status["error"] = str(e)
        print(f"❌ Pipeline error: {e}")
        import traceback; traceback.print_exc()
    finally:
        pipeline_status["running"] = False
        shutil.rmtree(str(session), ignore_errors=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@app.get("/")
def root():
    return {"status": "ok", "service": "KidsContent.ai v3.0",
            "llm_stack": ["Gemini 2.5 Flash", "Groq Llama 3.3 70B", "OpenRouter Free"],
            "image_stack": ["ModelsLab FREE", "Pollinations.AI"]}


@app.post("/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    """Run pipeline. Optionally pass topic and content_type."""
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req.topic, req.content_type)
    return {"status": "started", "topic": req.topic or "auto-selected",
            "content_type": req.content_type or "auto-detected"}


@app.get("/status")
def get_status():
    return pipeline_status


@app.get("/logs")
def get_logs():
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text())


@app.get("/topics")
def get_topics():
    """Get the default topic pool — useful for the dashboard."""
    return {"topics": DEFAULT_TOPICS, "total": len(DEFAULT_TOPICS)}


@app.get("/health")
def health():
    keys_configured = {
        "gemini": bool(GEMINI_API_KEY),
        "groq": bool(GROQ_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
        "modelslab": bool(MODELSLAB_API_KEY),
        "youtube": bool(YOUTUBE_REFRESH_TOKEN),
    }
    return {"status": "healthy", "keys": keys_configured,
            "timestamp": datetime.now().isoformat()}
