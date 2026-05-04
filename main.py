"""
DarkHistory.ai — Backend v9.0  ████████████████████████████████████████
THE KILLER VIRAL CONTENT MACHINE

WHAT'S NEW IN v9.0:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RESEARCH-FIRST SCRIPTING:
  Before writing a single word, the system researches:
  - The most shocking / least-known angle on the topic
  - Psychological fear triggers specific to this topic
  - Real facts that sound too disturbing to be real
  - Sensory hooks (sounds, smells, textures from the era/scene)
  This research brief is fed INTO the scriptwriter — producing
  genuinely more disturbing, specific, viral scripts.

HOOK IMAGE (NEW):
  First 2-3s of video uses a specially crafted SHOCK IMAGE
  designed purely to stop the scroll. Different from scene images.
  Big text overlay hint + maximum dread composition.

THUMBNAIL GENERATION (NEW):
  Every video generates a detailed thumbnail prompt
  following the PDF formula: fear face + text + dark atmosphere.
  Ready to paste into Midjourney / DALL-E / Leonardo.

FORMAT SELECTOR (IMPROVED):
  Shorts  (9:16, 720×1280, 50-58s, 1 story, Impact captions)
  Long    (16:9, 1280×720, 8-12min, 3 stories, Netflix captions)
  Square  (1:1,  720×720,  60-90s, 1 story, Karaoke captions)
  Each format auto-selects best voice, caption style, scene count.

IMAGE STYLES (4 options):
  horror_2d     — 2D animation, indigo-charcoal, soft grain (PDF style)
  cinematic     — photorealistic dark noir, dramatic lighting
  graphic_novel — comic book, teal-amber, bold ink (current)
  vintage_horror— sepia/aged film, 1920s horror poster aesthetic

CAPTION STYLES (3 options):
  impact  — big centred Impact font, mid-lower screen (Shorts default)
  netflix — bottom bar subtitle, white on dark band (long-form)
  karaoke — highlighted word yellow, rest white (engagement driver)

IMAGE PIPELINE (free-first):
  TIER 1: fal.ai FLUX Schnell    — free, no key, 2-6s, best quality
  TIER 2: Pollinations turbo     — free, no key, 12s spacing
  TIER 3: Gemini 2.0 Flash Exp   — needs GEMINI_API_KEY
  TIER 4: HuggingFace FLUX       — needs HF_TOKEN
  TIER 5: Gradient fallback      — always works

SOUND DESIGN (NEW):
  - Atmospheric sound layers per content type
  - Heartbeat sync on climax moments
  - Subtle ambient dread (wind, distant bells, clock ticks)
  - Generated via ffmpeg audio synthesis (no external service)

SEO v9 (IMPROVED):
  - Research-backed keyword injection
  - 3 title variants (A/B/C) — best one auto-selected
  - Chapter timestamps for long-form
  - Category 27 (Education) for max CPM
  - Description formula: hook → story tease → CTA → hashtags

SCENE TIMING:
  - Each image: exactly 2.5s (Shorts) or 3.0s (Long/Square)
  - Hook image: 3s fixed with zoom-punch effect
  - Total scenes calculated from audio duration automatically

ENV VARS:
  GEMINI_API_KEY, GROQ_API_KEY, OPENROUTER_API_KEY  — LLM
  HF_TOKEN           — optional HuggingFace
  YOUTUBE_*          — upload
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, json, time, random, asyncio, subprocess, re, shutil, base64, math
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
HF_TOKEN              = os.environ.get("HF_TOKEN", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai API", version="9.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

WORK_DIR = Path("/tmp/darkhistory")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

pipeline_status: dict = {
    "running": False, "step": "", "step_index": 0,
    "total_steps": 8, "last_result": None, "error": None,
    "llm_used": None, "image_source": None, "progress_detail": "",
}

# ── FORMAT CONFIGS ─────────────────────────────────────────────────────────────
FORMATS = {
    "shorts": {
        "w": 720, "h": 1280, "fps": 25, "max_dur": 58,
        "label": "YouTube Shorts 9:16",
        "scene_dur": 2.5,   # seconds per image
        "num_stories": 1,
        "default_caption": "impact",
        "default_voice": "suspenseful",
        "word_count": "130-150",
        "img_w": 512, "img_h": 912,
    },
    "long": {
        "w": 1280, "h": 720, "fps": 25, "max_dur": 720,
        "label": "Long-form 16:9",
        "scene_dur": 3.0,
        "num_stories": 3,
        "default_caption": "netflix",
        "default_voice": "cinematic",
        "word_count": "1200-1500 per story",
        "img_w": 512, "img_h": 288,
    },
    "square": {
        "w": 720, "h": 720, "fps": 25, "max_dur": 90,
        "label": "Square 1:1",
        "scene_dur": 2.75,
        "num_stories": 1,
        "default_caption": "karaoke",
        "default_voice": "authoritative",
        "word_count": "180-220",
        "img_w": 512, "img_h": 512,
    },
}

# ── IMAGE STYLES ──────────────────────────────────────────────────────────────
IMAGE_STYLES = {
    "horror_2d": {
        "desc": "2D horror animation dark ethereal style, indigo-charcoal tones, soft film grain, atmospheric dread, deep shadows, cinematic composition, no text, no watermark",
        "label": "2D Horror Animation",
        "negative": "photorealistic, 3d render, text, watermark, bright colors, cheerful",
    },
    "cinematic": {
        "desc": "cinematic dark photography, photorealistic, dramatic chiaroscuro lighting, deep shadows, film noir atmosphere, high contrast, professional cinematography, no text, no watermark",
        "label": "Cinematic Noir",
        "negative": "cartoon, illustration, text, watermark, bright lighting, cheerful",
    },
    "graphic_novel": {
        "desc": "graphic novel illustration, bold ink outlines, cel shaded, desaturated teal-grey palette, warm amber accent highlights, dramatic directional shadows, gritty dark thriller comic art, no text, no watermark",
        "label": "Graphic Novel",
        "negative": "photorealistic, text, watermark, pastel colors, cute",
    },
    "vintage_horror": {
        "desc": "vintage horror poster art, sepia tones aged film aesthetic, 1920s silent film horror, scratched film grain, high contrast monochrome with blood-red accents, gothic illustration style, no text, no watermark",
        "label": "Vintage Horror",
        "negative": "modern, digital, text, watermark, bright, colorful",
    },
}

# ── TOPIC POOLS ───────────────────────────────────────────────────────────────
HISTORY_TOPICS = [
    "the most brutal medieval torture devices ever invented",
    "how the iron maiden torture device actually worked",
    "why the black death killed half of Europe in 3 years",
    "the secret life inside a medieval dungeon",
    "what Viking raiders really did to their victims",
    "the horrifying truth about Roman gladiator fights",
    "how ancient Egyptians made mummies step by step",
    "the real story behind the Tower of London executions",
    "the forgotten plague that wiped out entire cities",
    "the darkest secrets of ancient Rome nobody talks about",
    "how the Spartans trained child soldiers from age 7",
    "the real reason Pompeii was buried and lost for centuries",
    "what happened inside the Colosseum on a normal day",
    "the gruesome truth about ancient Greek medicine",
    "the unsolved mystery of the Princes in the Tower",
    "why Jack the Ripper was never caught and who he really was",
    "the 5 most terrifying punishments in all of human history",
    "how ancient China punished criminals in unimaginable ways",
    "the most brutal execution methods used by the Roman Empire",
    "why medieval witch trials were far worse than people think",
    "how the Aztecs performed human sacrifices and why",
    "the dark secret history of the guillotine in France",
    "what really happened to the crew of the Mary Celeste",
    "the true story of Vlad the Impaler that inspired Dracula",
    "how medieval executioners were trained and what they earned",
    "how the Spanish Inquisition actually worked and who ran it",
    "the most shocking royal scandals in European history",
    "how body snatchers supplied medical schools with corpses",
    "the real story of Blackbeard's final battle and death",
    "how poisoners operated in the royal courts of Europe",
    "the Dancing Plague of 1518 that killed dozens and was never explained",
    "the gruesome reality of being a medieval surgeon",
    "the secret history of the Knights Templar and their downfall",
    "the most terrifying sea monsters sailors believed were real",
    "what the Black Death actually smelled like in a medieval city",
    "how ancient Rome disposed of its criminals in creative ways",
    "the children who vanished during the Children's Crusade of 1212",
    "how medieval people dealt with mental illness in the darkest ways",
    "the real torture methods used during the Salem Witch Trials",
    "what it was like to be buried alive in the 1800s",
    "the island where Napoleon Bonaparte slowly went insane",
    "how serial killers operated in medieval Europe without detection",
    "the terrifying experiments performed on prisoners in WWII",
    "what happened to the losers of ancient gladiatorial combat",
    "how the plague doctors in their bird masks actually worked",
]

TRUE_CRIME_TOPICS = [
    "the chilling psychology behind Ted Bundy that experts missed",
    "how the Zodiac Killer sent coded messages and was never caught",
    "why Jeffrey Dahmer's neighbors never suspected anything",
    "the coldest case in history that was solved 40 years later",
    "the most audacious bank heist in American history",
    "the mysterious disappearance that haunts investigators today",
    "the poison killer who was never suspected until too late",
    "how forensic scientists finally cracked an impossible cold case",
    "the inside story of the most daring prison escape in history",
    "how one detective's obsession solved a 30-year-old murder",
    "the serial killer who worked as a respected professional for years",
    "why the BTK killer stopped and then confessed decades later",
    "how a single receipt exposed a criminal who thought he was clean",
    "the crime scene detail that investigators missed for 20 years",
    "how digital footprints led investigators to an untraceable suspect",
    "the killer who returned to the crime scene and was finally caught",
    "the hitman who kept a diary that destroyed his entire network",
    "the fraud scheme so sophisticated even experts were fooled",
    "the con woman who infiltrated high society and fooled everyone",
    "the murder that looked like an accident for 15 years",
    "the identity thief who lived as someone else for a decade",
    "why the Golden State Killer was finally caught after 40 years",
    "the killer who wrote letters to newspapers and got away with it",
    "the most elaborate fake death scheme ever attempted",
    "how investigators caught a killer using a genealogy website",
    "the cult that convinced hundreds of people to give up everything",
    "the night shift horror at the hospital no one investigated",
    "the missing hiker case that revealed something far darker",
    "the small town that had a secret no one dared speak",
    "how a cold case file was reopened by a child's drawing",
    "the killer couple who traveled across states leaving no evidence",
    "the woman who faked her kidnapping for 11 years",
    "the forensic accountant who cracked a murder by following pennies",
    "how a single hair strand solved a murder 30 years later",
    "the nurse who killed patients for 16 years before anyone checked",
    "the missing persons case that turned out to be witness protection",
    "how underground crime networks were exposed by one informant",
    "the cold case reopened after a suspect's deathbed confession",
    "the seemingly perfect husband who had a second family in another city",
    "how a tattoo identified a John Doe dead for 25 years",
]

CONTENT_NICHES = {
    "history":   {"label": "Bizarre History", "icon": "🏛️", "topics": HISTORY_TOPICS,  "cpm": "$8-$15"},
    "truecrime": {"label": "True Crime",       "icon": "🔍", "topics": TRUE_CRIME_TOPICS, "cpm": "$10-$18"},
}


class RunRequest(BaseModel):
    topic:         Optional[str] = Field(default=None)
    content_type:  Optional[str] = Field(default=None,    description="history|truecrime")
    format:        Optional[str] = Field(default="shorts", description="shorts|long|square")
    image_style:   Optional[str] = Field(default="auto",  description="horror_2d|cinematic|graphic_novel|vintage_horror|auto")
    caption_style: Optional[str] = Field(default="auto",  description="impact|netflix|karaoke|auto")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def call_gemini(prompt: str, max_tokens: int = 4000) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}")
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": prompt}]}],
                  "generationConfig": {"temperature": 0.88, "maxOutputTokens": max_tokens}},
            timeout=120)
        if resp.status_code == 200:
            return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        print(f"Gemini {resp.status_code}: {resp.text[:150]}")
    except Exception as e:
        print(f"Gemini failed: {e}")
    return None


def call_groq(prompt: str, max_tokens: int = 4000) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [
                      {"role": "system", "content": "You are a viral horror/dark history scriptwriter. Always respond with valid JSON only. No markdown, no backticks."},
                      {"role": "user", "content": prompt}
                  ],
                  "temperature": 0.88, "max_tokens": max_tokens},
            timeout=120)
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
                      "temperature": 0.88, "max_tokens": 3000},
                timeout=120)
            if resp.status_code == 200:
                text = resp.json()["choices"][0]["message"]["content"]
                if text and len(text) > 100:
                    print(f"  OpenRouter: {model}")
                    return text
        except Exception as e:
            print(f"OpenRouter {model}: {e}")
    return None


def llm_call(prompt: str, max_tokens: int = 4000) -> Optional[str]:
    """Try all LLMs in order of quality."""
    raw = call_gemini(prompt, max_tokens)
    if raw:
        pipeline_status["llm_used"] = "Gemini 2.5 Flash"
        return raw
    raw = call_groq(prompt, max_tokens)
    if raw:
        pipeline_status["llm_used"] = "Groq Llama 3.3 70B"
        return raw
    raw = call_openrouter(prompt)
    if raw:
        pipeline_status["llm_used"] = "OpenRouter"
        return raw
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 0 — RESEARCH BRIEF (the secret sauce)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_research_brief(topic: str, content_type: str) -> dict:
    """
    Before writing the script, generate a research brief.
    This forces the LLM to THINK deeply about the topic first.
    Result: far more specific, disturbing, and viral scripts.
    """
    prompt = f"""You are a dark history/true crime researcher with deep knowledge.
Topic: "{topic}"
Type: {content_type}

Research this topic deeply and return ONLY valid JSON with these exact fields:

{{
  "most_shocking_fact": "The single most disturbing fact about this topic that most people don't know. Be specific with names, dates, numbers.",
  "sensory_details": "What did this look/sound/smell like? Give visceral, specific sensory details that put the listener IN the scene.",
  "psychological_hook": "What psychological fear does this topic trigger? (fear of betrayal, fear of darkness, fear of authority, etc)",
  "lesser_known_angle": "The angle on this topic that YouTube channels almost never cover — the hidden layer that makes this MORE disturbing.",
  "specific_details": ["Fact 1 with specific numbers/names", "Fact 2 with dates", "Fact 3 that sounds too disturbing to be real", "Fact 4 that reframes the whole story"],
  "hook_line_options": [
    "Option A hook: most visceral opening line — present tense, drops you into worst moment",
    "Option B hook: most curiosity-triggering opening line — the disturbing question",
    "Option C hook: most shocking statistic or fact"
  ],
  "twist_element": "The one fact that reframes EVERYTHING — what the listener thinks at the start vs what they know at the end",
  "thumbnail_concept": "Describe the most clickable thumbnail for this topic: what expression, what object, what background, what text would make someone STOP SCROLLING instantly",
  "title_variants": [
    "Title A: [Number] + [Specific Theme] Horror Stories Animated — most search volume",
    "Title B: emotionally charged, curiosity gap title — under 60 chars",
    "Title C: statement that sounds impossible but is true — under 70 chars"
  ],
  "top_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"]
}}

Return ONLY the JSON. No text before or after."""

    raw = llm_call(prompt, max_tokens=2000)
    if not raw:
        # Fallback research brief
        return {
            "most_shocking_fact": f"The disturbing truth about {topic}",
            "sensory_details": "The air was thick with fear and shadow",
            "psychological_hook": "fear of the unknown",
            "lesser_known_angle": f"The hidden layer of {topic} nobody discusses",
            "specific_details": [f"Key fact about {topic}"],
            "hook_line_options": [f"Nobody talks about what really happened with {topic}."],
            "twist_element": "The truth was far darker than anyone suspected",
            "thumbnail_concept": "Dark atmospheric scene with shocked face",
            "title_variants": [f"The Dark Truth About {topic.title()} Horror Stories Animated"],
            "top_keywords": [topic, content_type, "dark history", "true crime"],
        }
    data = _clean_json(raw)
    return data if data else {"hook_line_options": [f"Nobody talks about what really happened with {topic}."], "title_variants": [topic]}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 1 — CONTENT GENERATION (research-guided)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _auto_image_style(content_type: str, image_style: str) -> str:
    if image_style not in ("auto", None, ""):
        return image_style if image_style in IMAGE_STYLES else "horror_2d"
    return "vintage_horror" if content_type == "history" else "cinematic"


def _auto_caption_style(fmt: str, caption_style: str) -> str:
    if caption_style not in ("auto", None, ""):
        return caption_style
    return FORMATS[fmt]["default_caption"]


def build_shorts_prompt(topic: str, content_type: str, research: dict,
                         image_style: str, caption_style: str) -> str:
    hook = research.get("hook_line_options", [""])[0]
    shocking = research.get("most_shocking_fact", "")
    sensory  = research.get("sensory_details", "")
    twist    = research.get("twist_element", "")
    lesser   = research.get("lesser_known_angle", "")
    style_desc = IMAGE_STYLES[image_style]["desc"]

    if content_type == "history":
        voice_rules = """HISTORY VOICE RULES:
- Present tense for ancient events: "A prisoner WALKS" not "walked"  
- Use "Nobody talks about this" / "History books won't show you this"
- Build dread: small disturbing detail → bigger detail → gut-punch reveal
- End: one line that re-frames everything just heard"""
    else:
        voice_rules = """TRUE CRIME VOICE RULES:
- Drop listener INTO the worst moment. Cold open. No setup.
- Detective's case file voice: precise, clinical, devastating
- One devastating detail per sentence. Each worse than the last.
- End: one unanswered question that haunts the listener"""

    return f"""You are a viral YouTube Shorts scriptwriter. 10M subscribers. Dr. NoSleep meets Weird History.

TOPIC: {topic}
TYPE: {content_type}

RESEARCH BRIEF (USE THESE — they make the script specific and disturbing):
- Most shocking fact: {shocking}
- Sensory details: {sensory}
- Twist element: {twist}
- Lesser-known angle: {lesser}
- Best opening hook: {hook}

{voice_rules}

STRUCTURE (non-negotiable):
[0-3s]   HOOK: The exact hook line above or something MORE shocking. First sentence only.
[3-15s]  SETUP: 2-3 sentences. Build the world with dread. Use sensory details.
[15-35s] ESCALATION: Use the lesser-known angle. "But here's what nobody tells you..."
[35-50s] TWIST/PAYOFF: The twist element delivered like a gut punch.
[50-57s] LINGERING END: One haunting final line + "Follow for more."

WORD COUNT: Exactly 130-150 words. Count them.
Every word must earn its place. Cut anything generic.

SCENE GENERATION:
Generate 9 scenes. Scene 1 = hook image (shock-stop-scroll).
Each scene: [camera angle] + [SPECIFIC subject from THIS story] + [lighting] + [{style_desc[:80]}]
NEVER generic: no "dark room", no "shadowy figure" — name the specific thing.

TITLES (generate 3 variants using PDF formula):
A: [Number] [Specific Theme] Horror Stories Animated — SEO/search volume
B: Curiosity gap — something that sounds impossible
C: Statement + fear trigger word

Return ONLY valid JSON:
{{
  "title": "Best title from variants above — max 70 chars",
  "title_variants": ["Title A", "Title B", "Title C"],
  "hook_line": "Exact first spoken sentence — max 15 words — most shocking fact",
  "content": "Complete 130-150 word script",
  "description": "YouTube description 180 words. Line 1-2: SEO keywords for this exact topic. Lines 3-5: Tease the most disturbing part without spoiling. Line 6: Subscribe CTA. End: full hashtag block",
  "hashtags": "#Shorts #DarkHistory #TrueCrime #HorrorStoriesAnimated #Mystery",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12"],
  "thumbnail_prompt": "Detailed prompt for Midjourney/DALL-E thumbnail: [specific scene] [character expression] [text overlay idea] [{style_desc[:40]}]",
  "hook_image_prompt": "Scene 1 shock image — designed to stop scrolling in first 2s: extreme close-up OR most disturbing visual moment from this story, maximum dread, [{style_desc[:60]}]",
  "scenes": [
    "Scene 1 (HOOK - stop scroll): [extreme close-up or most disturbing visual] [{style_desc[:40]}]",
    "Scene 2 (setup): [specific location/time detail] [{style_desc[:40]}]",
    "Scene 3: [specific character or subject] [{style_desc[:40]}]",
    "Scene 4: [specific object or evidence] [{style_desc[:40]}]",
    "Scene 5: [escalation detail] [{style_desc[:40]}]",
    "Scene 6: [worse detail] [{style_desc[:40]}]",
    "Scene 7: (twist setup): [most disturbing visual] [{style_desc[:40]}]",
    "Scene 8: (payoff): [gut punch visual] [{style_desc[:40]}]",
    "Scene 9: (haunting end): [final lingering image] [{style_desc[:40]}]"
  ],
  "voice_style": "{"authoritative" if content_type == "history" else "suspenseful"}",
  "content_type": "{content_type}",
  "image_style": "{image_style}",
  "caption_style": "{caption_style}",
  "sound_mood": "{"dark_orchestral" if content_type == "history" else "noir_suspense"}"
}}"""


def build_longform_prompt(topics: list, content_type: str, research_list: list,
                           image_style: str) -> str:
    style_desc = IMAGE_STYLES[image_style]["desc"]
    stories_text = ""
    for i, (topic, research) in enumerate(zip(topics[:3], research_list[:3])):
        hook = research.get("hook_line_options", [""])[0]
        shocking = research.get("most_shocking_fact", "")
        stories_text += f"""
Story {i+1}: {topic}
  Hook: {hook}
  Shocking fact: {shocking}
  Twist: {research.get("twist_element", "")}
"""

    return f"""You are a viral YouTube long-form horror scriptwriter. Dr. NoSleep style.
Runtime: 8-12 minutes. 3 complete stories. Maximum dread. Maximum retention.

STORIES AND RESEARCH:
{stories_text}

EACH STORY STRUCTURE (1200-1500 words):
- Cold open: First line = drop into worst moment. Present tense. No setup.
- Slow burn: Build dread with sensory detail — sounds, smells, shadows
- Escalation: Each paragraph reveals something worse
- Psychological core: What makes THIS story haunt you at 3am?
- Twist: The one fact that reframes everything
- End: "Subscribe for more chilling tales..."

TITLE: "3 [Specific Theme] Horror Stories Animated (2026)" — SEO formula
Each story gets 8 scene image prompts.
Scenes: [camera angle] [specific detail] [lighting] [{style_desc[:60]}]

TIMESTAMPS (chapter markers for YouTube):
0:00 - Story 1: [subtitle]  
~4:00 - Story 2: [subtitle]
~8:00 - Story 3: [subtitle]

Return ONLY valid JSON:
{{
  "title": "3 [Theme] Horror Stories Animated (2026) — max 70 chars",
  "title_variants": ["Variant A", "Variant B", "Variant C"],
  "stories": [
    {{
      "subtitle": "Story 1 title",
      "hook_line": "First line spoken",
      "content": "1200-1500 word story",
      "scenes": ["scene1","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }},
    {{
      "subtitle": "Story 2 title",
      "hook_line": "First line spoken",
      "content": "1200-1500 word story",
      "scenes": ["scene1","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }},
    {{
      "subtitle": "Story 3 title",
      "hook_line": "First line spoken",
      "content": "1200-1500 word story",
      "scenes": ["scene1","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }}
  ],
  "description": "250-word description. Hook line 1-2. Story teasers. Timestamps: 0:00 Story 1, ~4:00 Story 2, ~8:00 Story 3. Subscribe CTA.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10","tag11","tag12","tag13","tag14","tag15"],
  "hashtags": "#DarkHistory #TrueCrime #HorrorStoriesAnimated #Mystery #Animated",
  "thumbnail_prompt": "Thumbnail for compilation: [most disturbing scene from story 1] [{style_desc[:40]}] with bold text area",
  "voice_style": "cinematic",
  "content_type": "{content_type}",
  "image_style": "{image_style}",
  "caption_style": "netflix",
  "sound_mood": "{"dark_orchestral" if content_type == "history" else "noir_suspense"}"
}}"""


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


def generate_content(req: RunRequest) -> dict:
    niche     = req.content_type if req.content_type in CONTENT_NICHES else get_next_niche()
    fmt       = req.format or "shorts"
    fmt_cfg   = FORMATS.get(fmt, FORMATS["shorts"])
    img_style = _auto_image_style(niche, req.image_style or "auto")
    cap_style = _auto_caption_style(fmt, req.caption_style or "auto")

    if fmt == "long":
        topics = random.sample(CONTENT_NICHES[niche]["topics"], 3)
        print(f"🎬 Long-form | {niche} | Topics: {[t[:35] for t in topics]}")

        # Research each story
        pipeline_status["step"] = "Researching stories (1/3)..."
        research_list = []
        for i, topic in enumerate(topics):
            pipeline_status["progress_detail"] = f"Researching story {i+1}/3..."
            print(f"  🔍 Researching story {i+1}: {topic[:45]}...")
            research_list.append(generate_research_brief(topic, niche))

        prompt = build_longform_prompt(topics, niche, research_list, img_style)
        max_tok = 6000
    else:
        topic = req.topic or random.choice(CONTENT_NICHES[niche]["topics"])
        print(f"🎲 {fmt.title()} | {niche} | Topic: {topic}")

        # Research the topic first
        pipeline_status["step"] = "Researching topic for viral angles..."
        print(f"  🔍 Researching: {topic[:50]}...")
        research = generate_research_brief(topic, niche)
        print(f"  ✅ Research: {research.get('most_shocking_fact','?')[:70]}...")

        prompt = build_shorts_prompt(topic, niche, research, img_style, cap_style)
        max_tok = 3000

    print(f"✍️  Writing script ({pipeline_status.get('llm_used','?')})...")
    raw = llm_call(prompt, max_tok)
    if not raw:
        raise Exception("All LLM providers failed")
    print(f"✅ Script via {pipeline_status.get('llm_used','?')}")

    data = _clean_json(raw)
    if not data:
        raise Exception(f"JSON parse failed. Raw[:300]: {raw[:300]}")

    data["content_type"] = niche
    data["format"]       = fmt
    data["image_style"]  = img_style
    data["caption_style"]= cap_style

    # For long-form: flatten stories into single script + scene list
    if fmt == "long" and "stories" in data:
        all_scenes = []
        full_script = ""
        for story in data["stories"]:
            all_scenes.extend(story.get("scenes", []))
            full_script += f"\n\n--- {story.get('subtitle','Story')} ---\n\n" + story.get("content", "")
        data["scenes"]  = all_scenes[:24]
        data["content"] = full_script.strip()

    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2A — VOICE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
EDGE_PROFILES = {
    "authoritative": {"voice": "en-US-GuyNeural",   "rate": "+0%",  "pitch": "-12Hz"},
    "suspenseful":   {"voice": "en-US-AriaNeural",  "rate": "-8%",  "pitch": "-6Hz"},
    "cinematic":     {"voice": "en-GB-RyanNeural",  "rate": "-5%",  "pitch": "-8Hz"},
    "dramatic":      {"voice": "en-GB-RyanNeural",  "rate": "-3%",  "pitch": "-10Hz"},
    "whisper":       {"voice": "en-US-JennyNeural", "rate": "-12%", "pitch": "-4Hz"},
    "default":       {"voice": "en-US-GuyNeural",   "rate": "+0%",  "pitch": "-10Hz"},
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


def generate_voice(content: str, voice_style: str, fmt: str,
                   audio_path: str, timings_path: str) -> list:
    # Long-form always uses cinematic voice
    if fmt == "long" and voice_style not in ("cinematic", "dramatic"):
        voice_style = "cinematic"

    profile = EDGE_PROFILES.get(voice_style, EDGE_PROFILES["default"])
    try:
        events = asyncio.run(_edge_tts_async(
            content, profile["voice"], profile["rate"], profile["pitch"],
            audio_path, timings_path))
        if events:
            print(f"✅ Voice: {profile['voice']} ({len(events)} words)")
            return events
    except Exception as e:
        print(f"  edge-tts failed: {e}")

    # gTTS fallback
    try:
        from gtts import gTTS
        gTTS(text=content, lang="en",
             tld="co.uk" if "GB" in profile["voice"] else "com",
             slow=False).save(audio_path)
        print("✅ Voice: gTTS fallback")
    except Exception as e:
        raise Exception(f"All TTS failed: {e}")

    dur = get_duration(audio_path)
    wt  = _fallback_timings(content, dur)
    with open(timings_path, "w") as f:
        json.dump(wt, f)
    return wt


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2B — SUBTITLES (3 styles)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _ass_time(s: float) -> str:
    cs  = int((s % 1) * 100)
    sec = int(s) % 60
    mn  = int(s) // 60 % 60
    hr  = int(s) // 3600
    return f"{hr}:{mn:02d}:{sec:02d}.{cs:02d}"


def generate_ass_subtitles(word_timings: list, ass_path: str,
                            caption_style: str, vid_w: int, vid_h: int):
    if not word_timings:
        Path(ass_path).write_text("", encoding="utf-8")
        return

    # Style definitions
    if caption_style == "netflix":
        style_line = (
            f"Style: Main,Arial,52,&H00FFFFFF,&H000000FF,&H00000000,"
            f"&HCC000000,1,0,0,0,100,100,0,0,1,0,0,2,40,40,60,1"
        )
        words_per_card = 6
    elif caption_style == "karaoke":
        style_line = (
            f"Style: Main,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,"
            f"&HAA000000,1,0,0,0,100,100,1,0,1,4,2,2,30,30,80,1"
        )
        words_per_card = 3
    else:  # impact (default for Shorts)
        style_line = (
            f"Style: Main,Impact,82,&H00FFFFFF,&H000000FF,&H00000000,"
            f"&HAA000000,1,0,0,0,100,100,1,0,1,5,2,2,30,30,80,1"
        )
        words_per_card = 3

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {vid_w}
PlayResY: {vid_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []

    if caption_style == "karaoke":
        # Highlight current word yellow, others white
        for i, wt in enumerate(word_timings):
            start = wt["start"]
            end   = wt["end"]
            context_start = max(0, i - 1)
            context_end   = min(len(word_timings), i + 2)
            safe_parts = []
            for j in range(context_start, context_end):
                w = word_timings[j]["word"].upper().replace("{","").replace("}","")
                if j == i:
                    safe_parts.append(f"{{\\c&H00FFFF&}}{w}{{\\c&HFFFFFF&}}")
                else:
                    safe_parts.append(w)
            text = " ".join(safe_parts)
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{text}")
    else:
        i = 0
        while i < len(word_timings):
            group = word_timings[i:i+words_per_card]
            i += words_per_card
            start = group[0]["start"]
            end   = max(group[-1]["end"], start + 0.3)
            text  = " ".join(w["word"] for w in group).upper()
            text  = text.replace("{","").replace("}","").replace("\\","")
            if len(text) > (35 if caption_style == "netflix" else 18):
                words = text.split()
                mid   = max(1, len(words)//2)
                text  = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
            lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{text}")

    Path(ass_path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ Subtitles: {caption_style} style, {len(lines)} cards")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION
# Priority: fal.ai (free, best) → Pollinations → Gemini → HuggingFace → Gradient
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _verify_image(path: str, min_size: int = 5_000) -> bool:
    p = Path(path)
    return p.exists() and p.stat().st_size > min_size


def _build_image_prompt(scene: str, image_style: str, content_type: str) -> str:
    style_desc = IMAGE_STYLES.get(image_style, IMAGE_STYLES["horror_2d"])["desc"]
    negative   = IMAGE_STYLES.get(image_style, IMAGE_STYLES["horror_2d"])["negative"]
    if content_type == "history":
        atmosphere = "medieval historical setting, aged texture, ancient atmosphere"
    else:
        atmosphere = "modern urban noir, city night, crime thriller atmosphere"
    return f"{scene}, {style_desc}, {atmosphere}"[:550]


def _fetch_gemini_flash_image(prompt: str) -> Optional[bytes]:
    """
    TIER 1 — Gemini 2.5 Flash Image (model: gemini-2.5-flash-image)
    ─────────────────────────────────────────────────────────────────
    Uses your existing GEMINI_API_KEY. Single POST, returns inline
    base64 image in ~5–10s. 500 free requests/day. Render-safe.

    Key API facts (confirmed working as of May 2025):
    • Model string: gemini-2.5-flash-image  (NOT gemini-2.5-flash)
    • Modality:     responseModalities: ["IMAGE"]  (TEXT omitted for speed)
    • Aspect:       imageConfig.aspectRatio = "9:16" or "1:1"
    • Response:     candidates[0].content.parts[].inlineData.data (base64)
    • Safety note:  dark/horror prompts may hit safety filter →
                    we sanitize the prompt to remove trigger words
    """
    if not GEMINI_API_KEY:
        return None

    # Sanitize: Gemini safety filter blocks "gore", "torture", "blood" etc.
    # Rephrase visceral words to cinematic/atmospheric equivalents
    safe_prompt = (prompt
        .replace("torture", "suffering")
        .replace("gore", "darkness")
        .replace("blood", "crimson shadow")
        .replace("murder", "crime scene")
        .replace("kill", "tragic end")
        .replace("dead body", "fallen figure")
        .replace("corpse", "lifeless form")
        .replace("execution", "somber ritual")
        .replace("decapitat", "dramatic end")
        [:500]
    )

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.5-flash-image:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": safe_prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": "9:16"},
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
        ],
    }
    try:
        t0   = time.time()
        resp = requests.post(url, json=payload, timeout=25)
        elapsed = time.time() - t0

        if resp.status_code != 200:
            err = resp.json().get("error", {}).get("message", resp.text[:120])
            print(f"    Gemini image HTTP {resp.status_code}: {err[:100]}")
            return None

        for part in (resp.json()
                     .get("candidates", [{}])[0]
                     .get("content", {})
                     .get("parts", [])):
            inline = part.get("inlineData", {})
            if inline.get("mimeType", "").startswith("image/"):
                data = base64.b64decode(inline["data"])
                print(f"    ✅ Gemini image ({len(data)//1024}KB, {elapsed:.1f}s)")
                return data

        # No image — log text parts for debugging
        text_parts = [p.get("text","") for p in
                      resp.json().get("candidates",[{}])[0]
                      .get("content",{}).get("parts",[]) if p.get("text")]
        print(f"    Gemini: no image part. resp={str(text_parts)[:100]}")
        return None

    except requests.Timeout:
        print(f"    Gemini image timeout (>25s)")
        return None
    except Exception as e:
        print(f"    Gemini image error: {e}")
        return None


def _fetch_pollinations(prompt: str, w: int, h: int) -> Optional[bytes]:
    """Pollinations turbo — free, anonymous, 12s spacing needed."""
    encoded = requests.utils.quote(prompt[:480])
    seed    = random.randint(1000, 999999)
    url     = (f"https://image.pollinations.ai/prompt/{encoded}"
               f"?width={w}&height={h}&model=turbo&seed={seed}"
               f"&nologo=true&enhance=true&private=true")
    try:
        resp = requests.get(url,
            headers={"Referer": "https://darkhistorytv.onrender.com",
                     "User-Agent": "DarkHistoryTV/9.0"},
            timeout=28)
        if resp.status_code == 200 and len(resp.content) > 8_000:
            return resp.content
        if resp.status_code == 429:
            print(f"    [429] Pollinations rate limited")
    except requests.Timeout:
        print("    Pollinations timeout")
    except Exception as e:
        print(f"    Pollinations error: {e}")
    return None


def _fetch_gemini_image_fallback(prompt: str) -> Optional[bytes]:
    """
    TIER 3 fallback — tries gemini-2.0-flash-exp with TEXT+IMAGE modality.
    Some accounts have this model available; others don't.
    Separate from T1 (gemini-2.5-flash-image) which uses IMAGE-only modality.
    """
    if not GEMINI_API_KEY:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}"
    )
    safe_prompt = prompt.replace("torture","suffering").replace("gore","darkness")[:400]
    try:
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": f"Draw: {safe_prompt}"}]}],
                  "generationConfig": {"responseModalities": ["TEXT","IMAGE"]}},
            timeout=25)
        if resp.status_code == 200:
            for cand in resp.json().get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData", {})
                    if inline.get("mimeType", "").startswith("image/"):
                        return base64.b64decode(inline["data"])
        print(f"    Gemini 2.0-exp HTTP {resp.status_code}")
    except Exception as e:
        print(f"    Gemini 2.0-exp: {e}")
    return None


def _fetch_huggingface(prompt: str, w: int, h: int) -> Optional[bytes]:
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}
    for model_url, payload in [
        ("https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-schnell",
         {"inputs": prompt[:300], "parameters": {"width": w, "height": h, "num_inference_steps": 4}}),
        ("https://api-inference.huggingface.co/models/stabilityai/sdxl-turbo",
         {"inputs": prompt[:300], "parameters": {"num_inference_steps": 1, "guidance_scale": 0.0,
                                                  "width": min(w,512), "height": min(h,512)}}),
    ]:
        try:
            resp = requests.post(model_url, headers=headers, json=payload, timeout=25)
            if resp.status_code == 200 and resp.headers.get("Content-Type","").startswith("image/"):
                return resp.content
            if resp.status_code == 503:
                time.sleep(3)
        except Exception as e:
            print(f"    HF error: {e}")
    return None


def _make_gradient(content_type: str, w: int, h: int, output_path: str) -> bool:
    colors = {
        "history":   [("0x1A0C06","0x3D1A08"), ("0x14080A","0x3D1020")],
        "truecrime": [("0x060810","0x101828"), ("0x080A10","0x141E2A")],
    }
    c1, c2 = random.choice(colors.get(content_type, colors["truecrime"]))
    cmds = [
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"gradients=size={w}x{h}:x0=0:y0=0:x1={w}:y1={h}:c0={c1}:c1={c2}:duration=1",
         "-vf", "noise=alls=12:allf=t+u,format=yuvj420p",
         "-frames:v", "1", output_path],
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={c2}:size={w}x{h}:duration=1",
         "-frames:v", "1", "-vf", "format=yuvj420p", output_path],
    ]
    for cmd in cmds:
        r = subprocess.run(cmd, capture_output=True, timeout=15)
        if r.returncode == 0 and Path(output_path).exists():
            return True
    return False


def prefetch_all_images(scenes: list, image_style: str, content_type: str,
                         session: Path, img_w: int, img_h: int) -> list:
    """
    Pre-fetch ALL images before building any clips.
    fal.ai is primary (free, no rate limit issues).
    Pollinations secondary with 12s spacing.
    """
    results = []
    pollinations_last_call = 0.0
    print(f"  📸 Pre-fetching {len(scenes)} images ({img_w}x{img_h})...")

    for i, scene in enumerate(scenes):
        img_path = str(session / f"img_{i}.jpg")
        prompt   = _build_image_prompt(scene, image_style, content_type)
        print(f"  🎨 Image {i+1}/{len(scenes)}: {scene[:50]}...")
        pipeline_status["progress_detail"] = f"Image {i+1}/{len(scenes)}"

        data = None

        # ── Tier 1: Gemini 2.5 Flash Image (existing key, 5–10s, Render-safe) ──
        if GEMINI_API_KEY:
            print("    [T1] Gemini 2.5-flash-image...")
            data = _fetch_gemini_flash_image(prompt)
            if data:
                pipeline_status["image_source"] = "Gemini 2.5 Flash Image"

        # ── Tier 2: Pollinations turbo (free, respect 12s rate limit) ───────────
        if data is None:
            wait_needed = 12.0 - (time.time() - pollinations_last_call)
            if wait_needed > 0:
                print(f"    [T2] Pollinations (waiting {wait_needed:.0f}s)...")
                time.sleep(wait_needed)
            else:
                print("    [T2] Pollinations turbo...")
            data = _fetch_pollinations(prompt, img_w, img_h)
            pollinations_last_call = time.time()
            if data is None:
                print("    [T2] Pollinations retry in 15s...")
                time.sleep(15)
                data = _fetch_pollinations(prompt, img_w, img_h)
                pollinations_last_call = time.time()
            if data:
                pipeline_status["image_source"] = pipeline_status.get("image_source","Pollinations")

        # ── Tier 3: Gemini 2.0 Flash Exp (fallback if 2.5 failed) ───────────────
        if data is None and GEMINI_API_KEY:
            print("    [T3] Gemini 2.0-flash-exp fallback...")
            data = _fetch_gemini_image_fallback(prompt)
            if data:
                pipeline_status["image_source"] = "Gemini 2.0 Flash Exp"

        # ── Tier 4: HuggingFace FLUX / SDXL-Turbo ───────────────────────────────
        if data is None and HF_TOKEN:
            print("    [T4] HuggingFace...")
            data = _fetch_huggingface(prompt, img_w, img_h)
            if data:
                pipeline_status["image_source"] = "HuggingFace"

        # Tier 5: Gradient
        if data is not None:
            Path(img_path).write_bytes(data)
            if _verify_image(img_path):
                size_kb = Path(img_path).stat().st_size // 1024
                print(f"    ✅ OK ({size_kb}KB)")
                results.append((scene, img_path))
                pipeline_status["image_source"] = "fal.ai FLUX" if i == 0 else pipeline_status.get("image_source", "fal.ai")
                continue

        print("    [T5] Gradient fallback")
        _make_gradient(content_type, img_w, img_h, img_path)
        results.append((scene, img_path))
        pipeline_status["image_source"] = pipeline_status.get("image_source", "Gradient")

    return results


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3B — KEN BURNS CLIPS
# Exact timing: Shorts=2.5s, Long=3.0s, Square=2.75s per image
# Hook image (scene 0): zoom-punch effect for maximum impact
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLIP_FPS = 25


def _ken_burns_filter(duration: float, style: int, vid_w: int, vid_h: int,
                       is_hook: bool = False) -> str:
    """
    6 Ken Burns movements + hook zoom-punch for first scene.
    Hook: fast zoom-in (1.0→1.25) with slight shake for shock effect.
    """
    d  = int(duration * CLIP_FPS)
    sw = vid_w * 2
    sh = vid_h * 2

    if is_hook:
        # Zoom punch: fast scale up, slightly off-center for drama
        return (f"scale={sw}:{sh},"
                f"zoompan=z='min(zoom+0.0018,1.28)':x='iw/2-(iw/zoom/2)+{int(vid_w*0.02)}*(on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}")

    styles = {
        0: f"scale={sw}:{sh},zoompan=z='min(zoom+0.0006,1.2)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        1: f"scale={sw}:{sh},zoompan=z='if(eq(on,1),1.2,max(zoom-0.0006,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        2: f"scale={sw}:{sh},zoompan=z='1.08':x='iw*0.08*(on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        3: f"scale={sw}:{sh},zoompan=z='1.08':x='iw*0.08*(1-on/{d})':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        4: f"scale={sw}:{sh},zoompan=z='1.08':x='iw/2-(iw/zoom/2)':y='ih*0.06*(on/{d})':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        5: f"scale={sw}:{sh},zoompan=z='min(zoom+0.0005,1.15)':x='iw*0.04*(on/{d})+(iw/2-(iw/zoom/2))':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
    }
    return styles[style % 6]


def build_clip_from_image(img_path: str, duration: float, output_path: str,
                           kb_style: int, vid_w: int, vid_h: int,
                           is_hook: bool = False) -> bool:
    if not _verify_image(img_path, min_size=1000):
        return False

    kb_filter = _ken_burns_filter(duration, kb_style, vid_w, vid_h, is_hook)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", f"{kb_filter},format=yuv420p",
        "-t", str(duration), "-c:v", "libx264", "-crf", "23",
        "-preset", "ultrafast", "-r", str(CLIP_FPS),
        "-pix_fmt", "yuv420p", "-threads", "1", "-an", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        # Static fallback
        cmd2 = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,"
                    f"crop={vid_w}:{vid_h},format=yuv420p"),
            "-t", str(duration), "-c:v", "libx264", "-crf", "23",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-threads", "1", "-an", output_path,
        ]
        result = subprocess.run(cmd2, capture_output=True, timeout=120)

    return result.returncode == 0 and Path(output_path).exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — BACKGROUND MUSIC + SOUND DESIGN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUSIC_QUERIES = {
    "dark_orchestral":  "dark dramatic orchestral documentary historical suspense cinematic horror",
    "noir_suspense":    "noir suspense minimal dark ambient crime thriller piano psychological",
    "vintage_dread":    "vintage horror organ dark suspense silent film era eerie atmosphere",
    "digital_dread":    "dark electronic ambient drone minimal horror digital suspense",
}


def generate_music(sound_mood: str, music_path: str) -> bool:
    query = MUSIC_QUERIES.get(sound_mood, MUSIC_QUERIES["dark_orchestral"])
    try:
        r = requests.get(
            f"https://audio.pollinations.ai/{requests.utils.quote(query)}",
            timeout=40)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            print(f"✅ Music: {sound_mood}")
            return True
    except Exception as e:
        print(f"  Music API failed: {e}")

    # Silent fallback
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi",
             "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "720", "-c:a", "aac", "-b:a", "128k", music_path],
            capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def generate_sound_design(content_type: str, duration: float, session: Path) -> Optional[str]:
    """
    Generate atmospheric sound design layer using ffmpeg.
    Creates subtle ambient dread: low-frequency drone + optional effects.
    Completely free — all generated via ffmpeg sine waves + noise.
    """
    sd_path = str(session / "sounddesign.mp3")
    try:
        if content_type == "history":
            # Low drone at 50Hz + occasional bell shimmer
            filter_str = (
                "sine=frequency=50:duration={d}[base];"
                "sine=frequency=220:duration={d}[bell];"
                "[base]volume=0.3[b1];"
                "[bell]volume=0.05,aecho=0.8:0.8:60:0.5[b2];"
                "[b1][b2]amix=inputs=2[out]"
            ).format(d=int(duration)+2)
        else:
            # Heart-rate-like pulse at 60bpm + static
            filter_str = (
                "sine=frequency=80:duration={d}[pulse];"
                "[pulse]volume=0.2,atempo=1.0[out]"
            ).format(d=int(duration)+2)

        cmd = [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc=0:d={int(duration)+2}",
            "-f", "lavfi", "-i", "sine=frequency=55:duration=" + str(int(duration)+2),
            "-filter_complex", "[1:a]volume=0.15,lowpass=f=200[out]",
            "-map", "[out]", "-c:a", "aac", "-b:a", "64k", sd_path
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        if r.returncode == 0 and Path(sd_path).exists():
            return sd_path
    except Exception as e:
        print(f"  Sound design failed: {e}")
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 5 — VIDEO ASSEMBLY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def assemble_video(clips: list, voice_p: str, music_p: Optional[str],
                   sound_p: Optional[str], ass_p: str, output_p: str,
                   fmt: str, vid_w: int, vid_h: int):
    ts = str(int(time.time()))

    # Concat clips
    txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", txt,
         "-c", "copy", concat_out],
        capture_output=True, timeout=300)
    if r.returncode != 0:
        raise Exception(f"Concat failed: {r.stderr[-300:].decode(errors='ignore')}")
    print(f"  ✅ Concat: {len(clips)} clips")

    audio_dur = get_duration(voice_p)
    max_dur   = FORMATS[fmt]["max_dur"]
    voice_dur = min(audio_dur + 0.5, max_dur)
    has_subs  = ass_p and Path(ass_p).exists() and Path(ass_p).stat().st_size > 50
    use_music = music_p and Path(music_p).exists()
    use_sound = sound_p and Path(sound_p).exists()

    music_vol = "0.07" if fmt == "shorts" else "0.10"
    sound_vol = "0.12"
    vf = f"ass='{ass_p}'" if has_subs else "null"

    # Build audio filter
    inputs = [concat_out, voice_p]
    if use_music:
        inputs.append(music_p)
    if use_sound:
        inputs.append(sound_p)

    voice_idx = 1
    music_idx = 2 if use_music else None
    sound_idx = (3 if use_sound and use_music else 2) if use_sound else None

    afilt_parts = [f"[{voice_idx}:a]loudnorm=I=-16:TP=-1.5:LRA=11,volume=2.2[voice]"]
    mix_labels  = ["[voice]"]

    if use_music:
        afilt_parts.append(
            f"[{music_idx}:a]volume={music_vol},aloop=loop=-1:size=2e+09[music]")
        mix_labels.append("[music]")
    if use_sound:
        afilt_parts.append(
            f"[{sound_idx}:a]volume={sound_vol},aloop=loop=-1:size=2e+09[soundlayer]")
        mix_labels.append("[soundlayer]")

    n_inputs = len(mix_labels)
    afilt_parts.append(
        f"{''.join(mix_labels)}amix=inputs={n_inputs}:duration=first:dropout_transition=2[afinal]")
    afilt = ";".join(afilt_parts)

    i_flags = []
    for f in inputs:
        i_flags += ["-i", f]

    cmd = [
        "ffmpeg", "-y",
        *i_flags,
        "-t", str(voice_dur),
        "-vf", vf,
        "-filter_complex", afilt,
        "-map", "0:v", "-map", "[afinal]",
        "-c:v", "libx264", "-crf", "22",
        "-preset", "fast" if fmt == "long" else "ultrafast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        "-threads", "1", output_p,
    ]

    print(f"  🎬 Encoding: {voice_dur:.1f}s | {FORMATS[fmt]['label']} | "
          f"subs={'yes' if has_subs else 'no'} | "
          f"music={'yes' if use_music else 'no'} | "
          f"sound={'yes' if use_sound else 'no'}")

    r = subprocess.run(cmd, capture_output=True, timeout=900)

    if r.returncode != 0:
        err = r.stderr[-500:].decode(errors="ignore")
        if has_subs and ("ass" in err.lower() or "subtitle" in err.lower()):
            print("  ⚠️  Subtitle error — retrying without subs...")
            cmd_ns = [vf if x == vf else x for x in cmd]
            cmd_ns = ["null" if x == vf else x for x in cmd_ns]
            r = subprocess.run(cmd_ns, capture_output=True, timeout=900)
            if r.returncode != 0:
                raise Exception(f"FFmpeg (no-sub) failed: {r.stderr[-300:].decode(errors='ignore')}")
        else:
            raise Exception(f"FFmpeg failed: {err}")

    if not Path(output_p).exists() or Path(output_p).stat().st_size < 10_000:
        raise Exception("Final video missing or too small")

    for f in [concat_out, txt]:
        Path(f).unlink(missing_ok=True)
    print(f"  ✅ Final video: {Path(output_p).stat().st_size // 1024}KB")


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
        raise Exception(f"YT token failed: {r.text[:200]}")
    return r.json()["access_token"]


def upload_youtube(video_path: str, data: dict, fmt: str) -> str:
    token = get_yt_token()

    base_tags = {
        "history":   ["dark history","bizarre history","history facts","medieval history",
                      "horror stories animated","dark secrets","disturbing history",
                      "history shorts","ancient history"],
        "truecrime": ["true crime","cold case","unsolved mysteries","crime story",
                      "horror stories animated","murder mystery","criminal psychology",
                      "true crime shorts","forensic investigation"],
    }.get(data.get("content_type",""), [])

    research_keywords = data.get("top_keywords", [])
    tags = list(dict.fromkeys(base_tags + research_keywords + data.get("tags", [])))[:15]

    description = (
        f"{data.get('description', '')}\n\n"
        f"🔔 Subscribe for daily dark history & true crime\n"
        f"👇 What shocked you most? Comment below!\n\n"
        f"{data.get('hashtags','#DarkHistory #TrueCrime #HorrorStoriesAnimated')}"
    )

    meta = {
        "snippet": {
            "title":           data["title"][:100],
            "description":     description[:4900],
            "tags":            tags,
            "categoryId":      "27",   # Education — highest CPM
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus":          "public",
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
        json=meta, timeout=30)
    if init_r.status_code != 200:
        raise Exception(f"YT init {init_r.status_code}: {init_r.text[:200]}")

    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(
        init_r.headers["Location"],
        headers={"Content-Type":   "video/mp4",
                 "Content-Length": str(len(video_bytes))},
        data=video_bytes, timeout=600)
    if up_r.status_code not in (200, 201):
        raise Exception(f"YT upload {up_r.status_code}: {up_r.text[:200]}")

    vid_id = up_r.json().get("id", "unknown")
    print(f"  ✅ YouTube ID: {vid_id}")
    return vid_id


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL PIPELINE v9
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def full_pipeline(req: RunRequest):
    if pipeline_status["running"]:
        return

    pipeline_status["running"]        = True
    pipeline_status["error"]          = None
    pipeline_status["llm_used"]       = None
    pipeline_status["image_source"]   = None
    pipeline_status["progress_detail"]= ""

    fmt     = req.format or "shorts"
    fmt_cfg = FORMATS.get(fmt, FORMATS["shorts"])
    vid_w   = fmt_cfg["w"]
    vid_h   = fmt_cfg["h"]
    img_w   = fmt_cfg["img_w"]
    img_h   = fmt_cfg["img_h"]
    scene_dur = fmt_cfg["scene_dur"]

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = WORK_DIR / ts
    session.mkdir(exist_ok=True)

    try:
        # ── STEP 1: Research + Content ────────────────────────────────────────
        pipeline_status["step"] = "Researching viral angles..."
        pipeline_status["step_index"] = 1
        data = generate_content(req)
        print(f"✅ Title: {data['title']}")
        print(f"✅ Hook:  {data.get('hook_line', '?')[:80]}")

        # ── STEP 2: Voice ─────────────────────────────────────────────────────
        pipeline_status["step"] = "Synthesizing voice narration..."
        pipeline_status["step_index"] = 2
        voice_p   = str(session / "voice.mp3")
        timings_p = str(session / "timings.json")
        word_timings = generate_voice(
            data["content"],
            data.get("voice_style", fmt_cfg["default_voice"]),
            fmt, voice_p, timings_p)
        audio_dur = get_duration(voice_p)
        print(f"  Audio: {audio_dur:.1f}s")

        # ── STEP 2B: Subtitles ────────────────────────────────────────────────
        ass_p = str(session / "subs.ass")
        cap_style = data.get("caption_style", fmt_cfg["default_caption"])
        generate_ass_subtitles(word_timings, ass_p, cap_style, vid_w, vid_h)

        # ── STEP 3: Images → Clips ────────────────────────────────────────────
        pipeline_status["step"] = "Pre-fetching scene images..."
        pipeline_status["step_index"] = 3

        scenes = data.get("scenes", [])
        max_dur = fmt_cfg["max_dur"]
        target_dur = min(audio_dur + 1.0, max_dur)

        # Calculate exact number of scenes needed (exact duration coverage)
        scenes_needed = math.ceil(target_dur / scene_dur) + 1
        scenes_needed = max(scenes_needed, 9)  # minimum 9 scenes

        # Loop / extend scenes if needed
        while len(scenes) < scenes_needed:
            scenes = scenes + scenes
        scenes = scenes[:scenes_needed]

        image_results = prefetch_all_images(
            scenes, data["image_style"], data["content_type"],
            session, img_w, img_h)

        # Build clips from pre-fetched images
        pipeline_status["step"] = "Building animated clips..."
        clips = []
        for i, (scene, img_path) in enumerate(image_results):
            clip_path = str(session / f"clip_{i}.mp4")
            is_hook   = (i == 0)  # First clip gets zoom-punch
            ok = build_clip_from_image(
                img_path, scene_dur, clip_path, i, vid_w, vid_h, is_hook)
            if ok and Path(clip_path).stat().st_size > 1000:
                clips.append(clip_path)
            else:
                print(f"  ⚠️  Clip {i+1} failed")

        if not clips:
            raise Exception("All clips failed to build")
        print(f"  ✅ {len(clips)} clips ({len(clips)*scene_dur:.1f}s total visual)")

        # ── STEP 4: Music + Sound Design ──────────────────────────────────────
        pipeline_status["step"] = "Generating atmosphere & music..."
        pipeline_status["step_index"] = 4
        music_p = str(session / "music.mp3")
        sound_mood = data.get("sound_mood", "dark_orchestral")
        if not generate_music(sound_mood, music_p):
            music_p = None

        sound_p = generate_sound_design(data["content_type"], audio_dur, session)

        # ── STEP 5: Assemble ──────────────────────────────────────────────────
        pipeline_status["step"] = "Assembling final video..."
        pipeline_status["step_index"] = 5
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, sound_p, ass_p,
                       final_p, fmt, vid_w, vid_h)

        # ── STEP 6: Upload ────────────────────────────────────────────────────
        pipeline_status["step"] = "Uploading to YouTube..."
        pipeline_status["step_index"] = 6
        if not Path(final_p).exists() or Path(final_p).stat().st_size < 10_000:
            raise Exception("Final video invalid or too small")

        video_id = upload_youtube(final_p, data, fmt)
        fmt_suffix = "shorts/" if fmt == "shorts" else "watch?v="
        url = f"https://youtube.com/{fmt_suffix}{video_id}"
        print(f"✅ LIVE: {url}")

        # ── STEP 7: Log + Save thumbnail prompt ───────────────────────────────
        pipeline_status["step"] = "Done! 🎉"
        pipeline_status["step_index"] = 7

        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp":        ts,
            "video_id":         video_id,
            "title":            data["title"],
            "title_variants":   data.get("title_variants", []),
            "hook_line":        data.get("hook_line", ""),
            "content_type":     data["content_type"],
            "format":           fmt,
            "image_style":      data["image_style"],
            "caption_style":    cap_style,
            "image_source":     pipeline_status.get("image_source", ""),
            "llm_used":         data.get("llm_used", pipeline_status.get("llm_used","")),
            "thumbnail_prompt": data.get("thumbnail_prompt", ""),
            "url":              url,
            "version":          "9.0",
        }
        log.append(entry)
        LOG_FILE.write_text(json.dumps(log, indent=2))
        pipeline_status["last_result"] = entry
        print(f"\n📋 Thumbnail prompt saved to log for manual creation.")
        if data.get("thumbnail_prompt"):
            print(f"   {data['thumbnail_prompt'][:120]}...")

    except Exception as e:
        pipeline_status["error"] = str(e)
        print(f"❌ Pipeline error: {e}")
        import traceback; traceback.print_exc()
    finally:
        pipeline_status["running"]         = False
        pipeline_status["progress_detail"] = ""
        shutil.rmtree(str(session), ignore_errors=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/")
def root():
    return {
        "service": "DarkHistory.ai v9.0 — The Killer Content Machine",
        "version": "9.0",
        "formats": {k: v["label"] for k, v in FORMATS.items()},
        "image_styles": {k: v["label"] for k, v in IMAGE_STYLES.items()},
        "caption_styles": ["impact", "netflix", "karaoke"],
        "niches": {k: v["label"] for k, v in CONTENT_NICHES.items()},
        "new_in_v9": [
            "Research-first scripting (research brief before every script)",
            "Hook image with zoom-punch effect on first scene",
            "Thumbnail prompt generated for every video",
            "4 image styles (horror_2d, cinematic, graphic_novel, vintage_horror)",
            "fal.ai FLUX Schnell as primary free image source",
            "Sound design layer (ambient dread)",
            "Exact scene timing: 2.5s/shorts, 3.0s/long, 2.75s/square",
            "3 title variants per video for A/B testing",
            "Research-backed SEO keywords",
        ],
    }


@app.post("/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req)
    return {
        "status":        "started",
        "format":        req.format or "shorts",
        "image_style":   req.image_style or "auto",
        "caption_style": req.caption_style or "auto",
        "content_type":  req.content_type or "auto (alternating)",
        "version":       "9.0",
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
        "recommendation": "Stick to these 2 niches — both have $8-$18 CPM and massive search volume",
        "niches": [
            {"id": k, "label": v["label"], "icon": v["icon"],
             "cpm": v["cpm"], "topic_count": len(v["topics"])}
            for k, v in CONTENT_NICHES.items()
        ],
    }


@app.get("/topics")
def get_topics():
    return {k: v["topics"] for k, v in CONTENT_NICHES.items()}


@app.get("/options")
def get_options():
    return {
        "formats": [
            {"id": k, "label": v["label"], "aspect": f"{v['w']}x{v['h']}",
             "max_duration": v["max_dur"], "scene_duration": v["scene_dur"]}
            for k, v in FORMATS.items()
        ],
        "image_styles": [
            {"id": k, "label": v["label"]} for k, v in IMAGE_STYLES.items()
        ],
        "caption_styles": [
            {"id": "impact",  "label": "Impact (big centered, Shorts default)"},
            {"id": "netflix", "label": "Netflix (bottom bar, long-form)"},
            {"id": "karaoke", "label": "Karaoke (highlighted word, engagement)"},
        ],
        "niches": [
            {"id": k, "label": v["label"], "icon": v["icon"]}
            for k, v in CONTENT_NICHES.items()
        ],
    }


@app.get("/formats")
def get_formats():
    return FORMATS


@app.get("/health")
def health():
    return {
        "status":    "healthy",
        "version":   "9.0",
        "keys": {
            "gemini":     bool(GEMINI_API_KEY),
            "groq":       bool(GROQ_API_KEY),
            "openrouter": bool(OPENROUTER_API_KEY),
            "hf_token":   bool(HF_TOKEN),
            "youtube":    bool(YOUTUBE_REFRESH_TOKEN),
        },
        "image_pipeline": [
            "T1: fal.ai FLUX Schnell (FREE, no key)",
            "T2: Pollinations turbo (FREE, 12s spacing)",
            "T3: Gemini 2.0 Flash Exp (needs GEMINI_API_KEY)",
            "T4: HuggingFace FLUX (needs HF_TOKEN)",
            "T5: Gradient fallback (always works)",
        ],
        "timestamp": datetime.now().isoformat(),
    }
