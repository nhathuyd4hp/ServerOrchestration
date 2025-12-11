from datetime import datetime
from celery import shared_task

@shared_task
def gui_ban_ve_toei(
    from_date: datetime | str,
    to_date: datetime | str,
):
    return from_date, to_date