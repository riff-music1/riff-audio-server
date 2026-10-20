from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import yt_dlp

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"status": "RIFF Audio Engine Online"}

@app.get("/stream")
def get_stream(id: str):
    if not id:
        raise HTTPException(status_code=400, detail="Video ID is required")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={id}", download=False)
            audio_url = info.get('url')
            if not audio_url:
                raise HTTPException(status_code=404, detail="Audio stream not found")
            return {
                "title": info.get('title'),
                "duration": info.get('duration'),
                "url": audio_url
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
