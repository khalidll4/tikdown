import re

TIKTOK_URL_PATTERNS = [
    r"https?://(www\.)?tiktok\.com/@[\w.]+/video/\d+",
    r"https?://vm\.tiktok\.com/[\w]+/?",
    r"https?://vt\.tiktok\.com/[\w]+/?",
    r"https?://m\.tiktok\.com/v/\d+\.html",
]

_compiled = [re.compile(p) for p in TIKTOK_URL_PATTERNS]


def validate_tiktok_url(url: str) -> tuple[bool, str]:
    """
    Validate a TikTok URL and return (is_valid, cleaned_url).
    cleaned_url strips trailing whitespace/newlines.
    """
    if not url or not isinstance(url, str):
        return False, ""

    cleaned = url.strip()

    for pattern in _compiled:
        if pattern.match(cleaned):
            return True, cleaned

    return False, cleaned
