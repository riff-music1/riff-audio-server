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

def clean_song_query(title: str) -> str:
    # Brackets aur extra text remove karein
    t = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    t = re.sub(r'(?i)(official video|music video|full video|lyrics|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup|visualizer|feat\.|ft\.|featuring)', '', t)
    t = re.sub(r'[-_~|/\\&]', ' ', t)
    return ' '.join(t.split())

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
                                "source": "jiosaavn-320kbps-full"
                            }
        except Exception:
            continue
    return None

def get_direct_piped_url(video_id: str) -> str:
    mirrors = [
        f"https://api.piped.private.coffee/streams/{video_id}",
        f"https://pipedapi.kavin.rocks/streams/{video_id}",
        f"https://pipedapi.tokhmi.xyz/streams/{video_id}"
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
    return {"status": "RIFF Audio Engine Online"}

# Server-side Relay: YouTube audio bytes ko bina IP lock ke client ko stream karta hai
@app.get("/audio")
def stream_audio_relay(id: str, request: Request):
    stream_url = get_direct_piped_url(id)
    if not stream_url:
        raise HTTPException(status_code=404, detail="Audio source not available")

    req_headers = {'User-Agent': 'Mozilla/5.0'}
    if 'range' in request.headers:
        req_headers['Range'] = request.headers['range']

    try:
        r = requests.get(stream_url, headers=req_headers, stream=True, timeout=10)
        res_headers = {
            'Accept-Ranges': 'bytes',
            'Content-Type': r.headers.get('content-type', 'audio/mp4'),
        }
        if 'content-range' in r.headers:
            res_headers['Content-Range'] = r.headers['content-range']
        if 'content-length' in r.headers:
            res_headers['Content-Length'] = r.headers['content-length']

        return StreamingResponse(
            r.iter_content(chunk_size=65536),
            status_code=r.status_code,
            headers=res_headers
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stream")
def get_stream(id: str, request: Request):
    if not id:
        raise HTTPException(status_code=400, detail="Video ID is required")

    # 1. First Tier: JioSaavn 320kbps Full Song (Fastest, unblocked, direct full length)
    yt_title = get_youtube_title(id)
    if yt_title:
        cleaned = clean_song_query(yt_title)
        saavn_res = get_saavn_stream(cleaned)
        if saavn_res:
            return saavn_res
        
        # Agar query lambi thi to first 3 words se search karein
        parts = cleaned.split()
        if len(parts) > 2:
            short_res = get_saavn_stream(" ".join(parts[:3]))
            if short_res:
                return short_res

    # 2. Second Tier: Railway Audio Relay (Google IP block ko bypass karke direct stream karega)
    host = request.headers.get("host", "riff-audio-server-production.up.railway.app")
    relay_url = f"https://{host}/audio?id={id}"
    return {
        "title": yt_title or "RIFF Audio Track",
        "url": relay_url,
        "duration": 240,
        "source": "railway-relay-full"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
