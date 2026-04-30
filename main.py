"""
KidsContent.ai — FastAPI Backend v2.2
Compatible with Python 3.14 + Pydantic v2
"""

import os, json, time, random, asyncio, subprocess, re, shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List
import requests

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── ENV VARS ──────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY     = os.environ.get("ANTHROPIC_API_KEY", "")
YOUTUBE_CLIENT_ID     = os.environ.get("YOUTUBE_CLIENT_ID", "")
YOUTUBE_CLIENT_SECRET = os.environ.get("YOUTUBE_CLIENT_SECRET", "")
YOUTUBE_REFRESH_TOKEN = os.environ.get("YOUTUBE_REFRESH_TOKEN", "")

# ── APP ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="KidsContent.ai API", version="2.2")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

WORK_DIR = Path("/tmp/kidscontent")
WORK_DIR.mkdir(exist_ok=True)
LOG_FILE = WORK_DIR / "upload_log.json"

# Use plain dict for status — avoids ALL pydantic issues
pipeline_status: dict = {
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
        "themes": [
            "farm animals waking up", "raindrops on umbrellas", "stars at bedtime",
            "dinosaurs going to school", "ocean fish dancing", "bunnies in garden",
            "train through colorful tunnels", "butterflies learning to fly",
        ],
    },
    "abc_learning": {
        "weight": 20, "label": "ABC Learning", "icon": "🔤",
        "voice": "en-US-JennyNeural", "voice_rate": "+0%", "voice_pitch": "+5Hz",
        "music_prompt": "gentle educational xylophone children tune",
        "image_style": "cute kawaii flat design educational illustration pastel colors",
        "themes": [
            "letter A with apples", "counting 1 to 10",
            "learning colors rainbow", "shapes circle square triangle",
            "days of the week", "alphabet A to Z adventure",
        ],
    },
    "bedtime_story": {
        "weight": 20, "label": "Bedtime Story", "icon": "🌙",
        "voice": "en-GB-SoniaNeural", "voice_rate": "-10%", "voice_pitch": "-2Hz",
        "music_prompt": "soft lullaby gentle piano night peaceful music",
        "image_style": "soft dreamy watercolor illustration night sky warm glowing colors",
        "themes": [
            "cloud afraid of the dark", "sleepy moon wants to play",
            "tiny star learning to shine", "bunny lost his blanket",
        ],
    },
    "animal_facts": {
        "weight": 20, "label": "Animal Facts", "icon": "🦁",
        "voice": "en-US-GuyNeural", "voice_rate": "+8%", "voice_pitch": "+3Hz",
        "music_prompt": "adventurous upbeat nature kids documentary music",
        "image_style": "vivid nature photography illustration detailed animal lush environment",
        "themes": [
            "amazing elephant facts", "funny penguin facts",
            "incredible dolphin facts", "cute red panda facts",
        ],
    },
}


# ── PYDANTIC MODELS (v2 compatible) ──────────────────────────────────────────
class RunRequest(BaseModel):
    enabled_niches: Optional[List[str]] = Field(default=None)


# ── STEP 1: CONTENT GENERATION ────────────────────────────────────────────────
def pick_niche(enabled_niches: List[str]) -> str:
    available = {k: v for k, v in NICHES.items() if k in enabled_niches}
    if not available:
        available = NICHES
    keys = list(available.keys())
    weights = [available[k]["weight"] for k in keys]
    return random.choices(keys, weights=weights, k=1)[0]


def generate_content(niche_key: str) -> dict:
    niche = NICHES[niche_key]
    theme = random.choice(niche["themes"])

    content_prompts = {
        "nursery_rhyme": f"Write an ORIGINAL nursery rhyme for toddlers (age 1-5) about: {theme}. 4 verses x 4 lines, AABB rhyme, catchy chorus, fun sound effects.",
        "abc_learning": f"Write an original educational song for toddlers (age 2-5) about: {theme}. Fun intro + 3 verses + repeating chorus.",
        "bedtime_story": f"Write a gentle 60-second bedtime story for children (age 2-6) about: {theme}. Calm, peaceful, happy ending, under 200 words.",
        "animal_facts": f"Write exciting animal facts for kids (age 4-8) about: {theme}. Hook + 4 facts + wow closing. Under 180 words.",
    }

    full_prompt = content_prompts[niche_key] + """

Also generate YouTube Shorts SEO. Return ONLY valid JSON with NO markdown fences:
{
  "title": "max 70 chars with emoji at start",
  "content": "full script here",
  "description": "150-200 word YouTube description",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8"],
  "hashtags": "#Shorts #Tag2 #Tag3 #Tag4 #Tag5",
  "scenes": ["scene1 description max 15 words","scene2","scene3","scene4","scene5"],
  "theme": "theme name here"
}"""

    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1500,
            "messages": [{"role": "user", "content": full_prompt}],
        },
        timeout=90,
    )
    if resp.status_code != 200:
        raise Exception(f"Claude API error {resp.status_code}: {resp.text[:200]}")

    raw = resp.json()["content"][0]["text"].strip()
    # Strip any markdown fences
    raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    data = json.loads(raw)
    data["niche_key"] = niche_key
    data["niche"] = niche
    return data


# ── STEP 2: EDGE TTS VOICE ────────────────────────────────────────────────────
async def _tts_async(text: str, voice: str, rate: str, pitch: str,
                     audio_out: str, srt_out: str):
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


def generate_voice(content: str, niche: dict, audio_path: str, srt_path: str):
    asyncio.run(_tts_async(
        text=content,
        voice=niche["voice"],
        rate=niche["voice_rate"],
        pitch=niche["voice_pitch"],
        audio_out=audio_path,
        srt_out=srt_path,
    ))


# ── STEP 3: SCENE IMAGES ─────────────────────────────────────────────────────
def generate_scene_image(scene: str, style: str, output_path: str) -> bool:
    prompt = f"{scene}, {style}, no text, no watermarks, vertical 9:16"
    encoded = requests.utils.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1080&height=1920&nologo=true&model=flux&seed={random.randint(1, 9999)}"
    )
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 5000:
            Path(output_path).write_bytes(r.content)
            return True
    except Exception as e:
        print(f"Image gen failed: {e}")
    return False


def build_scene_clip(scene: str, style: str, duration: float, output_path: str) -> bool:
    img_path = output_path.replace(".mp4", ".jpg")
    if not generate_scene_image(scene, style, img_path):
        return False

    frames = int(duration * 25)
    kb_effects = [
        "zoompan=z='zoom+0.0015':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.0015))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'",
        "zoompan=z='zoom+0.001':x='min(max(0,iw/2-(iw/zoom/2)+4*on),iw-iw/zoom)':y='ih/2-(ih/zoom/2)'",
    ]
    effect = random.choice(kb_effects)
    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", img_path,
        "-vf", (
            f"scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=0x1a1a2e,"
            f"{effect}:d={frames}:s=1080x1920:fps=25"
        ),
        "-t", str(duration),
        "-c:v", "libx264", "-crf", "22", "-preset", "fast",
        "-pix_fmt", "yuv420p", "-an", output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=180)
    Path(img_path).unlink(missing_ok=True)
    return result.returncode == 0


# ── STEP 4: BACKGROUND MUSIC ─────────────────────────────────────────────────
def generate_music(music_prompt: str, music_path: str) -> bool:
    url = f"https://audio.pollinations.ai/{requests.utils.quote(music_prompt)}"
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 200 and len(r.content) > 1000:
            Path(music_path).write_bytes(r.content)
            return True
    except Exception as e:
        print(f"Music gen failed: {e}")
    return False


# ── UTILITIES ─────────────────────────────────────────────────────────────────
def get_duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=30,
        )
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
            text = (text.replace("'", "\\'")
                       .replace(":", "\\:")
                       .replace("[", "\\[")
                       .replace("]", "\\]"))
            if len(text) > 35:
                text = text[:35] + "..."
            filters.append(
                f"drawtext=text='{text}'"
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
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


# ── STEP 5: ASSEMBLE FINAL VIDEO ─────────────────────────────────────────────
def assemble_video(scene_clips: list, voice_path: str,
                   music_path: Optional[str], srt_path: str, output_path: str):
    ts = str(int(time.time()))

    # Concat clips
    concat_txt = str(WORK_DIR / f"concat_{ts}.txt")
    with open(concat_txt, "w") as f:
        for c in scene_clips:
            f.write(f"file '{c}'\n")
    concat_out = str(WORK_DIR / f"concat_{ts}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_txt,
         "-c", "copy", concat_out],
        capture_output=True, timeout=120,
    )

    # Trim to voice duration
    voice_dur = min(get_duration(voice_path) + 0.5, 59.0)
    trimmed = str(WORK_DIR / f"trimmed_{ts}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-i", concat_out, "-t", str(voice_dur),
         "-c:v", "libx264", "-crf", "22", "-preset", "fast",
         "-pix_fmt", "yuv420p", trimmed],
        capture_output=True, timeout=180,
    )

    # Burn subtitles
    sub_filter = srt_to_drawtext(srt_path)
    subbed = str(WORK_DIR / f"subbed_{ts}.mp4")
    if sub_filter:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", trimmed, "-vf", sub_filter,
             "-c:v", "libx264", "-crf", "20", "-preset", "fast",
             "-pix_fmt", "yuv420p", subbed],
            capture_output=True, timeout=300,
        )
        subbed = subbed if r.returncode == 0 else trimmed
    else:
        subbed = trimmed

    # Mix audio
    if music_path and Path(music_path).exists():
        filt = (
            "[1:a]volume=1.4[voice];"
            "[2:a]volume=0.22,aloop=loop=-1:size=2e+09[music];"
            "[voice][music]amix=inputs=2:duration=first[afinal]"
        )
        subprocess.run(
            ["ffmpeg", "-y",
             "-i", subbed, "-i", voice_path, "-i", music_path,
             "-filter_complex", filt,
             "-map", "0:v", "-map", "[afinal]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", output_path],
            capture_output=True, timeout=300,
        )
    else:
        subprocess.run(
            ["ffmpeg", "-y",
             "-i", subbed, "-i", voice_path,
             "-map", "0:v", "-map", "1:a",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", output_path],
            capture_output=True, timeout=300,
        )


# ── STEP 6: YOUTUBE UPLOAD ────────────────────────────────────────────────────
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
        f"👍 Like if your little one enjoyed this!\n\n"
        f"{data.get('hashtags', '#Shorts #KidsSongs #NurseryRhymes')}"
    )
    tags = list(dict.fromkeys(
        data.get("tags", []) + ["kids songs", "children music", "toddler",
                                "nursery rhymes", "educational", "shorts",
                                niche["label"].lower()]
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
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-Upload-Content-Type": "video/mp4",
        },
        json=metadata,
    )
    if init_r.status_code != 200:
        raise Exception(f"YouTube init error {init_r.status_code}: {init_r.text[:200]}")
    video_bytes = Path(video_path).read_bytes()
    up_r = requests.put(
        init_r.headers["Location"],
        headers={"Content-Type": "video/mp4", "Content-Length": str(len(video_bytes))},
        data=video_bytes,
        timeout=600,
    )
    if up_r.status_code not in (200, 201):
        raise Exception(f"Upload error {up_r.status_code}: {up_r.text[:200]}")
    return up_r.json().get("id", "unknown")


# ── FULL PIPELINE ─────────────────────────────────────────────────────────────
def full_pipeline(enabled_niches: List[str]):
    if pipeline_status["running"]:
        return
    pipeline_status["running"] = True
    pipeline_status["error"] = None
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    session = WORK_DIR / ts
    session.mkdir(exist_ok=True)

    try:
        pipeline_status["step"] = "Generating script + SEO with Claude..."
        pipeline_status["step_index"] = 1
        niche_key = pick_niche(enabled_niches)
        data = generate_content(niche_key)
        niche = data["niche"]
        print(f"✅ Title: {data['title']}")

        pipeline_status["step"] = "Synthesizing voice with Edge TTS..."
        pipeline_status["step_index"] = 2
        voice_p = str(session / "voice.mp3")
        srt_p = str(session / "subs.srt")
        generate_voice(data["content"], niche, voice_p, srt_p)
        audio_dur = get_duration(voice_p)
        scene_dur = min(audio_dur / len(data["scenes"]), 12.0)

        pipeline_status["step"] = "Generating scene images..."
        pipeline_status["step_index"] = 3
        clips = []
        for i, scene in enumerate(data["scenes"]):
            out = str(session / f"scene_{i}.mp4")
            if build_scene_clip(scene, niche["image_style"], scene_dur, out):
                clips.append(out)
                print(f"  ✅ Scene {i+1}")
        if not clips:
            raise Exception("All scene generation failed")

        pipeline_status["step"] = "Generating background music..."
        pipeline_status["step_index"] = 4
        music_p = str(session / "music.mp3")
        if not generate_music(niche["music_prompt"], music_p):
            music_p = None

        pipeline_status["step"] = "Assembling final video..."
        pipeline_status["step_index"] = 5
        final_p = str(session / "final.mp4")
        assemble_video(clips, voice_p, music_p, srt_p, final_p)

        pipeline_status["step"] = "Uploading to YouTube..."
        pipeline_status["step_index"] = 6
        video_id = upload_youtube(final_p, data)
        url = f"https://youtube.com/shorts/{video_id}"
        print(f"✅ Live: {url}")

        pipeline_status["step"] = "Done!"
        pipeline_status["step_index"] = 7
        log = json.loads(LOG_FILE.read_text()) if LOG_FILE.exists() else []
        entry = {
            "timestamp": ts, "video_id": video_id,
            "title": data["title"], "niche": niche_key, "url": url,
        }
        log.append(entry)
        LOG_FILE.write_text(json.dumps(log, indent=2))
        pipeline_status["last_result"] = entry

    except Exception as e:
        pipeline_status["error"] = str(e)
        print(f"❌ Error: {e}")
        import traceback; traceback.print_exc()
    finally:
        pipeline_status["running"] = False
        shutil.rmtree(str(session), ignore_errors=True)


# ── API ROUTES ────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "service": "KidsContent.ai API v2.2"}


@app.post("/run")
async def run_pipeline_endpoint(req: RunRequest, background_tasks: BackgroundTasks):
    if pipeline_status["running"]:
        raise HTTPException(status_code=409, detail="Pipeline already running")
    niches = req.enabled_niches or list(NICHES.keys())
    background_tasks.add_task(full_pipeline, niches)
    return {"status": "started"}


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
    return {k: {"label": v["label"], "icon": v["icon"], "weight": v["weight"]}
            for k, v in NICHES.items()}


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
