import os
import re
import urllib.parse
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_title(title: str) -> str:
    t = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    t = re.sub(r'(?i)(official video|music video|full video|lyrics|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup|visualizer)', '', t)
    return t.strip()

def get_youtube_title(video_id: str) -> str:
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            return res.json().get('title', '')
    except Exception:
        pass
    return ""

def get_saavn_stream(query: str):
    if not query:
        return None
    endpoints = [
        f"https://saavn.dev/api/search/songs?query={urllib.parse.quote(query)}",
        f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={urllib.parse.quote(query)}"
    ]
    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=5)
            if res.status_code == 200:
                data = res.json()
                results = data.get('data', {}).get('results', []) or data.get('results', [])
                if results:
                    download_urls = results[0].get('downloadUrl', [])
                    if download_urls:
                        url = download_urls[-1].get('url') or download_urls[-1].get('link')
                        if url:
                            return {
                                "title": results[0].get('name') or query,
                                "url": url,
                                "duration": int(results[0].get('duration', 240)),
                                "source": "jiosaavn-320kbps"
                            }
        except Exception:
            continue
    return None

def get_proxy_stream(video_id: str):
    piped_instances = [
        f"https://api.piped.private.coffee/streams/{video_id}",
        f"https://pipedapi.kavin.rocks/streams/{video_id}",
        f"https://pipedapi.tokhmi.xyz/streams/{video_id}"
    ]
    for inst in piped_instances:
        try:
            r = requests.get(inst, timeout=4)
            if r.status_code == 200:
                data = r.json()
                streams = data.get("audioStreams", [])
                if streams:
                    best = sorted(streams, key=lambda x: x.get('bitrate', 0), reverse=True)[0]
                    return {
                        "title": data.get("title", ""),
                        "url": best.get("url"),
                        "duration": data.get("duration", 240),
                        "source": "piped-stream"
                    }
        except Exception:
            continue

    invidious_instances = [
        f"https://invidious.nerdvpn.de/api/v1/videos/{video_id}?local=true",
        f"https://inv.nadeko.net/api/v1/videos/{video_id}?local=true"
    ]
    for inst in invidious_instances:
        try:
            r = requests.get(inst, timeout=4)
            if r.status_code == 200:
                data = r.json()
                formats = [f for f in data.get("adaptiveFormats", []) if f.get("type", "").startswith("audio")]
                if formats:
                    return {
                        "title": data.get("title", ""),
                        "url": formats[0].get("url"),
                        "duration": data.get("lengthSeconds", 240),
                        "source": "invidious-stream"
                    }
        except Exception:
            continue
    return None

@app.get("/")
def root():
    return {"status": "RIFF Audio Engine Online"}

@app.get("/stream")
def stream_audio(id: str):
    if not id:
        raise HTTPException(status_code=400, detail="Video ID is required")

    # 1. Clean title se JioSaavn 320kbps full song check (Fastest, zero bot block)
    raw_title = get_youtube_title(id)
    if raw_title:
        cleaned = clean_title(raw_title)
        res = get_saavn_stream(cleaned)
        if res:
            return res

    # 2. Piped / Invidious unblocked audio streams
    stream = get_proxy_stream(id)
    if stream:
        return stream

    # 3. Raw title fallback
    if raw_title:
        res = get_saavn_stream(raw_title)
        if res:
            return res

    # 4. Zero-failure fallback taake app kabhi crash na ho
    return {
        "title": raw_title or "RIFF Music Stream",
        "url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "duration": 372,
        "source": "backup-stream"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
