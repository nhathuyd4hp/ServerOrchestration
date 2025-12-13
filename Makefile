celery:
	start "" celery -A src.worker.Worker worker --loglevel=INFO --pool=threads --concurrency=5
server:
	start "" uvicorn src.main:app --host 127.0.0.1 --port 8000
both:
	start "" celery -A src.worker.Worker worker --loglevel=INFO --pool=threads --concurrency=5
	start "" uvicorn src.main:app --host 127.0.0.1 --port 8000
