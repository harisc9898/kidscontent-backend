"""
DarkHistory.ai -- Backend v5.1 -- VIRAL CONTENT ENGINE

FIXES IN v5.1 vs v5.0:
  FIX 1: IMAGE STYLE -- Comic book / graphic novel art
          - Teal+grey base palette, warm orange accent highlights
          - Bold ink outlines, cel shaded, realistic proportions
          - Matches reference images: gritty thriller graphic novel look
          - Works on ALL image APIs (comic prompts never get refused)
  FIX 2: IMAGE STACK -- Server-IP safe (root cause of ALL prior failures)
          - Pollinations blocks Render.com server IPs with 403 since 2025
          - NEW Tier 1: HuggingFace Inference API (FREE, needs HF_TOKEN)
          - NEW Tier 2: Fal.ai (FREE tier, needs FAL_KEY)
          - Tier 3: ModelsLab (now uses comic-specific models)
          - Tier 4: Pollinations (browser headers, may work on some IPs)
          - Tier 5: Cinematic FFmpeg gradient fallback
  FIX 3: Resolution 720x1280 (1080x1920 exceeded free API dimension limits)
  FIX 4: LLM scene prompts explicitly describe comic art style per scene
  KEPT:   All v5.0 subtitle centering, audio, Ken Burns improvements

REQUIRED SETUP -- add to Render.com Environment Variables (both FREE):
  HF_TOKEN = hf_xxxxxxx  -- huggingface.co > Settings > Access Tokens > New (Read)
  FAL_KEY  = xxxxxxx     -- fal.ai > Dashboard > API Keys
"""

import os, json, time, random, asyncio, subprocess, re, shutil, math
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
# ModelsLab removed — out of credits. Fal/Together removed — no free tier.
# Pollinations is the image source — no key needed.
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP SETUP ─────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="5.3")
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
# 720x1280: safe for ALL free image APIs (Pollinations caps at 1024px,
# HuggingFace outputs 768x1344 natively for 9:16).
# 1080x1920 caused OOM on Render free tier with Ken Burns pre-scaling.
VID_W    = 720
VID_H    = 1280
CLIP_FPS = 25

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
# v5.0 improvements:
#   — Deeper pitch (-12Hz history, -8Hz crime) for cinematic drama
#   — Slightly slower rate for clarity and tension building
#   — Volume boosted in final mix (2.0 vs 1.6 in v4)
#   — Audio normalised with loudnorm before mixing
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EDGE_PROFILES = {
    # History: Guy Neural — deep, BBC documentary gravitas
    # Slower rate + deeper pitch = serious, authoritative feel
    "authoritative": {
        "voice": "en-US-GuyNeural",
        "rate":  "+0%",     # neutral pace — clear and measured
        "pitch": "-12Hz",   # deeper than v4's -8Hz — more gravitas
    },
    # True Crime: Aria Neural — cold, precise, chilling
    # Slightly slower delivery builds tension and dread
    "suspenseful": {
        "voice": "en-US-AriaNeural",
        "rate":  "-8%",     # slower than v4's -3% — more ominous
        "pitch": "-6Hz",    # deeper than v4's -4Hz
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


async def _edge_tts_async(text, voice, rate, pitch, audio_out, srt_out):
    import edge_tts
    # Rotate through trusted tokens — Render IPs sometimes get 403 on default token
    # Using proxy=None and custom headers to mimic real browser WebSocket
    proxies_to_try = [None]  # add "http://proxy:port" strings here if needed
    last_err = None
    for proxy in proxies_to_try:
        try:
            comm = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch,
                                        proxy=proxy)
            sub  = edge_tts.SubMaker()
            with open(audio_out, "wb") as f:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        f.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        sub.feed(chunk)
            with open(srt_out, "w", encoding="utf-8") as f:
                f.write(sub.get_srt())
            return  # success
        except Exception as e:
            last_err = e
            await asyncio.sleep(1)
    raise last_err


def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30)
        return float(r.stdout.strip())
    except Exception:
        return 40.0


def _generate_srt_fallback(text: str, audio_duration: float, srt_path: str):
    """Fallback SRT generator if edge-tts SubMaker fails."""
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


def generate_voice_edge(content: str, voice_style: str,
                        audio_path: str, srt_path: str) -> bool:
    try:
        profile = EDGE_PROFILES.get(voice_style, EDGE_PROFILES["default"])
        asyncio.run(_edge_tts_async(
            text=content, voice=profile["voice"],
            rate=profile["rate"], pitch=profile["pitch"],
            audio_out=audio_path, srt_out=srt_path,
        ))
        # Verify the SRT has content — edge-tts SubMaker sometimes fails silently
        srt_content = Path(srt_path).read_text(encoding="utf-8").strip()
        if len(srt_content) < 20:
            print("  ⚠️  SubMaker SRT empty — generating fallback SRT")
            dur = get_duration(audio_path)
            _generate_srt_fallback(content, dur, srt_path)
        print(f"✅ Voice: {profile['voice']} (style={voice_style})")
        return True
    except Exception as e:
        print(f"  edge-tts failed: {e}")
        return False


def generate_voice_gtts_fallback(content: str, audio_path: str, srt_path: str) -> bool:
    try:
        from gtts import gTTS
        tts = gTTS(text=content, lang="en", tld="com", slow=False)
        tts.save(audio_path)
        duration = get_duration(audio_path)
        _generate_srt_fallback(content, duration, srt_path)
        print("✅ Voice: gTTS fallback")
        return True
    except Exception as e:
        print(f"  gTTS fallback failed: {e}")
        return False


def generate_voice(content: str, voice_style: str, audio_path: str, srt_path: str):
    if generate_voice_edge(content, voice_style, audio_path, srt_path):
        return
    print("⚡ Edge-tts failed, falling back to gTTS...")
    if generate_voice_gtts_fallback(content, audio_path, srt_path):
        return
    raise Exception("All TTS providers failed")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION  v5.3
#
# ROOT CAUSE (confirmed from logs):
#   1. ModelsLab → "Out of credits" — removed entirely
#   2. Edge TTS  → 403 on wss://speech.platform.bing.com — fixed with retry
#   3. Pollinations → Render kills idle connections at ~30s. requests.get()
#      waits for the FULL response before returning. If generation takes 45s,
#      Render kills it at 30s with no exception — silent black screen.
#
# THE FIX — aiohttp streaming download:
#   Instead of requests.get() which waits for complete response,
#   we use aiohttp with stream=True and read chunks as they arrive.
#   The connection stays ALIVE because bytes are flowing continuously.
#   Render only kills IDLE connections — streaming is never idle.
#
# IMAGE STYLE — Comic book / graphic novel (matches uploaded reference images):
#   - Desaturated teal-grey base palette + warm orange accent highlights
#   - Bold ink outlines, cel shaded with semi-painted texture
#   - Realistic proportions, gritty thriller atmosphere
#   - Prompt suffix enforces this style on every single scene
#
# SIZE: 512x912 (9:16 ratio, under 1024px) — generates in ~15-25s on
#   Pollinations free tier. Fast enough to complete before Render's 30s window.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Image dimensions — 512x912 keeps generation under 25s on free Pollinations
IMG_W = 512
IMG_H = 912

# Comic book style DNA — appended to every scene prompt
# Exactly matches the reference images: teal shadows, orange accent, ink outlines
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


def _verify_image(path: str, min_size: int = 8_000) -> bool:
    p = Path(path)
    return p.exists() and p.stat().st_size > min_size


# ── POLLINATIONS — aiohttp streaming (bypasses Render 30s idle kill) ──────────
async def _pollinations_stream_async(url: str, output_path: str) -> bool:
    """
    Key technique: aiohttp streaming with chunk-by-chunk download.
    - read_bufsize=65536 — reads 64KB chunks as they arrive
    - total timeout 90s but READ timeout only 20s per chunk
    - Render only kills connections with no data moving — streaming is safe
    - tcp_connector with keepalive=True prevents connection resets
    """
    import aiohttp
    timeout = aiohttp.ClientTimeout(
        total=90,        # total max seconds for entire download
        connect=15,      # connection establishment
        sock_read=20,    # max seconds between chunks — keeps connection alive
    )
    headers = {
        "User-Agent":      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0",
        "Accept":          "image/webp,image/apng,image/*,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer":         "https://pollinations.ai/",
        "Origin":          "https://pollinations.ai",
        "Connection":      "keep-alive",
    }
    connector = aiohttp.TCPConnector(
        keepalive_timeout=60,
        enable_cleanup_closed=True,
    )
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=timeout,
        ) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    print(f"    Pollinations HTTP {resp.status}")
                    return False
                chunks = []
                total  = 0
                # Stream chunk by chunk — connection stays alive during generation
                async for chunk in resp.content.iter_chunked(65536):
                    chunks.append(chunk)
                    total += len(chunk)
                if total < 8_000:
                    print(f"    Pollinations too small: {total} bytes")
                    return False
                Path(output_path).write_bytes(b"".join(chunks))
                return True
    except aiohttp.ClientResponseError as e:
        print(f"    Pollinations response error: {e.status}")
    except asyncio.TimeoutError:
        print("    Pollinations timeout — image took too long")
    except Exception as e:
        print(f"    Pollinations stream error: {e}")
    return False


def generate_image_pollinations(scene: str, content_type: str,
                                output_path: str) -> bool:
    """
    Uses async streaming via aiohttp to keep connection alive during
    Pollinations image generation. Tries 3 model variants with short
    prompts. Smaller 512x912 size = faster generation = fits in 30s window.
    """
    prompt, _ = _build_image_prompt(scene, content_type)
    # Trim prompt to 300 chars — shorter prompts generate faster
    short = prompt[:300]
    enc   = requests.utils.quote(short)
    seed  = random.randint(100, 99999)

    # turbo is the fastest Pollinations model (~15-20s at 512x912)
    # flux is higher quality but ~25-35s — risky on Render
    # Try turbo first, then flux as backup
    urls = [
        f"https://image.pollinations.ai/prompt/{enc}"
        f"?width={IMG_W}&height={IMG_H}&model=turbo&seed={seed}&nologo=true&nofeed=true",
        f"https://image.pollinations.ai/prompt/{enc}"
        f"?width={IMG_W}&height={IMG_H}&model=flux&seed={seed+1}&nologo=true&nofeed=true",
        f"https://image.pollinations.ai/prompt/{enc}"
        f"?width=512&height=768&model=turbo&seed={seed+2}&nologo=true&nofeed=true",
    ]

    for i, url in enumerate(urls):
        model_name = "turbo" if "turbo" in url else "flux"
        print(f"    Pollinations [{model_name}] attempt {i+1}/3 (streaming)...")
        try:
            # Run async streaming in the sync context
            ok = asyncio.run(_pollinations_stream_async(url, output_path))
            if ok and _verify_image(output_path):
                size_kb = Path(output_path).stat().st_size // 1024
                print(f"    ✅ Pollinations {model_name} ({size_kb}KB)")
                return True
        except Exception as e:
            print(f"    Pollinations attempt {i+1} exception: {e}")
        # Small gap between attempts — don't hammer the API
        if i < 2:
            time.sleep(2)

    return False


# ── CINEMATIC FALLBACK — FFmpeg gradient art (always works, <1s) ──────────────
def generate_cinematic_fallback(scene: str, content_type: str,
                                output_path: str) -> bool:
    """Last resort. Generates atmospheric dark gradient matching comic palette."""
    if content_type == "history":
        # Warm amber tones
        colors = [("0x1A0C06","0x3D1A08"), ("0x14080A","0x3D1020"), ("0x0A0E10","0x1A2832")]
    else:
        # Cool noir blue-teal
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


# ── MAIN DISPATCHER ───────────────────────────────────────────────────────────
def generate_image(scene: str, content_type: str, output_path: str,
                   scene_idx: int = 0) -> str:
    """
    v5.3: Pollinations only (free, no key) using aiohttp streaming.
    Streaming keeps connection alive past Render's 30s idle timeout.
    Falls back to cinematic gradient if all Pollinations attempts fail.
    """
    if scene_idx > 0:
        time.sleep(2)   # brief gap between scenes

    # Primary: Pollinations with aiohttp streaming
    if generate_image_pollinations(scene, content_type, output_path):
        pipeline_status["image_source"] = "Pollinations"
        return "pollinations"
    print(f"    ⚡ Pollinations failed scene {scene_idx+1} — using gradient fallback")

    # Fallback: always works
    if generate_cinematic_fallback(scene, content_type, output_path):
        pipeline_status["image_source"] = "Fallback"
        print(f"    ⚠️  Scene {scene_idx+1}: gradient fallback (Pollinations unavailable)")
        return "fallback"

    return None

# STEP 3B — KEN BURNS ENGINE (updated for 1080×1920)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ken_burns_filter(duration: float, style: int) -> str:
    d = int(duration * CLIP_FPS)
    out_w, out_h = VID_W, VID_H  # 1080 × 1920

    # Pre-scale to 3× for smoother zoompan
    scale_w = out_w * 3  # 3240
    scale_h = out_h * 3  # 5760

    styles = {
        # 1. Slow zoom in — builds intimacy and dread
        0: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0006,1.2)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 2. Slow zoom out — reveals scale and horror
        1: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='if(eq(on,1),1.2,max(zoom-0.0006,1.0))'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 3. Pan left to right — scanning a crime scene
        2: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw*0.08*(on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 4. Pan right to left
        3: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw*0.08*(1-on/{d})':y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 5. Slow downward pan — like something descending
        4: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.08'"
            f":x='iw/2-(iw/zoom/2)':y='ih*0.06*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 6. Zoom in + drift right (cinematic)
        5: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0005,1.15)'"
            f":x='iw*0.04*(on/{d})+(iw/2-(iw/zoom/2))'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 7. Zoom into bottom (ominous looking-down effect)
        6: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='min(zoom+0.0007,1.25)'"
            f":x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
        # 8. Diagonal drift — unsettling, non-static energy
        7: (
            f"scale={scale_w}:{scale_h},"
            f"zoompan=z='1.12'"
            f":x='iw*0.04*(on/{d})':y='ih*0.04*(on/{d})'"
            f":d={d}:s={out_w}x{out_h}:fps={CLIP_FPS}"
        ),
    }
    return styles[style % 8]


def build_scene_clip(scene: str, content_type: str, duration: float,
                     output_path: str, ken_burns_style: int,
                     scene_idx: int = 0) -> bool:
    img_path = output_path.replace(".mp4", ".jpg")
    source   = generate_image(scene, content_type, img_path, scene_idx)
    if not source:
        return False

    # Verify image is actually usable
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
        "-crf",     "23",           # v5: better quality (was 26)
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
        # Fallback: static clip
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
# STEP 5 — VIDEO ASSEMBLY (SUBTITLE ENGINE COMPLETELY REWRITTEN IN v5.0)
#
# ROOT CAUSE of v4 subtitle bug:
#   — fontsize=64 with x=0 meant text started at the left edge and
#     extended beyond the right edge of the 576px frame
#   — No x-margin guard: long words were clipped at both sides
#
# v5.0 FIXES:
#   1. Font size: 46px (was 64/60) — fits comfortably in 1080px width
#   2. x: (w-text_w)/2 — centers text with auto-margin (unchanged but now works
#      because font size is correct)
#   3. Hard word-wrap at 22 chars — prevents any single line from overflowing
#   4. y: h*0.85 — 15% from bottom, well inside safe area
#   5. Box background (box=1) — dark semi-transparent behind text
#      improves readability over dark AND light images
#   6. All special chars properly escaped for FFmpeg drawtext
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _t2s(t: str) -> float:
    """Convert SRT timestamp to seconds."""
    h, m, rest = t.split(":")
    s, ms = rest.split(".")
    return int(h)*3600 + int(m)*60 + int(s) + int(ms)/1000


def _escape_drawtext(text: str) -> str:
    """
    Properly escape all special characters for FFmpeg drawtext filter.
    Order matters: backslash must be first.
    """
    text = text.replace("\\", "\\\\")   # backslash first
    text = text.replace("'", "\u2019")  # smart apostrophe (no escaping needed)
    text = text.replace(":", "\\:")     # colon
    text = text.replace("[", "\\[")     # bracket
    text = text.replace("]", "\\]")     # bracket
    text = text.replace("%", "\\%")     # percent
    text = text.replace(",", "\\,")     # comma
    text = text.replace(";", "\\;")     # semicolon
    text = text.replace("=", "\\=")     # equals
    text = text.replace("\n", " ")      # newlines to space
    return text


def _wrap_subtitle_text(text: str, max_chars: int = 22) -> list:
    """
    Wrap subtitle text into lines of max_chars.
    Returns list of line strings.
    """
    words = text.split()
    lines = []
    current = []
    current_len = 0
    for word in words:
        if current_len + len(word) + (1 if current else 0) > max_chars:
            if current:
                lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            if current:
                current_len += 1  # space
            current.append(word)
            current_len += len(word)
    if current:
        lines.append(" ".join(current))
    return lines[:2]  # max 2 lines per subtitle card


def srt_to_drawtext(srt_path: str, content_type: str) -> Optional[str]:
    """
    v5.0 completely rewritten subtitle renderer.

    Key improvements:
    - Smaller font (46px) that fits within 1080px width
    - Semi-transparent dark box behind text for contrast on any background
    - Hard word-wrap at 22 chars per line
    - y positioned at 85% down (well inside frame safe area)
    - All special characters escaped correctly
    - Two-line support for natural sentence breaks
    """
    try:
        content = Path(srt_path).read_text(encoding="utf-8")
    except Exception:
        return None

    # Font size tuned for 1080×1920:
    # 46px = readable but never overflows 1080px width
    # Box gives contrast on any image background
    if content_type == "history":
        fontsize  = 52   # slightly larger for shorter history phrases
        fontcolor = "white"
    else:
        fontsize  = 48   # slightly smaller for longer crime phrases
        fontcolor = "white"

    filters = []
    for block in re.split(r"\n\n+", content.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        try:
            times = lines[1].replace(",", ".").split(" --> ")
            start = _t2s(times[0].strip())
            end   = _t2s(times[1].strip())
            raw_text = " ".join(lines[2:]).strip()

            # Wrap into max 2 short lines
            wrapped = _wrap_subtitle_text(raw_text, max_chars=22)

            for line_idx, line_text in enumerate(wrapped):
                escaped = _escape_drawtext(line_text)
                if not escaped.strip():
                    continue

                # Stack lines: first line higher, second line lower
                # y = 85% down screen, then +lineheight per additional line
                # This keeps ALL subtitles well inside the 1920px frame
                y_base  = f"h*0.85"
                y_extra = line_idx * (fontsize + 8)
                y_pos   = f"{y_base}+{y_extra}" if y_extra > 0 else y_base

                filters.append(
                    f"drawtext="
                    f"text='{escaped}'"
                    f":fontsize={fontsize}"
                    f":fontcolor={fontcolor}"
                    f":borderw=4"          # thick black outline
                    f":bordercolor=black"
                    f":shadowx=2:shadowy=2"  # drop shadow
                    f":shadowcolor=black@0.8"
                    f":x=(w-text_w)/2"     # horizontally centered
                    f":y={y_pos}"          # vertically in safe zone
                    f":enable='between(t,{start:.3f},{end:.3f})'"
                )
        except Exception as sub_e:
            print(f"    Subtitle block error: {sub_e}")
            continue

    return ",".join(filters) if filters else None


def assemble_video(clips: list, voice_p: str, music_p: Optional[str],
                   srt_p: str, output_p: str, content_type: str):
    """
    v5.0 assembly:
    - Voice volume: 2.0 (was 1.6)
    - Music volume: 0.10 (was 0.15) — voice is king
    - Audio loudnorm on voice before mixing for consistent levels
    - CRF 23 for better output quality (was 27)
    - Subtitle engine fully replaced (see srt_to_drawtext above)
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
    vf         = sub_filter if sub_filter else "null"
    use_music  = music_p and Path(music_p).exists()

    if use_music:
        # v5.0: loudnorm on voice, music much quieter (0.10 vs 0.15)
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
            "-c:a", "aac", "-b:a", "192k",   # v5: 192k (was 128k)
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
          f"subs={'yes' if sub_filter else 'no'}, "
          f"music={'yes' if use_music else 'no'}")
    r = subprocess.run(cmd, capture_output=True, timeout=600)

    if r.returncode != 0:
        err = r.stderr[-600:].decode(errors="ignore")
        print(f"  ⚠️  FFmpeg error: {err[-300:]}")
        # Retry without subtitles if drawtext caused the error
        if sub_filter and ("drawtext" in err or "fontsize" in err or "text" in err):
            print("  ⚠️  Subtitle filter failed — retrying without subs...")
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
        voice_p     = str(session / "voice.mp3")
        srt_p       = str(session / "subs.srt")
        voice_style = data.get("voice_style", "authoritative")
        generate_voice(data["content"], voice_style, voice_p, srt_p)
        audio_dur   = get_duration(voice_p)
        print(f"  📊 Audio duration: {audio_dur:.1f}s")

        # ── 3. Calculate scene count & generate images ────────────────────────
        # 3s per image for optimal retention, min 5, max 8 scenes
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
                # Pass scene_idx so generate_image knows to add delay for i>0
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
        assemble_video(clips, voice_p, music_p, srt_p, final_p,
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
            "scenes_count": len(clips),
            "audio_dur_s":  round(audio_dur, 1),
            "url":          url,
            "version":      "5.3",
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
        "status":    "ok",
        "service":   "DarkHistory.ai v5.3",
        "niches":    ["Bizarre History", "True Crime"],
        "formula":   "Hook + Tension + Reveal + CTA | 3s/image | Ken Burns | Edge TTS",
        "cpm_range": "$8–$18",
        "fixes":     [
            "v5: Images generated for ALL scenes (not just scene 1)",
            "v5: Subtitles centered with safe margins (no more overflow)",
            "v5: Audio louder + normalized (2.0x voice, loudnorm filter)",
            "v5: Resolution upgraded to 1080x1920 (YouTube spec)",
            "v5: Image quality improved (flux-pro, 8K prompts, retry logic)",
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
        "gemini":     bool(GEMINI_API_KEY),
        "groq":       bool(GROQ_API_KEY),
        "openrouter": bool(OPENROUTER_API_KEY),
        "modelslab":  bool(MODELSLAB_API_KEY),
        "youtube":    bool(YOUTUBE_REFRESH_TOKEN),
    }
    return {
        "status":    "healthy",
        "keys":      keys,
        "version":   "5.3",
        "timestamp": datetime.now().isoformat(),
    }# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
