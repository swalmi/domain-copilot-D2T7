from celery import Celery

from src.infrastructure.config import get_settings

settings = get_settings()

celery_app = Celery(
    "domain_copilot_tasks",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.infrastructure.tasks.claim_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Twist T7 — restart survival. A task is acknowledged only after it has
    # finished, so a worker crash/restart hands unacknowledged work back to the
    # broker instead of losing it; `reject_on_worker_lost` redelivers when the
    # worker process is killed outright.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Long adjudications are not prefetched: one in-flight job per slot keeps
    # revocation (claim cancel) and pause/resume responsive.
    worker_prefetch_multiplier=1,
)
