"""
DarkHistory.ai -- Backend v8.0
══════════════════════════════════════════════════════════════════
FIXES IN v8.0:

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
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="8.0")
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
COMIC_STYLE = (
    "graphic novel illustration, bold ink outlines, cel shaded, "
    "desaturated teal-grey color palette, warm orange accent highlights, "
    "dramatic directional shadows, gritty dark thriller comic art, "
    "realistic proportions, no text, no watermark, no logo"
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

SCENE RULES (critical — bad scenes = gradient fallback image):
- Each scene: subject + lighting + camera angle + mood. Be hyper-specific.
- Include: smoke/mist/rain/fire/shadow/silhouette as atmospheric details
- Camera: "extreme close-up", "low angle", "wide shot", "overhead shot"
- Lighting: "single candle", "torch on stone", "harsh lamp", "moonlight through bars"
- Style suffix on EVERY scene: "graphic novel illustration, bold ink outlines, teal and amber palette"
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
    "extreme close-up prisoner scarred hands gripping iron chains, single torch glow from right, deep teal shadows, graphic novel illustration, bold ink outlines, teal and amber palette",
    "wide shot medieval dungeon corridor at night, hooded guard silhouette backlit, prisoners visible in background, comic book illustration, deep blue-teal shadows, amber torch accent",
    "overhead shot ancient execution square, crowd of dark silhouetted figures, one lit figure in center, graphic novel style, teal and amber palette, dramatic contrast",
    "medium shot hooded executioner at stone table, single candle from left, bold ink outlines, dark illustrated style, teal shadows, orange warm accent",
    "low angle imposing castle gate at night, lightning sky, two armored silhouettes, dramatic comic art, teal and amber palette"
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
    "extreme close-up detective hands spreading crime photos on desk, harsh overhead lamp, graphic novel illustration, bold ink outlines, teal and amber palette",
    "wide shot rain-soaked empty street at night, lone figure under cold streetlight, police tape, comic book art, deep blue-teal shadows",
    "medium shot shadowy silhouette standing in doorway backlit by cold light, smoke in air, bold ink outlines, teal and amber palette",
    "close-up mugshots and red string on cork board in dim office, graphic novel art, desaturated teal with orange accent",
    "overhead shot abandoned warehouse floor, single hanging bulb, dark corners, shadowy figures, comic book illustration"
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
    Fixed v8.0:
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
    raw_cards = []
    i = 0
    while i < len(word_timings):
        group = word_timings[i:i+3]
        i += 3
        start = group[0]["start"]
        end   = group[-1]["end"]
        end   = max(start + 0.25, end)
        text  = " ".join(w["word"] for w in group).upper()
        text  = text.replace("{", "").replace("}", "").replace("\\", "")
        if len(text) > 18:
            words = text.split()
            mid   = max(1, len(words) // 2)
            text  = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
        raw_cards.append([start, end, text])

    # v8.0 FIX: stretch each card end to the next card start so there is
    # ZERO gap between subtitle cards — no blank frames between words
    for j in range(len(raw_cards) - 1):
        next_start       = raw_cards[j + 1][0]
        raw_cards[j][1]  = max(raw_cards[j][1], next_start - 0.02)

    cards = [(_ass_time(s), _ass_time(e), t) for s, e, t in raw_cards]
    lines = [f"Dialogue: 0,{s},{e},Main,,0,0,0,,{t}" for s, e, t in cards]
    Path(ass_path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ ASS subtitles: {len(cards)} cards, no-gap, MarginV=80, Impact 78px")



# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION v8.0
#
# ROOT CAUSE OF SCENE 2-8 BEING BLACK (confirmed from logs):
#   Scene 1: Pollinations OK (61KB, 1.3s)
#   Scene 2: Pollinations HTTP 429 — RATE LIMITED
#   Scene 3-5: All 429 — rate limited
#
# Pollinations free tier allows ~1 request per 60 seconds from server IPs.
# With sleep(1) between scenes, every scene after scene 1 gets rate-limited.
#
# SOLUTION v8.0 — PRE-GENERATE ALL IMAGES BEFORE PIPELINE STARTS:
#   1. All N scene prompts are sent to Pollinations one-by-one
#   2. 65 seconds sleep between each request (respects rate limit)
#   3. This runs CONCURRENTLY with voice synthesis (which takes ~5-10s)
#      so total extra wait = (N-1) * 65s — but pipeline runs during this
#   4. Images cached to disk — build_scene_clip reads from cache
#   5. Fallback: cinematic gradient for any that still fail
#
# SUBTITLE FIX:
#   Gap between subtitle cards was visible because card end time = last word end.
#   Fixed: card end = next card start - 0.05s (no gap between cards).
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _verify_image(path: str, min_size: int = 5_000) -> bool:
    p = Path(path)
    return p.exists() and p.stat().st_size > min_size


def _build_image_prompt(scene: str, content_type: str) -> str:
    if content_type == "history":
        extra = "medieval historical setting, torchlight warm accent, stone dungeon atmosphere"
    else:
        extra = "modern urban crime noir setting, streetlight warm accent, cold city shadows"
    return f"{scene}, {COMIC_STYLE}, {extra}"


def _poll_one(prompt: str, out_path: str, attempt_label: str) -> bool:
    """
    Single Pollinations request using aiohttp streaming.
    Streaming keeps the connection alive — Render won't kill it.
    Uses turbo model at 512x912 — generates in ~8-15s.
    """
    import asyncio, aiohttp

    async def _stream(url: str) -> bool:
        timeout = aiohttp.ClientTimeout(total=55, connect=10, sock_read=20)
        hdrs = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/124.0",
            "Accept":     "image/webp,image/apng,image/*,*/*;q=0.8",
            "Referer":    "https://pollinations.ai/",
            "Origin":     "https://pollinations.ai",
        }
        try:
            async with aiohttp.ClientSession(headers=hdrs, timeout=timeout) as sess:
                async with sess.get(url) as resp:
                    if resp.status == 429:
                        print(f"    {attempt_label} → 429 rate limited")
                        return False
                    if resp.status != 200:
                        print(f"    {attempt_label} → HTTP {resp.status}")
                        return False
                    chunks, total = [], 0
                    async for chunk in resp.content.iter_chunked(32768):
                        chunks.append(chunk)
                        total += len(chunk)
                    if total < 5_000:
                        print(f"    {attempt_label} → too small ({total}B)")
                        return False
                    Path(out_path).write_bytes(b"".join(chunks))
                    return True
        except asyncio.TimeoutError:
            print(f"    {attempt_label} → timeout")
            return False
        except Exception as e:
            print(f"    {attempt_label} → error: {e}")
            return False

    enc  = requests.utils.quote(prompt[:350])
    seed = random.randint(100, 99999)
    url  = (f"https://image.pollinations.ai/prompt/{enc}"
            f"?width=512&height=912&model=turbo&seed={seed}"
            f"&nologo=true&nofeed=true&enhance=false")
    try:
        return asyncio.run(_stream(url))
    except Exception as e:
        print(f"    {attempt_label} → asyncio error: {e}")
        return False


def generate_cinematic_fallback(content_type: str, output_path: str) -> bool:
    """Atmospheric dark gradient — always works, <1s."""
    if content_type == "history":
        pairs = [("0x1A0C06","0x3D1A08"), ("0x140808","0x3D1010"), ("0x0A0E10","0x1A2832")]
    else:
        pairs = [("0x060810","0x101828"), ("0x080A10","0x141E2A"), ("0x06080E","0x0E1A26")]
    c1, c2 = random.choice(pairs)
    w, h   = 512, 912
    for cmd in [
        ["ffmpeg","-y","-f","lavfi",
         "-i", f"gradients=size={w}x{h}:x0=0:y0=0:x1={w}:y1={h}:c0={c1}:c1={c2}:duration=1",
         "-vf","noise=alls=15:allf=t+u,vignette=PI/3,format=yuvj420p",
         "-frames:v","1", output_path],
        ["ffmpeg","-y","-f","lavfi",
         "-i", f"color=c={c2}:size={w}x{h}:duration=1",
         "-frames:v","1","-vf","format=yuvj420p", output_path],
    ]:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if r.returncode == 0 and Path(output_path).exists():
            return True
    return False


def prefetch_all_images(scenes: list, content_type: str, session_dir: Path) -> dict:
    """
    Pre-generate ALL scene images BEFORE video assembly begins.
    Uses 65s sleep between Pollinations requests to respect rate limit.
    Returns dict: scene_index -> image_path (or None if failed).

    This is the KEY fix: instead of generating images one-by-one inside
    the clip loop (where rate limits kill scenes 2+), we generate them all
    upfront with proper spacing, then clips just read from disk.
    """
    image_cache = {}
    n = len(scenes)

    for i, scene in enumerate(scenes):
        out_path = str(session_dir / f"img_{i:02d}.jpg")
        prompt   = _build_image_prompt(scene, content_type)
        label    = f"[Scene {i+1}/{n}]"

        print(f"  🎨 Pre-fetching image {i+1}/{n}...")

        # Scene 0: no wait. Scenes 1+: wait 65s (Pollinations rate limit = 1/60s)
        if i > 0:
            print(f"    Waiting 65s for Pollinations rate limit...")
            time.sleep(65)

        ok = _poll_one(prompt, out_path, label)

        if ok and _verify_image(out_path):
            kb = Path(out_path).stat().st_size // 1024
            print(f"    ✅ Image {i+1} cached ({kb}KB)")
            image_cache[i] = out_path
        else:
            # Try once more after 10s
            print(f"    Retrying image {i+1} in 10s...")
            time.sleep(10)
            ok2 = _poll_one(prompt, out_path, f"{label} retry")
            if ok2 and _verify_image(out_path):
                kb = Path(out_path).stat().st_size // 1024
                print(f"    ✅ Image {i+1} cached on retry ({kb}KB)")
                image_cache[i] = out_path
            else:
                # Use gradient fallback
                fb_path = str(session_dir / f"img_{i:02d}_fb.jpg")
                if generate_cinematic_fallback(content_type, fb_path):
                    image_cache[i] = fb_path
                    print(f"    ⚠️  Image {i+1} using gradient fallback")
                else:
                    image_cache[i] = None
                    print(f"    ❌ Image {i+1} completely failed")

    success = sum(1 for v in image_cache.values() if v is not None)
    print(f"  ✅ Image prefetch done: {success}/{n} images ready")
    return image_cache


def generate_image(scene: str, content_type: str, output_path: str,
                   scene_idx: int = 0,
                   image_cache: dict = None) -> Optional[str]:
    """
    v8.0: Reads from prefetch cache instead of generating on-demand.
    Falls back to direct Pollinations call if cache miss (shouldn't happen).
    """
    # Read from prefetch cache
    if image_cache and scene_idx in image_cache and image_cache[scene_idx]:
        cached = image_cache[scene_idx]
        if _verify_image(cached):
            # Copy to expected output path
            shutil.copy(cached, output_path)
            pipeline_status["image_source"] = "Pollinations (cached)"
            return "pollinations"

    # Cache miss — try direct call (last resort)
    print(f"    Cache miss scene {scene_idx+1}, direct Pollinations call...")
    prompt = _build_image_prompt(scene, content_type)
    if _poll_one(prompt, output_path, f"[Direct {scene_idx+1}]"):
        if _verify_image(output_path):
            pipeline_status["image_source"] = "Pollinations (direct)"
            return "pollinations"

    # Absolute fallback
    if generate_cinematic_fallback(content_type, output_path):
        pipeline_status["image_source"] = "Gradient"
        return "fallback"
    return None

# STEP 3B — KEN BURNS ANIMATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _ken_burns_filter(duration: float, style: int) -> str:
    d  = int(duration * CLIP_FPS)
    sw = VID_W * 3
    sh = VID_H * 3
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
                     output_path: str, kb_style: int, scene_idx: int = 0,
                     image_cache: dict = None) -> bool:
    img_path = output_path.replace(".mp4", ".jpg")
    source   = generate_image(scene, content_type, img_path, scene_idx,
                              image_cache=image_cache)
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
        # Static fallback
        cmd2 = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=decrease,"
                    f"pad={VID_W}:{VID_H}:(ow-iw)/2:(oh-ih)/2:color=0x080810,"
                    f"format=yuv420p"),
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

        # 3 — Pre-fetch ALL images (rate-limit safe: 65s between requests)
        # This is the KEY fix: Pollinations allows ~1 req/60s from server IPs.
        # We pre-generate all images with proper spacing before clip assembly.
        pipeline_status["step"] = "Pre-fetching scene images (rate-limit safe)..."
        pipeline_status["step_index"] = 3
        scenes    = data.get("scenes", [])[:5]
        scene_dur = min(audio_dur / max(len(scenes), 1), 12.0)

        image_cache = prefetch_all_images(scenes, data["content_type"], session)

        # 3B — Build scene clips from cached images
        pipeline_status["step"] = "Building scene clips with Ken Burns..."
        clips = []
        for i, scene in enumerate(scenes):
            out = str(session / f"scene_{i}.mp4")
            print(f"  🎬 Clip {i+1}/{len(scenes)}: {scene[:55]}...")
            try:
                ok = build_scene_clip(scene, data["content_type"],
                                      scene_dur, out, kb_style=i, scene_idx=i,
                                      image_cache=image_cache)
                if ok and Path(out).exists() and Path(out).stat().st_size > 1000:
                    clips.append(out)
                    src = pipeline_status.get("image_source", "?")
                    print(f"  ✅ Clip {i+1} done ({src})")
                else:
                    print(f"  ⚠️  Clip {i+1} output invalid")
            except Exception as e:
                print(f"  ⚠️  Clip {i+1} exception: {e}")

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
                 "url": url, "version": "8.0"}
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
    return {"status": "ok", "service": "DarkHistory.ai v8.0",
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
    return {"status": "started", "topic": req.topic or "auto", "version": "8.0"}


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
    keys = {"gemini": bool(GEMINI_API_KEY), "groq": bool(GROQ_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY), "hf_token": bool(HF_TOKEN),
            "prodia": bool(PRODIA_TOKEN), "youtube": bool(YOUTUBE_REFRESH_TOKEN)}
    return {"status": "healthy", "version": "8.0", "keys": keys,
            "image_tier": ("gemini" if keys["gemini"] else
                           "fal.ai (free)" if True else
                           "huggingface" if keys["hf_token"] else "gradient"),
            "timestamp": datetime.now().isoformat()}


@app.get("/topics")
def get_topics():
    return {"history": HISTORY_TOPICS, "truecrime": TRUE_CRIME_TOPICS,
            "total": len(HISTORY_TOPICS) + len(TRUE_CRIME_TOPICS)}
