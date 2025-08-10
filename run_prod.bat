@echo off
IF EXIST .venv\Scripts\activate.bat (
  call .venv\Scripts\activate.bat
)
set PYTHONPATH=.
waitress-serve --listen=%HOST%:%PORT% app.wsgi:application
