# Gunicorn tuning for a small Flask app
workers = 2
threads = 4
timeout = 180
graceful_timeout = 30
keepalive = 30
accesslog = "-"
errorlog = "-"
