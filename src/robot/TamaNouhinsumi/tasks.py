import shutil
from pathlib import Path
import subprocess
from celery import shared_task

@shared_task(bind=True, name="Tama Nouhinsumi")
def TamaNouhinsumi(self):
    exe_path = Path(__file__).resolve().parents[2] / "robot" / "TamaNouhinsumi" / "Nouhin_kanryo_V1.2.exe"
    cwd_path = exe_path.parent
    
    log_dir = Path(__file__).resolve().parents[3] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{self.request.id}.log"

    with open(log_file, "w", encoding="utf-8", errors="ignore") as f:
        process = subprocess.Popen(
            [str(exe_path)], 
            cwd=str(cwd_path), 
            stdout=f, 
            stderr=subprocess.STDOUT, 
            text=True
        )
        process.wait()

    token_log_source = cwd_path / "Access_token_log"
    logs_folder_source = cwd_path / "Logs"

    if token_log_source.exists():
        try:
            shutil.copy(token_log_source, log_file)
            token_log_source.unlink()
        except Exception as e:
            pass

    if logs_folder_source.exists() and logs_folder_source.is_dir():
        try:
            shutil.rmtree(logs_folder_source)
        except Exception as e:
            pass