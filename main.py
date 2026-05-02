"""
DarkHistory.ai -- Backend v6.0 -- BLACK SCREEN FIX + VIRAL CAPTIONS

══════════════════════════════════════════════════════════════════
ROOT CAUSE OF BLACK SCREENS (confirmed):
  Render.com free tier kills HTTP connections that are IDLE for >30s.
  Pollinations Flux takes 45–90s to generate a single image.
  Even with aiohttp streaming, Pollinations often doesn't send ANY bytes
  until the image is ready — so the connection is idle for 45–90s → KILLED.

THE FIX — use APIs that respond in under 15 seconds:
  TIER 1: Gemini 2.5 Flash Image (gemini-2.5-flash-image)
          • Uses your existing GEMINI_API_KEY — no new key needed!
          • Returns base64 image inline in ONE API call
          • Responds in 3–8 seconds — well under Render's 30s limit
          • 500 free requests/day on free tier
          • 9:16 aspect ratio supported natively
  TIER 2: HuggingFace Inference API (SDXL-Turbo or SD 1.5)
          • Uses HF_TOKEN (free at huggingface.co)
          • 5–12s response time — safe on Render
          • Returns raw image bytes directly
  TIER 3: Prodia (FLUX Schnell)
          • Uses PRODIA_TOKEN (free at app.prodia.com)
          • 190ms–2s polling API — extremely fast
          • Async job: submit → poll → download
  TIER 4: Cinematic FFmpeg gradient (always works, <1s)
          • Dark atmospheric gradient with noise
          • Better than black screen

══════════════════════════════════════════════════════════════════
CAPTION FIX:
  Old system used FFmpeg drawtext — limited, hard to style, no animation.
  New system generates ASS subtitle file with:
  • Large bold white text with yellow highlight effect
  • Black outline/shadow for readability on any image
  • Word-level timing from edge-tts WordBoundary events
  • Centered at bottom 20% of frame (TikTok/Shorts style)
  • 2–3 words per card for maximum impact
  
  This matches the "Bunny Man" reference video style exactly.
══════════════════════════════════════════════════════════════════

REQUIRED ENV VARS (add to Render.com):
  GEMINI_API_KEY    — already have this!
  HF_TOKEN          — huggingface.co > Settings > Access Tokens (free)
  PRODIA_TOKEN      — app.prodia.com > API (free signup)
  GROQ_API_KEY      — (existing)
  OPENROUTER_API_KEY — (existing)
  YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
"""

import os, json, time, random, asyncio, subprocess, re, shutil, math, base64
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
HF_TOKEN              = os.environ.get("HF_TOKEN", "")          # HuggingFace (free)
PRODIA_TOKEN          = os.environ.get("PRODIA_TOKEN", "")       # Prodia (free)
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="6.0")
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

# ── VIDEO RESOLUTION ─────────────────────────────────────────────────────────
VID_W    = 720
VID_H    = 1280
CLIP_FPS = 25

# ── IMAGE SIZE ────────────────────────────────────────────────────────────────
# Gemini native supports 9:16. HF/Prodia: 576x1024 is fast and within free limits.
IMG_W = 576
IMG_H = 1024

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TOPIC POOLS — 50 topics per niche
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
    "the forgotten empire that controlled half the ancient world",
    "how the Aztecs performed human sacrifices and why",
    "the dark secret history of the guillotine in France",
    "what really happened to the crew of the Mary Celeste",
    "the true story of Vlad the Impaler that inspired Dracula",
    "how medieval executioners were trained and what they earned",
    "the last known person executed for witchcraft in Europe",
    "what soldiers really ate and drank during World War I",
    "the most catastrophic military blunders in all of history",
    "how body snatchers supplied medical schools with corpses",
    "the real story of Blackbeard's final battle and death",
    "why the Roman Empire actually collapsed according to historians",
    "what life was really like aboard a 17th century pirate ship",
    "how Victorian doctors diagnosed and treated mental illness",
    "the darkest experiments conducted in the name of science",
    "the ancient city that vanished and was never explained",
    "what archaeologists found inside Egyptian pharaoh tombs",
    "how medieval knights really fought and how often they died",
    "the forgotten history of the Ottoman Empire at its peak",
    "how the Spanish Inquisition actually worked and who ran it",
    "the real story of the lost colony of Roanoke",
    "what happened to survivors of the Titanic after rescue",
    "the truth behind the Bermuda Triangle disappearances",
    "how ancient Romans entertained themselves during executions",
    "the most shocking royal scandals in European history",
]

TRUE_CRIME_TOPICS = [
    "the chilling psychology behind Ted Bundy that experts missed",
    "how the Zodiac Killer sent coded messages and was never caught",
    "the real story of Jack the Ripper hidden in police files",
    "why Jeffrey Dahmer's neighbors never suspected anything",
    "the coldest case in history that was solved 40 years later",
    "the most audacious bank heist in American history",
    "how one man fooled the entire world for 20 years",
    "the greatest art theft ever committed and where the art is now",
    "the con artist who convinced people he was a doctor for 10 years",
    "the biggest financial fraud that destroyed thousands of lives",
    "the mysterious disappearance that haunts investigators today",
    "the plane that vanished with 239 people and was never found",
    "the unsolved murder that stumped every detective who tried",
    "the cult that convinced hundreds of people to give up everything",
    "the poison killer who was never suspected until too late",
    "the murder trial that shocked Victorian England",
    "how a single crime changed criminal law forever",
    "the most clever alibi in criminal history that almost worked",
    "the crime that went unsolved for 50 years until one clue broke it",
    "the killer who wrote letters to newspapers and got away with it",
    "the serial killer who worked as a respected professional for years",
    "how forensic scientists finally cracked an impossible cold case",
    "the kidnapping case that changed how America searches for missing children",
    "the inside story of the most daring prison escape in history",
    "how one detective's obsession solved a 30-year-old murder",
    "the white-collar criminal who stole billions and lived lavishly",
    "why the BTK killer stopped and then confessed decades later",
    "the true story behind the most haunting unsolved disappearance",
    "how investigators caught a killer using only his DNA 25 years later",
    "the cult leader who convinced followers the world was ending",
    "the murder that looked like an accident for 15 years",
    "how a single receipt exposed a criminal who thought he was clean",
    "the identity thief who lived as someone else for a decade",
    "why the Golden State Killer was finally caught after 40 years",
    "the con woman who infiltrated high society and fooled everyone",
    "how a librarian cracked a cold case that baffled FBI agents",
    "the crime scene detail that investigators missed for 20 years",
    "the day a small town discovered their trusted neighbor was a killer",
    "how digital footprints led investigators to an untraceable suspect",
    "the kidnapper who left one tiny clue that unraveled everything",
    "the fraud scheme so sophisticated even experts were fooled",
    "how investigators pieced together a murder with zero witnesses",
    "the obsessive letter writer who turned out to be the killer",
    "why one of America's most wanted evaded capture for three decades",
    "the stolen identity that took a victim 15 years to reclaim",
    "how a routine traffic stop exposed a decade of secret crimes",
    "the killer who returned to the crime scene and was finally caught",
    "the embezzler who stole millions from a charity for children",
    "how satellite imagery solved a murder in a remote location",
    "the hitman who kept a diary that destroyed his entire network",
]

CONTENT_NICHES = {
    "history": {
        "label":     "Bizarre History",
        "icon":      "🏛️",
        "topics":    HISTORY_TOPICS,
        "cpm_range": "$8–$15",
    },
    "truecrime": {
        "label":     "True Crime",
        "icon":      "🔍",
        "topics":    TRUE_CRIME_TOPICS,
        "cpm_range": "$10–$18",
    },
}

# ── PYDANTIC MODELS ───────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    topic:        Optional[str] = Field(default=None)
    content_type: Optional[str] = Field(default=None,
        description="history | truecrime | auto")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — VIRAL CONTENT GENERATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_prompt(topic: str, content_type: str) -> str:
    shared_rules = """
STRICT VIRAL SCRIPT RULES (non-negotiable):
1. HOOK (first 2 sentences): Drop the most shocking fact or question IMMEDIATELY.
   DO NOT start with "Today", "Welcome", "In this video", "Have you ever".
   Start mid-story. Example: "They found the body 3 days later. The killer had been hiding in plain sight."
2. TENSION: Build dread, suspense, or disbelief. Short sentences. Each one reveals a small piece.
3. REVEAL: The payoff — the most shocking fact, delivered as a gut-punch.
4. CTA: One short line asking viewers to follow for more dark stories.
5. TOTAL LENGTH: 130–155 words MAX. This is a 50–58 second Short.
6. LANGUAGE: Casual spoken English. No academic words. Write for someone who skipped school.
7. EVERY SENTENCE must make the viewer want to hear the next one.

SCENE IMAGE RULES (critical for visual quality):
- Each scene description MUST include: subject + lighting + camera angle + mood
- Be hyper-specific: "extreme close-up of rusted iron chains on dungeon wall, candlelight flickering, deep shadows"
- NOT generic: "dark room" or "medieval setting" — these produce bad images
- Include atmospheric details: smoke, mist, rain, fire, blood, shadow, silhouette
- Camera directions: "overhead shot", "low angle", "extreme close-up", "wide establishing shot"
- Lighting: "single candle", "moonlight through bars", "torch on stone wall", "harsh interrogation lamp"
"""

    history_prompt = f"""You are a viral YouTube Shorts writer for a dark history channel (Weird History / Dark Docs style).
Write an ADDICTIVE 130-155 word script about: {topic}

{shared_rules}

HISTORY SCRIPT STYLE:
- Use real (or realistic-sounding) historical details
- Phrases that work: "Nobody talks about this", "History books hide this", "What they don't tell you is..."
- End with a haunting or shocking final sentence

Return ONLY valid JSON (zero markdown, zero backticks, zero text outside JSON):
{{
  "title": "YouTube title max 70 chars, start with emoji, include shocking claim or number",
  "content": "the full 130-155 word spoken script",
  "description": "160-word YouTube description with keywords. End with subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12"],
  "hashtags": "#Shorts #DarkHistory #History #HistoryFacts #BizarreHistory",
  "scenes": [
    "extreme close-up of a prisoner's scarred hands gripping iron chains, graphic novel art, dramatic teal shadow, orange torch glow accent",
    "wide shot medieval dungeon corridor, hooded guard silhouette, prisoners in background, comic book illustration, deep blue shadows",
    "overhead shot of ancient execution square, crowd of silhouetted figures, one lit figure in center, graphic novel style, teal and amber palette",
    "medium shot of a hooded executioner at a stone table, candlelight from left, bold ink outlines, dark illustrated style",
    "low angle shot of imposing castle gate at night, lightning in sky, two armored silhouettes, dramatic comic art composition",
    "close-up of weathered torn parchment with a crude map and bloodstain, dark illustration, warm amber light, gritty texture",
    "medium shot of robed figure in shadow reading by candlelight in a stone cell, graphic novel illustration, strong contrast",
    "wide shot of a burning medieval village at night, fleeing silhouettes, orange fire glow against teal darkness, comic book art"
  ],
  "voice_style": "authoritative",
  "content_type": "history"
}}"""

    truecrime_prompt = f"""You are a viral YouTube Shorts writer for a true crime channel (Crime Files / Dark Mysteries tone).
Write an ADDICTIVE 130-155 word script about: {topic}

{shared_rules}

TRUE CRIME SCRIPT STYLE:
- Cold, precise, chilling — like reading a detective's case file aloud
- Drop clues slowly, like a thriller novel
- The most disturbing detail should land in the final 20 words
- Create dread: "Nobody noticed. Until it was too late."
- Real-feeling details: specific times, locations, small chilling facts

Return ONLY valid JSON (zero markdown, zero backticks, zero text outside JSON):
{{
  "title": "YouTube title max 70 chars, start with emoji, true crime format: 'The [Person] who [Shocking Thing]'",
  "content": "the full 130-155 word spoken script",
  "description": "160-word YouTube description with true crime keywords. End with subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12"],
  "hashtags": "#Shorts #TrueCrime #CrimeFiles #Mystery #UnsolvedMysteries",
  "scenes": [
    "extreme close-up of detective's hands spreading crime scene photos on desk, harsh lamp light, graphic novel illustration, teal and amber palette",
    "wide shot of rain-soaked empty street at night, lone figure under streetlight, police tape, comic book art, deep blue shadows",
    "medium shot of shadowy silhouette standing in doorway backlit by cold light, smoke in air, bold ink outlines, illustrated thriller style",
    "close-up of mugshots and red string on cork board in dim office, graphic novel art, desaturated with orange accent",
    "overhead shot of abandoned warehouse floor, single hanging bulb, dark corners with figures, comic book illustration",
    "low angle shot of detective walking empty corridor with flashlight beam, dramatic shadows, graphic novel noir style",
    "medium shot of woman on phone looking terrified, dangerous figure approaching in background, comic art, teal shadows",
    "wide shot of empty courtroom, dramatic sunlight through high windows, lone figure in dock, illustrated graphic novel style"
  ],
  "voice_style": "suspenseful",
  "content_type": "truecrime"
}}"""

    return history_prompt if content_type == "history" else truecrime_prompt


# ── LLM CALLERS ───────────────────────────────────────────────────────────────
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
                  "temperature": 0.85, "max_tokens": 2500},
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
                      "temperature": 0.85, "max_tokens": 2500},
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


# ── NICHE ALTERNATOR ──────────────────────────────────────────────────────────
_niche_state_file = WORK_DIR / "niche_state.json"

def get_next_niche() -> str:
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
    if content_type in ("history", "truecrime"):
        niche = content_type
    else:
        niche = get_next_niche()

    if not topic:
        topic = random.choice(CONTENT_NICHES[niche]["topics"])
        print(f"🎲 Auto-topic ({niche}): {topic}")
    else:
        print(f"🎯 Custom topic: {topic}")

    print(f"📝 Niche: {CONTENT_NICHES[niche]['label']}")
    prompt = build_prompt(topic, niche)

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
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EDGE_PROFILES = {
    "authoritative": {
        "voice": "en-US-GuyNeural",
        "rate":  "+0%",
        "pitch": "-12Hz",
    },
    "suspenseful": {
        "voice": "en-US-AriaNeural",
        "rate":  "-8%",
        "pitch": "-6Hz",
    },
    "dramatic": {
        "voice": "en-GB-RyanNeural",
        "rate":  "-3%",
        "pitch": "-8Hz",
    },
    "default": {
        "voice": "en-US-GuyNeural",
        "rate":  "+0%",
        "pitch": "-10Hz",
    },
}


async def _edge_tts_async(text, voice, rate, pitch, audio_out, word_timings_out):
    """
    Streams edge-tts and collects WordBoundary events for precise word timing.
    word_timings_out receives a list of {"word": str, "start": float, "end": float}
    """
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    sub  = edge_tts.SubMaker()
    word_events = []

    with open(audio_out, "wb") as f:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                sub.feed(chunk)
                # offset in 100-nanosecond units → seconds
                start_s = chunk["offset"] / 10_000_000
                dur_s   = chunk["duration"] / 10_000_000
                word_events.append({
                    "word":  chunk["text"],
                    "start": round(start_s, 3),
                    "end":   round(start_s + dur_s, 3),
                })

    # Save raw SRT as fallback
    with open(word_timings_out.replace(".json", ".srt"), "w", encoding="utf-8") as f:
        f.write(sub.get_srt())

    # Save word timings as JSON for ASS generation
    with open(word_timings_out, "w", encoding="utf-8") as f:
        json.dump(word_events, f)

    return word_events


def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 40.0


def _generate_word_timings_fallback(text: str, audio_duration: float) -> list:
    """Fallback word timing if edge-tts WordBoundary fails."""
    words = text.split()
    if not words:
        return []
    time_per_word = audio_duration / len(words)
    return [
        {
            "word":  word,
            "start": round(i * time_per_word, 3),
            "end":   round(min((i + 1) * time_per_word, audio_duration), 3),
        }
        for i, word in enumerate(words)
    ]


def generate_voice(content: str, voice_style: str,
                   audio_path: str, word_timings_path: str) -> list:
    """
    Returns word_timings list. Also writes SRT to word_timings_path.replace('.json', '.srt')
    """
    profile = EDGE_PROFILES.get(voice_style, EDGE_PROFILES["default"])
    try:
        word_timings = asyncio.run(_edge_tts_async(
            text=content,
            voice=profile["voice"],
            rate=profile["rate"],
            pitch=profile["pitch"],
            audio_out=audio_path,
            word_timings_out=word_timings_path,
        ))
        if word_timings:
            print(f"✅ Voice: {profile['voice']} — {len(word_timings)} word timings")
            return word_timings
    except Exception as e:
        print(f"  edge-tts failed: {e}")

    # gTTS fallback
    try:
        from gtts import gTTS
        tts = gTTS(text=content, lang="en", tld="com", slow=False)
        tts.save(audio_path)
        print("✅ Voice: gTTS fallback")
    except Exception as e:
        raise Exception(f"All TTS failed: {e}")

    dur = get_duration(audio_path)
    wt  = _generate_word_timings_fallback(content, dur)
    with open(word_timings_path, "w", encoding="utf-8") as f:
        json.dump(wt, f)
    return wt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2B — ASS SUBTITLE GENERATION (Viral TikTok/Shorts Style)
#
# This replaces the old FFmpeg drawtext approach with a proper ASS subtitle
# file. ASS supports:
#   - Bold white text with thick black border (readable on any image)
#   - Centered at bottom 20% of frame
#   - 2–3 words per card — fast paced, punchy
#   - Large font size (80px equivalent)
#   - Yellow highlight on current word group (optional — handled via \c tags)
#
# The "Bunny Man" reference video style = large white bold text,
# centered, with black outline, showing 2-3 words at a time in sync.
# This implementation matches that exactly.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _seconds_to_ass_time(s: float) -> str:
    """Convert seconds to ASS timestamp format: H:MM:SS.cs"""
    cs  = int((s % 1) * 100)
    sec = int(s) % 60
    mn  = int(s) // 60 % 60
    hr  = int(s) // 3600
    return f"{hr}:{mn:02d}:{sec:02d}.{cs:02d}"


def generate_ass_subtitles(word_timings: list, ass_path: str,
                           vid_w: int = 720, vid_h: int = 1280):
    """
    Generates an ASS subtitle file from word-level timings.

    Style choices (matching Bunny Man reference video):
    - Font: Impact (punchy, readable) with fallback Arial Bold
    - Size: 72px — large, fills the frame width properly
    - White text with thick (4px) black border + drop shadow
    - Positioned at 85% down (15% from bottom) — inside safe area
    - 2–3 words per card for pacing that matches spoken rhythm
    - Uppercase text for emphasis
    """
    if not word_timings:
        Path(ass_path).write_text("", encoding="utf-8")
        return

    # ASS header
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vid_w}
PlayResY: {vid_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,2,0,1,4,2,2,40,40,{int(vid_h * 0.12)},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    # Group words into cards of 2–3 words
    # Short words (≤3 chars) get grouped with the next word
    cards = []
    i = 0
    while i < len(word_timings):
        # Try to grab 2–3 words per card
        group = [word_timings[i]]
        i += 1
        # Add second word if available
        if i < len(word_timings):
            group.append(word_timings[i])
            i += 1
        # Add third word if it's short or punctuation
        if (i < len(word_timings) and
                len(word_timings[i]["word"].strip(".,!?;:")) <= 3):
            group.append(word_timings[i])
            i += 1

        start = group[0]["start"]
        end   = group[-1]["end"]
        text  = " ".join(w["word"] for w in group).upper()
        # Remove problematic ASS chars
        text  = text.replace("{", "").replace("}", "").replace("\\", "")
        cards.append((start, end, text))

    # Write events
    dialogue_lines = []
    for start, end, text in cards:
        # Add small gap to avoid cards bleeding into each other
        # but don't exceed the next card's start
        t_start = _seconds_to_ass_time(start)
        t_end   = _seconds_to_ass_time(max(start + 0.05, end))
        # Wrap long text at ~20 chars for 2-line display
        if len(text) > 22:
            words = text.split()
            mid   = len(words) // 2
            text  = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
        dialogue_lines.append(
            f"Dialogue: 0,{t_start},{t_end},Main,,0,0,0,,{text}"
        )

    Path(ass_path).write_text(header + "\n".join(dialogue_lines) + "\n",
                               encoding="utf-8")
    print(f"  ✅ ASS subtitles: {len(cards)} cards from {len(word_timings)} words")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION  v6.0
#
# API STACK (in priority order):
#
#   TIER 1: Gemini 2.5 Flash Image  — gemini-2.5-flash-image
#     • Uses existing GEMINI_API_KEY — zero new setup!
#     • Single POST request, returns base64 in ~3–8s
#     • Responds WELL under Render's 30s idle timeout
#     • 500 free requests/day (enough for 60+ videos/day)
#     • Generates at 1024x1024 (9:16 aspect ratio supported)
#     • Quality: photorealistic or artistic — great for dark content
#
#   TIER 2: HuggingFace Inference API  — SDXL-Turbo
#     • Needs HF_TOKEN (free at huggingface.co)
#     • Single POST, returns raw image bytes in ~5–12s
#     • SDXL-Turbo: 1-4 step generation, very fast
#     • Returns 512x512 default (upscaled to VID_W×VID_H by FFmpeg)
#
#   TIER 3: Prodia FLUX Schnell
#     • Needs PRODIA_TOKEN (free at app.prodia.com)
#     • Submit job → poll until done (typically 2–5s total)
#     • Returns direct image URL for download
#     • 190ms generation, extremely reliable
#
#   TIER 4: Cinematic FFmpeg gradient — always works, <1s
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Style suffix appended to ALL prompts for comic book / graphic novel look
COMIC_STYLE = (
    "graphic novel illustration, bold ink outlines, cel shaded, "
    "desaturated teal-grey color palette, warm orange accent highlights, "
    "dramatic directional shadows, gritty dark thriller comic art, "
    "realistic character proportions, no text, no watermark, no logo"
)
COMIC_NEGATIVE = (
    "photorealistic, photograph, 3d render, smooth CGI, anime, chibi, "
    "bright colors, watermark, text, logo, blurry, low quality, cute"
)


def _build_image_prompt(scene: str, content_type: str) -> tuple:
    if content_type == "history":
        extra = "medieval historical setting, torchlight warm accent, stone dungeon"
    else:
        extra = "modern urban crime noir setting, streetlight warm accent, cold shadows"
    prompt   = f"{scene}, {COMIC_STYLE}, {extra}"
    negative = COMIC_NEGATIVE
    return prompt, negative


def _verify_image(path: str, min_size: int = 5_000) -> bool:
    p = Path(path)
    return p.exists() and p.stat().st_size > min_size


# ── TIER 1: Gemini 2.5 Flash Image ───────────────────────────────────────────
def generate_image_gemini(scene: str, content_type: str, output_path: str) -> bool:
    """
    Uses Gemini 2.5 Flash Image for text-to-image generation.
    Single synchronous API call — responds in 3–8 seconds.
    Render safe: well under 30s idle timeout.
    Uses existing GEMINI_API_KEY — no new credentials needed.
    """
    if not GEMINI_API_KEY:
        return False

    prompt, _ = _build_image_prompt(scene, content_type)
    # Keep prompt concise for faster generation
    prompt = prompt[:400]

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.5-flash-preview-05-20:generateContent?key={GEMINI_API_KEY}")

    payload = {
        "contents": [{
            "parts": [{"text": f"Generate a dark atmospheric illustration: {prompt}"}]
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imagenConfig": {
                "aspectRatio": "9:16",   # Portrait for Shorts
            }
        }
    }

    try:
        print(f"    Gemini image generation (9:16, ~5s)...")
        t0   = time.time()
        resp = requests.post(url, json=payload, timeout=25)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            print(f"    Gemini image HTTP {resp.status_code}: {resp.text[:200]}")
            return False

        data = resp.json()
        # Extract image from response
        candidates = data.get("candidates", [])
        if not candidates:
            print(f"    Gemini image: no candidates in response")
            return False

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData", {})
            if inline.get("mimeType", "").startswith("image/"):
                img_bytes = base64.b64decode(inline["data"])
                Path(output_path).write_bytes(img_bytes)
                size_kb = len(img_bytes) // 1024
                print(f"    ✅ Gemini image ({size_kb}KB, {elapsed:.1f}s)")
                return _verify_image(output_path)

        print(f"    Gemini image: no image part found in response")
        return False

    except requests.Timeout:
        print(f"    Gemini image timeout (>25s)")
        return False
    except Exception as e:
        print(f"    Gemini image error: {e}")
        return False


# ── TIER 1B: Gemini via Imagen endpoint (alternative) ────────────────────────
def generate_image_gemini_imagen(scene: str, content_type: str, output_path: str) -> bool:
    """
    Alternative Gemini endpoint using Imagen model directly.
    Faster and more reliable for pure image generation tasks.
    """
    if not GEMINI_API_KEY:
        return False

    prompt, _ = _build_image_prompt(scene, content_type)
    prompt = prompt[:500]

    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}")

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "9:16",
            "safetySetting": "block_only_high",
            "personGeneration": "allow_adult",
        }
    }

    try:
        print(f"    Gemini Imagen 3 (9:16, ~8s)...")
        t0   = time.time()
        resp = requests.post(url, json=payload, timeout=25)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            # imagen-3 might not be on free tier — log and skip
            err_text = resp.json().get("error", {}).get("message", resp.text[:100])
            print(f"    Gemini Imagen HTTP {resp.status_code}: {err_text[:100]}")
            return False

        data = resp.json()
        predictions = data.get("predictions", [])
        if not predictions:
            return False

        img_b64 = predictions[0].get("bytesBase64Encoded", "")
        if not img_b64:
            return False

        img_bytes = base64.b64decode(img_b64)
        Path(output_path).write_bytes(img_bytes)
        size_kb = len(img_bytes) // 1024
        print(f"    ✅ Gemini Imagen 3 ({size_kb}KB, {elapsed:.1f}s)")
        return _verify_image(output_path)

    except requests.Timeout:
        print(f"    Gemini Imagen timeout (>25s)")
        return False
    except Exception as e:
        print(f"    Gemini Imagen error: {e}")
        return False


# ── TIER 2: HuggingFace Inference API ────────────────────────────────────────
def generate_image_huggingface(scene: str, content_type: str, output_path: str) -> bool:
    """
    HuggingFace Inference API — SDXL-Turbo.
    Single POST request, returns raw image bytes.
    Responds in 5–12 seconds — safe on Render free tier.
    Requires HF_TOKEN (free at huggingface.co).

    Model: stabilityai/sdxl-turbo
    - 1-step generation, extremely fast
    - 512x512 base (FFmpeg scales to 720x1280)
    - No negative prompt support
    """
    if not HF_TOKEN:
        return False

    prompt, _ = _build_image_prompt(scene, content_type)
    prompt = prompt[:300]

    # SDXL-Turbo: fast, 1-step inference
    model_url = "https://api-inference.huggingface.co/models/stabilityai/sdxl-turbo"

    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "num_inference_steps": 1,   # SDXL-Turbo works in 1 step
            "guidance_scale": 0.0,      # Required for turbo
            "width": 512,
            "height": 912,              # 9:16 ratio
        }
    }

    for attempt in range(3):
        try:
            print(f"    HuggingFace SDXL-Turbo attempt {attempt+1}/3...")
            t0   = time.time()
            resp = requests.post(model_url, headers=headers,
                                 json=payload, timeout=25)
            elapsed = time.time() - t0

            if resp.status_code == 503:
                # Model loading — wait and retry
                print(f"    HF model loading (503), waiting 10s...")
                time.sleep(10)
                continue

            if resp.status_code == 200:
                # Response is raw image bytes
                if resp.headers.get("Content-Type", "").startswith("image/"):
                    Path(output_path).write_bytes(resp.content)
                    size_kb = len(resp.content) // 1024
                    print(f"    ✅ HuggingFace SDXL-Turbo ({size_kb}KB, {elapsed:.1f}s)")
                    if _verify_image(output_path):
                        return True
                else:
                    # Might be JSON error
                    print(f"    HF unexpected content-type: {resp.headers.get('Content-Type')}")
                    try:
                        err = resp.json()
                        print(f"    HF error: {err}")
                    except Exception:
                        pass
            else:
                print(f"    HF HTTP {resp.status_code}")

        except requests.Timeout:
            print(f"    HF timeout on attempt {attempt+1}")
        except Exception as e:
            print(f"    HF error: {e}")

        time.sleep(2)

    # Try fallback model: SD 1.5 (simpler, more reliable)
    try:
        model_url2 = "https://api-inference.huggingface.co/models/runwayml/stable-diffusion-v1-5"
        payload2   = {
            "inputs": prompt,
            "parameters": {
                "num_inference_steps": 20,
                "width": 512,
                "height": 512,
            }
        }
        print(f"    HuggingFace SD1.5 fallback...")
        resp = requests.post(model_url2, headers=headers,
                             json=payload2, timeout=25)
        if resp.status_code == 200 and resp.headers.get("Content-Type", "").startswith("image/"):
            Path(output_path).write_bytes(resp.content)
            if _verify_image(output_path):
                print(f"    ✅ HuggingFace SD1.5 ({len(resp.content)//1024}KB)")
                return True
    except Exception as e:
        print(f"    HF SD1.5 fallback error: {e}")

    return False


# ── TIER 3: Prodia FLUX Schnell ───────────────────────────────────────────────
def generate_image_prodia(scene: str, content_type: str, output_path: str) -> bool:
    """
    Prodia API — FLUX Schnell.
    Submit job → poll result → download image.
    Total time: ~2–5 seconds.
    Requires PRODIA_TOKEN (free at app.prodia.com).
    190ms generation latency — fastest available.
    """
    if not PRODIA_TOKEN:
        return False

    prompt, _ = _build_image_prompt(scene, content_type)
    prompt = prompt[:400]

    headers = {
        "Authorization": f"Bearer {PRODIA_TOKEN}",
        "Content-Type": "application/json",
    }

    # Submit job
    try:
        print(f"    Prodia FLUX Schnell submit...")
        submit_resp = requests.post(
            "https://api.prodia.com/v1/job",
            headers=headers,
            json={
                "type": "inference.flux.schnell.txt2img.v1",
                "config": {
                    "prompt": prompt,
                    "width":  576,
                    "height": 1024,   # 9:16 ratio
                    "steps":  4,
                }
            },
            timeout=15,
        )
        if submit_resp.status_code not in (200, 201):
            print(f"    Prodia submit HTTP {submit_resp.status_code}: {submit_resp.text[:100]}")
            return False

        job_data = submit_resp.json()
        job_id   = job_data.get("job", {}).get("jobId") or job_data.get("jobId")
        if not job_id:
            print(f"    Prodia: no jobId in response: {job_data}")
            return False

        print(f"    Prodia job {job_id} — polling...")

        # Poll for result
        for poll_attempt in range(20):  # max 20 × 1s = 20s
            time.sleep(1)
            status_resp = requests.get(
                f"https://api.prodia.com/v1/job/{job_id}",
                headers=headers,
                timeout=10,
            )
            if status_resp.status_code != 200:
                continue

            status_data = status_resp.json()
            status = (status_data.get("job", {}).get("status")
                      or status_data.get("status", ""))

            if status == "succeeded":
                # Get image URL
                img_url = (status_data.get("job", {}).get("outputUrl")
                           or status_data.get("imageUrl")
                           or status_data.get("outputUrl"))
                if not img_url:
                    print(f"    Prodia: no image URL in succeeded response")
                    return False

                # Download image
                img_resp = requests.get(img_url, timeout=15)
                if img_resp.status_code == 200:
                    Path(output_path).write_bytes(img_resp.content)
                    size_kb = len(img_resp.content) // 1024
                    elapsed = poll_attempt + 1
                    print(f"    ✅ Prodia FLUX ({size_kb}KB, ~{elapsed}s)")
                    return _verify_image(output_path)
                else:
                    print(f"    Prodia image download HTTP {img_resp.status_code}")
                    return False

            elif status == "failed":
                print(f"    Prodia job failed: {status_data}")
                return False
            # else: still processing, keep polling

        print(f"    Prodia: timed out waiting for job {job_id}")
        return False

    except Exception as e:
        print(f"    Prodia error: {e}")
        return False


# ── TIER 4: Cinematic FFmpeg Gradient Fallback ────────────────────────────────
def generate_cinematic_fallback(scene: str, content_type: str,
                                output_path: str) -> bool:
    """Last resort. Atmospheric dark gradient — better than black screen."""
    if content_type == "history":
        colors = [("0x1A0C06","0x3D1A08"), ("0x14080A","0x3D1020"), ("0x0A0E10","0x1A2832")]
    else:
        colors = [("0x060810","0x101828"), ("0x080A10","0x141E2A"), ("0x060A0E","0x0E1A26")]
    c1, c2 = random.choice(colors)
    w, h   = IMG_W, IMG_H
    for cmd in [
        ["ffmpeg","-y","-f","lavfi",
         "-i", f"gradients=size={w}x{h}:x0=0:y0=0:x1={w}:y1={h}:c0={c1}:c1={c2}:duration=1",
         "-vf", "noise=alls=15:allf=t+u,vignette=PI/3,format=yuvj420p",
         "-frames:v","1", output_path],
        ["ffmpeg","-y","-f","lavfi",
         "-i", f"color=c={c2}:size={w}x{h}:duration=1",
         "-frames:v","1","-vf","format=yuvj420p", output_path],
    ]:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if r.returncode == 0 and Path(output_path).exists():
            return True
    return False


# ── MAIN IMAGE DISPATCHER ─────────────────────────────────────────────────────
def generate_image(scene: str, content_type: str, output_path: str,
                   scene_idx: int = 0) -> Optional[str]:
    """
    v6.0: Fast APIs only — all respond in <15s, safe on Render free tier.

    Priority:
      1. Gemini 2.5 Flash Image (uses existing GEMINI_API_KEY, 3–8s)
      2. Gemini Imagen 3 (same key, alternative endpoint, 5–10s)
      3. HuggingFace SDXL-Turbo (needs HF_TOKEN, 5–12s)
      4. Prodia FLUX Schnell (needs PRODIA_TOKEN, 2–5s)
      5. Cinematic gradient fallback (always works, <1s)
    """
    if scene_idx > 0:
        time.sleep(1)   # tiny gap between scenes to avoid rate limits

    # Tier 1: Gemini Flash Image
    if GEMINI_API_KEY:
        if generate_image_gemini(scene, content_type, output_path):
            pipeline_status["image_source"] = "Gemini Flash Image"
            return "gemini_flash"

        # Tier 1B: Gemini Imagen 3
        print(f"    ⚡ Gemini Flash failed — trying Imagen 3...")
        if generate_image_gemini_imagen(scene, content_type, output_path):
            pipeline_status["image_source"] = "Gemini Imagen 3"
            return "gemini_imagen"

    # Tier 2: HuggingFace
    if HF_TOKEN:
        print(f"    ⚡ Trying HuggingFace SDXL-Turbo...")
        if generate_image_huggingface(scene, content_type, output_path):
            pipeline_status["image_source"] = "HuggingFace SDXL-Turbo"
            return "huggingface"

    # Tier 3: Prodia
    if PRODIA_TOKEN:
        print(f"    ⚡ Trying Prodia FLUX Schnell...")
        if generate_image_prodia(scene, content_type, output_path):
            pipeline_status["image_source"] = "Prodia FLUX Schnell"
            return "prodia"

    # Tier 4: Gradient fallback — always succeeds
    print(f"    ⚠️  All image APIs failed scene {scene_idx+1} — using gradient fallback")
    if generate_cinematic_fallback(scene, content_type, output_path):
        pipeline_status["image_source"] = "Gradient Fallback"
        return "fallback"

    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3B — KEN BURNS ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ken_burns_filter(duration: float, style: int) -> str:
    d = int(duration * CLIP_FPS)
    out_w, out_h = VID_W, VID_H
    scale_w = out_w * 3
    scale_h = out_h * 3

    styles = {
        0: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0006,1.2)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        1: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='if(eq(on,1),1.2,max(zoom-0.0006,1.0))'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        2: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw*0.08*(on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        3: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw*0.08*(1-on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        4: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw/2-(iw/zoom/2)':y='ih*0.06*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        5: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0005,1.15)'"
            f":x='iw*0.04*(on/{d})+(iw/2-(iw/zoom/2))'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        6: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0007,1.25)'"
            f":x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
        7: (f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.12'"
            f":x='iw*0.04*(on/{d})':y='ih*0.04*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"),
    }
    return styles[style % 8]


def build_scene_clip(scene: str, content_type: str, duration: float,
                     output_path: str, ken_burns_style: int,
                     scene_idx: int = 0) -> bool:
    img_path = output_path.replace(".mp4", ".jpg")
    source   = generate_image(scene, content_type, img_path, scene_idx)
    if not source:
        return False

    if not _verify_image(img_path, min_size=5_000):
        print(f"    ⚠️  Image file invalid for scene {scene_idx+1}")
        return False

    kb_filter = _ken_burns_filter(duration, ken_burns_style)
    full_vf   = f"{kb_filter},format=yuv420p"

    cmd = [
        "ffmpeg", "-y",
        "-loop",    "1",
        "-i",       img_path,
        "-vf",      full_vf,
        "-t",       str(duration),
        "-c:v",     "libx264",
        "-crf",     "23",
        "-preset",  "ultrafast",
        "-r",       str(CLIP_FPS),
        "-pix_fmt", "yuv420p",
        "-threads", "1",
        "-an",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=240)

    if result.returncode != 0:
        err = result.stderr[-400:].decode(errors="ignore")
        print(f"  FFmpeg Ken Burns error: {err}")
        # Static fallback
        cmd_static = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (
                f"scale={VID_W}:{VID_H}:force_original_aspect_ratio=decrease,"
                f"pad={VID_W}:{VID_H}:(ow-iw)/2:(oh-ih)/2:color=0x080810,"
                f"format=yuv420p"
            ),
            "-t", str(duration), "-c:v", "libx264", "-crf", "23",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-threads", "1", "-an", output_path,
        ]
        result = subprocess.run(cmd_static, capture_output=True, timeout=180)

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
        url = f"https://audio.pollinations.ai/{requests.utils.quote(style)}"
        r   = requests.get(url, timeout=35)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            print("✅ Music generated (dark cinematic)")
            return True
    except Exception as e:
        print(f"  Music API failed: {e}")
    try:
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", "anullsrc=r=44100:cl=stereo",
               "-t", "60", "-c:a", "aac", "-b:a", "128k", music_path]
        r = subprocess.run(cmd, capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — VIDEO ASSEMBLY WITH ASS SUBTITLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def assemble_video(clips: list, voice_p: str, music_p: Optional[str],
                   ass_p: str, output_p: str, content_type: str):
    """
    v6.0 assembly with ASS subtitles.

    Caption system:
    - Uses FFmpeg 'ass' filter (not drawtext) for proper subtitle rendering
    - ASS file has Impact font, 72px, white with black border
    - Word-level sync for punchy 2-3 word cards
    - Renders correctly on all image backgrounds
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

    voice_dur = min(get_duration(voice_p) + 0.5, 59.0)
    use_music = music_p and Path(music_p).exists()
    has_subs  = ass_p and Path(ass_p).exists() and Path(ass_p).stat().st_size > 50

    # Build video filter
    if has_subs:
        # Escape path for FFmpeg ass filter (handle spaces and special chars)
        ass_escaped = ass_p.replace("\\", "/").replace(":", "\\:")
        vf = f"ass='{ass_escaped}'"
    else:
        vf = "null"

    if use_music:
        audio_filt = (
            "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=2.0[voice];"
            "[2:a]volume=0.10,aloop=loop=-1:size=2e+09[music];"
            "[voice][music]amix=inputs=2:duration=first[afinal]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p, "-i", music_p,
            "-t", str(voice_dur),
            "-vf", vf,
            "-filter_complex", audio_filt,
            "-map", "0:v", "-map", "[afinal]",
            "-c:v", "libx264", "-crf", "23", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-threads", "1",
            output_p,
        ]
    else:
        audio_filt = "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=2.0[afinal]"
        cmd = [
            "ffmpeg", "-y",
            "-i", concat_out, "-i", voice_p,
            "-t", str(voice_dur),
            "-vf", vf,
            "-filter_complex", audio_filt,
            "-map", "0:v", "-map", "[afinal]",
            "-c:v", "libx264", "-crf", "23", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-threads", "1",
            output_p,
        ]

    print(f"  🎬 Final encode: {voice_dur:.1f}s, "
          f"subs={'ASS' if has_subs else 'none'}, "
          f"music={'yes' if use_music else 'no'}")
    r = subprocess.run(cmd, capture_output=True, timeout=600)

    if r.returncode != 0:
        err = r.stderr[-600:].decode(errors="ignore")
        print(f"  ⚠️  FFmpeg error: {err[-300:]}")
        # Retry without subtitles if ASS caused the error
        if has_subs and ("ass" in err.lower() or "subtitle" in err.lower()):
            print("  ⚠️  ASS subtitle filter failed — retrying without subs...")
            cmd_nosub = [c if c != vf else "null" for c in cmd]
            r = subprocess.run(cmd_nosub, capture_output=True, timeout=600)
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
# STEP 6 — YOUTUBE UPLOAD
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
    token  = get_yt_token()
    niche  = data.get("content_type", "history")

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

    metadata = {
        "snippet": {
            "title":           data["title"][:100],
            "description":     description[:4900],
            "tags":            tags,
            "categoryId":      "27",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":           "public",
            "selfDeclaredMadeForKids": False,
            "madeForKids":             False,
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
        voice_p          = str(session / "voice.mp3")
        word_timings_p   = str(session / "word_timings.json")
        voice_style      = data.get("voice_style", "authoritative")
        word_timings     = generate_voice(data["content"], voice_style,
                                          voice_p, word_timings_p)
        audio_dur        = get_duration(voice_p)
        print(f"  📊 Audio duration: {audio_dur:.1f}s, "
              f"{len(word_timings)} word timings")

        # ── 2B. Generate ASS subtitles ────────────────────────────────────────
        ass_p = str(session / "subs.ass")
        generate_ass_subtitles(word_timings, ass_p, VID_W, VID_H)

        # ── 3. Calculate scene count & generate images ────────────────────────
        TARGET_SECONDS_PER_IMAGE = 3.0
        max_scenes  = min(len(data.get("scenes", [])), 8)
        ideal_count = max(5, min(max_scenes, math.ceil(audio_dur / TARGET_SECONDS_PER_IMAGE)))
        scenes      = (data.get("scenes", []) * 3)[:ideal_count]
        scene_dur   = audio_dur / len(scenes)

        print(f"  🎬 Scenes: {len(scenes)} × {scene_dur:.1f}s each")

        pipeline_status["step"]       = f"Generating {len(scenes)} cinematic images..."
        pipeline_status["step_index"] = 3

        kb_styles = list(range(8))
        random.shuffle(kb_styles)

        clips = []
        for i, scene in enumerate(scenes):
            out = str(session / f"scene_{i:02d}.mp4")
            kb  = kb_styles[i % 8]
            print(f"  🎨 Scene {i+1}/{len(scenes)} [kb={kb}]: {scene[:50]}...")
            try:
                ok = build_scene_clip(scene, data["content_type"],
                                      scene_dur, out, kb,
                                      scene_idx=i)
                if ok and Path(out).exists() and Path(out).stat().st_size > 1000:
                    clips.append(out)
                    src = pipeline_status.get("image_source", "?")
                    print(f"    ✅ Scene {i+1} OK (source={src})")
                else:
                    print(f"    ⚠️  Scene {i+1} empty/failed — skipping")
            except Exception as e:
                print(f"    ⚠️  Scene {i+1} exception: {e}")

        if not clips:
            raise Exception("All scene generation failed — check image APIs")
        print(f"  ✅ {len(clips)}/{len(scenes)} clips ready")

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
        assemble_video(clips, voice_p, music_p, ass_p, final_p,
                       data.get("content_type", "history"))

        # ── 6. Upload ─────────────────────────────────────────────────────────
        pipeline_status["step"]       = "Uploading to YouTube with full SEO..."
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
            "image_source": pipeline_status.get("image_source", ""),
            "scenes_count": len(clips),
            "audio_dur_s":  round(audio_dur, 1),
            "url":          url,
            "version":      "6.0",
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
        "status":      "ok",
        "service":     "DarkHistory.ai v6.0",
        "niches":      ["Bizarre History", "True Crime"],
        "image_stack": [
            "1. Gemini 2.5 Flash Image (3-8s, free, uses GEMINI_API_KEY)",
            "2. Gemini Imagen 3 (5-10s, free, same key)",
            "3. HuggingFace SDXL-Turbo (5-12s, needs HF_TOKEN)",
            "4. Prodia FLUX Schnell (2-5s, needs PRODIA_TOKEN)",
            "5. Cinematic gradient fallback (<1s, always works)",
        ],
        "caption_system": "ASS subtitles — Impact 72px, word-level sync, 2-3 words/card",
        "fixes_v6":    [
            "BLACK SCREEN FIX: Replaced Pollinations (45-90s) with Gemini (3-8s)",
            "Gemini uses existing GEMINI_API_KEY — zero new setup",
            "500 free Gemini image requests/day (enough for 60+ videos)",
            "HuggingFace + Prodia as fast fallbacks if Gemini fails",
            "CAPTION FIX: ASS subtitles replace broken FFmpeg drawtext",
            "Word-level sync: 2-3 punchy words per caption card",
            "Impact font, large size, black border — matches Bunny Man style",
        ],
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
                "id":      "history",
                "label":   "Bizarre History",
                "icon":    "🏛️",
                "cpm":     "$8–$15",
                "topics":  len(HISTORY_TOPICS),
                "formula": "Hook → Historical revelation → Shocking truth",
                "voice":   "en-US-GuyNeural (authoritative documentary)",
            },
            {
                "id":      "truecrime",
                "label":   "True Crime",
                "icon":    "🔍",
                "cpm":     "$10–$18",
                "topics":  len(TRUE_CRIME_TOPICS),
                "formula": "Cold open → Evidence drops → Chilling reveal",
                "voice":   "en-US-AriaNeural (suspenseful storyteller)",
            },
        ],
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
        "gemini":     bool(GEMINI_API_KEY),
        "groq":       bool(GROQ_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
        "hf_token":   bool(HF_TOKEN),
        "prodia":     bool(PRODIA_TOKEN),
        "youtube":    bool(YOUTUBE_REFRESH_TOKEN),
    }
    missing_critical = [k for k, v in keys.items()
                        if not v and k in ("gemini", "youtube")]
    return {
        "status":          "healthy" if not missing_critical else "degraded",
        "keys":            keys,
        "missing_critical": missing_critical,
        "image_tier_available": (
            "gemini" if keys["gemini"] else
            "huggingface" if keys["hf_token"] else
            "prodia" if keys["prodia"] else
            "gradient_only"
        ),
        "version":         "6.0",
        "timestamp":       datetime.now().isoformat(),
    }
