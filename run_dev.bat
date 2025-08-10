@echo off
REM Activate venv (adjust if your venv folder name differs)
IF EXIST .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
set FLASK_DEBUG=1
set PYTHONPATH=.
python -m flask --app app.server:app run --host=127.0.0.1 --port=5000
