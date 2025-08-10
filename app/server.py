# app/server.py

from flask import Flask, render_template, request, send_file, abort
from pathlib import Path
import tempfile
import shutil
import logging
import threading
import mimetypes

from .settings import TMP_ROOT, LOGS_DIR, HOST, PORT
from .downloader import run_spotdl, convert_to_format, SpotdlError
from .packer import zip_folder
from .cleanup import start_cleanup_thread

app = Flask(__name__)

# Logging
LOGS_DIR.mkdir(parents=True, exist_ok=True)
file_handler = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
file_handler.setLevel(logging.INFO)
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)

# Background cleanup
start_cleanup_thread()

# MIME tweaks (Windows can be spotty)
mimetypes.add_type("audio/mpeg", ".mp3")
mimetypes.add_type("audio/mp4", ".m4a")
mimetypes.add_type("audio/ogg", ".opus")
mimetypes.add_type("audio/flac", ".flac")
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("application/zip", ".zip")

@app.get("/")
def index():
    return render_template("index.html")
@app.get("/faq")
def faq():
    return render_template("faq.html")

@app.get("/contact")
def contact():
    return render_template("contact.html")

# optional: also serve with .html paths if you like
@app.get("/faq.html")
def faq_html():
    return render_template("faq.html")

@app.get("/contact.html")
def contact_html():
    return render_template("contact.html")

@app.post("/download")
def download():
    raw = (request.form.get("spotify_urls") or "").strip()
    if not raw:
        abort(400, "No URL(s) provided")

    # Multiple URLs (newline-separated)
    urls = [u.strip() for u in raw.replace("\r", "\n").split("\n") if u.strip()]
    if not urls:
        abort(400, "No valid URL(s) provided")

    # Requested output format (default mp3)
    req_fmt = (request.form.get("format") or "mp3").lower().strip()
    allowed = {"mp3", "m4a", "opus", "flac", "wav", "ogg"}
    if req_fmt not in allowed:
        req_fmt = "mp3"

    # Unique temp workspace under ./tmp
    workspace = Path(tempfile.mkdtemp(prefix="job_", dir=TMP_ROOT))
    out_dir = workspace / "out"
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1) Fast/stable network step: download MP3s
        mp3_files = run_spotdl(urls, out_dir)

        # 2) If the user asked for a different format, transcode locally
        final_files = mp3_files if req_fmt == "mp3" else convert_to_format(mp3_files, req_fmt, out_dir)

        # >1 file => ZIP
        if len(final_files) > 1:
            zip_path = workspace / ("playlist_" + req_fmt + ".zip")
            if req_fmt == "mp3":
                zip_folder(out_dir, zip_path)
            else:
                conv_dir = out_dir / f"converted_{req_fmt}"
                zip_folder(conv_dir, zip_path)

            threading.Timer(10.0, lambda: shutil.rmtree(workspace, ignore_errors=True)).start()
            return send_file(
                zip_path,
                as_attachment=True,
                download_name=zip_path.name,
                mimetype="application/zip",
                max_age=0
            )

        # Single file
        f = Path(final_files[0])
        ext = f.suffix.lower()
        mime_map = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/mp4",
            ".opus": "audio/ogg",
            ".flac": "audio/flac",
            ".wav": "audio/wav",
            ".ogg": "audio/ogg",
        }
        mtype = mime_map.get(ext, mimetypes.guess_type(str(f))[0] or "application/octet-stream")

        threading.Timer(10.0, lambda: shutil.rmtree(workspace, ignore_errors=True)).start()
        return send_file(
            f,
            as_attachment=True,
            download_name=f.name,
            mimetype=mtype,
            max_age=0
        )

    except SpotdlError as e:
        app.logger.exception("spotDL error")
        shutil.rmtree(workspace, ignore_errors=True)
        return f"<pre>Download failed:\n{e}</pre>", 500

    except Exception as e:
        app.logger.exception("Internal error")
        shutil.rmtree(workspace, ignore_errors=True)
        return f"<pre>Internal server error:\n{e}</pre>", 500

if __name__ == "__main__":
    # Dev server
    app.run(host=HOST, port=PORT, debug=True)
