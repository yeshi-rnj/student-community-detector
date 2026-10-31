"""Gunicorn settings. Data lives in process memory, so run exactly ONE worker
process (threads give concurrency); several workers would each hold a
different copy of the dataset."""
import os

bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = 1
threads = int(os.environ.get("WEB_THREADS", "8"))
timeout = 60
accesslog = "-"
errorlog = "-"
