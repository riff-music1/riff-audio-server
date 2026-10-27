import os
import re
import urllib.parse
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
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

def clean_text(text: str) -> str:
    if not text:
        return ""
    # Brackets aur unke andar ka text remove karein
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', text)
    # Extra keywords remove karein
    t = re.sub(r'(?i)(official video|music video|full video|full song|lyrics|lyrical|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup|visualizer|feat\.|ft\.|featuring)', ' ', t)
    # Special characters ko space banayein
    t = re.sub(r'[-_~|/\\&:]', ' ', t)
    return ' '.join(t.split())

def query_saavn_direct(query: str):
    if not query or len(query.strip()) < 2:
        return None
    
    encoded = urllib.parse.quote(query.strip())
    endpoints = [
        f"https://saavn.dev/api/search/songs?query={encoded}",
        f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={encoded}",
        f"https://saavn.sumit.co/api/search/songs?query={encoded}"
    ]
    
    for ep in endpoints:
        try:
            r = requests.get(ep, timeout=4)
            if r.status_code == 200:
                data = r.json()
                results = data.get('data', {}).get('results', []) or data.get('results', [])
                if isinstance(results, list) and len(results) > 0:
                    first = results[0]
                    downloads = first.get('downloadUrl', [])
                    if isinstance(downloads, list) and downloads:
                        # Highest quality CDN URL uthayein (320kbps)
                        best = downloads[-1].get('url') or downloads[-1].get('link')
                        if best:
                            return {
                                "title": first.get('name') or query,
                                "artist": first.get('artists', {}).get('primary', [{}])[0].get('name', ''),
                                "duration": int(first.get('duration', 240)),
                                "url": best,
                                "quality": "320kbps-cdn",
                                "source": "saavn-direct"
                            }
        except Exception:
            continue
    return None

def fetch_youtube_title(video_id: str) -> str:
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            return res.json().get('title', '')
    except Exception:
        pass
    return ""

def get_piped_stream_url(video_id: str) -> str:
    mirrors = [
        f"https://api.piped.private.coffee/streams/{video_id}",
        f"https://pipedapi.kavin.rocks/streams/{video_id}"
    ]
    for m in mirrors:
        try:
            r = requests.get(m, timeout=4)
            if r.status_code == 200:
                data = r.json()
                streams = data.get("audioStreams", [])
                if streams:
                    best = sorted(streams, key=lambda x: x.get('bitrate', 0), reverse=True)[0]
                    return best.get("url", "")
        except Exception:
            continue
    return ""

@app.get("/")
def home():
    return {"status": "RIFF Smart Audio Server 100% Online"}

# Server-side Relay: 403 Google IP block bypass karne ke liye
@app.get("/audio_stream")
def audio_stream(id: str, request: Request):
    if not id:
        raise HTTPException(status_code=400, detail="ID required")
    
    stream_url = get_piped_stream_url(id)
    if not stream_url:
        raise HTTPException(status_code=404, detail="Stream unavailable")

    headers = {'User-Agent': 'Mozilla/5.0'}
    if 'range' in request.headers:
        headers['Range'] = request.headers['range']

    try:
        r = requests.get(stream_url, headers=headers, stream=True, timeout=8)
        res_headers = {'Accept-Ranges': 'bytes', 'Content-Type': r.headers.get('content-type', 'audio/mp4')}
        if 'content-range' in r.headers:
            res_headers['Content-Range'] = r.headers['content-range']
        if 'content-length' in r.headers:
            res_headers['Content-Length'] = r.headers['content-length']
        return StreamingResponse(r.iter_content(chunk_size=65536), status_code=r.status_code, headers=res_headers)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
def get_stream(query: str = None, id: str = None, request: Request = None):
    # Target search string prepare karein
    raw_text = query or ""
    
    # 1. Agar video ID hai aur query nahi to YouTube title lein
    if id and not raw_text:
        raw_text = fetch_youtube_title(id)
    
    cleaned = clean_text(raw_text)
    
    # Duplicate words hatayein (maslan "295 Sidhu Sidhu" -> "295 Sidhu")
    words = cleaned.split()
    seen = set()
    deduped = []
    for w in words:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            deduped.append(w)
    smart_query = " ".join(deduped)

    # 2. Multi-tier Saavn Lookup
    # Tier A: Full smart query
    if smart_query:
        res = query_saavn_direct(smart_query)
        if res:
            return res

    # Tier B: Sirf pehle 2 ya 3 words (e.g. "Pasoori", "Kahani Suno", "295")
    if len(words) > 1:
        res = query_saavn_direct(" ".join(words[:2]))
        if res:
            return res

    # 3. Agar Saavn par na mile aur YouTube ID ho, to Server Relay Stream de dein (Zero 403 block)
    if id:
        host = request.headers.get("host", "riff-audio-server-production.up.railway.app")
        return {
            "title": raw_text or "RIFF Track",
            "url": f"https://{host}/audio_stream?id={id}",
            "duration": 240,
            "source": "server-relay-unblocked"
        }

    # 4. Fallback safe stream
    return {
        "title": "RIFF Stream",
        "url": "https://aac.saavn.cdn.jiosaavn.com/264/34b6b668d2a6a6fa58dfc9a59b9a544d_320.mp4",
        "duration": 240,
        "source": "cdn-fallback"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
