import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from slowapi.errors import RateLimitExceeded

from middleware.rate_limiter import limiter
from models.schemas import ErrorResponse, VideoRequest, VideoResponse
from services.ytdlp_service import VideoExtractionError, get_video_info
from utils.validators import validate_tiktok_url

router = APIRouter(prefix="/api/v1")

MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.post(
    "/video/info",
    response_model=VideoResponse,
    responses={400: {"model": ErrorResponse}, 422: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def video_info(request: Request, body: VideoRequest):
    is_valid, cleaned_url = validate_tiktok_url(body.url)
    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error_code="INVALID_URL",
                message="The provided URL is not a valid TikTok URL.",
            ).model_dump(),
        )

    try:
        result = await get_video_info(cleaned_url)
        return result
    except VideoExtractionError as exc:
        status = 404 if exc.error_code in ("VIDEO_PRIVATE", "VIDEO_UNAVAILABLE") else 502
        raise HTTPException(
            status_code=status,
            detail=ErrorResponse(error_code=exc.error_code, message=exc.message).model_dump(),
        )


@router.get("/video/stream")
@limiter.limit("5/minute")
async def stream_video(request: Request, url: str, filename: str = "video.mp4"):
    """
    Proxy-stream a TikTok CDN video URL to the client.
    Supports Range header for resumable downloads.
    """
    try:
        decoded_url = urllib.parse.unquote(url)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid URL encoding.")

    range_header = request.headers.get("Range")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Mobile Safari/537.36"
        ),
        "Referer": "https://www.tiktok.com/",
    }
    if range_header:
        headers["Range"] = range_header

    async def stream_chunks(client: httpx.AsyncClient, response: httpx.Response):
        async for chunk in response.aiter_bytes(chunk_size=65536):
            yield chunk

    try:
        client = httpx.AsyncClient(timeout=30, follow_redirects=True)
        upstream = await client.send(
            client.build_request("GET", decoded_url, headers=headers),
            stream=True,
        )

        content_length = int(upstream.headers.get("Content-Length", 0))
        if content_length > MAX_FILE_SIZE_BYTES:
            await upstream.aclose()
            await client.aclose()
            raise HTTPException(status_code=413, detail="File too large.")

        response_headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": upstream.headers.get("Content-Type", "video/mp4"),
            "Accept-Ranges": "bytes",
            "X-Content-Type-Options": "nosniff",
        }
        if "Content-Length" in upstream.headers:
            response_headers["Content-Length"] = upstream.headers["Content-Length"]
        if "Content-Range" in upstream.headers:
            response_headers["Content-Range"] = upstream.headers["Content-Range"]

        status_code = upstream.status_code

        return StreamingResponse(
            stream_chunks(client, upstream),
            status_code=status_code,
            headers=response_headers,
        )

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream request timed out.")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Failed to reach upstream: {exc}")
