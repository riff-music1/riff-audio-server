from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp
import requests
import re
import urllib.parse

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_song_title(title: str) -> str:
    cleaned = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    cleaned = re.sub(r'(?i)(official video|music video|full video|lyrics|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup)', '', cleaned)
    return cleaned.strip()

def fetch_saavn_stream(query: str):
    try:
        url = f"https://saavn.dev/api/search/songs?query={urllib.parse.quote(query)}"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            results = data.get('data', {}).get('results', []) or data.get('results', [])
            if results:
                download_urls = results[0].get('downloadUrl', [])
                if download_urls:
                    return download_urls[-1].get('url') or download_urls[-1].get('link')
    except Exception:
        pass
    return None

def fetch_youtube_title(video_id: str):
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        res = requests.get(oembed_url, timeout=4)
        if res.status_code == 200:
            return res.json().get('title')
    except Exception:
        pass
    return None

@app.get("/")
def home():
    return {"status": "RIFF Audio Engine Online"}

@app.get("/stream")
def get_stream(id: str):
    if not id:
        raise HTTPException(status_code=400, detail="Video ID is required")
    
    # 1. Tier 1: YouTube Title + JioSaavn 320kbps Full Song (Fastest, zero blocking, 100% full length)
    yt_title = fetch_youtube_title(id)
    if yt_title:
        clean_name = clean_song_title(yt_title)
        saavn_url = fetch_saavn_stream(clean_name)
        if saavn_url:
            return {
                "title": yt_title,
                "url": saavn_url,
                "duration": 240,
                "source": "saavn-320kbps-full"
            }

    # 2. Tier 2: yt-dlp with Android/iOS Client Spoofing
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'ios'],
            }
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={id}", download=False)
            audio_url = info.get('url')
            if audio_url:
                return {
                    "title": info.get('title'),
                    "duration": info.get('duration', 240),
                    "url": audio_url,
                    "source": "yt-direct"
                }
    except Exception:
        pass

    # 3. Tier 3: Invidious / Piped Mirrors
    mirrors = [
        f"https://api.piped.private.coffee/streams/{id}",
        f"https://invidious.nerdvpn.de/api/v1/videos/{id}?local=true"
    ]
    for mirror in mirrors:
        try:
            r = requests.get(mirror, timeout=4)
            if r.status_code == 200:
                data = r.json()
                if "audioStreams" in data and data["audioStreams"]:
                    return {"title": data.get("title"), "url": data["audioStreams"][0]["url"], "duration": 240, "source": "piped"}
                if "adaptiveFormats" in data:
                    audio_formats = [f for f in data["adaptiveFormats"] if f.get("type", "").startswith("audio")]
                    if audio_formats:
                        return {"title": data.get("title"), "url": audio_formats[0]["url"], "duration": 240, "source": "invidious"}
        except Exception:
            continue

    raise HTTPException(status_code=404, detail="Audio stream not found")
