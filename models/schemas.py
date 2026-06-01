from pydantic import BaseModel


class VideoRequest(BaseModel):
    url: str


class AuthorInfo(BaseModel):
    username: str
    display_name: str
    avatar_url: str | None = None


class VideoInfo(BaseModel):
    title: str
    duration: int
    thumbnail: str
    author: AuthorInfo
    view_count: int | None = None
    like_count: int | None = None


class DownloadLink(BaseModel):
    quality: str
    url: str
    ext: str
    filesize: int | None = None


class VideoResponse(BaseModel):
    success: bool
    video_info: VideoInfo
    download_links: list[DownloadLink]
    expires_at: int


class ErrorResponse(BaseModel):
    success: bool = False
    error_code: str
    message: str
