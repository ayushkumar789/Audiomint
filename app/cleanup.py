import threading
import time
from pathlib import Path
import shutil
from .settings import TMP_ROOT, CLEANUP_TTL_MIN

def _sweeper():
    ttl = CLEANUP_TTL_MIN * 60
    while True:
        now = time.time()
        try:
            for d in TMP_ROOT.iterdir():
                if d.is_dir():
                    try:
                        mtime = d.stat().st_mtime
                        if now - mtime > ttl:
                            shutil.rmtree(d, ignore_errors=True)
                    except Exception:
                        pass
        except FileNotFoundError:
            TMP_ROOT.mkdir(parents=True, exist_ok=True)
        time.sleep(60)  # run every minute

def start_cleanup_thread():
    t = threading.Thread(target=_sweeper, name="tmp-cleanup", daemon=True)
    t.start()
