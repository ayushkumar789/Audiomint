# spotify_downloader (Windows, PyCharm)

## Python version (IMPORTANT)
spotDL 4.3.0 requires Python **>=3.9 and <3.14**. Use **Python 3.13.5** for this project.  
Source: PyPI metadata.  

## Setup
1) Install Python 3.13.5 (x64) and add to PATH.  
2) In PyCharm, create a **virtualenv** using Python 3.13.5 for this project.  
3) `pip install -r requirements.txt`

### FFmpeg
- Option A: Install FFmpeg and add to PATH.
- Option B: Let spotDL auto-install a local copy (the app triggers `spotdl --download-ffmpeg` if FFmpeg is missing).

### YouTube Music cookies (for true 256 kbps M4A)
- Log into **music.youtube.com** (Premium).
- Use a browser extension (e.g., “Get cookies.txt”) to export cookies for **music.youtube.com**.
- Save as `cookies/music_youtube_cookies.txt`.

> The app uses: `--audio youtube-music --format m4a --bitrate disable --cookie-file cookies/...`  
This keeps **source quality** and avoids re-encoding. Note: `--bitrate 256` only re-encodes and won't increase quality if the source isn't 256 kbps.

## Run (dev)
