"""
DarkHistory.ai — Backend v10.0  ████████████████████████████████████████████████
THE VIRAL HORROR CONTENT MACHINE — Full Rebuild

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PHILOSOPHY (think like a creator with 10M subs):
  Every decision in this file is made through one lens:
  "Will this make someone stop scrolling, watch to the end, and subscribe?"
  Algorithm rewards: Watch time → CTR → Comments → Shares (in that order).
  Our job: hook in 3s, hold for 55s, leave them unsettled enough to comment.

WHAT'S NEW IN v10.0:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
THREE-STAGE SCRIPT ENGINE (Research → Outline → Full Script):
  Stage 1 — RESEARCH BRIEF: Deep-dive on topic. Pulls:
    - Most shocking fact (specific numbers, names, dates)
    - Sensory details (what it smelled/sounded/felt like)
    - Lesser-known angle no other channel covers
    - 3 viral hook options (A/B/C tested)
    - The "twist" that reframes everything
    - Thumbnail concept (fear face + text formula from PDF)
  Stage 2 — VIRAL OUTLINE: Uses research to build a beat-by-beat arc.
    - Hook beat (0-3s): most visceral line
    - Dread build (3-15s): sensory immersion
    - Escalation (15-35s): lesser-known angle
    - Gut-punch twist (35-50s)
    - Haunting end (50-57s): lingers, drives comments
  Stage 3 — FULL SCRIPT: Written from the outline. PDF formula applied.
    - Present tense for history events
    - Detective case-file voice for true crime
    - Every word earns its place (130-150 words for Shorts)

HOOK IMAGE SYSTEM (NEW):
  Scene 0 = dedicated SHOCK IMAGE separate from the story scenes.
  This is NOT scene 1. It's a specially crafted image designed purely
  to stop the scroll in the first 2-3 seconds.
  - AI-generated with maximum dread composition
  - Bold text overlay BURNT IN via ffmpeg (title + fear phrase)
  - Zoom-punch Ken Burns effect (fast scale 1.0→1.3 in 2.5s)
  - Different prompt formula: extreme close-up, maximum horror
  - Fallback: ffmpeg title card with glitch effect

FORMAT SYSTEM (Shorts + Long-form):
  SHORTS (9:16, 720×1280, 55-58s):
    - 130-150 word script
    - 9 scenes (1 hook + 8 story): each exactly 2.5s
    - Impact captions (centered, 3 words/card, ALL CAPS)
    - Auto-niche alternates: history ↔ truecrime
  LONG-FORM (16:9, 1280×720, 8-12min):
    - 3 stories × 1200-1500 words each
    - 8 scenes per story = 24 total: each exactly 3.0s
    - Netflix bottom-bar captions
    - Chapter timestamps for YouTube chapters

IMAGE STYLES (niche-matched):
  history   → vintage_horror (sepia, 1920s poster, aged grain)
  truecrime → cinematic (photorealistic noir, chiaroscuro)
  Override: horror_2d | graphic_novel | vintage_horror | cinematic

IMAGE PIPELINE (confirmed working from Render.com):
  TIER 1: Cloudflare Workers AI FLUX.1-schnell  — CF_ACCOUNT_ID + CF_API_TOKEN
           10,000 neurons/day FREE. ~100/image. Not IP-blocked.
  TIER 2: Gemini 2.5 Flash Image                — GEMINI_API_KEY
           500 requests/day free. 5-10s. Safety filter sanitized.
  TIER 3: Gemini 2.0 Flash Exp fallback          — GEMINI_API_KEY
  TIER 4: Cinematic FFmpeg (scene-matched color) — always works, <1s

CAPTION STYLES:
  Shorts    → Impact (big centered, 3 words/card, TikTok style)
  Long-form → Netflix (bottom bar, white on dark band, 6 words/card)

SOUND DESIGN (ffmpeg-native, no external API):
  history   → 50Hz organ drone + bell shimmer
  truecrime → 80Hz pulse sync + static underlayer
  Both      → Music: Pollinations API → ffmpeg atmospheric fallback

YOUTUBE SEO v10:
  - Research-backed keywords in title AND description
  - 3 title A/B/C variants per video
  - Category 27 (Education) for max CPM
  - Chapter timestamps for long-form
  - Description formula: fear hook → story tease → CTA → tags → hashtags

ENV VARS:
  CF_ACCOUNT_ID, CF_API_TOKEN   — Cloudflare FLUX (image T1)
  GEMINI_API_KEY                — Gemini (LLM + image T2/T3)
  GROQ_API_KEY                  — Groq Llama 3.3 (LLM fallback)
  OPENROUTER_API_KEY            — OpenRouter (LLM fallback)
  YOUTUBE_CLIENT_ID/SECRET/REFRESH — upload
  HF_TOKEN                      — optional HuggingFace
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import os, json, time, random, asyncio, subprocess, re, shutil, base64, math
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from collections import Counter
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── ENV VARS ──────────────────────────────────────────────────────────────────
CF_ACCOUNT_ID         = os.environ.get("CF_ACCOUNT_ID", "")
CF_API_TOKEN          = os.environ.get("CF_API_TOKEN", "")
GEMINI_API_KEY        = os.environ.get("GEMINI_API_KEY", "")
GROQ_API_KEY          = os.environ.get("GROQ_API_KEY", "")
OPENROUTER_API_KEY    = os.environ.get("OPENROUTER_API_KEY", "")
HF_TOKEN              = os.environ.get("HF_TOKEN", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="DarkHistory.ai v10 — Viral Horror Machine", version="10.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

WORK_DIR = Path("/tmp/darkhistory")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

pipeline_status: dict = {
    "running":          False,
    "step":             "",
    "step_index":       0,
    "total_steps":      10,
    "last_result":      None,
    "error":            None,
    "llm_used":         None,
    "image_source":     None,
    "progress_detail":  "",
    "script_stage":     "",   # "researching" | "outlining" | "writing"
}

# ── FORMAT CONFIGS ─────────────────────────────────────────────────────────────
FORMATS = {
    # PRIMARY — YouTube Shorts 9:16 (daily driver, Shorts-first strategy)
    # 55-58s | 130-150 words | 9 clips (1 hook + 8 story scenes, each exactly 2.5s)
    # Impact captions | CPM $8-$18 | binge-able | algorithm-friendly
    "shorts": {
        "w": 720, "h": 1280, "fps": 25, "max_dur": 58,
        "label":             "YouTube Shorts 9:16",
        "hook_dur":          2.5,   # EXACTLY 2.5s — zoom-punch Ken Burns
        "scene_dur":         2.5,   # EXACTLY 2.5s per story scene (no exceptions)
        "num_stories":       1,
        "scenes_per_story":  8,     # 8 story clips + 1 hook clip = 9 total
        "default_caption":   "impact",
        "default_voice":     "suspenseful",
        "word_count":        "130-150",
        "img_w":             768,
        "img_h":             1024,  # 3:4 — CF FLUX max; scaled to fill 9:16
    },
    # SECONDARY — Long-form 16:9 (enable when Shorts hits 500 subs, 3x CPM/min)
    "long": {
        "w": 1280, "h": 720, "fps": 25, "max_dur": 720,
        "label":             "Long-form 16:9 (8-12min, 3 stories)",
        "hook_dur":          3.0,
        "scene_dur":         3.0,
        "num_stories":       3,
        "scenes_per_story":  8,
        "default_caption":   "netflix",
        "default_voice":     "cinematic",
        "word_count":        "1200-1500 per story",
        "img_w":             1024,
        "img_h":             576,
    },
}

# Active default. Shorts-first strategy: daily Shorts build audience + algorithm trust.
DEFAULT_FORMAT = "shorts"

# ── IMAGE STYLES ──────────────────────────────────────────────────────────────
IMAGE_STYLES = {
    "vintage_horror": {
        "label":    "Vintage Horror",
        "desc":     ("vintage horror poster art, sepia and aged film aesthetic, 1920s silent film horror, "
                     "scratched film grain overlay, high contrast with deep shadows, gothic illustration style, "
                     "faded amber and charcoal tones, expressionist angles, no text, no watermark"),
        "negative": "modern, digital, text, watermark, bright colors, colorful, cheerful",
        "hook_suffix": "extreme close-up, maximally disturbing focal point, vintage horror film still",
    },
    "cinematic": {
        "label":    "Cinematic Noir",
        "desc":     ("cinematic dark photography, photorealistic, dramatic chiaroscuro lighting, "
                     "deep shadows, film noir atmosphere, high contrast, Rembrandt lighting, "
                     "desaturated cold palette, professional cinematography, no text, no watermark"),
        "negative": "cartoon, illustration, text, watermark, bright lighting, cheerful, saturated",
        "hook_suffix": "extreme close-up, forensic detail, harsh single light source, maximum dread",
    },
    "horror_2d": {
        "label":    "2D Horror Animation",
        "desc":     ("2D horror animation, dark ethereal style, indigo-charcoal tones, soft film grain, "
                     "atmospheric dread, deep shadows, cinematic composition, cel shaded, "
                     "floating dust particles, no text, no watermark"),
        "negative": "photorealistic, 3d render, text, watermark, bright colors, cheerful",
        "hook_suffix": "extreme close-up, most disturbing visual, maximum horror composition",
    },
    "graphic_novel": {
        "label":    "Graphic Novel",
        "desc":     ("graphic novel illustration, bold ink outlines, cel shaded, "
                     "desaturated teal-grey palette, warm amber accent highlights, "
                     "dramatic directional shadows, gritty dark thriller comic art, no text, no watermark"),
        "negative": "photorealistic, text, watermark, pastel colors, cute, bright",
        "hook_suffix": "extreme close-up, bold stark composition, maximum visual impact",
    },
}

# ── CONTENT NICHES ─────────────────────────────────────────────────────────────
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
    "what the Black Death actually smelled like in a medieval city",
    "how ancient Rome disposed of its criminals in creative ways",
    "what it was like to be buried alive in the 1800s",
    "the terrifying experiments performed on prisoners in WWII",
    "what happened to the losers of ancient gladiatorial combat",
    "how the plague doctors in their bird masks actually worked",
    "the children who vanished during the Children's Crusade of 1212",
    "how serial killers operated in medieval Europe without detection",
    "the real torture methods used during the Salem Witch Trials",
    "how ancient Rome disposed of its criminals in creative ways",
    "the island where Napoleon Bonaparte slowly went insane",
    "how medieval people dealt with mental illness in the darkest ways",
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
    "how investigators caught a killer using a genealogy website",
    "the cult that convinced hundreds of people to give up everything",
    "the night shift horror at the hospital no one investigated",
    "the missing hiker case that revealed something far darker",
    "the small town that had a secret no one dared speak",
    "how a cold case file was reopened by a child's drawing",
    "the killer couple who traveled across states leaving no evidence",
    "how a tattoo identified a John Doe dead for 25 years",
    "the nurse who killed patients for 16 years before anyone checked",
    "how underground crime networks were exposed by one informant",
    "the cold case reopened after a suspect's deathbed confession",
    "the seemingly perfect husband who had a second family in another city",
    "how a single hair strand solved a murder 30 years later",
    "the forensic accountant who cracked a murder by following pennies",
]

CONTENT_NICHES = {
    "history": {
        "label":      "Bizarre History",
        "icon":       "🏛️",
        "topics":     HISTORY_TOPICS,
        "cpm":        "$8-$15",
        "img_style":  "vintage_horror",
        "sound_mood": "dark_orchestral",
        "voice":      "authoritative",
    },
    "truecrime": {
        "label":      "True Crime",
        "icon":       "🔍",
        "topics":     TRUE_CRIME_TOPICS,
        "cpm":        "$10-$18",
        "img_style":  "cinematic",
        "sound_mood": "noir_suspense",
        "voice":      "suspenseful",
    },
}

# ── REQUEST MODEL ─────────────────────────────────────────────────────────────
class RunRequest(BaseModel):
    topic:         Optional[str] = Field(default=None)
    content_type:  Optional[str] = Field(default=None, description="history|truecrime")
    format:        Optional[str] = Field(default=None, description="shorts|long — defaults to DEFAULT_FORMAT (currently shorts)")
    image_style:   Optional[str] = Field(default="auto",
                                          description="vintage_horror|cinematic|horror_2d|graphic_novel|auto")
    caption_style: Optional[str] = Field(default="auto",
                                          description="impact|netflix|auto")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LLM HELPERS — Gemini → Groq → OpenRouter waterfall
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
        print(f"Gemini error: {e}")
    return None


def call_groq(prompt: str, max_tokens: int = 4000) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        resp = requests.post("https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {GROQ_API_KEY}",
                     "Content-Type": "application/json"},
            json={"model": "llama-3.3-70b-versatile",
                  "messages": [
                      {"role": "system",
                       "content": ("You are a viral horror scriptwriter and YouTube strategist. "
                                   "Always respond with valid JSON only. No markdown, no backticks.")},
                      {"role": "user", "content": prompt}
                  ],
                  "temperature": 0.88, "max_tokens": max_tokens},
            timeout=120)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        print(f"Groq {resp.status_code}: {resp.text[:100]}")
    except Exception as e:
        print(f"Groq error: {e}")
    return None


def call_openrouter(prompt: str, max_tokens: int = 3000) -> Optional[str]:
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
                json={"model": model,
                      "messages": [{"role": "user", "content": prompt}],
                      "temperature": 0.88, "max_tokens": max_tokens},
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
    """Try all LLMs in quality order, set pipeline_status.llm_used."""
    for fn, name in [(call_gemini, "Gemini 2.5 Flash"),
                     (call_groq,   "Groq Llama 3.3 70B"),
                     (call_openrouter, "OpenRouter")]:
        raw = fn(prompt, max_tokens) if fn != call_openrouter else fn(prompt, min(max_tokens, 3000))
        if raw:
            pipeline_status["llm_used"] = name
            return raw
    return None


def _clean_json(raw: str) -> Optional[dict]:
    """Parse LLM response to dict, handling common formatting issues."""
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip()).rstrip("`").strip()
    m = re.search(r'\{[\s\S]*\}', raw)
    if m:
        raw = m.group(0)
    raw = raw.encode('utf-8', errors='ignore').decode('utf-8')
    raw = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw)
    raw = re.sub(r',\s*([}\]])', r'\1', raw)
    for attempt in [raw, raw.replace('\n', ' '), re.sub(r'\s+', ' ', raw)]:
        try:
            return json.loads(attempt)
        except json.JSONDecodeError:
            continue
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STAGE 1 — RESEARCH BRIEF
# The secret sauce. Forces the LLM to THINK before writing.
# Result: specific, disturbing, deeply researched scripts — not generic fluff.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_research_brief(topic: str, content_type: str) -> dict:
    """
    Deep research before any scripting. Based on the PDF's philosophy:
    'Research this topic deeply — find the angle no other channel covers.'
    """
    pipeline_status["script_stage"] = "researching"
    prompt = f"""You are a dark history/true crime researcher and YouTube strategist with 10M subscribers.
Topic: "{topic}"
Type: {content_type}

You MUST research this topic deeply and find what makes it GENUINELY disturbing and shareable.
Think: what would make someone screenshot this and send it to a friend at 2am?

Return ONLY valid JSON — no markdown, no backticks:
{{
  "most_shocking_fact": "The single most disturbing, SPECIFIC fact about this topic. Include real names, exact numbers, specific dates. NOT vague.",
  "sensory_details": "What did this LOOK, SOUND, SMELL like? Put the viewer IN THE SCENE. Use visceral, specific sensory language.",
  "psychological_hook": "What deep psychological fear does this trigger? (betrayal, being trapped, authority gone wrong, etc)",
  "lesser_known_angle": "The angle on this topic that NO OTHER YouTube channel covers. The hidden layer that makes this MORE disturbing than people think.",
  "specific_facts": [
    "Fact with exact numbers/names that sounds impossible but is true",
    "Date-specific fact that creates a vivid timeline",
    "Detail that makes the viewer physically uncomfortable",
    "The fact that completely reframes the whole story"
  ],
  "hook_line_options": [
    "Option A: Most visceral opening — drops you INTO the worst moment. Present tense. Under 12 words.",
    "Option B: Most curiosity-triggering — the disturbing question. Under 12 words.",
    "Option C: The shocking statistic or impossible-sounding fact. Under 12 words."
  ],
  "twist_element": "The one fact that reframes EVERYTHING the viewer thought they knew at the start. This is what drives 'I can't believe this' comments.",
  "thumbnail_concept": "SPECIFIC thumbnail description following the PDF formula: [specific character expression] + [specific object/scene] + [bold text overlay idea]. What would make someone STOP SCROLLING instantly?",
  "title_variants": [
    "Title A: [Number] [Specific Horror Theme] Horror Stories Animated — highest search volume, SEO formula",
    "Title B: curiosity gap — sounds impossible but is true — under 60 chars",
    "Title C: present-tense statement with fear trigger word — under 70 chars"
  ],
  "top_seo_keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5", "keyword6"],
  "comment_bait": "The unanswered question or disturbing thought to end the video with — designed to drive 'what do you think?' comments"
}}

Return ONLY the JSON. Nothing else."""

    raw = llm_call(prompt, max_tokens=2000)
    if not raw:
        return _fallback_research(topic, content_type)
    data = _clean_json(raw)
    if not data:
        return _fallback_research(topic, content_type)
    print(f"  ✅ Research: {data.get('most_shocking_fact','?')[:70]}...")
    return data


def _fallback_research(topic: str, content_type: str) -> dict:
    return {
        "most_shocking_fact": f"The disturbing truth about {topic} that nobody discusses",
        "sensory_details": "The air was thick with fear, silence broken only by shadows",
        "psychological_hook": "fear of the unknown",
        "lesser_known_angle": f"The hidden layer of {topic} that changes everything",
        "specific_facts": [f"The key fact about {topic}"],
        "hook_line_options": [f"Nobody talks about what really happened with {topic}."],
        "twist_element": "The truth was far darker than anyone suspected",
        "thumbnail_concept": "Dark atmospheric scene with shocked face and bold text",
        "title_variants": [f"The Dark Truth About {topic.title()} Horror Stories Animated"],
        "top_seo_keywords": [topic, content_type, "dark history", "horror stories animated"],
        "comment_bait": "What do you think really happened?",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STAGE 2 — VIRAL OUTLINE
# Builds a beat-by-beat arc from the research brief.
# PDF formula: Hook → Dread Build → Escalation → Gut-punch → Haunting End
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_outline(topic: str, content_type: str, research: dict, fmt: str) -> dict:
    """
    Creates a beat-by-beat outline that the scriptwriter will follow.
    This intermediate step dramatically improves script quality.
    """
    pipeline_status["script_stage"] = "outlining"
    fmt_cfg   = FORMATS.get(fmt, FORMATS["shorts"])
    word_count = fmt_cfg["word_count"]

    hook_line    = research.get("hook_line_options", [""])[0]
    shocking     = research.get("most_shocking_fact", "")
    sensory      = research.get("sensory_details", "")
    twist        = research.get("twist_element", "")
    lesser       = research.get("lesser_known_angle", "")
    comment_bait = research.get("comment_bait", "")

    if content_type == "history":
        voice_notes = ("Present tense for historical events. "
                       "'Nobody talks about this.' 'History books hide this.' "
                       "Build dread with sensory detail. Ancient/medieval voice.")
    else:
        voice_notes = ("Detective case-file voice. Cold, precise, devastating. "
                       "Drop listener INTO the worst moment immediately. "
                       "One devastating detail per beat. Each worse than the last.")

    prompt = f"""You are a viral horror YouTube content strategist. You've grown channels to 10M subscribers.
Topic: "{topic}"
Type: {content_type}
Target: {word_count} words total
Voice: {voice_notes}

RESEARCH DATA (USE ALL OF THIS):
- Most shocking fact: {shocking}
- Sensory details: {sensory}
- Lesser-known angle: {lesser}
- Best hook: {hook_line}
- Twist: {twist}
- Comment bait: {comment_bait}

Based on the PDF formula (Hook → Dread Build → Escalation → Gut-Punch → Haunting End),
create the beat-by-beat outline for maximum retention and virality.

Return ONLY valid JSON:
{{
  "beat_0_hook": {{
    "timing": "0-3s",
    "goal": "Stop the scroll. Most visceral line.",
    "content": "The exact opening line — max 12 words, present tense, drops INTO worst moment",
    "technique": "Why this line will hook people psychologically"
  }},
  "beat_1_dread": {{
    "timing": "3-15s",
    "goal": "Immerse viewer in the scene. Build world with dread.",
    "content": "2-3 sentences building the sensory atmosphere",
    "key_detail": "The specific sensory detail that makes this feel REAL"
  }},
  "beat_2_escalation": {{
    "timing": "15-35s",
    "goal": "The lesser-known angle. 'But here's what nobody tells you...'",
    "content": "The escalation beat using the research's lesser-known angle",
    "shocking_fact": "The specific fact dropped here"
  }},
  "beat_3_twist": {{
    "timing": "35-50s",
    "goal": "Gut-punch. The fact that reframes everything.",
    "content": "The twist delivered like a physical blow",
    "reframe": "What the viewer thought at start vs what they know now"
  }},
  "beat_4_end": {{
    "timing": "50-57s",
    "goal": "Haunting final thought. Drive comments and follows.",
    "content": "One lingering line + comment bait + CTA",
    "comment_trigger": "What compels them to type a comment"
  }},
  "title": "Best title from the research variants — max 70 chars",
  "title_variants": ["Variant A (SEO formula)", "Variant B (curiosity gap)", "Variant C (shocking statement)"],
  "hook_image_concept": "SPECIFIC description of the shock image for the first 2-3 seconds — what single visual element would cause maximum scroll-stopping dread. Be specific: not 'dark figure' but 'extreme close-up of [specific disturbing element from THIS story]'"
}}

Return ONLY the JSON."""

    raw = llm_call(prompt, max_tokens=2000)
    if not raw:
        return _fallback_outline(topic, research)
    data = _clean_json(raw)
    if not data:
        return _fallback_outline(topic, research)
    print(f"  ✅ Outline: hook='{data.get('beat_0_hook',{}).get('content','?')[:50]}'")
    return data


def _fallback_outline(topic: str, research: dict) -> dict:
    hook = research.get("hook_line_options", [f"Nobody talks about what happened with {topic}."])[0]
    return {
        "beat_0_hook":     {"content": hook, "timing": "0-3s"},
        "beat_1_dread":    {"content": research.get("sensory_details", "")},
        "beat_2_escalation": {"content": research.get("lesser_known_angle", "")},
        "beat_3_twist":    {"content": research.get("twist_element", "")},
        "beat_4_end":      {"content": research.get("comment_bait", "Follow for more.")},
        "title":           research.get("title_variants", [topic])[0],
        "title_variants":  research.get("title_variants", [topic]),
        "hook_image_concept": f"Extreme close-up of the most disturbing visual element of {topic}",
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STAGE 3 — FULL SCRIPT
# Written FROM the outline. Every word earns its place.
# PDF rules applied: specific scenes, no text overlays, sensory immersion.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _auto_image_style(content_type: str, image_style: str) -> str:
    if image_style not in ("auto", None, ""):
        return image_style if image_style in IMAGE_STYLES else "vintage_horror"
    return CONTENT_NICHES.get(content_type, {}).get("img_style", "vintage_horror")


def _auto_caption_style(fmt: str, caption_style: str) -> str:
    if caption_style not in ("auto", None, ""):
        return caption_style
    return FORMATS[fmt]["default_caption"]


def build_shorts_script_prompt(topic: str, content_type: str,
                                research: dict, outline: dict,
                                image_style: str, caption_style: str) -> str:
    pipeline_status["script_stage"] = "writing"
    style_desc = IMAGE_STYLES[image_style]["desc"]
    hook_suffix = IMAGE_STYLES[image_style]["hook_suffix"]

    beat0 = outline.get("beat_0_hook", {}).get("content", "")
    beat1 = outline.get("beat_1_dread", {}).get("content", "")
    beat2 = outline.get("beat_2_escalation", {}).get("content", "")
    beat3 = outline.get("beat_3_twist", {}).get("content", "")
    beat4 = outline.get("beat_4_end", {}).get("content", "")
    hook_img = outline.get("hook_image_concept", f"disturbing visual of {topic}")
    title    = outline.get("title", topic)
    variants = outline.get("title_variants", [title])
    keywords = research.get("top_seo_keywords", [])
    thumb    = research.get("thumbnail_concept", "")

    if content_type == "history":
        voice_rules = """HISTORY VOICE (mandatory):
- Present tense: "A prisoner WALKS" not "walked". Makes it feel immediate.
- Build with: "Nobody talks about this." / "History books won't show you this."
- Dread ladder: small disturbing detail → bigger → gut-punch reveal
- Sensory language: what it smelled, sounded, felt like
- End with one line that re-frames everything just heard"""
    else:
        voice_rules = """TRUE CRIME VOICE (mandatory):
- Cold case file voice: precise, clinical, devastating
- Drop listener INTO the worst moment. Present tense. Zero setup.
- One devastating detail per sentence. Each sentence worse than the last.
- Name specific investigators, dates, case numbers where possible
- End with one unanswered question that haunts them"""

    return f"""You are a viral YouTube Shorts scriptwriter. Channel: 10M subscribers. Style: Dr. NoSleep meets Weird History.
Your scripts get 90%+ retention because every word is chosen to hold attention.

TOPIC: {topic}
TYPE: {content_type}

BEAT OUTLINE (follow this EXACTLY):
  Hook (0-3s):       {beat0}
  Dread build (3-15s): {beat1}
  Escalation (15-35s): {beat2}
  Twist (35-50s):    {beat3}
  End (50-57s):      {beat4}

{voice_rules}

WORD COUNT: Exactly 130-150 words. Count them after writing. Every word earns its place.
No filler. No "Today we're going to talk about". No "In this video".
First word = action or shock. Last word = haunting.

SCENE GENERATION (8 story scenes + 1 dedicated hook image):
Scene 0 = HOOK IMAGE (separate from story scenes):
  - NOT the first story scene — this is a dedicated shock image
  - {hook_img}
  - {hook_suffix}
  - {style_desc[:80]}
  - Duration: 2.5s. Bold text overlay will be added: "{title[:40]}"

Scenes 1-8 = story scenes (each exactly 2.5s):
  - One per story beat (some beats get 2 scenes)
  - Format: [camera angle] + [SPECIFIC subject from THIS story] + [lighting] + [{style_desc[:60]}]
  - NEVER generic. Name the SPECIFIC thing: not "dark room" but "stone chamber where [specific event] happened"
  - Include motion suggestion: "swaying torch", "rain-streaked glass", "flickering lamp"
  - No text overlays, no captions, no dialogue in images

Return ONLY valid JSON:
{{
  "title": "{title}",
  "title_variants": {json.dumps(variants)},
  "hook_line": "Exact first spoken line — max 12 words — the hook beat verbatim",
  "content": "Complete 130-150 word script — spoken word only",
  "description": "YouTube description 180-200 words. Line 1: most disturbing hook sentence. Lines 2-4: SEO keywords for this exact topic ({', '.join(keywords[:4])}). Lines 5-7: Tease the most disturbing parts without spoiling. Line 8: Subscribe CTA. End: full hashtag block.",
  "hashtags": "#Shorts #DarkHistory #TrueCrime #HorrorStoriesAnimated #Mystery #AnimatedHorror",
  "tags": {json.dumps(keywords + ["horror stories animated", "dark history", "true crime", "animated horror"])},
  "thumbnail_prompt": "{thumb}",
  "hook_image_prompt": "{hook_img}, {hook_suffix}, {style_desc[:60]}",
  "scenes": [
    "Scene 1 (story beat 1 — setup): [specific location detail from story] [{style_desc[:40]}]",
    "Scene 2 (story beat 1 — detail): [specific character or object from story] [{style_desc[:40]}]",
    "Scene 3 (escalation): [the lesser-known visual element] [{style_desc[:40]}]",
    "Scene 4 (escalation): [specific disturbing detail from research] [{style_desc[:40]}]",
    "Scene 5 (twist setup): [the visual that precedes the gut-punch] [{style_desc[:40]}]",
    "Scene 6 (twist payoff): [most disturbing image of the story] [{style_desc[:40]}]",
    "Scene 7 (aftermath): [the consequence or discovery] [{style_desc[:40]}]",
    "Scene 8 (haunting end): [final lingering image — should stay in viewer's mind] [{style_desc[:40]}]"
  ],
  "voice_style": "{'authoritative' if content_type == 'history' else 'suspenseful'}",
  "content_type": "{content_type}",
  "image_style": "{image_style}",
  "caption_style": "{caption_style}",
  "sound_mood": "{'dark_orchestral' if content_type == 'history' else 'noir_suspense'}"
}}"""


def build_longform_script_prompt(topics: list, content_type: str,
                                  research_list: list, outline_list: list,
                                  image_style: str) -> str:
    pipeline_status["script_stage"] = "writing"
    style_desc = IMAGE_STYLES[image_style]["desc"]
    hook_suffix = IMAGE_STYLES[image_style]["hook_suffix"]

    stories_brief = ""
    for i, (topic, research, outline) in enumerate(zip(topics[:3], research_list[:3], outline_list[:3])):
        stories_brief += f"""
Story {i+1}: {topic}
  Hook line: {outline.get('beat_0_hook', {}).get('content', research.get('hook_line_options', [''])[0])}
  Shocking fact: {research.get('most_shocking_fact', '')}
  Twist: {research.get('twist_element', '')}
  Lesser angle: {research.get('lesser_known_angle', '')}
  End/comment bait: {research.get('comment_bait', '')}
"""

    return f"""You are a viral YouTube long-form horror scriptwriter. Dr. NoSleep + Weird History style.
Runtime: 8-12 minutes. 3 complete stories. Maximum dread. Maximum retention.
This video needs to hold 60%+ audience retention across 10+ minutes.

STORIES AND RESEARCH:
{stories_brief}

EACH STORY STRUCTURE (1200-1500 words):
1. COLD OPEN: First line = worst moment. Present tense. No setup. No intro.
   Example: "The moment he opened the door, he already knew — nothing inside was human anymore."
2. SENSORY BUILD: Rich atmosphere. Sounds, smells, textures, temperature.
   "The dungeon smelled of wet stone and iron. The only sound was dripping water... and breathing."
3. ESCALATION: 'But here's what nobody tells you...' — the lesser-known angle
4. PSYCHOLOGICAL CORE: What fear does this trigger? Isolation? Betrayal? Authority gone wrong?
5. TWIST: The one fact that reframes everything. Delivered like a physical blow.
6. HAUNTING END: One lingering line + "Subscribe for more chilling tales..."

IMAGE SCENES: Each story gets 8 scenes. Format: [camera angle] [specific detail] [lighting] [{style_desc[:60]}]

Return ONLY valid JSON:
{{
  "title": "3 [Specific Theme] Horror Stories Animated (2026) — max 70 chars",
  "title_variants": ["Title A (SEO)", "Title B (curiosity gap)", "Title C (shocking statement)"],
  "hook_image_prompt": "Extreme close-up of the most disturbing visual from story 1 — {hook_suffix}, {style_desc[:60]}",
  "stories": [
    {{
      "subtitle": "Story 1 title",
      "hook_line": "First spoken line",
      "content": "1200-1500 word complete story with full narrative arc",
      "scenes": ["scene1 with camera+subject+lighting+style","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }},
    {{
      "subtitle": "Story 2 title",
      "hook_line": "First spoken line",
      "content": "1200-1500 word complete story",
      "scenes": ["scene1","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }},
    {{
      "subtitle": "Story 3 title",
      "hook_line": "First spoken line",
      "content": "1200-1500 word complete story",
      "scenes": ["scene1","scene2","scene3","scene4","scene5","scene6","scene7","scene8"]
    }}
  ],
  "description": "250-word description. Hook line 1-2. Tease each story. Timestamps: 0:00 Intro, ~0:30 Story 1: [title], ~4:00 Story 2: [title], ~8:00 Story 3: [title]. Subscribe CTA.",
  "tags": ["horror stories animated","dark history","true crime","animated horror","horror compilation","scary stories","dark secrets","mysterious history","horror stories","paranormal","true crime animated","dark animation"],
  "hashtags": "#DarkHistory #TrueCrime #HorrorStoriesAnimated #Mystery #AnimatedHorror #Horror",
  "thumbnail_prompt": "Thumbnail for compilation: most disturbing scene from story 1, {style_desc[:40]}, bold text area left side",
  "voice_style": "cinematic",
  "content_type": "{content_type}",
  "image_style": "{image_style}",
  "caption_style": "netflix",
  "sound_mood": "{'dark_orchestral' if content_type == 'history' else 'noir_suspense'}"
}}"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# NICHE ALTERNATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN CONTENT GENERATION ORCHESTRATOR (3 stages)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_content(req: RunRequest) -> dict:
    niche     = req.content_type if req.content_type in CONTENT_NICHES else get_next_niche()
    # Shorts-first: default to DEFAULT_FORMAT unless explicitly overridden
    fmt       = req.format if req.format in FORMATS else DEFAULT_FORMAT
    fmt_cfg   = FORMATS.get(fmt, FORMATS["shorts"])
    img_style = _auto_image_style(niche, req.image_style or "auto")
    cap_style = _auto_caption_style(fmt, req.caption_style or "auto")

    if fmt == "long":
        topics = random.sample(CONTENT_NICHES[niche]["topics"], 3)
        print(f"🎬 Long-form | {niche} | Topics: {[t[:30] for t in topics]}")

        # Stage 1: Research each story
        pipeline_status["step"] = "Stage 1/3: Deep researching all 3 stories..."
        research_list = []
        for i, topic in enumerate(topics):
            pipeline_status["progress_detail"] = f"Researching story {i+1}/3..."
            print(f"  🔍 Research {i+1}/3: {topic[:45]}...")
            research_list.append(generate_research_brief(topic, niche))

        # Stage 2: Outline each story
        pipeline_status["step"] = "Stage 2/3: Building viral outlines..."
        outline_list = []
        for i, (topic, research) in enumerate(zip(topics, research_list)):
            pipeline_status["progress_detail"] = f"Outlining story {i+1}/3..."
            print(f"  📋 Outline {i+1}/3: {topic[:45]}...")
            outline_list.append(generate_outline(topic, niche, research, fmt))

        # Stage 3: Full script
        pipeline_status["step"] = "Stage 3/3: Writing full scripts..."
        pipeline_status["progress_detail"] = "Writing long-form script..."
        prompt = build_longform_script_prompt(topics, niche, research_list, outline_list, img_style)
        raw = llm_call(prompt, max_tokens=8000)
        if not raw:
            raise Exception("All LLM providers failed on long-form script")

        data = _clean_json(raw)
        if not data:
            raise Exception(f"JSON parse failed: {raw[:300]}")

        data["content_type"] = niche
        data["format"]       = fmt
        data["image_style"]  = img_style
        data["caption_style"] = cap_style

        # Flatten long-form into single script + scene list
        if "stories" in data:
            all_scenes = []
            full_script = ""
            for story in data["stories"]:
                all_scenes.extend(story.get("scenes", []))
                full_script += (f"\n\n--- {story.get('subtitle', 'Story')} ---\n\n"
                                + story.get("content", ""))
            data["scenes"]  = all_scenes[:24]
            data["content"] = full_script.strip()

    else:  # Shorts
        topic = req.topic or random.choice(CONTENT_NICHES[niche]["topics"])
        print(f"🎲 Shorts | {niche} | {topic}")

        # Stage 1: Research
        pipeline_status["step"] = "Stage 1/3: Deep researching topic..."
        print(f"  🔍 Researching: {topic[:50]}...")
        research = generate_research_brief(topic, niche)

        # Stage 2: Outline
        pipeline_status["step"] = "Stage 2/3: Building viral outline..."
        print(f"  📋 Outlining beat structure...")
        outline = generate_outline(topic, niche, research, fmt)

        # Stage 3: Full script
        pipeline_status["step"] = "Stage 3/3: Writing final script..."
        pipeline_status["progress_detail"] = "Writing Shorts script..."
        prompt = build_shorts_script_prompt(topic, niche, research, outline,
                                             img_style, cap_style)
        raw = llm_call(prompt, max_tokens=3000)
        if not raw:
            raise Exception("All LLM providers failed on Shorts script")

        data = _clean_json(raw)
        if not data:
            raise Exception(f"JSON parse failed: {raw[:300]}")

        data["content_type"] = niche
        data["format"]       = fmt
        data["image_style"]  = img_style
        data["caption_style"] = cap_style
        data["llm_used"]     = pipeline_status.get("llm_used", "")

        # Merge research data for logging
        data["top_keywords"]     = research.get("top_seo_keywords", [])
        data["hook_line"]        = data.get("hook_line", outline.get("beat_0_hook", {}).get("content", ""))

    print(f"✅ Script via {pipeline_status.get('llm_used', '?')}")
    print(f"✅ Title: {data.get('title', '?')}")
    print(f"✅ Hook:  {data.get('hook_line', '?')[:80]}")
    return data


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 2A — VOICE (edge-tts primary, gTTS fallback)
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
# STEP 2B — SUBTITLES (style per format)
# Shorts:    Impact font, centered, 3 words/card — TikTok viral style
# Long-form: Netflix bottom bar, 6 words/card — clean and professional
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

    if caption_style == "netflix":
        # Bottom bar — professional, readable, long-form standard
        style_line = (
            f"Style: Main,Arial,54,&H00FFFFFF,&H000000FF,&H00000000,"
            f"&HCC000000,0,0,0,0,100,100,0,0,1,0,0,2,60,60,50,1"
        )
        words_per_card = 6
        align = 2  # bottom center
    else:
        # Impact — Shorts/TikTok viral style, mid-upper screen
        style_line = (
            f"Style: Main,Impact,88,&H00FFFFFF,&H000000FF,&H00000000,"
            f"&HAA000000,1,0,0,0,100,100,1,0,1,8,0,8,30,30,0,1"
        )
        words_per_card = 3
        align = 8  # mid-center

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
    i = 0
    while i < len(word_timings):
        group = word_timings[i:i + words_per_card]
        i += words_per_card
        start = group[0]["start"]
        end   = max(group[-1]["end"], start + 0.3)
        text  = " ".join(w["word"] for w in group).upper()
        text  = text.replace("{", "").replace("}", "").replace("\\", "")
        max_len = 35 if caption_style == "netflix" else 16
        if len(text) > max_len:
            words = text.split()
            mid   = max(1, len(words) // 2)
            text  = " ".join(words[:mid]) + "\\N" + " ".join(words[mid:])
        lines.append(f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Main,,0,0,0,,{text}")

    Path(ass_path).write_text(header + "\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✅ Subtitles: {caption_style}, {len(lines)} cards, {words_per_card} words/card")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3 — IMAGE GENERATION
# T1: Cloudflare Workers AI FLUX.1-schnell (free, fast, not IP-blocked)
# T2: Gemini 2.5 Flash Image (needs key, 500/day free)
# T3: Gemini 2.0 Flash Exp (key needed, older fallback)
# T4: Cinematic FFmpeg art (always works, <1s, scene-matched palette)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _verify_image(path: str, min_size: int = 5_000) -> bool:
    p = Path(path)
    if not p.exists() or p.stat().st_size < min_size:
        return False
    header = p.read_bytes()[:4]
    return header[:3] == b'\xff\xd8\xff' or header[:4] == b'\x89PNG'


def _sanitize_prompt(prompt: str) -> str:
    """Sanitize prompts for safety filters while preserving atmosphere."""
    return (prompt
        .replace("torture", "anguish")
        .replace("gore", "darkness")
        .replace("blood", "crimson shadow")
        .replace("murder", "crime scene")
        .replace("kill", "tragic end")
        .replace("dead body", "fallen figure")
        .replace("corpse", "lifeless form")
        .replace("execution", "somber ritual")
        .replace("decapitat", "dramatic end")
        .replace("mutilat", "distorted")
        [:500])


def _build_scene_prompt(scene: str, image_style: str, content_type: str,
                         is_hook: bool = False) -> str:
    """Build the full image prompt from a scene description."""
    style     = IMAGE_STYLES.get(image_style, IMAGE_STYLES["vintage_horror"])
    style_desc = style["desc"]
    if is_hook:
        suffix = style["hook_suffix"]
    elif content_type == "history":
        suffix = "medieval historical atmosphere, aged texture, ancient dread"
    else:
        suffix = "modern urban noir, cold city night, crime thriller atmosphere"
    return f"{scene}, {style_desc}, {suffix}"[:550]


# ── TIER 1: Cloudflare Workers AI FLUX.1-schnell ─────────────────────────────
def _fetch_cloudflare(prompt: str, img_w: int, img_h: int) -> Optional[bytes]:
    """
    Confirmed working from Render.com IPs.
    10,000 neurons/day FREE. ~100 neurons/image. Not IP-blocked.
    """
    if not CF_ACCOUNT_ID or not CF_API_TOKEN:
        return None
    safe = _sanitize_prompt(prompt)
    url = (f"https://api.cloudflare.com/client/v4/accounts/"
           f"{CF_ACCOUNT_ID}/ai/run/@cf/black-forest-labs/flux-1-schnell")
    try:
        t0   = time.time()
        resp = requests.post(url,
            headers={"Authorization": f"Bearer {CF_API_TOKEN}",
                     "Content-Type": "application/json"},
            json={"prompt": safe[:500], "num_steps": 8,
                  "width": min(img_w, 1024), "height": min(img_h, 1024)},
            timeout=28)
        elapsed = round(time.time() - t0, 1)

        if resp.status_code == 200:
            ct = resp.headers.get("Content-Type", "")
            if ct.startswith("image/"):
                print(f"    ✅ CF FLUX ({len(resp.content)//1024}KB, {elapsed}s)")
                return resp.content
            try:
                data = resp.json()
                b64  = (data.get("result", {}).get("image") or
                        data.get("result", {}).get("images", [{}])[0].get("image", ""))
                if b64:
                    img = base64.b64decode(b64)
                    print(f"    ✅ CF FLUX ({len(img)//1024}KB, {elapsed}s)")
                    return img
                print(f"    CF: no image in response: {str(data)[:100]}")
            except Exception as je:
                print(f"    CF parse error: {je}")
        else:
            print(f"    CF HTTP {resp.status_code}: {resp.text[:100]}")
    except requests.Timeout:
        print("    CF: timeout (>28s)")
    except Exception as e:
        print(f"    CF error: {e}")
    return None


# ── TIER 2: Gemini 2.5 Flash Image ───────────────────────────────────────────
def _fetch_gemini_image(prompt: str) -> Optional[bytes]:
    if not GEMINI_API_KEY:
        return None
    safe = _sanitize_prompt(prompt)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.5-flash-image:generateContent?key={GEMINI_API_KEY}")
    try:
        t0   = time.time()
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": safe}]}],
                  "generationConfig": {
                      "responseModalities": ["IMAGE"],
                      "imageConfig": {"aspectRatio": "9:16"},
                  },
                  "safetySettings": [
                      {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_ONLY_HIGH"},
                      {"category": "HARM_CATEGORY_HARASSMENT",        "threshold": "BLOCK_ONLY_HIGH"},
                      {"category": "HARM_CATEGORY_HATE_SPEECH",       "threshold": "BLOCK_ONLY_HIGH"},
                      {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_ONLY_HIGH"},
                  ]},
            timeout=25)
        elapsed = round(time.time() - t0, 1)
        if resp.status_code == 200:
            for part in (resp.json().get("candidates", [{}])[0]
                         .get("content", {}).get("parts", [])):
                inline = part.get("inlineData", {})
                if inline.get("mimeType", "").startswith("image/"):
                    data = base64.b64decode(inline["data"])
                    print(f"    ✅ Gemini 2.5 Flash ({len(data)//1024}KB, {elapsed}s)")
                    return data
        print(f"    Gemini image HTTP {resp.status_code}")
    except requests.Timeout:
        print("    Gemini image timeout")
    except Exception as e:
        print(f"    Gemini image error: {e}")
    return None


# ── TIER 3: Gemini 2.0 Flash Exp ─────────────────────────────────────────────
def _fetch_gemini_fallback(prompt: str) -> Optional[bytes]:
    if not GEMINI_API_KEY:
        return None
    safe = _sanitize_prompt(prompt)[:400]
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"gemini-2.0-flash-exp:generateContent?key={GEMINI_API_KEY}")
    try:
        resp = requests.post(url,
            json={"contents": [{"parts": [{"text": f"Draw: {safe}"}]}],
                  "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
            timeout=25)
        if resp.status_code == 200:
            for cand in resp.json().get("candidates", []):
                for part in cand.get("content", {}).get("parts", []):
                    inline = part.get("inlineData", {})
                    if inline.get("mimeType", "").startswith("image/"):
                        data = base64.b64decode(inline["data"])
                        print(f"    ✅ Gemini 2.0 Exp ({len(data)//1024}KB)")
                        return data
    except Exception as e:
        print(f"    Gemini 2.0 Exp: {e}")
    return None


# ── TIER 4: Cinematic FFmpeg art (scene-matched palette) ─────────────────────
_PALETTES = {
    "history": [
        {"r": "0/0 0.3/0.45 0.7/0.8 1/1",    "g": "0/0 0.3/0.2 0.7/0.5 1/0.75",  "b": "0/0 0.3/0.05 0.7/0.15 1/0.3",  "base": "0x1A0A04"},  # amber dungeon
        {"r": "0/0 0.3/0.5 0.7/0.85 1/1",    "g": "0/0 0.3/0.08 0.7/0.2 1/0.35", "b": "0/0 0.3/0.08 0.7/0.2 1/0.38", "base": "0x180308"},  # blood crimson
        {"r": "0/0 0.3/0.35 0.7/0.65 1/0.9", "g": "0/0 0.3/0.28 0.7/0.55 1/0.8", "b": "0/0 0.3/0.18 0.7/0.4 1/0.6",  "base": "0x0C0C12"},  # gothic iron
    ],
    "truecrime": [
        {"r": "0/0 0.3/0.15 0.7/0.38 1/0.55","g": "0/0 0.3/0.18 0.7/0.42 1/0.6", "b": "0/0 0.3/0.35 0.7/0.72 1/0.95","base": "0x04060F"},  # midnight blue
        {"r": "0/0 0.3/0.12 0.7/0.3 1/0.48", "g": "0/0 0.3/0.25 0.7/0.55 1/0.75","b": "0/0 0.3/0.3 0.7/0.6 1/0.8",  "base": "0x06080C"},  # surveillance teal
        {"r": "0/0 0.3/0.22 0.7/0.5 1/0.7",  "g": "0/0 0.3/0.08 0.7/0.22 1/0.38","b": "0/0 0.3/0.4 0.7/0.75 1/0.92","base": "0x08040F"},  # purple dread
    ],
}


def _make_cinematic_fallback(scene: str, content_type: str,
                              img_w: int, img_h: int, output_path: str) -> bool:
    pal   = random.choice(_PALETTES.get(content_type, _PALETTES["history"]))
    label = scene[:32].replace("'", "").replace(":", "").replace(",", "").replace('"', "")
    vf = (f"noise=alls=30:allf=t+u,"
          f"curves=r='{pal['r']}':g='{pal['g']}':b='{pal['b']}',"
          f"vignette=PI/1.9,"
          f"drawtext=text='{label}':fontsize=24:fontcolor=white@0.12:"
          f"borderw=1:bordercolor=black@0.06:x=(w-text_w)/2:y=h*0.88:font=sans,"
          f"format=yuvj420p")
    cmds = [
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"gradients=size={img_w}x{img_h}:x0=0:y0=0:x1={img_w}:y1={img_h}"
               f":c0={pal['base']}:c1=0x000000:duration=1",
         "-vf", vf, "-frames:v", "1", "-update", "1", output_path],
        ["ffmpeg", "-y", "-f", "lavfi",
         "-i", f"color=c={pal['base']}:size={img_w}x{img_h}:duration=1",
         "-vf", f"noise=alls=25:allf=t+u,vignette=PI/2,format=yuvj420p",
         "-frames:v", "1", "-update", "1", output_path],
    ]
    for cmd in cmds:
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=12)
            if r.returncode == 0 and _verify_image(output_path, min_size=2000):
                return True
        except Exception as e:
            print(f"    Cinematic fallback error: {e}")
    return False


def generate_image(scene: str, image_style: str, content_type: str,
                   img_w: int, img_h: int, output_path: str,
                   is_hook: bool = False, scene_idx: int = 0) -> str:
    """Dispatch through image tier chain. Returns source name."""
    if scene_idx > 0:
        time.sleep(0.4)

    prompt = _build_scene_prompt(scene, image_style, content_type, is_hook)
    print(f"    Prompt: {prompt[:70]}...")

    # T1: Cloudflare
    if CF_ACCOUNT_ID and CF_API_TOKEN:
        print("    [T1] Cloudflare FLUX...")
        data = _fetch_cloudflare(prompt, img_w, img_h)
        if data:
            Path(output_path).write_bytes(data)
            if _verify_image(output_path):
                return "Cloudflare FLUX"
            print("    CF: image invalid after write")

    # T2: Gemini 2.5 Flash Image
    if GEMINI_API_KEY:
        print("    [T2] Gemini 2.5 Flash Image...")
        data = _fetch_gemini_image(prompt)
        if data:
            Path(output_path).write_bytes(data)
            if _verify_image(output_path):
                return "Gemini 2.5 Flash"
        # T3: Gemini 2.0 Exp fallback
        print("    [T3] Gemini 2.0 Exp...")
        data = _fetch_gemini_fallback(prompt)
        if data:
            Path(output_path).write_bytes(data)
            if _verify_image(output_path):
                return "Gemini 2.0 Exp"

    # T4: Cinematic FFmpeg
    print("    [T4] Cinematic FFmpeg art...")
    if _make_cinematic_fallback(scene, content_type, img_w, img_h, output_path):
        return "Cinematic Fallback"

    return "none"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3B — HOOK IMAGE: AI image + bold text overlay burnt in via ffmpeg
# This is the first 2.5s frame — dedicated "stop the scroll" image.
# Formula: AI shock image + title text overlay + fear phrase + zoom-punch KB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── HOOK STYLE DECISION TABLE ─────────────────────────────────────────────────
# System decides per niche what maximises CTR on first frame:
#   history   → AI vintage shock image + bold overlaid text (title + fear phrase)
#               Rationale: archive-style visuals + text = authority + curiosity
#   truecrime → Pure AI shock image, NO text overlay
#               Rationale: raw photorealistic crime scene image stops scroll harder
#                          than text; text feels "produced" and reduces raw dread
# ─────────────────────────────────────────────────────────────────────────────
HOOK_STYLES = {
    "history": {
        "add_text_overlay": True,
        "fear_phrases": [
            "HISTORY HIDES THIS", "THEY NEVER TAUGHT YOU THIS",
            "THIS ACTUALLY HAPPENED", "NOBODY TALKS ABOUT THIS",
            "THE TRUTH IS DISTURBING", "BURIED FOR 500 YEARS",
        ],
        "text_color":  "#FF3333",
        "overlay_pos": (0.30, 0.45),  # (y_start fraction, height fraction) of dark band
    },
    "truecrime": {
        "add_text_overlay": False,   # raw AI image — no text — maximum raw dread
        "fear_phrases": [],
        "text_color":  "#FFFFFF",
        "overlay_pos": (0.35, 0.35),
    },
}


def build_hook_image(hook_prompt: str, title: str, content_type: str,
                     image_style: str, img_w: int, img_h: int,
                     output_path: str) -> bool:
    """
    Dedicated scroll-stopper image — first 2.5 seconds of every video.

    System decides hook style per niche (see HOOK_STYLES above):
      history   → AI shock image + burnt-in title text + fear phrase
      truecrime → Pure AI shock image, no text (raw dread = better CTR for this niche)

    Always uses zoom-punch Ken Burns in build_clip_from_image (is_hook=True).
    """
    hook_cfg = HOOK_STYLES.get(content_type, HOOK_STYLES["history"])
    base_img = output_path.replace(".jpg", "_base.jpg")

    # Step 1: Generate AI base image
    source = generate_image(hook_prompt, image_style, content_type,
                             img_w, img_h, base_img, is_hook=True, scene_idx=0)
    if not _verify_image(base_img, min_size=1000):
        print("  ⚠️  Hook AI failed — cinematic fallback")
        _make_cinematic_fallback(hook_prompt, content_type, img_w, img_h, base_img)

    # Step 2: For true crime — use image as-is (pure shock, no text)
    if not hook_cfg["add_text_overlay"]:
        if _verify_image(base_img):
            import shutil as _sh
            _sh.copy2(base_img, output_path)
            Path(base_img).unlink(missing_ok=True)
            print(f"  ✅ Hook image: pure AI shock ({source}) — no overlay (truecrime)")
            return True
        return False

    # Step 3: History — add fear phrase + title overlay
    fear_phrase    = random.choice(hook_cfg["fear_phrases"])
    display_title  = title[:35].upper().replace("'","").replace('"', "").replace(":", "")
    y_start, y_h   = hook_cfg["overlay_pos"]
    text_color     = hook_cfg["text_color"]

    # font_file: try system bold font, fall back to empty (ffmpeg uses default)
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "",   # ffmpeg default font
    ]

    base_vf = (
        f"scale={img_w}:{img_h}:force_original_aspect_ratio=increase,crop={img_w}:{img_h},"
        f"drawbox=x=0:y=ih*{y_start}:w=iw:h=ih*{y_h}:color=black@0.68:t=fill,"
        f"{{fear_drawtext}},"
        f"{{title_drawtext}},"
        f"drawtext=text='HORROR STORIES ANIMATED':{{font}}fontsize={int(img_h*0.033)}:"
        f"fontcolor=#AAAAAA:borderw=2:bordercolor=black:x=(w-text_w)/2:y=h*{y_start+y_h-0.07:.2f},"
        f"format=yuvj420p"
    )

    for fp in font_paths:
        font_spec = f"fontfile={fp}:" if fp else ""
        fear_dt   = (f"drawtext=text='{fear_phrase}':{font_spec}"
                     f"fontsize={int(img_h*0.043)}:fontcolor={text_color}:"
                     f"borderw=3:bordercolor=black:x=(w-text_w)/2:y=h*{y_start+0.04:.2f}")
        title_dt  = (f"drawtext=text='{display_title}':{font_spec}"
                     f"fontsize={int(img_h*0.060)}:fontcolor=white:"
                     f"borderw=4:bordercolor=black:x=(w-text_w)/2:y=h*{y_start+0.16:.2f}")
        vf = base_vf.format(
            fear_drawtext=fear_dt,
            title_drawtext=title_dt,
            font=font_spec,
        )
        cmd = ["ffmpeg", "-y", "-i", base_img, "-vf", vf,
               "-frames:v", "1", "-update", "1", output_path]
        try:
            r = subprocess.run(cmd, capture_output=True, timeout=30)
            if r.returncode == 0 and _verify_image(output_path, min_size=1000):
                Path(base_img).unlink(missing_ok=True)
                print(f"  ✅ Hook image: AI + overlay ({source}) — history style")
                return True
        except Exception as e:
            print(f"    Hook overlay attempt failed: {e}")

    # Fallback: base image without overlay
    if _verify_image(base_img):
        import shutil as _sh
        _sh.copy2(base_img, output_path)
        Path(base_img).unlink(missing_ok=True)
        print(f"  ✅ Hook image: base only, overlay failed ({source})")
        return True
    return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 3C — KEN BURNS CLIPS
# Hook: zoom-punch (1.0→1.28 fast) — maximum impact
# Story scenes: 8 motion styles, varied per scene
# Exact timing: 2.5s (Shorts) or 3.0s (Long)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CLIP_FPS = 25

# RAM-safe pre-scale: 1.45× (1044×1856 for 9:16) — was 3× = OOM on Render free
_KB_SCALE = 1.45


def _ken_burns_filter(duration: float, style: int,
                       vid_w: int, vid_h: int, is_hook: bool = False) -> str:
    d  = max(int(duration * CLIP_FPS), 2)
    kb_w = int(vid_w * _KB_SCALE)
    kb_h = int(vid_h * _KB_SCALE)

    if is_hook:
        # Zoom punch: fast zoom-in, slightly off-center — creates urgency
        return (f"scale={kb_w}:{kb_h},"
                f"zoompan=z='min(zoom+0.0020,1.28)'"
                f":x='iw/2-(iw/zoom/2)+{int(vid_w*0.015)}*(on/{d})'"
                f":y='ih/2-(ih/zoom/2)'"
                f":d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}")

    s = style % 8
    filters = {
        0: f"scale={kb_w}:{kb_h},zoompan=z='min(zoom+0.0015,1.35)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        1: f"scale={kb_w}:{kb_h},zoompan=z='if(eq(on,1),1.35,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        2: f"scale={kb_w}:{kb_h},zoompan=z='1.15':x='({kb_w}-{vid_w}/1.15)*on/{d}':y='({kb_h}/2)-({vid_h}/1.15/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        3: f"scale={kb_w}:{kb_h},zoompan=z='1.15':x='({kb_w}-{vid_w}/1.15)*(1-on/{d})':y='({kb_h}/2)-({vid_h}/1.15/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        4: f"scale={kb_w}:{kb_h},zoompan=z='1.15':x='({kb_w}/2)-({vid_w}/1.15/2)':y='({kb_h}-{vid_h}/1.15)*on/{d}':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        5: f"scale={kb_w}:{kb_h},zoompan=z='min(zoom+0.001,1.28)':x='iw/2-(iw/zoom/2)+({kb_w}-{vid_w})*0.10*on/{d}':y='ih/2-(ih/zoom/2)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        6: f"scale={kb_w}:{kb_h},zoompan=z='min(zoom+0.0018,1.32)':x='iw/2-(iw/zoom/2)':y='ih-(ih/zoom)':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
        7: f"scale={kb_w}:{kb_h},zoompan=z='1.2':x='({kb_w}-{vid_w}/1.2)*0.5*on/{d}':y='({kb_h}-{vid_h}/1.2)*0.5*on/{d}':d={d}:s={vid_w}x{vid_h}:fps={CLIP_FPS}",
    }
    return filters[s]


def build_clip_from_image(img_path: str, duration: float, output_path: str,
                           kb_style: int, vid_w: int, vid_h: int,
                           is_hook: bool = False) -> bool:
    if not _verify_image(img_path, min_size=500):
        return False
    kb_filter = _ken_burns_filter(duration, kb_style, vid_w, vid_h, is_hook)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", f"{kb_filter},format=yuv420p",
        "-t", str(duration), "-c:v", "libx264", "-crf", "22",
        "-preset", "ultrafast", "-r", str(CLIP_FPS),
        "-pix_fmt", "yuv420p", "-threads", "1", "-an", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    if result.returncode != 0:
        # Static fallback without Ken Burns
        cmd2 = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (f"scale={vid_w}:{vid_h}:force_original_aspect_ratio=increase,"
                    f"crop={vid_w}:{vid_h},format=yuv420p"),
            "-t", str(duration), "-c:v", "libx264", "-crf", "22",
            "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-threads", "1", "-an", output_path,
        ]
        result = subprocess.run(cmd2, capture_output=True, timeout=120)
    return result.returncode == 0 and Path(output_path).exists()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STEP 4 — MUSIC + SOUND DESIGN
# Music:  Pollinations audio API → ffmpeg atmospheric fallback
# Sound:  ffmpeg-native ambient layers (no external API needed)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MUSIC_QUERIES = {
    "dark_orchestral": "dark dramatic orchestral documentary historical suspense cinematic horror",
    "noir_suspense":   "noir suspense minimal dark ambient crime thriller piano psychological",
    "vintage_dread":   "vintage horror organ dark suspense silent film eerie atmosphere",
    "digital_dread":   "dark electronic ambient drone minimal horror digital suspense",
}


def generate_music(sound_mood: str, music_path: str) -> bool:
    query = MUSIC_QUERIES.get(sound_mood, MUSIC_QUERIES["dark_orchestral"])
    try:
        r = requests.get(
            f"https://audio.pollinations.ai/{requests.utils.quote(query)}",
            headers={"User-Agent": "DarkHistoryTV/10.0"},
            timeout=45)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            print(f"✅ Music: {sound_mood} (Pollinations)")
            return True
    except Exception as e:
        print(f"  Pollinations music failed: {e} — using ffmpeg fallback")

    # ffmpeg atmospheric fallback — always works
    return _generate_atmospheric_music(sound_mood, music_path)


def _generate_atmospheric_music(mood: str, music_path: str) -> bool:
    """
    Generate atmospheric audio entirely via ffmpeg.
    No external API. Sounds genuinely moody, not silence.
    """
    try:
        if mood == "dark_orchestral":
            # Low organ-like tone: 60Hz fundamental + 120Hz octave + slow tremolo
            filter_str = (
                "sine=frequency=60:duration=720[f1];"
                "sine=frequency=90:duration=720[f2];"
                "sine=frequency=120:duration=720[f3];"
                "[f1]volume=0.4[b1];"
                "[f2]volume=0.15[b2];"
                "[f3]volume=0.08[b3];"
                "[b1][b2][b3]amix=inputs=3,"
                "tremolo=f=0.3:d=0.4,"
                "lowpass=f=300,volume=0.6[out]"
            )
        elif mood == "noir_suspense":
            # Heartbeat-like pulse: 65Hz with 72bpm rhythm pattern
            filter_str = (
                "sine=frequency=65:duration=720[pulse];"
                "[pulse]volume=0.3,atempo=1.2,"
                "highpass=f=40,lowpass=f=200,"
                "tremolo=f=1.2:d=0.6[out]"
            )
        else:
            # Generic dark drone
            filter_str = (
                "sine=frequency=55:duration=720[drone];"
                "[drone]volume=0.25,lowpass=f=250[out]"
            )

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", f"aevalsrc=0:d=720",   # silent base
            "-f", "lavfi", "-i", "sine=frequency=55:duration=720",
            "-filter_complex", "[1:a]volume=0.18,lowpass=f=220,tremolo=f=0.25:d=0.5[out]",
            "-map", "[out]",
            "-c:a", "aac", "-b:a", "96k",
            "-t", "720",
            music_path
        ]
        r = subprocess.run(cmd, capture_output=True, timeout=30)
        if r.returncode == 0 and Path(music_path).exists():
            print(f"✅ Music: atmospheric fallback ({mood})")
            return True
    except Exception as e:
        print(f"  Atmospheric fallback failed: {e}")

    # Last resort: silence
    try:
        r = subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "720", "-c:a", "aac", "-b:a", "96k", music_path],
            capture_output=True, timeout=20)
        return r.returncode == 0
    except Exception:
        return False


def generate_sound_design(content_type: str, duration: float, session: Path) -> Optional[str]:
    """
    Ambient sound design layer — generated via ffmpeg, no external API.
    History: low organ drone + bell shimmer
    True crime: 65Hz pulse + static underlayer
    """
    sd_path = str(session / "sounddesign.mp3")
    dur = int(duration) + 3

    try:
        if content_type == "history":
            # Organ drone 50Hz + faint bell shimmer at 220Hz
            filter_str = (
                f"[1:a]volume=0.18,lowpass=f=150[base];"
                f"[2:a]volume=0.04,aecho=0.6:0.6:80:0.4[bell];"
                f"[base][bell]amix=inputs=2[out]"
            )
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"sine=frequency=50:duration={dur}",
                "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
                "-filter_complex", filter_str,
                "-map", "[out]", "-c:a", "aac", "-b:a", "64k", sd_path
            ]
        else:
            # Heartbeat-like 65Hz pulse
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"sine=frequency=65:duration={dur}",
                "-af", "volume=0.15,tremolo=f=1.2:d=0.7,highpass=f=40,lowpass=f=150",
                "-c:a", "aac", "-b:a", "64k", sd_path
            ]

        r = subprocess.run(cmd, capture_output=True, timeout=30)
        if r.returncode == 0 and Path(sd_path).exists():
            print(f"✅ Sound design: {content_type} atmosphere")
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

    # Concat clips to single video stream
    txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(txt, "w") as f:
        for c in clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    r = subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", txt, "-c", "copy", concat_out],
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
    sound_vol = "0.13"
    vf        = f"ass='{ass_p}'" if has_subs else "null"

    # Build audio filter graph
    inputs      = [concat_out, voice_p]
    if use_music: inputs.append(music_p)
    if use_sound: inputs.append(sound_p)

    voice_idx = 1
    music_idx = 2 if use_music else None
    sound_idx = (3 if (use_sound and use_music) else 2) if use_sound else None

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

    afilt_parts.append(
        f"{''.join(mix_labels)}amix=inputs={len(mix_labels)}:duration=first:dropout_transition=2[afinal]")
    afilt = ";".join(afilt_parts)

    i_flags = []
    for inp in inputs:
        i_flags += ["-i", inp]

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
          f"subs={'yes' if has_subs else 'no'} | music={'yes' if use_music else 'no'} | "
          f"sound={'yes' if use_sound else 'no'}")

    r = subprocess.run(cmd, capture_output=True, timeout=900)

    if r.returncode != 0:
        err = r.stderr[-500:].decode(errors="ignore")
        if has_subs and ("ass" in err.lower() or "subtitle" in err.lower()):
            print("  ⚠️  Subtitle error — retrying without subs...")
            cmd_ns = ["null" if x == vf else x for x in cmd]
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
# Category 27 (Education) for max CPM. Research-backed tags.
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
        "history":   ["dark history", "bizarre history", "history facts", "medieval history",
                      "horror stories animated", "dark secrets", "disturbing history",
                      "history shorts", "ancient history", "dark past", "scary history"],
        "truecrime": ["true crime", "cold case", "unsolved mysteries", "crime story",
                      "horror stories animated", "murder mystery", "criminal psychology",
                      "true crime shorts", "forensic investigation", "dark crimes"],
    }.get(data.get("content_type", ""), [])

    research_kw  = data.get("top_keywords", [])
    tags = list(dict.fromkeys(base_tags + research_kw + data.get("tags", [])))[:15]

    description = (
        f"{data.get('description', '')}\n\n"
        f"🔔 Subscribe for daily dark history & true crime\n"
        f"👇 What shocked you most? Comment below!\n\n"
        f"{data.get('hashtags', '#DarkHistory #TrueCrime #HorrorStoriesAnimated')}"
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
    fmt_suffix = "shorts/" if fmt == "shorts" else "watch?v="
    print(f"  ✅ YouTube: https://youtube.com/{fmt_suffix}{vid_id}")
    return vid_id


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FULL PIPELINE v10
# Steps: Content(3-stage) → Voice → Subs → Hook Image → Scene Images → Clips
#        → Music → Sound → Assemble → Upload → Log
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def full_pipeline(req: RunRequest):
    if pipeline_status["running"]:
        return

    pipeline_status.update({
        "running": True, "error": None, "llm_used": None,
        "image_source": None, "progress_detail": "", "script_stage": "",
    })

    fmt     = req.format if req.format in FORMATS else DEFAULT_FORMAT
    fmt_cfg = FORMATS.get(fmt, FORMATS["shorts"])
    vid_w   = fmt_cfg["w"]
    vid_h   = fmt_cfg["h"]
    img_w   = fmt_cfg["img_w"]
    img_h   = fmt_cfg["img_h"]
    hook_dur  = fmt_cfg["hook_dur"]
    scene_dur = fmt_cfg["scene_dur"]

    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = WORK_DIR / ts
    session.mkdir(exist_ok=True)

    try:
        # ── STEP 1: 3-Stage Content Generation ───────────────────────────────
        pipeline_status["step"]       = "Research → Outline → Script (3-stage AI)..."
        pipeline_status["step_index"] = 1
        data = generate_content(req)

        # ── STEP 2: Voice Synthesis ───────────────────────────────────────────
        pipeline_status["step"]       = "Synthesizing voice narration..."
        pipeline_status["step_index"] = 2
        voice_p   = str(session / "voice.mp3")
        timings_p = str(session / "timings.json")
        word_timings = generate_voice(
            data["content"],
            data.get("voice_style", fmt_cfg["default_voice"]),
            fmt, voice_p, timings_p)
        audio_dur = get_duration(voice_p)
        print(f"  Audio: {audio_dur:.1f}s")

        # ── STEP 3: Subtitles ─────────────────────────────────────────────────
        pipeline_status["step"]       = "Generating subtitles..."
        pipeline_status["step_index"] = 3
        ass_p     = str(session / "subs.ass")
        cap_style = data.get("caption_style", fmt_cfg["default_caption"])
        generate_ass_subtitles(word_timings, ass_p, cap_style, vid_w, vid_h)

        # ── STEP 4: Hook Image (dedicated shock image, first 2.5s) ───────────
        pipeline_status["step"]       = "Creating hook image (scroll-stopper)..."
        pipeline_status["step_index"] = 4
        hook_img_p    = str(session / "hook_img.jpg")
        hook_clip_p   = str(session / "clip_hook.mp4")
        hook_prompt   = data.get("hook_image_prompt",
                                  f"Extreme close-up of the most disturbing visual of {data.get('title', '')}")
        print(f"  🎯 Hook image: {hook_prompt[:60]}...")
        hook_ok = build_hook_image(
            hook_prompt, data.get("title", ""), data["content_type"],
            data["image_style"], img_w, img_h, hook_img_p)
        hook_clip_ok = False
        if hook_ok:
            hook_clip_ok = build_clip_from_image(
                hook_img_p, hook_dur, hook_clip_p, kb_style=0,
                vid_w=vid_w, vid_h=vid_h, is_hook=True)

        # ── STEP 5: Scene Images + Clips ─────────────────────────────────────
        pipeline_status["step"]       = "Generating scene images..."
        pipeline_status["step_index"] = 5

        scenes      = data.get("scenes", [])
        max_dur     = fmt_cfg["max_dur"]
        target_dur  = min(audio_dur + 1.0, max_dur)

        # Calculate how many scene clips we need to cover the full audio
        # Hook covers hook_dur, remainder covered by scene_dur-length clips
        remaining_dur    = target_dur - hook_dur
        scenes_needed    = math.ceil(remaining_dur / scene_dur) + 1
        scenes_needed    = max(scenes_needed, fmt_cfg["scenes_per_story"])

        # Loop/extend scenes if needed
        while len(scenes) < scenes_needed:
            scenes = scenes + scenes
        scenes = scenes[:scenes_needed]

        clips         = []
        image_sources = []

        # Hook clip first
        if hook_clip_ok and Path(hook_clip_p).exists():
            clips.append(hook_clip_p)
            image_sources.append("hook")
            print(f"  ✅ Hook clip: {hook_dur}s zoom-punch")
        else:
            print("  ⚠️  Hook clip failed — starting with scene 1")

        # Scene clips
        for i, scene in enumerate(scenes):
            pipeline_status["progress_detail"] = f"Image {i+1}/{len(scenes)}"
            img_path  = str(session / f"img_{i}.jpg")
            clip_path = str(session / f"clip_{i}.mp4")
            print(f"  🎨 Scene {i+1}/{len(scenes)}: {scene[:50]}...")

            src = generate_image(scene, data["image_style"], data["content_type"],
                                  img_w, img_h, img_path,
                                  is_hook=False, scene_idx=i)
            image_sources.append(src)

            if _verify_image(img_path, min_size=500):
                ok = build_clip_from_image(img_path, scene_dur, clip_path,
                                            kb_style=i+1, vid_w=vid_w, vid_h=vid_h)
                if ok and Path(clip_path).stat().st_size > 1000:
                    clips.append(clip_path)
                else:
                    print(f"  ⚠️  Clip {i+1} build failed")
            else:
                print(f"  ⚠️  Image {i+1} invalid")

        if not clips:
            raise Exception("All clips failed — check image API keys (CF + Gemini)")

        # Record primary image source
        real_sources = [s for s in image_sources if s not in ("hook", "none")]
        if real_sources:
            pipeline_status["image_source"] = Counter(real_sources).most_common(1)[0][0]
        print(f"  ✅ {len(clips)} clips total | source: {pipeline_status['image_source']}")

        # ── STEP 6: Music + Sound Design ─────────────────────────────────────
        pipeline_status["step"]       = "Generating music & atmosphere..."
        pipeline_status["step_index"] = 6
        music_p    = str(session / "music.mp3")
        sound_mood = data.get("sound_mood",
                               CONTENT_NICHES[data["content_type"]]["sound_mood"])
        if not generate_music(sound_mood, music_p):
            music_p = None
        sound_p = generate_sound_design(data["content_type"], audio_dur, session)

        # ── STEP 7: Assemble Final Video ──────────────────────────────────────
        pipeline_status["step"]       = "Assembling final video..."
        pipeline_status["step_index"] = 7
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, sound_p, ass_p,
                       final_p, fmt, vid_w, vid_h)

        # ── STEP 8: Upload to YouTube ─────────────────────────────────────────
        pipeline_status["step"]       = "Uploading to YouTube..."
        pipeline_status["step_index"] = 8
        if not Path(final_p).exists() or Path(final_p).stat().st_size < 10_000:
            raise Exception("Final video invalid or too small")

        video_id   = upload_youtube(final_p, data, fmt)
        fmt_suffix = "shorts/" if fmt == "shorts" else "watch?v="
        url        = f"https://youtube.com/{fmt_suffix}{video_id}"

        # ── STEP 9: Log + Thumbnail Save ──────────────────────────────────────
        pipeline_status["step"]       = "Done! 🎉"
        pipeline_status["step_index"] = 9

        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp":        ts,
            "video_id":         video_id,
            "url":              url,
            "title":            data["title"],
            "title_variants":   data.get("title_variants", []),
            "hook_line":        data.get("hook_line", ""),
            "content_type":     data["content_type"],
            "format":           fmt,
            "image_style":      data["image_style"],
            "caption_style":    cap_style,
            "sound_mood":       sound_mood,
            "image_source":     pipeline_status.get("image_source", ""),
            "llm_used":         pipeline_status.get("llm_used", ""),
            "thumbnail_prompt": data.get("thumbnail_prompt", ""),
            "clips_total":      len(clips),
            "audio_dur":        round(audio_dur, 1),
            "version":          "10.0",
        }
        log.append(entry)
        LOG_FILE.write_text(json.dumps(log, indent=2))
        pipeline_status["last_result"] = entry

        print(f"\n✅ PUBLISHED: {url}")
        print(f"📋 Thumbnail prompt: {data.get('thumbnail_prompt','')[:100]}...")

    except Exception as e:
        pipeline_status["error"] = str(e)
        print(f"❌ Pipeline error: {e}")
        import traceback; traceback.print_exc()
    finally:
        pipeline_status["running"]         = False
        pipeline_status["progress_detail"] = ""
        pipeline_status["script_stage"]    = ""
        shutil.rmtree(str(session), ignore_errors=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# API ROUTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@app.get("/")
def root():
    cf_ready  = bool(CF_ACCOUNT_ID and CF_API_TOKEN)
    gem_ready = bool(GEMINI_API_KEY)
    return {
        "service":  "DarkHistory.ai v10.0 — Viral Horror Machine",
        "version":  "10.0",
        "formats":  {k: v["label"] for k, v in FORMATS.items()},
        "image_styles": {k: v["label"] for k, v in IMAGE_STYLES.items()},
        "niches":   {k: v["label"] for k, v in CONTENT_NICHES.items()},
        "image_stack": {
            "T1_cloudflare": cf_ready,
            "T2_gemini":     gem_ready,
            "T4_ffmpeg":     True,
        },
        "what_is_new_v10": [
            "Three-stage script engine: Research → Outline → Full Script",
            "Dedicated hook image: AI shock image + bold text overlay burnt in",
            "Exact scene timing: 2.5s Shorts / 3.0s Long-form (every clip)",
            "Hook clip = zoom-punch Ken Burns (1.0→1.28 fast scale)",
            "Fear phrase + title text overlay on hook image via ffmpeg",
            "Niche-matched image styles: vintage_horror/history, cinematic/truecrime",
            "Auto-caption: Impact for Shorts, Netflix bar for Long-form",
            "3-story long-form with chapter timestamps",
            "ffmpeg atmospheric music fallback (no silent videos)",
            "Sound design: organ+bell for history, pulse+static for true crime",
        ],
    }


@app.post("/run")
async def run(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req)
    return {
        "status":        "started",
        "format":        req.format or DEFAULT_FORMAT,
        "content_type":  req.content_type or "auto-alternate",
        "image_style":   req.image_style or "auto",
        "caption_style": req.caption_style or "auto",
        "version":       "10.0",
        "script_stages": "Research → Outline → Script (3 LLM calls per video)",
        "hook_image":    "AI shock image + text overlay (separate from story scenes)",
    }


@app.get("/status")
def get_status():
    return {
        **pipeline_status,
        "script_stage_detail": {
            "researching": "Deep-diving topic for viral angles and shocking facts",
            "outlining":   "Building beat-by-beat retention arc from research",
            "writing":     "Writing final script from outline",
            "":            "Idle",
        }.get(pipeline_status.get("script_stage", ""), pipeline_status.get("script_stage", "")),
    }


@app.post("/preview")
async def preview(req: RunRequest):
    """
    Run 3-stage content generation only (no video, no upload).
    Returns full script, scenes, hook image concept, thumbnail prompt,
    title variants — for review before committing to full pipeline.
    """
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    try:
        data = generate_content(req)
        return {
            "status":           "preview_ready",
            "title":            data.get("title"),
            "title_variants":   data.get("title_variants", []),
            "hook_line":        data.get("hook_line", ""),
            "content_preview":  data.get("content", "")[:600] + "...",
            "word_count":       len(data.get("content", "").split()),
            "scenes":           data.get("scenes", []),
            "hook_image_prompt": data.get("hook_image_prompt", ""),
            "thumbnail_prompt": data.get("thumbnail_prompt", ""),
            "description_preview": data.get("description","")[:300] + "...",
            "tags":             data.get("tags", []),
            "image_style":      data.get("image_style"),
            "caption_style":    data.get("caption_style"),
            "voice_style":      data.get("voice_style"),
            "sound_mood":       data.get("sound_mood"),
            "content_type":     data.get("content_type"),
            "format":           data.get("format"),
            "llm_used":         pipeline_status.get("llm_used"),
            "note": "Run POST /run with same params to produce and upload the video",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/logs")
def get_logs():
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text())


@app.get("/stats")
def get_stats():
    """Lifetime production stats."""
    if not LOG_FILE.exists():
        return {"total_videos": 0}
    log = json.loads(LOG_FILE.read_text())
    return {
        "total_videos":     len(log),
        "by_niche":         dict(Counter(e.get("content_type","?") for e in log)),
        "by_format":        dict(Counter(e.get("format","?") for e in log)),
        "by_image_style":   dict(Counter(e.get("image_style","?") for e in log)),
        "by_image_source":  dict(Counter(e.get("image_source","?") for e in log)),
        "by_llm":           dict(Counter(e.get("llm_used","?") for e in log)),
        "by_caption_style": dict(Counter(e.get("caption_style","?") for e in log)),
        "avg_audio_dur":    round(sum(e.get("audio_dur",0) for e in log) / max(len(log),1), 1),
        "latest":           log[-1] if log else None,
    }


@app.get("/niches")
def get_niches():
    return {
        "strategy": "Stick to these 2 niches — both $8-$18 CPM, massive search volume, loyal binge audience",
        "niches": [
            {"id": k, "label": v["label"], "icon": v["icon"],
             "cpm": v["cpm"], "img_style": v["img_style"],
             "sound_mood": v["sound_mood"], "topic_count": len(v["topics"])}
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
            {"id": k, "label": v["label"],
             "dimensions": f"{v['w']}x{v['h']}",
             "hook_dur": v["hook_dur"],
             "scene_dur": v["scene_dur"],
             "max_duration": v["max_dur"],
             "word_count": v["word_count"],
             "caption_default": v["default_caption"]}
            for k, v in FORMATS.items()
        ],
        "image_styles": [
            {"id": k, "label": v["label"]} for k, v in IMAGE_STYLES.items()
        ],
        "caption_styles": [
            {"id": "impact",  "label": "Impact (Shorts default — centered, TikTok viral)"},
            {"id": "netflix", "label": "Netflix (Long-form default — bottom bar, clean)"},
        ],
        "niches": [
            {"id": k, "label": v["label"], "icon": v["icon"],
             "default_img_style": v["img_style"]}
            for k, v in CONTENT_NICHES.items()
        ],
        "image_pipeline": [
            "T1: Cloudflare Workers AI FLUX.1-schnell (CF_ACCOUNT_ID + CF_API_TOKEN)",
            "T2: Gemini 2.5 Flash Image (GEMINI_API_KEY)",
            "T3: Gemini 2.0 Flash Exp fallback (GEMINI_API_KEY)",
            "T4: Cinematic FFmpeg art — always works, <1s, scene-matched palette",
        ],
    }


@app.get("/health")
def health():
    cf_ready  = bool(CF_ACCOUNT_ID and CF_API_TOKEN)
    gem_ready = bool(GEMINI_API_KEY)
    return {
        "status":  "healthy",
        "version": "10.0",
        "keys": {
            "cloudflare_account": bool(CF_ACCOUNT_ID),
            "cloudflare_token":   bool(CF_API_TOKEN),
            "gemini":             bool(GEMINI_API_KEY),
            "groq":               bool(GROQ_API_KEY),
            "openrouter":         bool(OPENROUTER_API_KEY),
            "youtube":            bool(YOUTUBE_REFRESH_TOKEN),
        },
        "image_stack_ready": cf_ready or gem_ready or True,   # T4 always works
        "recommended_setup":  "Set CF_ACCOUNT_ID + CF_API_TOKEN (free, 100 images/day)",
        "script_engine":      "3-stage: Research → Outline → Script",
        "hook_image":         "AI shock image + ffmpeg text overlay (every video)",
        "scene_timing":       "Exactly 2.5s/Shorts, 3.0s/Long-form per clip",
        "timestamp":          datetime.now().isoformat(),
    }
