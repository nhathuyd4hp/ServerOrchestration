from celery import shared_task
from typing import Literal

@shared_task
def ngoai_hanwa(
    sheet_name : Literal["1","2","3","4","5","6","7","8","9","10"] = '1',
    count : Literal[1,2,3,4,5,6,7,8,9,10] = 1,
):
    return sheet_name,count