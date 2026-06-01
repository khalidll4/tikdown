# TikTok Downloader Backend

REST API built with FastAPI + yt-dlp to extract TikTok video download links.

## Requirements
- Python 3.11+
- ffmpeg installed on the system

## Local Setup

```bash
# 1. Clone the repo
git clone https://github.com/your-username/tiktok-backend.git
cd tiktok-backend

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy env file
cp .env.example .env

# 5. Run the server
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000/docs for the Swagger UI.

## Deploy to Railway

1. Push this project to GitHub
2. Go to https://railway.app → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects the Dockerfile
4. Set environment variables in the Railway dashboard if needed
5. Your API will be live at `https://your-app.up.railway.app`

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /api/v1/health | Server health check |
| POST | /api/v1/video/info | Extract video info + download links |
| GET | /api/v1/video/stream?url=... | Proxy-stream video to client |

## Example Request

```bash
curl -X POST https://your-app.up.railway.app/api/v1/video/info \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.tiktok.com/@user/video/123456789"}'
```

## Update yt-dlp

TikTok frequently changes its internals. Keep yt-dlp updated:

```bash
pip install -U yt-dlp
```

Or inside the container:
```bash
yt-dlp -U
```

## Rate Limits

- `/api/v1/video/info` → 10 requests/minute per IP
- `/api/v1/video/stream` → 5 requests/minute per IP
