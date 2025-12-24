import contextlib
import subprocess
from datetime import datetime
from io import BytesIO
from pathlib import Path

from celery import shared_task

from src.core.config import settings
from src.service import ResultService as minio


@shared_task(bind=True, name="OHD MITSUMORI")
def OHD_MITSUMORI(self):
    exe_path = Path(__file__).resolve().parents[2] / "robot" / "OHDMITSUMORI" / "OHDNew_b5d7VmU.exe"

    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{self.request.id}.log"

    exe_dir = exe_path.parent
    ohd_bot_log = exe_dir / "OHD_bot.log"

    with open(log_file, "w", encoding="utf-8", errors="ignore") as f:
        process = subprocess.Popen(
            [str(exe_path)], cwd=str(exe_path.parent), stdout=f, stderr=subprocess.STDOUT, text=True
        )
        process.wait()

    if ohd_bot_log.exists():
        with contextlib.suppress(Exception):
            ohd_bot_log.unlink()

    result_files = list(exe_dir.glob("OHD_result_*.xlsx"))
    if not result_files:
        return None

    latest_result = max(result_files, key=lambda p: p.stat().st_mtime)

    excel_buffer = BytesIO()
    with open(latest_result, "rb") as f:
        excel_buffer.write(f.read())

    excel_buffer.seek(0)

    object_name = f"OHDMITSUMORI/{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"

    result = minio.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        data=excel_buffer,
        length=excel_buffer.getbuffer().nbytes,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # 3️⃣ (Optional) xóa file local sau khi upload
    latest_result.unlink(missing_ok=True)

    return result.object_name
