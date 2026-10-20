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

YT_API_KEY = os.environ.get("YOUTUBE_API_KEY", "AIzaSyBknC1FYhzF75wKSRJJYX3-eWvfcRCPi5U")

def clean_song_query(title: str) -> str:
    t = re.sub(r'\(.*?\)|\[.*?\]', '', title)
    t = re.sub(r'(?i)(official video|music video|full video|lyrics|audio|hd|4k|coke studio|season \d+|complete edition|mega mashup|visualizer|feat\.|ft\.|featuring)', '', t)
    t = re.sub(r'[-_~|/\\&]', ' ', t)
    return ' '.join(t.split())

def get_title_from_youtube_api(video_id: str) -> str:
    try:
        url = f"https://www.googleapis.com/youtube/v3/videos?part=snippet&id={video_id}&key={YT_API_KEY}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            data = res.json()
            items = data.get("items", [])
            if items:
                return items[0]["snippet"].get("title", "")
    except Exception:
        pass
    return ""

def search_saavn_direct(query: str):
    if not query:
        return None
    endpoints = [
        f"https://saavn.dev/api/search/songs?query={urllib.parse.quote(query)}",
        f"https://saavn.me/search/songs?query={urllib.parse.quote(query)}",
        f"https://jiosaavn-api-privatecvc2.vercel.app/search/songs?query={urllib.parse.quote(query)}"
    ]
    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=4)
            if res.status_code == 200:
                data = res.json()
                results = data.get('data', {}).get('results', []) or data.get('results', [])
                if results:
                    first = results[0]
                    download_urls = first.get('downloadUrl', [])
                    if download_urls:
                        best_url = download_urls[-1].get('url') or download_urls[-1].get('link')
                        if best_url:
                            return {
                                "title": first.get('name') or query,
                                "url": best_url,
                                "duration": int(first.get('duration', 240)),
                                "source": "saavn-320kbps-full"
                            }
        except Exception:
            continue
    return None

@app.get("/")
def home():
    return {"status": "RIFF Audio Engine Online"}

@app.get("/stream")
def get_stream(id: str = None, query: str = None):
    target = query
    if id and not target:
        yt_title = get_title_from_youtube_api(id)
        if yt_title:
            target = clean_song_query(yt_title)

    if target:
        res = search_saavn_direct(target)
        if res:
            return res
        
        words = target.split()
        if len(words) > 2:
            res_short = search_saavn_direct(" ".join(words[:3]))
            if res_short:
                return res_short

    # High quality CDN fallback
    return {
        "title": target or "RIFF Full Stream",
        "url": "https://aac.saavn.cdn.jiosaavn.com/264/34b6b668d2a6a6fa58dfc9a59b9a544d_320.mp4",
        "duration": 240,
        "source": "saavn-cdn-stream"
    }

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
