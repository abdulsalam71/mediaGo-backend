import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from parser import parse_media_info
from proxy import proxy_download

app = FastAPI(
    title="vidGo Media Downloader Backend",
    description="FastAPI + yt-dlp backend mimicking SaveFrom.net logic",
    version="1.0.0"
)

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class InfoRequest(BaseModel):
    url: str

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "vidGo Downloader Backend",
        "endpoints": {
            "info": "POST /api/info",
            "proxy": "GET /api/proxy"
        }
    }

@app.post("/api/info")
async def get_info(request: InfoRequest):
    """
    Extracts video information and lists direct download links categorized by quality.
    """
    if not request.url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    
    try:
        info = parse_media_info(request.url)
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy")
async def get_proxy(
    url: str = Query(..., description="The direct media stream URL to proxy"),
    filename: str = Query(None, description="Optional filename for content-disposition header")
):
    """
    Tunnels download traffic from the source CDN to the mobile device.
    Uses 0MB storage.
    """
    if not url:
        raise HTTPException(status_code=400, detail="url parameter is required")
        
    return await proxy_download(url, filename)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
