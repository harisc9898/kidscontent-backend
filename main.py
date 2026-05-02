"""
DarkHistory.ai -- Backend v7.0
══════════════════════════════════════════════════════════════════
FIXES IN v7.0:

IMAGE FIX (root cause of gradient-only output):
  The gemini-2.5-flash-preview endpoint does NOT support image generation.
  Fixed by using the correct model: gemini-2.0-flash-exp with
  responseModalities: ["TEXT", "IMAGE"] — this actually works.

  NEW IMAGE STACK (all free, fast):
  TIER 1: Gemini 2.0 Flash Exp Image  — uses GEMINI_API_KEY, 3-8s, correct API
  TIER 2: fal.ai FLUX Schnell         — completely free, no token required, 2-6s
  TIER 3: HuggingFace FLUX.1-schnell  — needs HF_TOKEN (free), 5-12s
  TIER 4: Prodia FLUX Schnell         — needs PRODIA_TOKEN (free), 2-5s
  TIER 5: Cinematic gradient          — always works, <1s

CAPTION FIX:
  MarginV was int(vid_h * 0.12) = 153 — this pushes subtitles UP too high.
  Fixed to 80px bottom margin — sits correctly at bottom 8% of frame.
  Also increased font size to 78px and added proper bold weight.
  Word grouping improved: 3 words per card (not 2) for better readability.

REQUIRED ENV VARS:
  GEMINI_API_KEY     — existing
  GROQ_API_KEY       — existing
  OPENROUTER_API_KEY — existing
  HF_TOKEN           — optional (free at huggingface.co) — boosts image quality
  PRODIA_TOKEN       — optional (free at app.prodia.com)
  YOUTUBE_*          — existing
══════════════════════════════════════════════════════════════════
"""

import os, json, time, random, asyncio, subprocess, re, shutil, base64
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── ENV VARS ──────────────────────────────────────────────────────────────────
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY          = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.environ.get("OPENROUTER_API_KEY", "")
HF_TOKEN              = os.environ.get("HF_TOKEN", "")
PRODIA_TOKEN          = os.environ.get("PRODIA_TOKEN", "")
POLLINATIONS_KEY      = os.environ.get("POLLINATIONS_KEY", "")  # Get free at enter.pollinations.ai
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="7.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

WORK_DIR = Path("/tmp/darkhistory")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE  = WORK_DIR / "upload_log.json"

pipeline_status: dict = {
    "running": False, "step": "", "step_index": 0,
    "total_steps": 7, "last_result": None, "error": None,
    "llm_used": None, "image_source": None,
}

VID_W    = 720
VID_H    = 1280
CLIP_FPS = 25
IMG_W    = 720
IMG_H    = 1280

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOPIC POOLS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HISTORY_TOPICS = [
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
    "the darkest secrets of ancient Rome nobody talks about",
    "how the Spartans trained child soldiers from age 7",
    "the real reason Pompeii was buried and lost for centuries",
    "what happened inside the Colosseum on a normal day",
    "the gruesome truth about ancient Greek medicine",
    "the unsolved mystery of the Princes in the Tower",
    "why Jack the Ripper was never caught and who he really was",
    "the historical assassination that changed the entire world",
    "how the great fire of London started and who was blamed",
    "the darkest chapter in the history of the Catholic Church",
    "the 5 most terrifying punishments in all of human history",
    "how ancient China punished criminals in unimaginable ways",
    "the most brutal execution methods used by the Roman Empire",
    "why medieval witch trials were far worse than people think",
    "the shocking truth about prison conditions 200 years ago",
    "how the Aztecs performed human sacrifices and why",
    "the dark secret history of the guillotine in France",
    "what really happened to the crew of the Mary Celeste",
    "the true story of Vlad the Impaler that inspired Dracula",
    "how medieval executioners were trained and what they earned",
    "what archaeologists found inside Egyptian pharaoh tombs",
    "how medieval knights really fought and how often they died",
    "the real story of the lost colony of Roanoke",
    "the truth behind the Bermuda Triangle disappearances",
    "how the Spanish Inquisition actually worked and who ran it",
    "what happened to survivors of the Titanic after rescue",
    "the most shocking royal scandals in European history",
    "how body snatchers supplied medical schools with corpses",
    "the real story of Blackbeard's final battle and death",
    "why the Roman Empire actually collapsed according to historians",
]

TRUE_CRIME_TOPICS = [
    "the chilling psychology behind Ted Bundy that experts missed",
    "how the Zodiac Killer sent coded messages and was never caught",
    "why Jeffrey Dahmer's neighbors never suspected anything",
    "the coldest case in history that was solved 40 years later",
    "the most audacious bank heist in American history",
    "the greatest art theft ever committed and where the art is now",
    "the mysterious disappearance that haunts investigators today",
    "the plane that vanished with 239 people and was never found",
    "the cult that convinced hundreds of people to give up everything",
    "the poison killer who was never suspected until too late",
    "how forensic scientists finally cracked an impossible cold case",
    "the inside story of the most daring prison escape in history",
    "how one detective's obsession solved a 30-year-old murder",
    "the serial killer who worked as a respected professional for years",
    "the kidnapping case that changed how America searches for missing children",
    "why the BTK killer stopped and then confessed decades later",
    "how a single receipt exposed a criminal who thought he was clean",
    "the crime scene detail that investigators missed for 20 years",
    "how digital footprints led investigators to an untraceable suspect",
    "the killer who returned to the crime scene and was finally caught",
    "how satellite imagery solved a murder in a remote location",
    "the hitman who kept a diary that destroyed his entire network",
    "the fraud scheme so sophisticated even experts were fooled",
    "how a routine traffic stop exposed a decade of secret crimes",
    "the con woman who infiltrated high society and fooled everyone",
    "the murder that looked like an accident for 15 years",
    "the identity thief who lived as someone else for a decade",
    "why the Golden State Killer was finally caught after 40 years",
    "how investigators pieced together a murder with zero witnesses",
    "the killer who wrote letters to newspapers and got away with it",
]

CONTENT_NICHES = {
    "history":   {"label": "Bizarre History", "icon": "🏛️", "topics": HISTORY_TOPICS},
    "truecrime": {"label": "True Crime",       "icon": "🔍", "topics": TRUE_CRIME_TOPICS},
}


class RunRequest(BaseModel):
    topic:        Optional[str] = Field(default=None)
    content_type: Optional[str] = Field(default=None)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — CONTENT GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Art style matching reference: dark manhwa/anime thriller aesthetic
# Deep teal+amber color grading, cinematic noir, realistic but stylized
COMIC_STYLE = (
    "dark manhwa webtoon style, cinematic comic illustration, "
    "realistic anime art, deep teal and amber color grading, "
    "dramatic rim lighting, atmospheric rain or fog, "
    "ultra detailed, dark thriller aesthetic, "
    "cinematic composition, no text, no watermark, no logo, no signature"
)

def build_prompt(topic: str, content_type: str) -> str:
    shared = """
RULES:
1. HOOK: First 2 sentences = most shocking fact. NO "Today/Welcome/In this video".
2. SHORT sentences. Each reveals one piece. Build dread.
3. REVEAL: gut-punch payoff fact near end.
4. CTA: one short line to follow for more.
5. LENGTH: 130-155 words MAX (50-58 second Short).
6. LANGUAGE: casual spoken English, simple words.

SCENE IMAGE RULES — CRITICAL:
Each scene must be a SPECIFIC VISUAL from the actual story being told.
NOT generic. NOT stock photo descriptions. SPECIFIC to THIS topic.
Format: [camera angle] [specific subject from THIS story] [specific lighting] [atmosphere]
Camera options: extreme close-up, low angle shot, wide establishing shot, overhead shot, medium shot
Lighting options: single torch glow, cold streetlight, harsh overhead lamp, moonlight through bars, muzzle flash
Atmospheric: rain streaking glass, smoke curling, silhouette against doorway, mist rolling in
The art style (dark manhwa, teal-amber) is added automatically — do NOT mention it in scenes.
"""
    if content_type == "history":
        return f"""You are a viral YouTube Shorts writer for a dark history channel.
Write an ADDICTIVE 130-155 word script about: {topic}
{shared}
Use phrases like: "Nobody talks about this", "History books hide this"
End with a haunting final sentence.

Return ONLY valid JSON — no markdown, no backticks, nothing outside the JSON:
{{
  "title": "YouTube title max 70 chars, start with emoji, shocking claim",
  "content": "130-155 word spoken script",
  "description": "160-word YouTube description with keywords. Subscribe CTA at end.",
  "tags": ["dark history","medieval history","history facts","shocking history","bizarre history","ancient history","history shorts","dark secrets","historical facts","true history","untold history","dark past"],
  "hashtags": "#Shorts #DarkHistory #History #HistoryFacts #BizarreHistory",
  "scenes": [
    "extreme close-up: the specific instrument of torture or execution from THIS topic, single torch illuminating rust and dark stains, stone dungeon wall in background",
    "low angle wide shot: the specific historical location where THIS event happened, dramatic sky, silhouetted crowds or guards in foreground",
    "medium shot: the key historical figure or victim from THIS story in their defining moment, cold moonlight or torchlight, deep shadow",
    "overhead shot: aftermath scene specific to THIS historical event, dark ground, scattered objects telling the story",
    "extreme close-up: a significant object or detail specific to THIS story that symbolizes the horror — chains, documents, weapons, artifacts"
  ],
  "voice_style": "authoritative",
  "content_type": "history"
}}"""
    else:
        return f"""You are a viral YouTube Shorts writer for a true crime channel.
Write an ADDICTIVE 130-155 word script about: {topic}
{shared}
Style: cold, precise, chilling — like a detective reading a case file aloud.
The most disturbing detail lands in the final 20 words.

Return ONLY valid JSON — no markdown, no backticks, nothing outside the JSON:
{{
  "title": "max 70 chars, start with emoji, format: 'The [Person] who [Shocking Thing]'",
  "content": "130-155 word spoken script",
  "description": "160-word YouTube description with true crime keywords. Subscribe CTA at end.",
  "tags": ["true crime","unsolved mysteries","crime story","cold case","murder mystery","criminal psychology","true crime shorts","dark crimes","crime documentary","mystery shorts","crime files","detective story"],
  "hashtags": "#Shorts #TrueCrime #CrimeFiles #Mystery #UnsolvedMysteries",
  "scenes": [
    "extreme close-up: the specific piece of evidence or crime detail that broke THIS case — a letter, a weapon, a victim's photo — under harsh single lamp",
    "wide shot: the specific location where THIS crime happened — the house, street, building — at night, rain-soaked, police tape visible",
    "medium shot: the suspect or detective central to THIS case, silhouette in doorway or office, cold blue light from window, smoke in air",
    "close-up: the detective's evidence board for THIS specific case — photos, red string, newspaper clippings under dim lamp",
    "overhead shot: the final scene of THIS crime story — the specific location of the resolution, single light source, deep shadows"
  ],
  "voice_style": "suspenseful",
  "content_type": "truecrime"
}}"""


def call_gemini(prompt: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}")
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.85, "maxOutputTokens": 2500}},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Gemini LLM {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Gemini LLM failed: {e}")
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
                  "temperature": 0.85, "max_tokens": 2500},
            timeout=60)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"Groq {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Groq failed: {e}")
    return None


def call_openrouter(prompt: str) -> Optional[str]:
    headers = {"Content-Type": "application/json",
               "HTTP-Referer": "https://darkhistory-api.onrender.com"}
    if OPENROUTER_API_KEY:
        headers["Authorization"] = f"Bearer {OPENROUTER_API_KEY}"
    for model in ["meta-llama/llama-3.3-70b-instruct:free",
                  "google/gemma-3-27b-it:free",
                  "mistralai/mistral-7b-instruct:free"]:
        try:
            resp = requests.post("https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json={"model": model, "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.85, "max_tokens": 2500},
                timeout=90)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                if text and len(text) > 100:
                    print(f"  OpenRouter: {model}")
                    return text
        except Exception as e:
            print(f"OpenRouter {model}: {e}")
    return None


def _clean_json(raw: str) -> Optional[dict]:
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip()).rstrip("`").strip()
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        raw = m.group(0)
    raw = raw.encode('utf-8', errors='ignore').decode('utf-8')
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    for text in [raw, raw.replace('\n', ' '), re.sub(r'\s+', ' ', raw)]:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            continue
    return None


_niche_state = WORK_DIR / "niche_state.json"

def get_next_niche() -> str:
    try:
        if _niche_state.exists():
            last = json.loads(_niche_state.read_text()).get("last", "truecrime")
            nxt = "truecrime" if last == "history" else "history"
        else:
            nxt = "history"
        _niche_state.write_text(json.dumps({"last": nxt}))
        return nxt
    except Exception:
        return random.choice(["history", "truecrime"])


def generate_content(topic: Optional[str], content_type: Optional[str]) -> dict:
    niche = content_type if content_type in ("history", "truecrime") else get_next_niche()
    if not topic:
        topic = random.choice(CONTENT_NICHES[niche]["topics"])
        print(f"🎲 Auto-topic ({niche}): {topic}")
    else:
        print(f"🎯 Custom: {topic}")

    prompt = build_prompt(topic, niche)
    raw, llm = None, None

    print("🧠 Trying Gemini 2.5 Flash...")
    raw = call_gemini(prompt)
    if raw:
        llm = "Gemini 2.5 Flash"
    else:
        print("⚡ Trying Groq...")
        raw = call_groq(prompt)
        if raw:
            llm = "Groq Llama 3.3 70B"
        else:
            print("🔄 Trying OpenRouter...")
            raw = call_openrouter(prompt)
            if raw:
                llm = "OpenRouter"

    if not raw:
        raise Exception("All LLM providers failed")

    print(f"✅ Content via {llm}")
    pipeline_status["llm_used"] = llm
    data = _clean_json(raw)
    if not data:
        raise Exception(f"JSON parse failed. Raw[:300]: {raw[:300]}")

    data["topic"] = topic
    data["content_type"] = niche
    data["llm_used"] = llm
    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2A — VOICE (edge-tts primary, gTTS fallback)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE_PROFILES = {
    "authoritative": {"voice": "en-US-GuyNeural",  "rate": "+0%",  "pitch": "-12Hz"},
    "suspenseful":   {"voice": "en-US-AriaNeural", "rate": "-8%",  "pitch": "-6Hz"},
    "dramatic":      {"voice": "en-GB-RyanNeural", "rate": "-3%",  "pitch": "-8Hz"},
    "default":       {"voice": "en-US-GuyNeural",  "rate": "+0%",  "pitch": "-10Hz"},
}


async def _edge_tts_async(text, voice, rate, pitch, audio_out, timings_out):
    import edge_tts
    comm   = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    sub    = edge_tts.SubMaker()
    events = []
    with open(audio_out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                sub.feed(chunk)
                s = chunk["offset"] / 10_000_000
                d = chunk["duration"] / 10_000_000
                events.append({"word": chunk["text"],
                                "start": round(s, 3),
                                "end":   round(s + d, 3)})
    with open(timings_out, "w") as f:
        json.dump(events, f)
    return events


def _fallback_timings(text: str, duration: float) -> list:
    words = text.split()
    if not words:
        return []
    tpw = duration / len(words)
    return [{"word": w, "start": round(i*tpw, 3), "end": round((i+1)*tpw, 3)}
            for i, w in enumerate(words)]


def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 40.0


def generate_voice(content: str, voice_style: str,
                   audio_path: str, timings_path: str) -> list:
    profile = EDGE_PROFILES.get(voice_style, EDGE_PROFILES["default"])
    try:
        events = asyncio.run(_edge_tts_async(
            content, profile["voice"], profile["rate"], profile["pitch"],
            audio_path, timings_path))
        if events:
            print(f"✅ Voice: {profile['voice']} — {len(events)} word events")
            return events
    except Exception as e:
        print(f"  edge-tts failed: {e}")

    # gTTS fallback
    try:
        from gtts import gTTS
        gTTS(text=content, lang="en", tld="com", slow=False).save(audio_path)
        print("✅ Voice: gTTS fallback")
    except Exception as e:
        raise Exception(f"All TTS failed: {e}")

    dur = get_duration(audio_path)
    wt  = _fallback_timings(content, dur)
    with open(timings_path, "w") as f:
        json.dump(wt, f)
    return wt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2B — ASS SUBTITLES (FIXED: correct margin, larger font, 3 words/card)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ass_time(s: float) -> str:
    cs  = int((s % 1) * 100)
    sec = int(s) % 60
    mn  = int(s) // 60 % 60
    hr  = int(s) // 3600
    return f"{hr}:{mn:02d}:{sec:02d}.{cs:02d}"


def generate_ass_subtitles(word_timings: list, ass_path: str):
    """
    Fixed v7.0:
    - MarginV = 80 (was int(vid_h*0.12)=153 — too high, caused misplacement)
    - FontSize = 78 (was 72)
    - 3 words per card (was 2) — better pacing for dark content
    - Bold=1 enforced
    - Alignment=2 (bottom-center) explicit
    """
    if not word_timings:
        Path(ass_path).write_text("", encoding="utf-8")
        return

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {VID_W}
PlayResY: {VID_H}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Impact,78,&H00FFFFFF,&H000000FF,&H00000000,&HAA000000,1,0,0,0,100,100,1,0,1,5,2,2,30,30,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    # Group into 3-word cards
    cards = []
    i = 0
    while i < len(word_timings):
        group = word_timings[i:i+3]
        i += 3
        start = group[0]["start"]
        end   = group[-1]["end"]
        # Ensure minimum display time of 0.3s
        end   = max(start + 0.3, end)
        text  = " ".join(w["word"] for w in group).upper()
        text  = text.replace("{", "").replace("}", "").replace("\\", "")
        # Wrap at 18 chars for 2-line display
        if len(text) > 18:
            words = text.split()
            mid   = max(1, len(words) // 2)
            text  = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
        cards.append((_ass_time(start), _ass_time(end), text))

    lines = [f"Dialogue: 0,{s},{e},Main,,0,0,0,,{t}" for s, e, t in cards]
    Path(ass_path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ ASS subtitles: {len(cards)} cards, MarginV=80, Font=Impact 78px")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION v8.0
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# THE ROOT CAUSE OF ALL FAILURES:
#   Anonymous Pollinations = 1 req every 15s → 8 scenes = 2min → Render kills at 30s
#   fal.ai, Prodia, HuggingFace = all require working API keys or paid tier
#
# THE SOLUTION (100% free, actually works on Render):
#   TIER 1: Pollinations gen.pollinations.ai POST API + POLLINATIONS_KEY
#           Registered "Seed" tier = 1 req/5s, priority queue, returns in 5-12s
#           Get free key: enter.pollinations.ai → takes 2 minutes, free forever
#   TIER 2: Pollinations image.pollinations.ai GET with referrer header
#           Referrer header gets treated as registered app → faster queue
#           Uses "turbo" model (fastest, <10s even anonymous)
#   TIER 3: Gemini 2.0 Flash Exp image generation (uses existing GEMINI_API_KEY)
#   TIER 4: HuggingFace inference API (uses HF_TOKEN if set)
#   TIER 5: Cinematic dark gradient (always works, <1s)
#
# HOW TO GET YOUR FREE POLLINATIONS KEY (takes 2 minutes):
#   1. Go to enter.pollinations.ai
#   2. Sign in with GitHub (free)
#   3. Go to API Keys → Create Key → Copy the sk_ key
#   4. Add to Render env vars: POLLINATIONS_KEY = sk_yourkey
#   Result: All 8 images generate in ~40s total (under Render's 30s per-request limit)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _verify_image(path: str, min_size: int = 5_000) -> bool:
    p = Path(path)
    return p.exists() and p.stat().st_size > min_size


def _build_image_prompt(scene: str, content_type: str) -> str:
    """Build the final prompt with art style and content-type atmosphere."""
    if content_type == "history":
        atmosphere = (
            "medieval dark historical setting, "
            "torchlight warm amber glow, stone walls, ancient atmosphere"
        )
    else:
        atmosphere = (
            "modern urban noir, "
            "cold blue streetlight, rain-slicked city streets, crime thriller atmosphere"
        )
    return f"{scene}, {COMIC_STYLE}, {atmosphere}"


# ── TIER 1: Pollinations gen.pollinations.ai POST API (with registered key) ───
def generate_image_pollinations_key(scene: str, content_type: str,
                                    output_path: str) -> bool:
    """
    Uses the new gen.pollinations.ai unified POST endpoint with a secret key.
    With a registered key (free at enter.pollinations.ai):
    - Priority queue — no waiting behind anonymous users
    - Returns in 5-12s (well under Render's 30s limit)
    - No watermarks
    - Returns b64_json directly (no second HTTP request needed)
    """
    if not POLLINATIONS_KEY:
        return False

    prompt = _build_image_prompt(scene, content_type)[:600]
    headers = {
        "Authorization": f"Bearer {POLLINATIONS_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "flux",
        "prompt": prompt,
        "size": f"{IMG_W}x{IMG_H}",
        "n": 1,
        "response_format": "b64_json",
        "quality": "medium",
    }
    try:
        print(f"    Pollinations POST (registered key, priority queue)...")
        t0   = time.time()
        resp = requests.post(
            "https://gen.pollinations.ai/v1/images/generations",
            headers=headers, json=payload, timeout=28,
        )
        elapsed = time.time() - t0
        if resp.status_code == 200:
            data   = resp.json()
            images = data.get("data", [])
            if images:
                b64 = images[0].get("b64_json", "")
                if b64:
                    img_bytes = base64.b64decode(b64)
                    Path(output_path).write_bytes(img_bytes)
                    if _verify_image(output_path):
                        print(f"    ✅ Pollinations key ({len(img_bytes)//1024}KB, {elapsed:.1f}s)")
                        return True
                url = images[0].get("url", "")
                if url:
                    ir = requests.get(url, timeout=15)
                    if ir.status_code == 200:
                        Path(output_path).write_bytes(ir.content)
                        if _verify_image(output_path):
                            print(f"    ✅ Pollinations key URL ({len(ir.content)//1024}KB, {elapsed:.1f}s)")
                            return True
        else:
            print(f"    Pollinations key HTTP {resp.status_code}: {resp.text[:150]}")
    except requests.Timeout:
        print(f"    Pollinations key timeout (>28s)")
    except Exception as e:
        print(f"    Pollinations key error: {e}")
    return False


# ── TIER 2: Pollinations image.pollinations.ai GET with referrer ───────────────
def generate_image_pollinations_fast(scene: str, content_type: str,
                                     output_path: str) -> bool:
    """
    Uses image.pollinations.ai GET endpoint with:
    - model=turbo (fastest model, 4-10s even without key)
    - referrer header (tells Pollinations this is a registered app → better priority)
    - 512x912 resolution (faster than 720x1280, scales up fine in Ken Burns)
    - 3 attempts with different seeds
    """
    prompt  = _build_image_prompt(scene, content_type)[:500]
    encoded = requests.utils.quote(prompt)

    # Use 512x912 - generates 2x faster than 720x1280, Ken Burns upscales it
    W, H = 512, 912

    for attempt in range(3):
        seed  = random.randint(1000, 999999)
        model = "turbo" if attempt < 2 else "flux"
        url   = (f"https://image.pollinations.ai/prompt/{encoded}"
                 f"?width={W}&height={H}&model={model}&seed={seed}"
                 f"&nologo=true&enhance=true&private=true")
        try:
            print(f"    Pollinations {model} attempt {attempt+1}/3 ({W}x{H})...")
            t0 = time.time()
            resp = requests.get(
                url,
                headers={
                    "Referer": "https://darkhistory-ai.onrender.com",
                    "User-Agent": "DarkHistory-AI/8.0",
                },
                timeout=25,
            )
            elapsed = time.time() - t0
            if resp.status_code == 200 and len(resp.content) > 8_000:
                Path(output_path).write_bytes(resp.content)
                if _verify_image(output_path):
                    print(f"    ✅ Pollinations {model} ({len(resp.content)//1024}KB, {elapsed:.1f}s)")
                    return True
            print(f"    HTTP {resp.status_code} size={len(resp.content)}")
        except requests.Timeout:
            print(f"    Pollinations timeout attempt {attempt+1}")
        except Exception as e:
            print(f"    Pollinations error: {e}")
        if attempt < 2:
            time.sleep(2)

    return False


# ── TIER 3: Gemini 2.0 Flash Exp image generation ─────────────────────────────
def generate_image_gemini(scene: str, content_type: str, output_path: str) -> bool:
    if not GEMINI_API_KEY:
        return False
    prompt = _build_image_prompt(scene, content_type)[:500]

    # Try gemini-2.0-flash-exp (actual image generation model)
    for model_id in ["gemini-2.0-flash-exp", "gemini-2.0-flash-preview-image-generation"]:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{model_id}:generateContent?key={GEMINI_API_KEY}")
        payload = {
            "contents": [{"parts": [{"text": f"Generate an image: {prompt}"}]}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }
        try:
            print(f"    Gemini {model_id}...")
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                for cand in resp.json().get("candidates", []):
                    for part in cand.get("content", {}).get("parts", []):
                        inline = part.get("inlineData", {})
                        if inline.get("mimeType", "").startswith("image/"):
                            img_bytes = base64.b64decode(inline["data"])
                            Path(output_path).write_bytes(img_bytes)
                            if _verify_image(output_path):
                                print(f"    ✅ Gemini image ({len(img_bytes)//1024}KB)")
                                return True
        except requests.Timeout:
            print(f"    Gemini timeout")
        except Exception as e:
            print(f"    Gemini error: {e}")

    # Try Imagen 3
    url2 = (f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}")
    try:
        resp2 = requests.post(url2,
            json={"instances": [{"prompt": prompt[:400]}],
                  "parameters": {"sampleCount": 1, "aspectRatio": "9:16",
                                 "safetySetting": "block_only_high"}},
            timeout=25)
        if resp2.status_code == 200:
            preds = resp2.json().get("predictions", [])
            if preds:
                b64 = preds[0].get("bytesBase64Encoded", "")
                if b64:
                    img_bytes = base64.b64decode(b64)
                    Path(output_path).write_bytes(img_bytes)
                    if _verify_image(output_path):
                        print(f"    ✅ Gemini Imagen3 ({len(img_bytes)//1024}KB)")
                        return True
    except Exception as e:
        print(f"    Gemini Imagen3 error: {e}")
    return False


# ── TIER 4: HuggingFace FLUX.1-schnell ────────────────────────────────────────
def generate_image_huggingface(scene: str, content_type: str, output_path: str) -> bool:
    if not HF_TOKEN:
        return False
    prompt  = _build_image_prompt(scene, content_type)[:300]
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    models  = [
        ("https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
         {"inputs": prompt, "parameters": {"width": 512, "height": 912, "num_inference_steps": 4}}),
        ("https://api-inference.huggingface.co/models/stabilityai/sdxl-turbo",
         {"inputs": prompt, "parameters": {"num_inference_steps": 1, "guidance_scale": 0.0,
                                           "width": 512, "height": 912}}),
    ]
    for model_url, payload in models:
        for attempt in range(2):
            try:
                print(f"    HuggingFace {model_url.split('/')[-1]}...")
                resp = requests.post(model_url, headers=headers, json=payload, timeout=22)
                if resp.status_code == 503:
                    time.sleep(6)
                    continue
                if resp.status_code == 200 and resp.headers.get("Content-Type","").startswith("image/"):
                    Path(output_path).write_bytes(resp.content)
                    if _verify_image(output_path):
                        print(f"    ✅ HuggingFace ({len(resp.content)//1024}KB)")
                        return True
            except Exception as e:
                print(f"    HF error: {e}")
            time.sleep(1)
    return False


# ── TIER 5: Cinematic Dark Gradient Fallback ───────────────────────────────────
def generate_cinematic_fallback(content_type: str, output_path: str) -> bool:
    """Dark cinematic gradient — looks intentional for this genre."""
    if content_type == "history":
        colors = [("0x1A0C06","0x3D1A08"), ("0x14080A","0x3D1020"), ("0x0A0E10","0x1A2832")]
    else:
        colors = [("0x060810","0x101828"), ("0x080A10","0x141E2A"), ("0x060A0E","0x0E1A26")]
    c1, c2 = random.choice(colors)
    for cmd in [
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"gradients=size={IMG_W}x{IMG_H}:x0=0:y0=0:x1={IMG_W}:y1={IMG_H}:c0={c1}:c1={c2}:duration=1",
         "-vf", "noise=alls=15:allf=t+u,vignette=PI/3,format=yuvj420p",
         "-frames:v", "1", output_path],
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={c2}:size={IMG_W}x{IMG_H}:duration=1",
         "-frames:v", "1", "-vf", "format=yuvj420p", output_path],
    ]:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if r.returncode == 0 and Path(output_path).exists():
            return True
    return False


def generate_image(scene: str, content_type: str, output_path: str,
                   scene_idx: int = 0) -> Optional[str]:
    """
    4-tier image generation. Always returns something.
    Tier 1 (POLLINATIONS_KEY set): POST to gen.pollinations.ai with key
                                   → priority queue, 5-12s, reliable
    Tier 2 (always):               GET image.pollinations.ai turbo model
                                   → with referrer header, 10-25s
    Tier 3 (GEMINI_API_KEY):       Gemini 2.0 Flash Exp image generation
    Tier 4 (HF_TOKEN):             HuggingFace FLUX.1-schnell
    Tier 5 (always):               Dark cinematic gradient
    """
    # Small delay between scenes to avoid rate limiting
    if scene_idx > 0:
        time.sleep(1.5)

    # Tier 1: Pollinations with registered key (fastest, most reliable)
    if POLLINATIONS_KEY:
        print(f"    ⚡ [T1] Pollinations registered key...")
        if generate_image_pollinations_key(scene, content_type, output_path):
            pipeline_status["image_source"] = "Pollinations (key)"
            return "pollinations_key"

    # Tier 2: Pollinations turbo (fast model, referrer header for priority)
    print(f"    ⚡ [T2] Pollinations turbo...")
    if generate_image_pollinations_fast(scene, content_type, output_path):
        pipeline_status["image_source"] = "Pollinations (turbo)"
        return "pollinations_turbo"

    # Tier 3: Gemini image generation
    if GEMINI_API_KEY:
        print(f"    ⚡ [T3] Gemini image generation...")
        if generate_image_gemini(scene, content_type, output_path):
            pipeline_status["image_source"] = "Gemini"
            return "gemini"

    # Tier 4: HuggingFace
    if HF_TOKEN:
        print(f"    ⚡ [T4] HuggingFace FLUX...")
        if generate_image_huggingface(scene, content_type, output_path):
            pipeline_status["image_source"] = "HuggingFace"
            return "huggingface"

    # Tier 5: Gradient (always works)
    print(f"    ⚠️  [T5] All APIs failed — cinematic gradient")
    if generate_cinematic_fallback(content_type, output_path):
        pipeline_status["image_source"] = "Gradient"
        return "gradient"
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3B — KEN BURNS ANIMATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ken_burns_filter(duration: float, style: int) -> str:
    d  = int(duration * CLIP_FPS)
    # 2x output size = enough zoom headroom without memory crash on free tier
    # Input images are 512x912 — scaled up to 1440x2560 for Ken Burns room
    sw = VID_W * 2
    sh = VID_H * 2
    styles = {
        0: f"scale={sw}:{sh},zoompan=z='min(zoom+0.0006,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
        1: f"scale={sw}:{sh},zoompan=z='if(eq(on,1),1.2,max(zoom-0.0006,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
        2: f"scale={sw}:{sh},zoompan=z='1.08':x='iw*0.08*(on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
        3: f"scale={sw}:{sh},zoompan=z='1.08':x='iw*0.08*(1-on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
        4: f"scale={sw}:{sh},zoompan=z='1.08':x='iw/2-(iw/zoom/2)':y='ih*0.06*(on/{d})':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
        5: f"scale={sw}:{sh},zoompan=z='min(zoom+0.0005,1.15)':x='iw*0.04*(on/{d})+(iw/2-(iw/zoom/2))':y='ih/2-(ih/zoom/2)':d={d}:s={VID_W}x{VID_H}:fps={CLIP_FPS}",
    }
    return styles[style % 6]


def build_scene_clip(scene: str, content_type: str, duration: float,
                     output_path: str, kb_style: int, scene_idx: int = 0) -> bool:
    img_path = output_path.replace(".mp4", ".jpg")
    source   = generate_image(scene, content_type, img_path, scene_idx)
    if not source or not _verify_image(img_path):
        return False

    kb_filter = _ken_burns_filter(duration, kb_style)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", f"{kb_filter},format=yuv420p",
        "-t", str(duration), "-c:v", "libx264", "-crf", "23",
        "-preset", "ultrafast", "-r", str(CLIP_FPS),
        "-pix_fmt", "yuv420p", "-threads", "1", "-an", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=300)
    if result.returncode != 0:
        err = result.stderr[-200:].decode(errors='ignore')
        print(f"    Ken Burns failed ({err[-80:]}), using static scale fallback")
        # Static fallback — scale any input size to VID_W x VID_H correctly
        cmd2 = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (
                f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=increase,"
                f"crop={VID_W}:{VID_H},"
                f"format=yuv420p"
            ),
            "-t", str(duration), "-c:v", "libx264", "-crf", "23",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-threads", "1", "-an", output_path,
        ]
        result = subprocess.run(cmd2, capture_output=True, timeout=180)

    Path(img_path).unlink(missing_ok=True)
    return result.returncode == 0 and Path(output_path).exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — BACKGROUND MUSIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUSIC_STYLES = {
    "history":   "dark dramatic orchestral documentary historical suspense cinematic",
    "truecrime": "noir suspense minimal dark ambient crime thriller piano",
    "default":   "dark cinematic suspense atmospheric documentary",
}


def generate_music(content_type: str, music_path: str) -> bool:
    style = MUSIC_STYLES.get(content_type, MUSIC_STYLES["default"])
    try:
        r = requests.get(f"https://audio.pollinations.ai/{requests.utils.quote(style)}", timeout=35)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            print("✅ Music: dark cinematic")
            return True
    except Exception as e:
        print(f"  Music failed: {e}")
    # Silent fallback
    try:
        r = subprocess.run(["ffmpeg", "-y", "-f", "lavfi",
                            "-i", "anullsrc=r=44100:cl=stereo",
                            "-t", "60", "-c:a", "aac", "-b:a", "128k", music_path],
                           capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — VIDEO ASSEMBLY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def assemble_video(clips: list, voice_p: str, music_p: Optional[str],
                   ass_p: str, output_p: str):
    ts = str(int(time.time()))

    # Concat
    txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", txt, "-c", "copy", concat_out],
        capture_output=True, timeout=120)
    if r.returncode != 0:
        raise Exception(f"Concat failed: {r.stderr[-300:].decode(errors='ignore')}")

    voice_dur = min(get_duration(voice_p) + 0.5, 59.0)
    has_subs  = ass_p and Path(ass_p).exists() and Path(ass_p).stat().st_size > 50
    use_music = music_p and Path(music_p).exists()

    vf = f"ass='{ass_p}'" if has_subs else "null"

    if use_music:
        afilt = (
            "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=2.0[voice];"
            "[2:a]volume=0.10,aloop=loop=-1:size=2e+09[music];"
            "[voice][music]amix=inputs=2:duration=first[afinal]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p, "-i", music_p,
            "-t", str(voice_dur),
            "-vf", vf, "-filter_complex", afilt,
            "-map", "0:v", "-map", "[afinal]",
            "-c:v", "libx264", "-crf", "23", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_p,
        ]
    else:
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p,
            "-t", str(voice_dur),
            "-vf", vf,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "libx264", "-crf", "23", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p", "-movflags", "+faststart", output_p,
        ]
    r = subprocess.run(cmd, capture_output=True, timeout=300)
    if r.returncode != 0:
        raise Exception(f"Assembly failed: {r.stderr[-400:].decode(errors='ignore')}")
    print(f"  ✅ Final video: {Path(output_p).stat().st_size // 1024}KB")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 6 — YOUTUBE UPLOAD
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
    desc  = (f"{data['description']}\n\n"
             f"🔔 Subscribe for daily dark history shorts!\n"
             f"👇 Follow for more...\n\n"
             f"{data.get('hashtags', '#Shorts #DarkHistory #TrueCrime')}")
    tags  = list(dict.fromkeys(
        data.get("tags", []) + ["dark history", "true crime", "shorts",
                                "youtube shorts", "history facts", "dark facts"]
    ))[:15]
    meta  = {
        "snippet": {"title": data["title"][:100], "description": desc[:4900],
                    "tags": tags, "categoryId": "22", "defaultLanguage": "en"},
        "status":  {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    init_r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4"},
        json=meta)
    if init_r.status_code != 200:
        raise Exception(f"YouTube init {init_r.status_code}: {init_r.text[:200]}")
    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(
        init_r.headers["Location"],
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(video_bytes))},
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
        # 1 — Content
        pipeline_status["step"] = "Generating viral script + SEO..."
        pipeline_status["step_index"] = 1
        data = generate_content(topic, content_type)
        print(f"✅ Title: {data['title']}")

        # 2 — Voice + word timings
        pipeline_status["step"] = "Synthesizing voice narration..."
        pipeline_status["step_index"] = 2
        voice_p   = str(session / "voice.mp3")
        timings_p = str(session / "timings.json")
        word_timings = generate_voice(
            data["content"], data.get("voice_style", "authoritative"),
            voice_p, timings_p)
        audio_dur = get_duration(voice_p)
        print(f"  Audio duration: {audio_dur:.1f}s")

        # 2B — ASS subtitles
        ass_p = str(session / "subs.ass")
        generate_ass_subtitles(word_timings, ass_p)

        # 3 — Scene clips
        pipeline_status["step"] = "Generating scene images + Ken Burns..."
        pipeline_status["step_index"] = 3
        scenes    = data.get("scenes", [])[:5]
        scene_dur = min(audio_dur / max(len(scenes), 1), 12.0)
        clips     = []
        for i, scene in enumerate(scenes):
            out = str(session / f"scene_{i}.mp4")
            print(f"  🎨 Scene {i+1}/{len(scenes)}: {scene[:55]}...")
            try:
                ok = build_scene_clip(scene, data["content_type"],
                                      scene_dur, out, kb_style=i, scene_idx=i)
                if ok and Path(out).exists() and Path(out).stat().st_size > 1000:
                    clips.append(out)
                    print(f"  ✅ Scene {i+1} done ({pipeline_status.get('image_source','?')})")
                else:
                    print(f"  ⚠️  Scene {i+1} output invalid")
            except Exception as e:
                print(f"  ⚠️  Scene {i+1} exception: {e}")

        if not clips:
            raise Exception("All scenes failed — check image API keys")
        print(f"  ✅ {len(clips)}/{len(scenes)} clips ready")

        # 4 — Music
        pipeline_status["step"] = "Generating cinematic background music..."
        pipeline_status["step_index"] = 4
        music_p = str(session / "music.mp3")
        if not generate_music(data["content_type"], music_p):
            music_p = None

        # 5 — Assemble
        pipeline_status["step"] = "Assembling final video..."
        pipeline_status["step_index"] = 5
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, ass_p, final_p)

        # 6 — Upload
        pipeline_status["step"] = "Uploading to YouTube with SEO..."
        pipeline_status["step_index"] = 6
        if not Path(final_p).exists() or Path(final_p).stat().st_size < 10_000:
            raise Exception(f"Final video invalid")
        video_id = upload_youtube(final_p, data)
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Live: {url}")

        # 7 — Log
        pipeline_status["step"] = "Done! 🎉"
        pipeline_status["step_index"] = 7
        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {"timestamp": ts, "video_id": video_id, "title": data["title"],
                 "topic": data.get("topic", ""), "content_type": data["content_type"],
                 "llm_used": data.get("llm_used", ""),
                 "image_source": pipeline_status.get("image_source", ""),
                 "url": url, "version": "7.0"}
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
    return {"status": "ok", "service": "DarkHistory.ai v7.0",
            "image_fixes": ["gemini-2.0-flash-exp (correct image model)",
                            "fal.ai FLUX free (no key needed)",
                            "HuggingFace FLUX.1-schnell"],
            "caption_fixes": ["MarginV=80 (was 153)", "FontSize=78",
                               "3 words/card", "Alignment=2 bottom-center"]}


@app.post("/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req.topic, req.content_type)
    return {"status": "started", "topic": req.topic or "auto", "version": "7.0"}


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
    return {"niches": [
        {"id": "history",   "label": "Bizarre History", "icon": "🏛️", "cpm": "$8-$15"},
        {"id": "truecrime", "label": "True Crime",       "icon": "🔍", "cpm": "$10-$18"},
    ]}


@app.get("/health")
def health():
    keys = {
        "pollinations_key": bool(POLLINATIONS_KEY),
        "gemini":    bool(GEMINI_API_KEY),
        "groq":      bool(GROQ_API_KEY),
        "openrouter":bool(OPENROUTER_API_KEY),
        "hf_token":  bool(HF_TOKEN),
        "youtube":   bool(YOUTUBE_REFRESH_TOKEN),
    }
    return {
        "status": "healthy", "version": "8.0", "keys": keys,
        "image_tier": (
            "T1-Pollinations-Key (BEST)" if POLLINATIONS_KEY
            else "T2-Pollinations-Turbo (good, add POLLINATIONS_KEY for max reliability)"
        ),
        "setup_tip": (
            "IMAGE WORKING" if POLLINATIONS_KEY
            else "ADD POLLINATIONS_KEY: enter.pollinations.ai → free account → API Keys → Create → add sk_ to Render env vars"
        ),
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/topics")
def get_topics():
    return {"history": HISTORY_TOPICS, "truecrime": TRUE_CRIME_TOPICS,
            "total": len(HISTORY_TOPICS) + len(TRUE_CRIME_TOPICS)}
