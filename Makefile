celery:
	start "" celery -A src.worker.Worker worker --loglevel=INFO --pool=solo --concurrency=1 --prefetch-multiplier=1 --max-tasks-per-child=1
server:
	start "" uvicorn src.main:app --host 0.0.0.0 --port 8000
