# app/downloader.py
# Old, fast flow (your original) + targeted yt-dlp fallback + optional transcode.
# Key fix: call yt-dlp via python -m yt_dlp so Windows never needs a PATH exe.

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

from .settings import COOKIES_FILE  # e.g. "cookies/music_youtube_cookies.txt"


class SpotdlError(Exception):
    pass


# Network step downloads MP3 (fast/stable), then we optionally transcode.
MP3_EXTS = {".mp3"}


def _collect_mp3s(out_dir: Path) -> List[Path]:
    return [p for p in out_dir.rglob("*") if p.is_file() and p.suffix.lower() in MP3_EXTS]


def _has_ffmpeg() -> bool:
    try:
        probe = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        return probe.returncode == 0
    except Exception:
        return False


def _ensure_ffmpeg_available() -> None:
    if _has_ffmpeg():
        return
    boot = subprocess.run(
        [sys.executable, "-m", "spotdl", "--download-ffmpeg"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if boot.returncode != 0:
        raise SpotdlError(f"FFmpeg bootstrap failed:\n{boot.stdout}")


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    print("spotdl CMD:", " ".join(cmd))
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _run_proc(label: str, cmd: List[str]) -> subprocess.CompletedProcess:
    print(f"{label} CMD:", " ".join(cmd))
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def _norm(u: str) -> str:
    # strip ?si=... etc.
    return u.split("?", 1)[0].strip()


_YT_URL_RE = re.compile(r"https?://(?:www\.)?(?:youtube\.com|music\.youtube\.com)/watch\?v=[\w\-]+")


def _extract_yt_url(text: str) -> Optional[str]:
    m = _YT_URL_RE.search(text or "")
    return m.group(0) if m else None


def _yt_dlp_direct_mp3(url: str, out_dir: Path) -> List[Path]:
    """
    Directly call yt-dlp to fetch bestaudio and convert to MP3 (256k-ish).
    IMPORTANT: invoke via `python -m yt_dlp` so Windows never needs PATH.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cookies sources
    opera_profile = os.path.join(os.environ.get("APPDATA", ""), "Opera Software", "Opera GX Stable")
    have_opera_live = os.path.isdir(opera_profile)
    cookie_file = Path(COOKIES_FILE)
    have_cookie_file = cookie_file.is_file()

    # Base args (stable on YT / YT Music)
    base = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio/best",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "--no-playlist",
        "--add-metadata", "--embed-thumbnail",
        "--force-ipv4",
        "--concurrent-fragments", "4",
        "--http-chunk-size", "16M",
        "--extractor-args", "youtube:player_client=android,web_safari",
        "--user-agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
        "-o", str(out_dir / "%(title)s.%(ext)s"),
        url,
    ]

    # Try: Opera live cookies -> cookie file -> no cookies
    if have_opera_live:
        cmd = base.copy()
        cmd[cmd.index("-o"):cmd.index("-o")+2]  # ensure indices exist (no-op)
        cmd[2:2] = ["--cookies-from-browser", f"opera:{opera_profile}"]
        proc = _run_proc("yt-dlp (opera cookies)", cmd)
        if proc.returncode == 0:
            mp3s = _collect_mp3s(out_dir)
            if mp3s:
                return mp3s

    if have_cookie_file:
        cmd = base.copy()
        cmd[2:2] = ["--cookies", str(cookie_file)]
        proc = _run_proc("yt-dlp (cookie file)", cmd)
        if proc.returncode == 0:
            mp3s = _collect_mp3s(out_dir)
            if mp3s:
                return mp3s

    # No cookies
    cmd = base.copy()
    proc = _run_proc("yt-dlp (no cookies)", cmd)
    if proc.returncode == 0:
        mp3s = _collect_mp3s(out_dir)
        if mp3s:
            return mp3s

    raise SpotdlError("yt-dlp direct fallback failed.\n" + proc.stdout)


def run_spotdl(urls: List[str], out_dir: Path) -> List[Path]:
    """
    Your previous working strategy (MP3 @ 256k) with a *targeted* yt-dlp fallback:
    if spotDL exits 0 but writes no files and prints a YT/YTM URL, download it directly.
    """
    if not urls:
        raise SpotdlError("No URLs provided.")
    _ensure_ffmpeg_available()
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = [_norm(u) for u in urls]

    # yt-dlp args must be ONE token after '='
    ytargs_fast = '--force-ipv4 --concurrent-fragments 4 --http-chunk-size 16M --extractor-args "youtube:player_client=android"'
    ytargs_slow = '--force-ipv4 --http-chunk-size 4M --extractor-args "youtube:player_client=android"'

    # Live Opera GX cookies (no manual export)
    opera_profile = os.path.join(os.environ.get("APPDATA", ""), "Opera Software", "Opera GX Stable")
    have_opera_live = os.path.isdir(opera_profile)
    ytargs_opera = (
        f'--cookies-from-browser "opera:{opera_profile}" '
        f'--force-ipv4 --concurrent-fragments 4 --http-chunk-size 16M '
        f'--extractor-args "youtube:player_client=android,web_safari"'
    )

    cookies_file = Path(COOKIES_FILE)
    have_cookie_file = cookies_file.is_file()

    attempts: List[tuple[str, List[str]]] = []

    # 0) YT-Music + Opera GX live cookies
    if have_opera_live:
        attempts.append((
            "ytmusic + operaGX-live (mp3 256k)",
            [sys.executable, "-m", "spotdl",
             "--audio", "youtube-music",
             "--format", "mp3",
             "--bitrate", "256k",
             f"--yt-dlp-args={ytargs_opera}",
             "--output", str(out_dir),
             "--threads", "2",
             "download"] + urls
        ))

    # 1) YouTube + Opera GX live cookies (android client)
    if have_opera_live:
        attempts.append((
            "youtube + operaGX-live (mp3 256k, android)",
            [sys.executable, "-m", "spotdl",
             "--audio", "youtube",
             "--format", "mp3",
             "--bitrate", "256k",
             "--dont-filter-results",
             "--search-query", "{artists} {title} audio",
             f"--yt-dlp-args={ytargs_opera}",
             "--output", str(out_dir),
             "--threads", "2",
             "download"] + urls
        ))

    # 2) YT-Music + cookie file (fast/slow)
    if have_cookie_file:
        attempts.append((
            "ytmusic + cookie-file (mp3 256k fast)",
            [sys.executable, "-m", "spotdl",
             "--audio", "youtube-music",
             "--format", "mp3",
             "--bitrate", "256k",
             f"--yt-dlp-args={ytargs_fast}",
             "--cookie-file", str(cookies_file),
             "--output", str(out_dir),
             "--threads", "2",
             "download"] + urls
        ))
        attempts.append((
            "ytmusic + cookie-file (mp3 256k slow)",
            [sys.executable, "-m", "spotdl",
             "--audio", "youtube-music",
             "--format", "mp3",
             "--bitrate", "256k",
             f"--yt-dlp-args={ytargs_slow}",
             "--cookie-file", str(cookies_file),
             "--output", str(out_dir),
             "--threads", "2",
             "download"] + urls
        ))

    # 3) YouTube + cookie file (android)
    if have_cookie_file:
        attempts.append((
            "youtube + cookie-file (mp3 256k, android)",
            [sys.executable, "-m", "spotdl",
             "--audio", "youtube",
             "--format", "mp3",
             "--bitrate", "256k",
             "--dont-filter-results",
             "--search-query", "{artists} {title} audio",
             f"--yt-dlp-args={ytargs_fast}",
             "--cookie-file", str(cookies_file),
             "--output", str(out_dir),
             "--threads", "2",
             "download"] + urls
        ))

    # 4) YouTube no cookies (android)
    attempts.append((
        "youtube no cookies (mp3 256k, android)",
        [sys.executable, "-m", "spotdl",
         "--audio", "youtube",
         "--format", "mp3",
         "--bitrate", "256k",
         "--dont-filter-results",
         "--search-query", "{artists} {title} audio",
         f"--yt-dlp-args={ytargs_fast}",
         "--output", str(out_dir),
         "--threads", "2",
         "download"] + urls
    ))

    errors: List[str] = []
    extracted_urls: List[str] = []

    for label, cmd in attempts:
        proc = _run(cmd)
        if proc.returncode == 0:
            files = _collect_mp3s(out_dir)
            if files:
                return files

            # Try direct yt-dlp on the URL spotDL printed
            yt_url = _extract_yt_url(proc.stdout)
            if yt_url:
                extracted_urls.append(yt_url)
                try:
                    mp3s = _yt_dlp_direct_mp3(yt_url, out_dir)
                    if mp3s:
                        return mp3s
                except SpotdlError:
                    pass  # accumulate error below

            errors.append(f"[{label}] success exit code but no files.\n{proc.stdout}")
        else:
            errors.append(f"[{label}] failed\n{proc.stdout}")

    # Last try: direct yt-dlp once more if we ever saw a URL
    if extracted_urls:
        try:
            mp3s = _yt_dlp_direct_mp3(extracted_urls[0], out_dir)
            if mp3s:
                return mp3s
        except SpotdlError as e:
            errors.append(f"[final yt-dlp fallback] failed\n{e}")

    raise SpotdlError("All providers failed.\n\n" + "\n\n".join(errors))


# ---------- Optional local transcode (after download) ----------

_ALLOWED_OUT = {"mp3", "m4a", "opus", "flac", "wav", "ogg"}

def convert_to_format(files: List[Path], target_fmt: str, out_base: Path) -> List[Path]:
    """
    Convert the given MP3 files to target_fmt using ffmpeg.
    Returns list of converted files (same order).
    """
    target_fmt = (target_fmt or "mp3").lower().strip()
    if target_fmt not in _ALLOWED_OUT:
        target_fmt = "mp3"

    if target_fmt == "mp3":
        return files

    _ensure_ffmpeg_available()

    out_dir = (out_base / f"converted_{target_fmt}")
    out_dir.mkdir(parents=True, exist_ok=True)

    converted: List[Path] = []
    for src in files:
        base = src.stem
        dst = out_dir / f"{base}.{target_fmt}"

        if target_fmt == "m4a":
            args = ["-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart"]
        elif target_fmt == "opus":
            args = ["-c:a", "libopus", "-b:a", "160k"]
        elif target_fmt == "flac":
            args = ["-c:a", "flac"]
        elif target_fmt == "wav":
            args = ["-c:a", "pcm_s16le"]
        elif target_fmt == "ogg":
            args = ["-c:a", "libvorbis", "-q:a", "5"]
        else:
            args = ["-c:a", "libmp3lame", "-b:a", "256k"]

        cmd = [
            "ffmpeg", "-y",
            "-i", str(src),
            "-vn",
            "-map_metadata", "0",
            "-loglevel", "error",
        ] + args + [str(dst)]

        proc = _run_proc("ffmpeg", cmd)
        if proc.returncode != 0 or not dst.exists() or dst.stat().st_size == 0:
            raise SpotdlError(f"FFmpeg transcode failed for {src.name} -> {dst.name}\n{proc.stdout}")

        converted.append(dst)

    return converted
