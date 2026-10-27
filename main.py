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

def clean_text(text: str) -> str:
    if not text:
        return ""
    t = re.sub(r'\(.*?\)|\[.*?\]', ' ', text)
    t = re.sub(r'(?i)(official video|music video|full video|full song|lyrics|lyrical|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup|visualizer|feat\.|ft\.|featuring)', ' ', t)
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
            r = requests.get(ep, timeout=5)
            if r.status_code == 200:
                data = r.json()
                results = data.get('data', {}).get('results', []) or data.get('results', [])
                if isinstance(results, list) and len(results) > 0:
                    first = results[0]
                    downloads = first.get('downloadUrl', [])
                    if isinstance(downloads, list) and downloads:
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
    if not video_id or len(video_id) != 11:
        return ""
    try:
        url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            return res.json().get('title', '')
    except Exception:
        pass
    return ""

@app.get("/")
def home():
    return {"status": "RIFF Audio Server 100% Online"}

@app.get("/stream")
def get_stream(query: str = "", id: str = ""):
    target = query.strip()
    
    if not target and id and len(id) == 11:
        yt_title = fetch_youtube_title(id)
        if yt_title:
            target = yt_title

    cleaned = clean_text(target)
    if cleaned:
        res = query_saavn_direct(cleaned)
        if res:
            return res

        words = cleaned.split()
        if len(words) > 1:
            res_short = query_saavn_direct(" ".join(words[:2]))
            if res_short:
                return res_short

    return {
        "title": target or "RIFF Track",
        "url": "https://aac.saavn.cdn.jiosaavn.com/264/34b6b668d2a6a6fa58dfc9a59b9a544d_320.mp4",
        "duration": 240,
        "source": "saavn-cdn"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
