# app/settings.py
import os
from pathlib import Path

# Load .env if present (safe no-op in prod Docker)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# ----- Paths -----
# project/
# ├─ app/
# ├─ cookies/
# ├─ logs/
# └─ tmp/
BASE_DIR: Path = Path(__file__).resolve().parents[1]

def _path_from_env(name: str, default: Path) -> Path:
    v = os.getenv(name)
    return Path(v) if v else default

TMP_ROOT: Path = _path_from_env("TMP_ROOT", BASE_DIR / "tmp")
LOGS_DIR: Path = _path_from_env("LOGS_DIR", BASE_DIR / "logs")

# Cookies file (support both env names). If not found, leave empty string.
_cookie_env = os.getenv("COOKIES_FILE") or os.getenv("YTMUSIC_COOKIES")
_default_cookie = BASE_DIR / "cookies" / "music_youtube_cookies1.txt"
if _cookie_env and Path(_cookie_env).is_file():
    COOKIES_FILE: str = _cookie_env
elif _default_cookie.is_file():
    COOKIES_FILE = str(_default_cookie)
else:
    COOKIES_FILE = ""  # downloader will gracefully skip cookies

# ----- Server -----
HOST: str = os.getenv("HOST", "0.0.0.0")  # 0.0.0.0 for Docker/Render
PORT: int = int(os.getenv("PORT", "8080"))  # many PaaS expect $PORT

# Background cleanup (minutes)
CLEANUP_TTL_MIN: int = int(os.getenv("CLEANUP_TTL_MIN", "60"))

# ----- spotDL defaults (can be overridden per-request or via env) -----
# Keep sensible, fast defaults; downloader may ignore some of these depending on strategy.
SPOTDL_AUDIO_SOURCE: str = os.getenv("SPOTDL_AUDIO_SOURCE", "youtube-music")
SPOTDL_FORMAT: str = os.getenv("SPOTDL_FORMAT", "mp3")      # UI may override
SPOTDL_BITRATE: str = os.getenv("SPOTDL_BITRATE", "256k")   # "disable" to avoid re-encode

# Ensure runtime dirs exist
for d in (TMP_ROOT, LOGS_DIR):
    d.mkdir(parents=True, exist_ok=True)
