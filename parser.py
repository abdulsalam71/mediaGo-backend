import yt_dlp
from typing import Dict, Any, List

def parse_media_info(url: str) -> Dict[str, Any]:
    """
    Extracts media information and filters video and audio formats.
    """
    ydl_opts = {
        'skip_download': True,
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'clients': ['android', 'ios']
            }
        }
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=False)
        except Exception as e:
            raise Exception(f"yt-dlp extraction failed: {str(e)}")

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
                "format_id": f.get('format_id'),
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
                    "format_id": f.get('format_id'),
                    "quality": quality_label,
                    "ext": ext,
                    "size_bytes": size,
                    "has_audio": not is_video_only,
                    "url": direct_url
                })

    # Sort video qualities descending (e.g. 1080p, 720p, etc)
    video_formats.sort(key=lambda x: int(x['quality'].replace('p', '')) if x['quality'].replace('p', '').isdigit() else 0, reverse=True)
    
    # Sort audio qualities descending (e.g. 320kbps, 128kbps, etc)
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
