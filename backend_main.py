"""
KidsContent.ai — FastAPI Backend
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Host on Render.com free tier (750hrs/month free)
All tools are 100% free — no GPU required on this server.

Tools used:
  - Claude API         → script + SEO generation
  - Edge TTS           → Microsoft Neural voice (no key, free forever)
  - HuggingFace Spaces → real video generation on free H200 GPU (ZeroGPU)
  - Pollinations.AI    → images + background music (no key)
  - FFmpeg             → video assembly (CPU only)
  - YouTube Data API   → upload with full SEO

Deploy: render.com → New Web Service → connect GitHub → free tier
"""

import os, json, time, random, asyncio, subprocess, re, base64, tempfile, shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ── ENV VARS (set in Render dashboard) ────────────────────────────────────────
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP SETUP ──────────────────────────────────────────────────────────────────
app = FastAPI(title="KidsContent.ai API", version="2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORK_DIR = Path("/tmp/kidscontent")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

pipeline_status = {
    "running": False,
    "step": "",
    "step_index": 0,
    "total_steps": 7,
    "last_result": None,
    "error": None,
}

# ── NICHE CONFIG ──────────────────────────────────────────────────────────────
NICHES = {
    "nursery_rhyme": {
        "weight": 40, "label": "Nursery Rhyme", "icon": "🎵",
        "voice": "en-US-AriaNeural", "voice_rate": "+5%", "voice_pitch": "+8Hz",
        "music_prompt": "cheerful upbeat children piano melody loop",
        "image_style": "bright vibrant 3D cartoon children's book illustration, colorful joyful",
        "themes": ["farm animals waking up","raindrops on umbrellas","stars at bedtime",
                   "dinosaurs going to school","ocean fish dancing","bunnies in garden",
                   "train through colorful tunnels","butterflies learning to fly",
                   "bears making honey sandwiches","monkeys in a jungle"],
    },
    "abc_learning": {
        "weight": 20, "label": "ABC Learning", "icon": "🔤",
        "voice": "en-US-JennyNeural", "voice_rate": "+0%", "voice_pitch": "+5Hz",
        "music_prompt": "gentle educational xylophone children tune",
        "image_style": "cute kawaii flat design educational illustration pastel colors",
        "themes": ["letter A with apples","letter B with butterflies","counting 1 to 10",
                   "learning colors rainbow","shapes circle square triangle",
                   "days of the week","months of the year","left and right with robot",
                   "number 5 with frogs","alphabet A to Z adventure"],
    },
    "bedtime_story": {
        "weight": 20, "label": "Bedtime Story", "icon": "🌙",
        "voice": "en-GB-SoniaNeural", "voice_rate": "-10%", "voice_pitch": "-2Hz",
        "music_prompt": "soft lullaby gentle piano night peaceful music",
        "image_style": "soft dreamy watercolor illustration night sky warm glowing colors",
        "themes": ["cloud afraid of the dark","sleepy moon wants to play","tiny star learning to shine",
                   "bunny lost his blanket","elephant finding a dream","owl guiding fireflies",
                   "fish finding coral bed","teddy bear dream adventure",
                   "child and shadow becoming friends","magical night garden"],
    },
    "animal_facts": {
        "weight": 20, "label": "Animal Facts", "icon": "🦁",
        "voice": "en-US-GuyNeural", "voice_rate": "+8%", "voice_pitch": "+3Hz",
        "music_prompt": "adventurous upbeat nature kids documentary music",
        "image_style": "vivid nature photography illustration detailed animal lush environment",
        "themes": ["amazing elephant facts","funny penguin facts","incredible dolphin facts",
                   "surprising octopus facts","cute red panda facts","amazing cheetah speed",
                   "funny sloth habits","incredible hummingbird facts","blue whale size facts",
                   "chameleon color change facts"],
    },
}


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — GENERATE CONTENT WITH CLAUDE
# ══════════════════════════════════════════════════════════════════════════════
def pick_niche(enabled_niches: list) -> str:
    available = {k: v for k, v in NICHES.items() if k in enabled_niches}
    if not available:
        available = NICHES
    keys = list(available.keys())
    weights = [available[k]["weight"] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def generate_content(niche_key: str) -> dict:
    niche = NICHES[niche_key]
    theme = random.choice(niche["themes"])

    prompts = {
        "nursery_rhyme": f"""Write an ORIGINAL nursery rhyme for toddlers (age 1-5) about: {theme}
- 4 verses × 4 lines, AABB rhyme scheme
- Catchy 2-line chorus repeated after each verse
- Fun sound effects (moo!, splash!, zoom!)
- Educational element woven in naturally""",
        "abc_learning": f"""Write an original educational song for toddlers (age 2-5) about: {theme}
- Fun intro + 3-4 educational verses × 4 lines
- Catchy repeating chorus
- Use repetition for memorization, make it engaging""",
        "bedtime_story": f"""Write a gentle original 60-second bedtime story for young children (age 2-6) about: {theme}
- Calm opening → short gentle adventure → peaceful happy ending
- Soothing repetitive phrases, end with "sweet dreams"
- Under 200 words""",
        "animal_facts": f"""Write an exciting animal facts script for kids (age 4-8) about: {theme}
- Hook: "Did you know..."
- 4-5 amazing age-appropriate facts with fun comparisons
- Exciting closing fact, under 180 words""",
    }

    seo_block = """
Also generate fully optimised YouTube Shorts SEO:
- TITLE: max 70 chars, primary keyword + 1 leading emoji, click-worthy for parents
- DESCRIPTION: 150-200 words, hook in first 2 sentences, keywords natural, CTA at end
- TAGS: exactly 8 backend tags (comma-separated), mix broad + niche
- HASHTAGS: exactly 5 hashtags starting with #Shorts
- SCENES: 5 different visual scene descriptions (max 15 words each) for image/video generation

Respond ONLY with valid JSON (no markdown fences):
{
  "title": "...",
  "content": "full script here",
  "description": "...",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8"],
  "hashtags": "#Shorts #Tag2 #Tag3 #Tag4 #Tag5",
  "scenes": ["scene1","scene2","scene3","scene4","scene5"],
  "theme": "theme name"
}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={"Content-Type": "application/json",
                 "x-api-key": ANTHROPIC_API_KEY,
                 "anthropic-version": "2023-06-01"},
        json={"model": "claude-sonnet-4-20250514", "max_tokens": 1500,
              "messages": [{"role": "user", "content": prompts[niche_key] + seo_block}]},
        timeout=90,
    )
    if resp.status_code != 200:
        raise Exception(f"Claude API error {resp.status_code}")

    raw = resp.json()["content"][0]["text"].strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    data = json.loads(raw)
    data["niche_key"] = niche_key
    data["niche"] = niche
    return data


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — EDGE TTS VOICE (Microsoft Neural, 100% free, no API key)
# ══════════════════════════════════════════════════════════════════════════════
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


def generate_voice(content, niche, audio_path, srt_path):
    asyncio.run(_tts_async(
        text=content,
        voice=niche["voice"],
        rate=niche["voice_rate"],
        pitch=niche["voice_pitch"],
        audio_out=str(audio_path),
        srt_out=str(srt_path),
    ))


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — HUGGINGFACE ZERОГPU — Real Video Generation (Free H200)
# ══════════════════════════════════════════════════════════════════════════════
HF_SPACES = [
    # LTX-Video Space (fast, good quality, free ZeroGPU)
    "https://lightricks-ltx-video.hf.space",
    # Wan2.1 community space
    "https://hysts-wan2-1.hf.space",
]

def generate_video_hf(scene_prompt: str, image_style: str, output_path: str, duration: int = 8) -> bool:
    """
    Calls HuggingFace ZeroGPU Spaces API to generate a real video clip.
    Uses the Gradio API exposed by public Spaces running LTX-Video or Wan2.1.
    Falls back gracefully to Pollinations image if HF is busy.
    """
    full_prompt = (
        f"{scene_prompt}, {image_style}, "
        f"children's animated style, bright vibrant colors, smooth motion, "
        f"no text, no watermarks, vertical 9:16, high quality"
    )

    # Try HuggingFace Gradio API
    for base_url in HF_SPACES:
        try:
            # Gradio API predict endpoint
            api_url = f"{base_url}/api/predict"
            payload = {
                "fn_index": 0,
                "data": [
                    full_prompt,
                    "",  # negative prompt
                    512, 896,  # width, height (9:16)
                    duration * 24,  # num_frames
                    42,  # seed
                ],
                "session_hash": f"kid{random.randint(10000,99999)}"
            }
            resp = requests.post(api_url, json=payload, timeout=180)
            if resp.status_code == 200:
                result = resp.json()
                if "data" in result and result["data"]:
                    video_data = result["data"][0]
                    # HF returns either a URL or base64
                    if isinstance(video_data, str) and video_data.startswith("http"):
                        video_resp = requests.get(video_data, timeout=120)
                        if video_resp.status_code == 200:
                            Path(output_path).write_bytes(video_resp.content)
                            return True
                    elif isinstance(video_data, dict) and "name" in video_data:
                        # Gradio file reference
                        file_url = f"{base_url}/file={video_data['name']}"
                        video_resp = requests.get(file_url, timeout=120)
                        if video_resp.status_code == 200:
                            Path(output_path).write_bytes(video_resp.content)
                            return True
        except Exception as e:
            print(f"HF Space {base_url} failed: {e}")
            continue

    return False  # Fall back to image-based approach


def generate_scene_image(scene: str, style: str, output_path: str) -> bool:
    """Pollinations.AI image fallback (always free, always available)."""
    prompt = f"{scene}, {style}, no text, no watermarks, vertical 9:16"
    encoded = requests.utils.quote(prompt)
    url = (f"https://image.pollinations.ai/prompt/{encoded}"
           f"?width=1080&height=1920&nologo=true&model=flux&seed={random.randint(1,9999)}")
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 5000:
            Path(output_path).write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


def build_scene_video(scene: str, style: str, duration: float, output_path: str):
    """
    For each scene: try HF real video → fallback to animated image with Ken Burns.
    """
    ts = str(int(time.time() * 1000))
    vid_path = str(WORK_DIR / f"scene_vid_{ts}.mp4")
    img_path = str(WORK_DIR / f"scene_img_{ts}.jpg")

    # Try real video first
    if generate_video_hf(scene, style, vid_path, duration=max(4, int(duration))):
        # Re-encode to exact duration and 9:16
        cmd = [
            "ffmpeg", "-y", "-i", vid_path,
            "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black",
            "-t", str(duration), "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-an", output_path
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        if result.returncode == 0:
            return "video"

    # Fallback: animated image with Ken Burns
    if generate_scene_image(scene, style, img_path):
        frames = int(duration * 25)
        kb_effects = [
            "zoompan=z='zoom+0.0015':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
            "zoompan=z='zoom+0.001':x='min(max(0,iw/2-(iw/zoom/2)+5*on),iw-iw/zoom)':y='ih/2-(ih/zoom/2)'",
        ]
        effect = random.choice(kb_effects)
        cmd = [
            "ffmpeg", "-y", "-loop", "1", "-i", img_path,
            "-vf", (f"scale=1080:1920:force_original_aspect_ratio=decrease,"
                    f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x1a1a2e,"
                    f"{effect}:d={frames}:s=1080x1920:fps=25"),
            "-t", str(duration), "-c:v", "libx264", "-crf", "22", "-preset", "fast",
            "-pix_fmt", "yuv420p", "-an", output_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)
        return "image"

    return None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — BACKGROUND MUSIC (Pollinations Audio, free)
# ══════════════════════════════════════════════════════════════════════════════
def generate_music(music_prompt: str, music_path: str) -> bool:
    url = f"https://audio.pollinations.ai/{requests.utils.quote(music_prompt)}"
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            return True
    except Exception:
        pass
    return False


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — ASSEMBLE FINAL VIDEO WITH FFMPEG
# ══════════════════════════════════════════════════════════════════════════════
def get_duration(path: str) -> float:
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True
    )
    try:
        return float(probe.stdout.strip())
    except Exception:
        return 10.0


def srt_to_drawtext(srt_path: str) -> Optional[str]:
    """Convert SRT to FFmpeg drawtext filter for burned-in captions."""
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
            text = text.replace("'", "\\'").replace(":", "\\:").replace("[","\\[").replace("]","\\]")
            if len(text) > 35:
                text = text[:35] + "..."
            filters.append(
                f"drawtext=text='{text}'"
                f":fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
                f":fontsize=68:fontcolor=white:borderw=4:bordercolor=black"
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


def assemble_final_video(scene_videos: list, voice_path: str,
                          music_path: Optional[str], srt_path: str,
                          output_path: str):
    """Concatenate scene clips + mix voice + music + burn subtitles."""
    ts = str(int(time.time()))

    # Step A: concatenate scene clips
    concat_list = WORK_DIR / f"concat_{ts}.txt"
    with open(concat_list, "w") as f:
        for v in scene_videos:
            f.write(f"file '{v}'\n")

    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", concat_out
    ], capture_output=True, timeout=120)

    # Step B: get total voice duration and trim/pad concat video
    voice_dur = min(get_duration(voice_path) + 0.5, 59.0)

    trimmed_out = str(WORK_DIR / f"trimmed_{ts}.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-i", concat_out,
        "-t", str(voice_dur), "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-pix_fmt", "yuv420p", trimmed_out
    ], capture_output=True, timeout=180)

    # Step C: burn subtitles
    sub_filter = srt_to_drawtext(srt_path)
    subbed_out = str(WORK_DIR / f"subbed_{ts}.mp4")
    if sub_filter:
        result = subprocess.run([
            "ffmpeg", "-y", "-i", trimmed_out,
            "-vf", sub_filter,
            "-c:v", "libx264", "-crf", "20", "-preset", "fast",
            "-pix_fmt", "yuv420p", subbed_out
        ], capture_output=True, timeout=300)
        if result.returncode != 0:
            subbed_out = trimmed_out  # skip subs if fail
    else:
        subbed_out = trimmed_out

    # Step D: mix voice + music
    if music_path and Path(music_path).exists():
        filter_complex = (
            "[1:a]volume=1.4[voice];"
            "[2:a]volume=0.22,aloop=loop=-1:size=2e+09[music];"
            "[voice][music]amix=inputs=2:duration=first[afinal]"
        )
        subprocess.run([
            "ffmpeg", "-y",
            "-i", subbed_out, "-i", voice_path, "-i", music_path,
            "-filter_complex", filter_complex,
            "-map", "0:v", "-map", "[afinal]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            output_path
        ], capture_output=True, timeout=300)
    else:
        subprocess.run([
            "ffmpeg", "-y",
            "-i", subbed_out, "-i", voice_path,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart",
            output_path
        ], capture_output=True, timeout=300)


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — YOUTUBE UPLOAD WITH FULL SEO
# ══════════════════════════════════════════════════════════════════════════════
def get_yt_token() -> str:
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": YOUTUBE_CLIENT_ID,
        "client_secret": YOUTUBE_CLIENT_SECRET,
        "refresh_token": YOUTUBE_REFRESH_TOKEN,
        "grant_type": "refresh_token",
    })
    if r.status_code != 200:
        raise Exception(f"Token refresh failed: {r.text[:200]}")
    return r.json()["access_token"]


def upload_youtube(video_path: str, data: dict) -> str:
    token = get_yt_token()
    niche = data["niche"]

    description = (
        f"{data['description']}\n\n"
        f"🔔 Subscribe for new videos every day!\n"
        f"👍 Like if your little one enjoyed this!\n"
        f"💬 Comment your child's favourite part!\n\n"
        f"{data.get('hashtags', '#Shorts #KidsSongs #NurseryRhymes #Children #Learning')}"
    )

    tags = list(dict.fromkeys(
        data.get("tags", []) + ["kids songs", "children music", "toddler",
                                "nursery rhymes", "educational", "shorts",
                                "youtube shorts", niche["label"].lower()]
    ))[:15]

    metadata = {
        "snippet": {
            "title": data["title"][:100],
            "description": description[:4900],
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": True,
            "madeForKids": True,
        },
    }

    init_r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos"
        "?uploadType=resumable&part=snippet,status",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json",
                 "X-Upload-Content-Type": "video/mp4"},
        json=metadata,
    )
    if init_r.status_code != 200:
        raise Exception(f"YouTube init error {init_r.status_code}: {init_r.text[:200]}")

    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(
        init_r.headers["Location"],
        headers={"Content-Type": "video/mp4",
                 "Content-Length": str(len(video_bytes))},
        data=video_bytes, timeout=600,
    )
    if up_r.status_code not in (200, 201):
        raise Exception(f"Upload error {up_r.status_code}: {up_r.text[:200]}")

    return up_r.json().get("id", "unknown")


# ══════════════════════════════════════════════════════════════════════════════
# FULL PIPELINE
# ══════════════════════════════════════════════════════════════════════════════
def set_status(step: str, index: int):
    pipeline_status["step"] = step
    pipeline_status["step_index"] = index
    print(f"[{index}/{pipeline_status['total_steps']}] {step}")


def full_pipeline(enabled_niches: list = None):
    if pipeline_status["running"]:
        return
    pipeline_status["running"] = True
    pipeline_status["error"] = None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = WORK_DIR / ts
    session_dir.mkdir(exist_ok=True)

    try:
        # 1 — Pick niche + generate content
        set_status("Generating script + SEO with Claude...", 1)
        niche_key = pick_niche(enabled_niches or list(NICHES.keys()))
        data = generate_content(niche_key)
        niche = data["niche"]
        print(f"✅ Content: {data['title']}")

        # 2 — Voice + subtitles
        set_status("Synthesizing voice with Edge TTS...", 2)
        voice_path = str(session_dir / "voice.mp3")
        srt_path = str(session_dir / "subs.srt")
        generate_voice(data["content"], niche, voice_path, srt_path)
        audio_dur = get_duration(voice_path)
        scene_dur = min(audio_dur / len(data["scenes"]), 12.0)

        # 3 — Scene videos (HF ZeroGPU or animated image fallback)
        set_status("Generating video scenes on HuggingFace GPU...", 3)
        scene_videos = []
        for i, scene in enumerate(data["scenes"]):
            out = str(session_dir / f"scene_{i}.mp4")
            result = build_scene_video(scene, niche["image_style"], scene_dur, out)
            if result and Path(out).exists():
                scene_videos.append(out)
                print(f"  ✅ Scene {i+1} ({result})")

        if not scene_videos:
            raise Exception("All scene generation attempts failed")

        # 4 — Background music
        set_status("Generating background music...", 4)
        music_path = str(session_dir / "music.mp3")
        music_ok = generate_music(niche["music_prompt"], music_path)
        if not music_ok:
            music_path = None

        # 5 — Assemble final video
        set_status("Assembling final video with FFmpeg...", 5)
        final_video = str(session_dir / "final.mp4")
        assemble_final_video(
            scene_videos=scene_videos,
            voice_path=voice_path,
            music_path=music_path,
            srt_path=srt_path,
            output_path=final_video,
        )
        print(f"✅ Final video: {final_video}")

        # 6 — Upload to YouTube
        set_status("Uploading to YouTube...", 6)
        video_id = upload_youtube(final_video, data)
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Uploaded: {url}")

        # 7 — Log
        set_status("Done!", 7)
        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp": ts, "video_id": video_id,
            "title": data["title"], "niche": niche_key,
            "url": url, "theme": data.get("theme", ""),
        }
        log.append(entry)
        LOG_FILE.write_text(json.dumps(log, indent=2))
        pipeline_status["last_result"] = entry

    except Exception as e:
        pipeline_status["error"] = str(e)
        print(f"❌ Pipeline error: {e}")
    finally:
        pipeline_status["running"] = False
        try:
            shutil.rmtree(session_dir, ignore_errors=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ══════════════════════════════════════════════════════════════════════════════
class RunRequest(BaseModel):
    enabled_niches: Optional[list] = None


@app.get("/")
def root():
    return {"status": "ok", "service": "KidsContent.ai API v2.0"}


@app.post("/run")
async def run_pipeline(req: RunRequest, background_tasks: BackgroundTasks):
    """Trigger a manual pipeline run."""
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    background_tasks.add_task(full_pipeline, req.enabled_niches)
    return {"status": "started"}


@app.get("/status")
def get_status():
    """Get current pipeline status."""
    return pipeline_status


@app.get("/logs")
def get_logs():
    """Get upload history."""
    if not LOG_FILE.exists():
        return []
    return json.loads(LOG_FILE.read_text())


@app.get("/niches")
def get_niches():
    """Get niche config (without theme lists for brevity)."""
    return {k: {"label": v["label"], "icon": v["icon"], "weight": v["weight"]}
            for k, v in NICHES.items()}


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
