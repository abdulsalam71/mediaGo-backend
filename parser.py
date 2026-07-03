import yt_dlp
import os
import re
import urllib.request
import json
from typing import Dict, Any, List

def extract_youtube_id(url: str) -> str:
    """
    Extracts the 11-character YouTube video ID from a URL.
    """
    match = re.search(r'(?:youtube\.com\/(?:[^\/]+\/.+\/|(?:v|e(?:mbed)?)\/|.*[?&]v=)|youtu\.be\/)([^"&?\/\s]{11})', url)
    return match.group(1) if match else ""

def parse_via_invidious(video_id: str) -> Dict[str, Any]:
    """
    Queries public Invidious API mirrors to retrieve direct streaming links.
    """
    instances = [
        "https://yewtu.be",
        "https://invidious.nerdvpn.de",
        "https://invidious.flokinet.to",
        "https://invidious.projectsegfau.lt"
    ]
    
    last_error = "Could not contact Invidious API"
    for instance in instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            req = urllib.request.Request(
                api_url, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
            video_formats = []
            audio_formats = []
            
            # formatStreams (standard pre-muxed video+audio formats)
            for f in data.get('formatStreams', []):
                direct_url = f.get('url')
                if not direct_url:
                    continue
                q = f.get('qualityLabel', '360p')
                size = int(f.get('size') or 0)
                video_formats.append({
                    "format_id": str(f.get('itag', '')),
                    "quality": q,
                    "ext": f.get('container', 'mp4'),
                    "size_bytes": size,
                    "has_audio": True,
                    "url": direct_url
                })
                
            # adaptiveFormats (separate high-res video and audio tracks)
            for f in data.get('adaptiveFormats', []):
                direct_url = f.get('url')
                if not direct_url:
                    continue
                
                size = int(f.get('size') or 0)
                type_str = f.get('type', '').lower()
                
                if 'audio' in type_str:
                    bitrate = int(f.get('bitrate') or 0) // 1000
                    audio_formats.append({
                        "format_id": str(f.get('itag', '')),
                        "quality": f"{bitrate}kbps" if bitrate > 0 else "audio",
                        "ext": f.get('container', 'm4a'),
                        "size_bytes": size,
                        "url": direct_url
                    })
                elif 'video' in type_str:
                    q = f.get('qualityLabel', 'video')
                    video_formats.append({
                        "format_id": str(f.get('itag', '')),
                        "quality": q,
                        "ext": f.get('container', 'mp4'),
                        "size_bytes": size,
                        "has_audio": False,
                        "url": direct_url
                    })

            # Sort descending
            video_formats.sort(key=lambda x: int(x['quality'].replace('p', '').split(' ')[0]) if x['quality'].replace('p', '').split(' ')[0].isdigit() else 0, reverse=True)
            audio_formats.sort(key=lambda x: int(x['quality'].replace('kbps', '')) if x['quality'].replace('kbps', '').isdigit() else 0, reverse=True)

            return {
                "title": data.get('title', 'YouTube Video'),
                "thumbnail": data.get('videoThumbnails', [{}])[0].get('url') if data.get('videoThumbnails') else None,
                "duration": data.get('lengthSeconds', 0),
                "source": "youtube",
                "formats": {
                    "video": video_formats,
                    "audio": audio_formats
                }
            }
        except Exception as e:
            print(f"Failed to query Invidious instance {instance}: {e}")
            last_error = str(e)
            continue
            
    raise Exception(f"All Invidious instances failed: {last_error}")

def parse_media_info(url: str) -> Dict[str, Any]:
    """
    Extracts media information and filters video and audio formats.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        },
        'extractor_args': {
            'youtube': {
                'clients': ['android', 'ios']
            }
        }
    }
    
    # Use cookies if provided to bypass YouTube bot verification blocks
    if os.path.exists('cookies.txt'):
        ydl_opts['cookiefile'] = 'cookies.txt'
    
    is_youtube = "youtube.com" in url.lower() or "youtu.be" in url.lower()
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            if is_youtube:
                print(f"yt-dlp YouTube extraction failed: {e}. Trying Invidious fallback...")
                yt_id = extract_youtube_id(url)
                if yt_id:
                    try:
                        return parse_via_invidious(yt_id)
                    except Exception as fallback_err:
                        print(f"Invidious fallback failed: {fallback_err}")
            raise Exception(f"Extraction failed: {str(e)}")

    if not info:
        raise Exception("Could not extract media info")

    # Group formats
    raw_formats = info.get('formats', [])
    video_formats = []
    audio_formats = []
    
    for f in raw_formats:
        # Check direct link availability
        direct_url = f.get('url')
        if not direct_url:
            continue
            
        ext = f.get('ext', 'mp4')
        size = f.get('filesize') or f.get('filesize_approx') or 0
        
        # Audio check: vcodec == 'none'
        vcodec = f.get('vcodec')
        acodec = f.get('acodec')
        
        is_audio_only = vcodec == 'none' or vcodec is None
        is_video_only = acodec == 'none' or acodec is None
        
        if is_audio_only:
            abr = f.get('abr') or 0
            quality_label = f"{int(abr)}kbps" if abr > 0 else "audio"
            audio_formats.append({
                "format_id": str(f.get('format_id', '')),
                "quality": quality_label,
                "ext": ext,
                "size_bytes": size,
                "url": direct_url
            })
        else:
            height = f.get('height') or 0
            if height > 0:
                quality_label = f"{height}p"
                video_formats.append({
                    "format_id": str(f.get('format_id', '')),
                    "quality": quality_label,
                    "ext": ext,
                    "size_bytes": size,
                    "has_audio": not is_video_only,
                    "url": direct_url
                })

    # Sort video qualities descending
    video_formats.sort(key=lambda x: int(x['quality'].replace('p', '').split(' ')[0]) if x['quality'].replace('p', '').split(' ')[0].isdigit() else 0, reverse=True)
    
    # Sort audio qualities descending
    audio_formats.sort(key=lambda x: int(x['quality'].replace('kbps', '')) if x['quality'].replace('kbps', '').isdigit() else 0, reverse=True)

    return {
        "title": info.get('title', 'Unknown Media'),
        "thumbnail": info.get('thumbnail') or (info.get('thumbnails')[0].get('url') if info.get('thumbnails') else None),
        "duration": info.get('duration') or 0,
        "source": info.get('extractor_key', 'generic').lower(),
        "formats": {
            "video": video_formats,
            "audio": audio_formats
        }
    }
