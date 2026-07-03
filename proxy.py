import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

async def proxy_download(url: str, filename: str = None) -> StreamingResponse:
    """
    Asynchronously streams data from the direct CDN URL to the client.
    Replicates headers to ensure progress tracking and MIME types match.
    """
    client = httpx.AsyncClient(follow_redirects=True)
    
    try:
        # Build stream request with standard browser headers to bypass CDN blocking
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Referer": "https://www.youtube.com/"
        }
        req = client.build_request("GET", url, headers=headers)
        response = await client.send(req, stream=True)
    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=500, detail=f"Failed to connect to source: {str(e)}")
    
    if response.status_code >= 400:
        await response.aclose()
        await client.aclose()
        raise HTTPException(status_code=response.status_code, detail=f"Source returned HTTP {response.status_code}")

    # Propagate essential headers
    headers = {}
    content_length = response.headers.get("content-length")
    content_type = response.headers.get("content-type")
    estimated_length = response.headers.get("estimated-content-length")
    
    if content_length:
        headers["content-length"] = content_length
    if content_type:
        headers["content-type"] = content_type
    if estimated_length:
        headers["estimated-content-length"] = estimated_length
        
    if filename:
        # Prevent headers parsing issues with non-ASCII filenames
        safe_filename = filename.encode('ascii', 'ignore').decode('ascii')
        headers["content-disposition"] = f'attachment; filename="{safe_filename}"'

    # Generator to stream chunks and guarantee cleanup
    async def stream_generator():
        try:
            async for chunk in response.aiter_bytes(chunk_size=16384): # 16KB chunks
                yield chunk
        finally:
            await response.aclose()
            await client.aclose()

    return StreamingResponse(stream_generator(), headers=headers)
