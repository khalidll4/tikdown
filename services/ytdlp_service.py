import asyncio
import time
from concurrent.futures import ThreadPoolExecutor

import yt_dlp
from yt_dlp.utils import DownloadError, ExtractorError

from models.schemas import AuthorInfo, DownloadLink, VideoInfo, VideoResponse

_executor = ThreadPoolExecutor(max_workers=4)

YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": False,
    "skip_download": True,
    "cookiefile": None,
    "socket_timeout": 15,
    "retries": 3,
    "format": "bestvideo+bestaudio/best",
    "noplaylist": True,
}

QUALITY_THRESHOLDS = {
    "1080p": 1080,
    "720p": 720,
    "480p": 480,
    "360p": 360,
}


def _extract_info(url: str) -> dict:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        return ydl.extract_info(url, download=False)


def _pick_best_formats(formats: list[dict]) -> list[DownloadLink]:
    """
    Group formats by quality tier and pick the best mp4 for each tier.
    Also adds an audio_only option if available.
    """
    tiers: dict[str, dict] = {}

    for fmt in formats:
        height = fmt.get("height") or 0
        ext = fmt.get("ext", "")
        vcodec = fmt.get("vcodec", "none")
        acodec = fmt.get("acodec", "none")
        url = fmt.get("url", "")

        if not url:
            continue

        # Audio only
        if vcodec == "none" and acodec != "none":
            existing = tiers.get("audio_only")
            abr = fmt.get("abr") or 0
            if not existing or abr > (existing.get("abr") or 0):
                tiers["audio_only"] = fmt
            continue

        # Video formats
        for label, threshold in QUALITY_THRESHOLDS.items():
            if height >= threshold:
                existing = tiers.get(label)
                if not existing:
                    tiers[label] = fmt
                else:
                    # Prefer mp4, then higher filesize
                    existing_is_mp4 = existing.get("ext") == "mp4"
                    current_is_mp4 = ext == "mp4"
                    if current_is_mp4 and not existing_is_mp4:
                        tiers[label] = fmt
                    elif current_is_mp4 == existing_is_mp4:
                        if (fmt.get("filesize") or 0) > (existing.get("filesize") or 0):
                            tiers[label] = fmt
                break

    links = []
    for quality, fmt in tiers.items():
        links.append(
            DownloadLink(
                quality=quality,
                url=fmt["url"],
                ext=fmt.get("ext", "mp4"),
                filesize=fmt.get("filesize") or fmt.get("filesize_approx"),
            )
        )

    # Sort: 1080p first, audio_only last
    order = ["1080p", "720p", "480p", "360p", "audio_only"]
    links.sort(key=lambda x: order.index(x.quality) if x.quality in order else 99)
    return links


def _map_error(exc: Exception) -> tuple[str, str]:
    msg = str(exc).lower()
    if isinstance(exc, DownloadError):
        if "private" in msg:
            return "VIDEO_PRIVATE", "This video is private and cannot be accessed."
        if "not available" in msg or "unavailable" in msg:
            return "VIDEO_UNAVAILABLE", "This video is not available."
        if "timed out" in msg or "timeout" in msg:
            return "TIMEOUT", "Request timed out. Please try again."
    if isinstance(exc, ExtractorError):
        return "EXTRACTION_FAILED", "Failed to extract video information."
    return "UNKNOWN_ERROR", "An unexpected error occurred."


async def get_video_info(url: str) -> VideoResponse:
    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(_executor, _extract_info, url)
    except (DownloadError, ExtractorError, Exception) as exc:
        error_code, message = _map_error(exc)
        raise VideoExtractionError(error_code=error_code, message=message) from exc

    formats = info.get("formats") or []
    download_links = _pick_best_formats(formats)

    thumbnail = info.get("thumbnail") or ""
    uploader = info.get("uploader") or info.get("creator") or "unknown"
    uploader_id = info.get("uploader_id") or uploader

    author = AuthorInfo(
        username=uploader_id,
        display_name=uploader,
        avatar_url=None,
    )

    video_info = VideoInfo(
        title=info.get("title") or "TikTok Video",
        duration=int(info.get("duration") or 0),
        thumbnail=thumbnail,
        author=author,
        view_count=info.get("view_count"),
        like_count=info.get("like_count"),
    )

    expires_at = int(time.time()) + 6 * 3600

    return VideoResponse(
        success=True,
        video_info=video_info,
        download_links=download_links,
        expires_at=expires_at,
    )


class VideoExtractionError(Exception):
    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
