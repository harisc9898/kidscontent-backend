"""
DarkHistory.ai — Backend v4.0 — VIRAL CONTENT ENGINE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NICHE: Bizarre History Facts + True Crime Shorts
STRATEGY: Bright Side / Infographics Show / Weird History formula
  — Fast Ken Burns cuts (3s/image), dramatic voice, bold text overlays
  — Scripts engineered with curiosity hooks + payoff loops
  — SEO-optimised for highest-CPM niches ($8–$18 RPM)

Content Engine:
  — Bizarre History: medieval punishments, dark secrets, forgotten events
  — True Crime: real cases, psychology, twisted timelines
  — Each video: HOOK (3s) → TENSION BUILD → REVEAL → CTA

LLM Stack (Triple Fallback — Completely Free):
  1. Google Gemini 2.5 Flash  → 500 req/day FREE (primary)
  2. Groq Llama 3.3 70B       → 1000 req/day FREE (backup)
  3. OpenRouter (free models)  → unlimited FREE (emergency)

Image Stack:
  1. ModelsLab FREE tier       → 100 calls/day, cinematic dark art
  2. Pollinations.AI           → unlimited FREE fallback

Voice (Edge TTS — PRIMARY — Microsoft Neural):
  — History:    en-US-GuyNeural   (deep, authoritative, documentary)
  — True Crime: en-US-AriaNeural  (suspenseful, story-driven female)
  — Both have dramatic rate/pitch tuning for max engagement

Video: FFmpeg Ken Burns (zoompan filter, 8 random motion styles)
Music: Pollinations Audio (cinematic, suspense, documentary styles)
Upload: YouTube Data API v3 (FREE, 6/day)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH FINDINGS APPLIED:
  - Visual change every 2-3s = highest Shorts retention (2026 data)
  - 50-58s ideal Short length for storytelling + watch time
  - Bold burn-in captions boost retention by 15-25%
  - Curiosity gap hooks in first 3s are non-negotiable
  - True crime + history = $8-18 CPM (vs kids $1-3 CPM)
  - Narration-led Shorts get 1.9x more shares than caption-only
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, json, time, random, asyncio, subprocess, re, shutil, io, math
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── ENV VARS ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY          = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.environ.get("OPENROUTER_API_KEY", "")
MODELSLAB_API_KEY     = os.environ.get("MODELSLAB_API_KEY", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="4.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

WORK_DIR = Path("/tmp/darkhistory")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

pipeline_status: dict = {
    "running": False, "step": "", "step_index": 0,
    "total_steps": 7, "last_result": None, "error": None,
    "llm_used": None, "image_source": None,
}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NICHE DEFINITIONS — DUAL CHANNEL STRATEGY
# Research: Both niches are $8-18 CPM. True crime gets higher engagement,
# History gets more consistent search volume. Alternating maximises both.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

HISTORY_TOPICS = [
    # Medieval horror — highest search volume in this niche
    "the most brutal medieval torture devices ever invented",
    "how the iron maiden torture device actually worked",
    "why the black death killed half of Europe in 3 years",
    "the secret life inside a medieval dungeon",
    "what Viking raiders really did to their victims",
    "the horrifying truth about Roman gladiator fights",
    "how ancient Egyptians made mummies step by step",
    "the real story behind the Tower of London executions",
    "why pirates buried treasure and what happened to it",
    "the forgotten plague that wiped out entire cities",
    # Ancient world dark secrets
    "the darkest secrets of ancient Rome nobody talks about",
    "how the Spartans trained child soldiers from age 7",
    "the real reason Pompeii was buried and lost for centuries",
    "what happened inside the Colosseum on a normal day",
    "the gruesome truth about ancient Greek medicine",
    # Historical crimes and conspiracies
    "the unsolved mystery of the Princes in the Tower",
    "why Jack the Ripper was never caught and who he really was",
    "the historical assassination that changed the entire world",
    "how the great fire of London started and who was blamed",
    "the darkest chapter in the history of the Catholic Church",
    # Punishment history (viral gold)
    "the 5 most terrifying punishments in all of human history",
    "how ancient China punished criminals in unimaginable ways",
    "the most brutal execution methods used by the Roman Empire",
    "why medieval witch trials were far worse than people think",
    "the shocking truth about prison conditions 200 years ago",
]

TRUE_CRIME_TOPICS = [
    # Serial killer psychology — highest click-through rate
    "the chilling psychology behind Ted Bundy that experts missed",
    "how the Zodiac Killer sent coded messages and was never caught",
    "the real story of Jack the Ripper hidden in police files",
    "why Jeffrey Dahmer's neighbors never suspected anything",
    "the coldest case in history that was solved 40 years later",
    # Heists and cons
    "the most audacious bank heist in American history",
    "how one man fooled the entire world for 20 years",
    "the greatest art theft ever committed and where the art is now",
    "the con artist who convinced people he was a doctor for 10 years",
    "the biggest financial fraud that destroyed thousands of lives",
    # Mysterious disappearances
    "the mysterious disappearance that haunts investigators today",
    "the plane that vanished with 239 people and was never found",
    "the unsolved murder that stumped every detective who tried",
    "the cult that convinced hundreds of people to give up everything",
    "the poison killer who was never suspected until too late",
    # Historical true crime
    "the murder trial that shocked Victorian England",
    "how a single crime changed criminal law forever",
    "the most clever alibi in criminal history that almost worked",
    "the crime that went unsolved for 50 years until one clue broke it",
    "the killer who wrote letters to newspapers and got away with it",
]

CONTENT_NICHES = {
    "history": {
        "label":    "Bizarre History",
        "icon":     "🏛️",
        "topics":   HISTORY_TOPICS,
        "cpm_range":"$8–$15",
    },
    "truecrime": {
        "label":    "True Crime",
        "icon":     "🔍",
        "topics":   TRUE_CRIME_TOPICS,
        "cpm_range":"$10–$18",
    },
}

# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    topic:        Optional[str] = Field(default=None)
    content_type: Optional[str] = Field(default=None,
        description="history | truecrime | auto")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — VIRAL CONTENT GENERATION
# Formula from research: HOOK (curiosity gap) → TENSION → REVEAL → CTA
# Every sentence must earn its place. Scripts under 160 words for 50-58s Shorts.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_prompt(topic: str, content_type: str) -> str:
    """
    MrBeast-level content engineering:
    — Every script opens with a pattern-interrupt hook (not 'Today we...')
    — Curiosity gap in sentence 1 (viewers MUST know the answer)
    — Short punchy sentences. No filler words.
    — Payoff loop: tease the most shocking reveal at the start, deliver at end
    — Natural spoken language — sounds like a storyteller, not a textbook
    — SEO: front-loaded keywords, emotional trigger words in title
    """

    shared_rules = """
STRICT VIRAL SCRIPT RULES (non-negotiable):
1. HOOK (first 2 sentences): Drop the most shocking fact or question IMMEDIATELY.
   DO NOT start with "Today", "Welcome", "In this video", "Have you ever".
   Start mid-story. Example: "They found the body 3 days later. The killer had been hiding in plain sight." or "Nobody expected what archaeologists found buried under the palace floor."
2. TENSION: Build dread, suspense, or disbelief. Short sentences. Each one reveals a small piece.
3. REVEAL: The payoff — the most shocking fact, delivered as a gut-punch.
4. CTA: One short line asking viewers to follow for more dark stories.
5. TOTAL LENGTH: 130–160 words MAX. This is a 50–58 second Short.
6. LANGUAGE: Casual spoken English. No academic words. Write for someone who skipped school.
7. EVERY SENTENCE must make the viewer want to hear the next one.
"""

    history_prompt = f"""You are a viral YouTube Shorts writer for a dark history channel (think Weird History, Dark Docs).
Write an ADDICTIVE 130-160 word script about: {topic}

{shared_rules}

HISTORY SCRIPT STYLE:
- Use real (or realistic-sounding) historical details
- The more bizarre, shocking or counterintuitive the better
- Phrases that work: "Nobody talks about this", "History books hide this", "What they don't tell you is..."
- End with a haunting or shocking final sentence

Also generate YouTube Shorts SEO + visual scenes.
Return ONLY valid JSON (zero markdown, zero backticks, zero text outside JSON):
{{
  "title": "YouTube title, max 70 chars, start with emoji, include a number or shocking claim — make it impossible NOT to click",
  "content": "the full 130-160 word spoken script here",
  "description": "160-word YouTube description. First sentence = search hook with keywords. Include related search terms organically. End with subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12"],
  "hashtags": "#Shorts #DarkHistory #History #HistoryFacts #BizarreHistory",
  "scenes": [
    "cinematic scene description for AI image gen, max 12 words, very specific visual — dark, dramatic, atmospheric",
    "scene 2 description",
    "scene 3 description",
    "scene 4 description",
    "scene 5 description",
    "scene 6 description",
    "scene 7 description",
    "scene 8 description"
  ],
  "voice_style": "authoritative",
  "content_type": "history"
}}"""

    truecrime_prompt = f"""You are a viral YouTube Shorts writer for a true crime channel (think Dark Mysteries, Crime Files, Mr. Nightmare tone but factual).
Write an ADDICTIVE 130-160 word script about: {topic}

{shared_rules}

TRUE CRIME SCRIPT STYLE:
- Cold, precise, chilling delivery — like reading a detective's report
- Drop clues slowly, like a thriller novel
- The most disturbing detail should land in the final 20 words
- Create dread: "Nobody noticed. Until it was too late."
- Real-feeling details (specific times, locations, small chilling facts)

Also generate YouTube Shorts SEO + visual scenes.
Return ONLY valid JSON (zero markdown, zero backticks, zero text outside JSON):
{{
  "title": "YouTube title, max 70 chars, start with emoji, true crime titles that work: 'The [PERSON] who [SHOCKING THING]' or '[NUMBER] signs nobody noticed about [KILLER/CASE]'",
  "content": "the full 130-160 word spoken script here",
  "description": "160-word YouTube description. First sentence = search hook. Include true crime keywords parents and curious adults search. End with subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12"],
  "hashtags": "#Shorts #TrueCrime #CrimeFiles #Mystery #UnsolvedMysteries",
  "scenes": [
    "cinematic scene description for AI image gen, max 12 words, noir/dark/moody detective atmosphere",
    "scene 2 description",
    "scene 3 description",
    "scene 4 description",
    "scene 5 description",
    "scene 6 description",
    "scene 7 description",
    "scene 8 description"
  ],
  "voice_style": "suspenseful",
  "content_type": "truecrime"
}}"""

    return history_prompt if content_type == "history" else truecrime_prompt


# ── LLM CALLERS (same triple-stack, unchanged) ────────────────────────────────
def call_gemini(prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}")
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2000}},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"Gemini failed: {e}")
    return None


def call_groq(prompt: str) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [{"role": "user", "content": prompt}],
                  "temperature": 0.85, "max_tokens": 2000},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Groq failed: {e}")
    return None


def call_openrouter(prompt: str) -> Optional[str]:
    headers = ({"Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://darkhistory-api.onrender.com"}
               if OPENROUTER_API_KEY
               else {"Content-Type": "application/json",
                     "HTTP-Referer": "https://darkhistory-api.onrender.com"})
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
                      "temperature": 0.85, "max_tokens": 2000},
                timeout=90)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                if text and len(text) > 100:
                    print(f"  OpenRouter used: {model}")
                    return text
        except Exception as e:
            print(f"OpenRouter {model} failed: {e}")
    return None


def _clean_json(raw: str) -> Optional[dict]:
    """Nuclear JSON cleaner — handles all LLM output quirks."""
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip()).rstrip("`").strip()
    json_match = re.search(r'\{[\s\S]*\}', raw)
    if json_match:
        raw = json_match.group(0)
    raw = raw.encode('utf-8', errors='ignore').decode('utf-8')
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw)
    raw = raw.replace('\r\n', '\n').replace('\r', '\n')
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    for text in [raw, raw.replace('\n', ' '), re.sub(r'\s+', ' ', raw)]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


# ── SMART NICHE ALTERNATOR ────────────────────────────────────────────────────
_niche_state_file = WORK_DIR / "niche_state.json"

def get_next_niche() -> str:
    """Alternates between history and truecrime on each run."""
    try:
        if _niche_state_file.exists():
            state = json.loads(_niche_state_file.read_text())
            last = state.get("last_niche", "truecrime")
            next_niche = "truecrime" if last == "history" else "history"
        else:
            next_niche = "history"
        _niche_state_file.write_text(json.dumps({"last_niche": next_niche}))
        return next_niche
    except Exception:
        return random.choice(["history", "truecrime"])


def generate_content(topic: Optional[str], content_type: Optional[str]) -> dict:
    """Generate viral content using the dark history / true crime formula."""

    # Determine niche
    if content_type in ("history", "truecrime"):
        niche = content_type
    elif not content_type or content_type == "auto":
        niche = get_next_niche()
    else:
        niche = get_next_niche()

    # Auto-select topic if not provided
    if not topic:
        topic = random.choice(CONTENT_NICHES[niche]["topics"])
        print(f"🎲 Auto-topic ({niche}): {topic}")
    else:
        print(f"🎯 Custom topic: {topic}")

    print(f"📝 Niche: {CONTENT_NICHES[niche]['label']}")
    prompt = build_prompt(topic, niche)

    # Triple-stack LLM
    raw, llm_used = None, None
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
            print("🔄 Trying OpenRouter...")
            raw = call_openrouter(prompt)
            if raw:
                llm_used = "OpenRouter (free)"

    if not raw:
        raise Exception("All 3 LLM providers failed. Check API keys.")

    print(f"✅ Content via {llm_used}")
    pipeline_status["llm_used"] = llm_used

    data = _clean_json(raw)
    if not data:
        raise Exception(f"JSON parse failed. Raw: {raw[:300]}")

    data["topic"]        = topic
    data["content_type"] = niche
    data["llm_used"]     = llm_used
    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2 — VOICE SYNTHESIS
# Research findings:
#   — edge-tts quality FAR superior to gTTS for retention
#   — Deep male voice (Guy) for history = authoritative documentary feel
#   — Suspenseful female (Aria) for true crime = emotional engagement
#   — Rate tuning: slightly fast keeps energy up without losing clarity
#   — Pitch tuning: slight drop = gravitas and seriousness
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Voice profiles researched and tuned for each content type
EDGE_PROFILES = {
    # History: Guy Neural — deep, authoritative, BBC documentary energy
    # Rate slightly elevated for energy, pitch lowered for gravitas
    "authoritative": {
        "voice": "en-US-GuyNeural",
        "rate":  "+5%",
        "pitch": "-8Hz",
    },
    # True Crime: Aria Neural — clear, measured, suspenseful
    # Slightly slower to build tension, neutral pitch for believability
    "suspenseful": {
        "voice": "en-US-AriaNeural",
        "rate":  "-3%",
        "pitch": "-4Hz",
    },
    # Fallback profiles
    "dramatic": {
        "voice": "en-GB-RyanNeural",
        "rate":  "+3%",
        "pitch": "-6Hz",
    },
    "default": {
        "voice": "en-US-GuyNeural",
        "rate":  "+3%",
        "pitch": "-5Hz",
    },
}


def _generate_srt_from_text(text: str, audio_duration: float, srt_path: str):
    words = text.split()
    if not words:
        Path(srt_path).write_text("")
        return
    time_per_word = audio_duration / len(words)
    lines = []
    idx = 1
    chunk_size = 4
    for i in range(0, len(words), chunk_size):
        chunk = words[i:i+chunk_size]
        start = i * time_per_word
        end   = min((i + chunk_size) * time_per_word, audio_duration)
        def fmt(s):
            h  = int(s // 3600)
            m  = int((s % 3600) // 60)
            sc = int(s % 60)
            ms = int((s - int(s)) * 1000)
            return f"{h:02d}:{m:02d}:{sc:02d},{ms:03d}"
        lines += [str(idx), f"{fmt(start)} --> {fmt(end)}", " ".join(chunk), ""]
        idx += 1
    Path(srt_path).write_text("\n".join(lines), encoding="utf-8")


def _get_audio_duration_quick(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15)
        return float(r.stdout.strip())
    except Exception:
        return 40.0


async def _edge_tts_async(text, voice, rate, pitch, audio_out, srt_out):
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    sub  = edge_tts.SubMaker()
    with open(audio_out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                sub.feed(chunk)
    with open(srt_out, "w", encoding="utf-8") as f:
        f.write(sub.get_srt())


def generate_voice_edge(content: str, voice_style: str,
                        audio_path: str, srt_path: str) -> bool:
    """Edge TTS — PRIMARY voice engine for dark/history content."""
    try:
        profile = EDGE_PROFILES.get(voice_style, EDGE_PROFILES["default"])
        asyncio.run(_edge_tts_async(
            text=content, voice=profile["voice"],
            rate=profile["rate"], pitch=profile["pitch"],
            audio_out=audio_path, srt_out=srt_path,
        ))
        print(f"✅ Voice: {profile['voice']} (style={voice_style})")
        return True
    except Exception as e:
        print(f"  edge-tts failed: {e}")
        return False


def generate_voice_gtts_fallback(content: str, audio_path: str, srt_path: str) -> bool:
    """gTTS fallback — only used if edge-tts fails on server."""
    try:
        from gtts import gTTS
        tts = gTTS(text=content, lang="en", tld="com", slow=False)
        tts.save(audio_path)
        duration = _get_audio_duration_quick(audio_path)
        _generate_srt_from_text(content, duration, srt_path)
        print("✅ Voice: gTTS fallback")
        return True
    except Exception as e:
        print(f"  gTTS fallback failed: {e}")
        return False


def generate_voice(content: str, voice_style: str, audio_path: str, srt_path: str):
    """Edge TTS first (high quality, dramatic). Falls back to gTTS."""
    if generate_voice_edge(content, voice_style, audio_path, srt_path):
        return
    print("⚡ Edge-tts failed, falling back to gTTS...")
    if generate_voice_gtts_fallback(content, audio_path, srt_path):
        return
    raise Exception("All TTS providers failed")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION
# For dark history and true crime, we need:
#   — Cinematic, atmospheric, dark art style (NOT cartoon)
#   — Dramatic lighting: torchlight, candlelight, moonlight, shadow
#   — Hyper-detailed portraits, crime scenes, historical settings
#   — 9:16 vertical for Shorts
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _dark_image_prompt(scene: str, content_type: str) -> str:
    """Craft prompts that generate cinematic, dark, high-quality images."""
    if content_type == "history":
        style = (
            "cinematic dark historical illustration, dramatic chiaroscuro lighting, "
            "oil painting style, rich deep colors, torchlight shadows, medieval atmosphere, "
            "hyper detailed, ultra high quality, photorealistic texture, no text, no watermark"
        )
        negative = (
            "cartoon, anime, bright colors, modern, cheerful, watermark, text, "
            "blurry, low quality, nsfw, children, cute"
        )
    else:  # truecrime
        style = (
            "cinematic noir photography, dark moody atmosphere, dramatic shadows, "
            "detective noir, crime scene documentary style, gritty realistic, "
            "high contrast black and white with selective color, hyper detailed, "
            "photorealistic, no text, no watermark, professional photography"
        )
        negative = (
            "cartoon, anime, bright cheerful colors, watermark, text, blurry, "
            "low quality, nsfw, unrealistic, painting"
        )
    return f"{scene}, {style}", negative


def generate_image_modelslab(scene: str, content_type: str, output_path: str) -> bool:
    if not MODELSLAB_API_KEY:
        return False
    try:
        # Best models for cinematic dark content
        dark_models = ["flux", "sdxl", "realistic-vision-v6", "dreamshaper-xl"]
        prompt, negative = _dark_image_prompt(scene, content_type)
        payload = {
            "key":              MODELSLAB_API_KEY,
            "model_id":         random.choice(dark_models),
            "prompt":           prompt,
            "negative_prompt":  negative,
            "width":            "576",
            "height":           "1024",
            "samples":          "1",
            "num_inference_steps": "25",
            "guidance_scale":   8.0,
            "safety_checker":   "yes",
            "enhance_prompt":   "yes",
        }
        resp = requests.post(
            "https://modelslab.com/api/v6/realtime/text2img",
            headers={"Content-Type": "application/json"},
            json=payload, timeout=120)
        if resp.status_code == 200:
            result = resp.json()
            if result.get("status") == "success" and result.get("output"):
                img_url = result["output"][0]
                img_r = requests.get(img_url, timeout=60)
                if img_r.status_code == 200 and len(img_r.content) > 5000:
                    Path(output_path).write_bytes(img_r.content)
                    return True
    except Exception as e:
        print(f"  ModelsLab failed: {e}")
    return False


def generate_image_pollinations(scene: str, content_type: str, output_path: str) -> bool:
    """Pollinations — unlimited free, supports flux model for high quality."""
    prompt, _ = _dark_image_prompt(scene, content_type)
    encoded   = requests.utils.quote(prompt)
    seed      = random.randint(1000, 999999)
    # Use flux model for best quality — Pollinations supports it free
    urls = [
        f"https://image.pollinations.ai/prompt/{encoded}?width=576&height=1024&nologo=true&model=flux&seed={seed}&enhance=true",
        f"https://image.pollinations.ai/prompt/{encoded}?width=576&height=1024&nologo=true&seed={seed}",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=50)
            if r.status_code == 200 and len(r.content) > 5000:
                Path(output_path).write_bytes(r.content)
                return True
        except Exception as e:
            print(f"  Pollinations attempt failed: {e}")
    return False


def generate_dark_gradient_fallback(scene: str, content_type: str, output_path: str) -> bool:
    """
    Dark cinematic gradient fallback — moody, not colorful.
    For history: dark sepia/amber gradients
    For truecrime: near-black to dark blue gradients
    """
    if content_type == "history":
        gradients = [
            ("0x2C1A0E", "0x6B3A1F"),  # deep brown to amber
            ("0x1A0E0E", "0x5C1A1A"),  # near-black to dark crimson
            ("0x0D1B1E", "0x1A3A3A"),  # dark teal-black
            ("0x1C1408", "0x4A3218"),  # dark sepia
        ]
    else:
        gradients = [
            ("0x0A0A0F", "0x1A1A2E"),  # near-black to navy
            ("0x0D0D0D", "0x1F1F1F"),  # pure dark gradient
            ("0x0A0F14", "0x14283C"),  # dark charcoal to midnight blue
            ("0x0F0A14", "0x1E0F28"),  # dark to deep purple
        ]
    c1, c2 = random.choice(gradients)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"gradients=size=576x1024:x0=0:y0=0:x1=576:y1=1024:c0={c1}:c1={c2}:duration=1",
        "-frames:v", "1", "-vf", "format=yuvj420p", output_path,
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=15)
    if r.returncode != 0:
        cmd2 = ["ffmpeg", "-y", "-f", "lavfi",
                "-i", f"color=c={c1}:size=576x1024:duration=1",
                "-frames:v", "1", "-vf", "format=yuvj420p", output_path]
        r = subprocess.run(cmd2, capture_output=True, timeout=15)
    return r.returncode == 0 and Path(output_path).exists()


def generate_image(scene: str, content_type: str, output_path: str) -> str:
    """4-tier fallback. Returns source name or None."""
    if MODELSLAB_API_KEY and generate_image_modelslab(scene, content_type, output_path):
        pipeline_status["image_source"] = "ModelsLab"
        return "modelslab"
    if generate_image_pollinations(scene, content_type, output_path):
        pipeline_status["image_source"] = "Pollinations"
        return "pollinations"
    print("  ⚡ Using dark gradient fallback")
    if generate_dark_gradient_fallback(scene, content_type, output_path):
        pipeline_status["image_source"] = "DarkGradient"
        return "gradient"
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3B — KEN BURNS ENGINE
# 8 distinct motion styles based on research + cinematography principles:
#   — Slow zoom-in: builds intimacy/dread as narrator speaks
#   — Slow zoom-out: reveals scale/horror of a situation
#   — Pan left/right: scanning crime scenes, historical battlefields
#   — Diagonal drift: cinematic, unsettling, non-static energy
# Each image gets a RANDOM motion style — no two consecutive images same.
# Duration = DYNAMIC: calculated from actual audio length and scene count.
# Target: 3 seconds per image (optimal per research).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# FPS for zoompan — lower = faster but choppier, 25 is ideal for free tier CPU
CLIP_FPS = 25

def _ken_burns_filter(duration: float, style: int) -> str:
    """
    Generate FFmpeg zoompan filter string for a given Ken Burns style.
    d = total frames = duration * fps
    All styles produce smooth, cinematic motion.
    """
    d = int(duration * CLIP_FPS)  # total frames
    out_w, out_h = 576, 1024

    # Pre-scale to 4× for smooth zoompan
    scale_w = out_w * 4  # 2304
    scale_h = out_h * 4  # 4096

    styles = {
        # 1. Slow zoom in — center → slightly closer
        0: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0008,1.25)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 2. Slow zoom out — starts close, pulls back
        1: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='if(eq(on,1),1.25,max(zoom-0.0008,1.0))'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 3. Pan left to right — horizontal sweep
        2: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.1'"
            f":x='iw*0.1*(on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 4. Pan right to left — reverse horizontal sweep
        3: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.1'"
            f":x='iw*0.1*(1-on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 5. Pan top to bottom — slow vertical drop (unsettling)
        4: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.1'"
            f":x='iw/2-(iw/zoom/2)':y='ih*0.08*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 6. Zoom in + subtle pan right (cinematic drift)
        5: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0006,1.2)'"
            f":x='iw*0.05*(on/{d})+(iw/2-(iw/zoom/2))'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 7. Zoom in on bottom (like looking down into a pit)
        6: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0009,1.3)'"
            f":x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 8. Diagonal drift — top-left to bottom-right
        7: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.15'"
            f":x='iw*0.05*(on/{d})':y='ih*0.05*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
    }
    return styles[style % 8]


def build_scene_clip(scene: str, content_type: str, duration: float,
                     output_path: str, ken_burns_style: int) -> bool:
    """
    Generate AI image → apply Ken Burns motion → produce video clip.
    This is what turns a flat image into cinematic visual content.
    """
    img_path = output_path.replace(".mp4", ".jpg")
    source   = generate_image(scene, content_type, img_path)
    if not source:
        return False

    kb_filter = _ken_burns_filter(duration, ken_burns_style)

    # Add format conversion at the end of the filter chain
    full_vf = f"{kb_filter},format=yuv420p"

    cmd = [
        "ffmpeg", "-y",
        "-loop",   "1",
        "-i",      img_path,
        "-vf",     full_vf,
        "-t",      str(duration),
        "-c:v",    "libx264",
        "-crf",    "26",
        "-preset", "ultrafast",
        "-r",      str(CLIP_FPS),
        "-pix_fmt","yuv420p",
        "-threads","1",
        "-an",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180)
    if result.returncode != 0:
        err = result.stderr[-400:].decode(errors="ignore")
        print(f"  FFmpeg Ken Burns error: {err}")
        # Fallback: static clip (better than nothing)
        cmd_static = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (
                f"scale=576:1024:force_original_aspect_ratio=decrease,"
                f"pad=576:1024:(ow-iw)/2:(oh-ih)/2:color=0x0a0a0f,"
                f"format=yuv420p"
            ),
            "-t", str(duration), "-c:v", "libx264", "-crf", "26",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-threads", "1", "-an", output_path,
        ]
        result = subprocess.run(cmd_static, capture_output=True, timeout=120)

    Path(img_path).unlink(missing_ok=True)
    return result.returncode == 0 and Path(output_path).exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — BACKGROUND MUSIC
# Cinematic music matched to content type:
#   History: dark orchestral, medieval, dramatic documentary
#   True Crime: noir, suspense, minimal dark ambient
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

MUSIC_STYLES = {
    "history":   "dark dramatic orchestral documentary historical suspense cinematic",
    "truecrime": "noir suspense minimal dark ambient crime thriller piano",
    "default":   "dark cinematic suspense atmospheric documentary",
}


def generate_music(content_type: str, music_path: str) -> bool:
    style = MUSIC_STYLES.get(content_type, MUSIC_STYLES["default"])
    try:
        url = f"https://audio.pollinations.ai/{requests.utils.quote(style)}"
        r   = requests.get(url, timeout=35)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            print("✅ Music generated (dark cinematic)")
            return True
    except Exception as e:
        print(f"  Music API failed: {e}")
    # Silence fallback
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", "anullsrc=r=44100:cl=stereo",
               "-t", "60", "-c:a", "aac", "-b:a", "128k", music_path]
        r = subprocess.run(cmd, capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — VIDEO ASSEMBLY
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


def srt_to_drawtext(srt_path: str, content_type: str) -> Optional[str]:
    """
    Convert SRT to FFmpeg drawtext filters.
    Dark theme: white text, thick black border — high contrast for dark visuals.
    Large font, centered, positioned in lower third.
    """
    try:
        content = Path(srt_path).read_text(encoding="utf-8")
    except Exception:
        return None

    # Style per content type
    if content_type == "history":
        # White with dark border — like documentary subtitles
        font_style = "fontsize=64:fontcolor=white:borderw=5:bordercolor=black"
    else:
        # Slightly smaller, same high-contrast style
        font_style = "fontsize=60:fontcolor=white:borderw=5:bordercolor=black"

    filters = []
    for block in re.split(r"\n\n+", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            times = lines[1].replace(",", ".").split(" --> ")
            start = _t2s(times[0].strip())
            end   = _t2s(times[1].strip())
            text  = " ".join(lines[2:]).strip()
            text  = (text.replace("'", "\u2019")
                        .replace(":", "\\:")
                        .replace("[", "\\[")
                        .replace("]", "\\]")
                        .replace("\\u2019", "'"))
            if len(text) > 35:
                text = text[:35] + "..."
            filters.append(
                f"drawtext=text='{text}'"
                f":{font_style}"
                f":x=(w-text_w)/2:y=(h-200)"
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
                   srt_p: str, output_p: str, content_type: str):
    """
    Single-pass assembly optimised for Render free tier (512 MB RAM).
    Concat clips → final pass with audio mix + subtitle burn-in.
    """
    ts = str(int(time.time()))

    # Concat clips
    txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
         "-i", txt, "-c", "copy", concat_out],
        capture_output=True, timeout=120)
    if r.returncode != 0 or not Path(concat_out).exists():
        raise Exception(f"FFmpeg concat failed: {r.stderr[-400:].decode(errors='ignore')}")
    print(f"  ✅ Concat done ({len(clips)} clips)")

    voice_dur  = min(get_duration(voice_p) + 0.5, 59.0)
    sub_filter = srt_to_drawtext(srt_p, content_type)
    vf         = sub_filter if sub_filter else "copy"
    use_music  = music_p and Path(music_p).exists()

    if use_music:
        # Music at 15% volume — supports the voice, doesn't fight it
        audio_filt = (
            "[1:a]volume=1.6[voice];"
            "[2:a]volume=0.15,aloop=loop=-1:size=2e+09[music];"
            "[voice][music]amix=inputs=2:duration=first[afinal]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p, "-i", music_p,
            "-t", str(voice_dur),
            "-vf", vf,
            "-filter_complex", audio_filt,
            "-map", "0:v", "-map", "[afinal]",
            "-c:v", "libx264", "-crf", "27", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-threads", "1",
            output_p,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p,
            "-t", str(voice_dur),
            "-vf", vf,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-crf", "27", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-threads", "1",
            output_p,
        ]

    print(f"  🎬 Final encode: {voice_dur:.1f}s, "
          f"subs={'yes' if sub_filter else 'no'}, "
          f"music={'yes' if use_music else 'no'}")
    r = subprocess.run(cmd, capture_output=True, timeout=480)

    if r.returncode != 0:
        err = r.stderr[-600:].decode(errors="ignore")
        if sub_filter and ("drawtext" in err or "fontfile" in err):
            print("  ⚠️  Subtitle filter failed — retrying without subs...")
            cmd_nosub = [c if c != vf else "copy" for c in cmd]
            r = subprocess.run(cmd_nosub, capture_output=True, timeout=480)
            if r.returncode != 0:
                raise Exception(f"FFmpeg failed (no-sub retry): {r.stderr[-400:].decode(errors='ignore')}")
        else:
            raise Exception(f"FFmpeg final pass failed: {err}")

    if not Path(output_p).exists() or Path(output_p).stat().st_size < 10_000:
        raise Exception("Final video missing or too small")

    Path(concat_out).unlink(missing_ok=True)
    Path(txt).unlink(missing_ok=True)
    print(f"  ✅ Final video: {Path(output_p).stat().st_size // 1024} KB")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 6 — YOUTUBE UPLOAD WITH FULL SEO
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_yt_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type":    "refresh_token",
    })
    if r.status_code != 200:
        raise Exception(f"Token refresh failed: {r.text[:200]}")
    return r.json()["access_token"]


def upload_youtube(video_path: str, data: dict) -> str:
    token   = get_yt_token()
    niche   = data.get("content_type", "history")

    # Base tags per niche
    base_tags_history = [
        "dark history", "bizarre history", "history facts", "weird history",
        "historical facts", "history shorts", "dark facts", "history channel",
        "medieval history", "ancient history",
    ]
    base_tags_truecrime = [
        "true crime", "crime stories", "mystery", "unsolved mysteries",
        "crime facts", "detective stories", "dark stories", "criminal psychology",
        "true crime shorts", "cold case",
    ]
    base_tags = base_tags_history if niche == "history" else base_tags_truecrime

    tags = list(dict.fromkeys(
        data.get("tags", []) + base_tags + ["shorts", "youtube shorts", "facts"]
    ))[:15]

    description = (
        f"{data['description']}\n\n"
        f"🔔 Subscribe for daily dark history and true crime stories!\n"
        f"👍 Like if this shocked you!\n"
        f"💬 What topic should we cover next?\n\n"
        f"{data.get('hashtags', '#Shorts #DarkHistory')}"
    )

    # NOT made for kids — adult content niche, higher CPM
    metadata = {
        "snippet": {
            "title":           data["title"][:100],
            "description":     description[:4900],
            "tags":            tags,
            "categoryId":      "27",   # Education
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":         "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":            False,
        },
    }
    init_r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={"Authorization":         f"Bearer {token}",
                 "Content-Type":          "application/json",
                 "X-Upload-Content-Type": "video/mp4"},
        json=metadata)
    if init_r.status_code != 200:
        raise Exception(f"YouTube init {init_r.status_code}: {init_r.text[:200]}")

    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(
        init_r.headers["Location"],
        headers={"Content-Type":   "video/mp4",
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
    pipeline_status["running"]      = True
    pipeline_status["error"]        = None
    pipeline_status["llm_used"]     = None
    pipeline_status["image_source"] = None

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = WORK_DIR / ts
    session.mkdir(exist_ok=True)

    try:
        # ── 1. Generate content ───────────────────────────────────────────────
        pipeline_status["step"]       = "Generating viral script with AI..."
        pipeline_status["step_index"] = 1
        data = generate_content(topic, content_type)
        print(f"✅ Title: {data['title']}")

        # ── 2. Voice synthesis ────────────────────────────────────────────────
        pipeline_status["step"]       = "Synthesising dramatic voice narration..."
        pipeline_status["step_index"] = 2
        voice_p = str(session / "voice.mp3")
        srt_p   = str(session / "subs.srt")
        voice_style = data.get("voice_style", "authoritative")
        generate_voice(data["content"], voice_style, voice_p, srt_p)
        audio_dur = get_duration(voice_p)
        print(f"  📊 Audio duration: {audio_dur:.1f}s")

        # ── 3. Smart image count based on audio length ────────────────────────
        # Research: 3 seconds per image is optimal for retention in storytelling
        # We cap at the number of scenes the LLM provided (up to 8)
        # We always generate at least 5 to ensure visual variety
        TARGET_SECONDS_PER_IMAGE = 3.0
        max_scenes = min(len(data.get("scenes", [])), 8)
        ideal_count = max(5, min(max_scenes, math.ceil(audio_dur / TARGET_SECONDS_PER_IMAGE)))
        scenes = (data.get("scenes", []) * 3)[:ideal_count]  # repeat if too few
        scene_dur = audio_dur / len(scenes)

        print(f"  🎬 Scenes: {len(scenes)} × {scene_dur:.1f}s each")

        pipeline_status["step"]       = f"Generating {len(scenes)} cinematic images..."
        pipeline_status["step_index"] = 3

        # Shuffle Ken Burns styles so each image has different motion
        kb_styles = list(range(8))
        random.shuffle(kb_styles)

        clips = []
        for i, scene in enumerate(scenes):
            out = str(session / f"scene_{i:02d}.mp4")
            kb  = kb_styles[i % 8]
            print(f"  🎨 Scene {i+1}/{len(scenes)} [motion={kb}]: {scene[:45]}...")
            try:
                ok = build_scene_clip(scene, data["content_type"], scene_dur, out, kb)
                if ok and Path(out).exists() and Path(out).stat().st_size > 1000:
                    clips.append(out)
                    print(f"    ✅ Scene {i+1} OK ({pipeline_status.get('image_source','?')})")
                else:
                    print(f"    ⚠️  Scene {i+1} empty/failed — skipping")
            except Exception as e:
                print(f"    ⚠️  Scene {i+1} exception: {e}")

        if not clips:
            raise Exception("All scene generation failed — check image APIs")
        print(f"  ✅ {len(clips)} clips ready")

        # ── 4. Music ──────────────────────────────────────────────────────────
        pipeline_status["step"]       = "Generating cinematic background music..."
        pipeline_status["step_index"] = 4
        music_p = str(session / "music.mp3")
        if not generate_music(data.get("content_type", "history"), music_p):
            music_p = None

        # ── 5. Assemble ───────────────────────────────────────────────────────
        pipeline_status["step"]       = "Assembling final video with Ken Burns effects..."
        pipeline_status["step_index"] = 5
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, srt_p, final_p,
                       data.get("content_type", "history"))

        # ── 6. Upload ─────────────────────────────────────────────────────────
        pipeline_status["step"]       = "Uploading to YouTube with SEO..."
        pipeline_status["step_index"] = 6
        if not Path(final_p).exists():
            raise Exception("Final video missing")
        final_size = Path(final_p).stat().st_size
        if final_size < 10_000:
            raise Exception(f"Final video too small ({final_size}b)")
        print(f"📤 Uploading {final_size // 1024}KB...")
        video_id = upload_youtube(final_p, data)
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Live: {url}")

        # ── 7. Log ────────────────────────────────────────────────────────────
        pipeline_status["step"]       = "Done! 🎉"
        pipeline_status["step_index"] = 7
        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp":    ts,
            "video_id":     video_id,
            "title":        data["title"],
            "topic":        data.get("topic", ""),
            "content_type": data.get("content_type", ""),
            "llm_used":     data.get("llm_used", ""),
            "scenes_count": len(clips),
            "audio_dur_s":  round(audio_dur, 1),
            "url":          url,
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
    return {
        "status":  "ok",
        "service": "DarkHistory.ai v4.0",
        "niches":  ["Bizarre History", "True Crime"],
        "formula": "Hook + Tension + Reveal + CTA | 3s/image | Ken Burns | Edge TTS",
        "cpm_range": "$8–$18",
    }


@app.post("/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req.topic, req.content_type)
    return {
        "status":       "started",
        "topic":        req.topic or "auto-selected",
        "content_type": req.content_type or "auto (alternating)",
    }


@app.get("/status")
def get_status():
    return pipeline_status


@app.get("/logs")
def get_logs():
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text())


@app.get("/niches")
def get_niches():
    return {
        "niches": [
            {
                "id":        "history",
                "label":     "Bizarre History",
                "icon":      "🏛️",
                "cpm":       "$8–$15",
                "topics":    len(HISTORY_TOPICS),
                "formula":   "Hook → Historical revelation → Shocking truth",
                "voice":     "en-US-GuyNeural (authoritative documentary)",
            },
            {
                "id":        "truecrime",
                "label":     "True Crime",
                "icon":      "🔍",
                "cpm":       "$10–$18",
                "topics":    len(TRUE_CRIME_TOPICS),
                "formula":   "Cold open → Evidence drops → Chilling reveal",
                "voice":     "en-US-AriaNeural (suspenseful storyteller)",
            },
        ],
        "strategy": (
            "Alternates between both niches automatically. "
            "Combined topic pool: history + true crime = broadest possible "
            "audience reach at highest CPM rates."
        ),
    }


@app.get("/topics")
def get_topics():
    return {
        "history":   HISTORY_TOPICS,
        "truecrime": TRUE_CRIME_TOPICS,
        "total":     len(HISTORY_TOPICS) + len(TRUE_CRIME_TOPICS),
    }


@app.get("/health")
def health():
    keys = {
        "gemini":    bool(GEMINI_API_KEY),
        "groq":      bool(GROQ_API_KEY),
        "openrouter":bool(OPENROUTER_API_KEY),
        "modelslab": bool(MODELSLAB_API_KEY),
        "youtube":   bool(YOUTUBE_REFRESH_TOKEN),
    }
    return {
        "status":    "healthy",
        "keys":      keys,
        "version":   "4.0",
        "timestamp": datetime.now().isoformat(),
    }
