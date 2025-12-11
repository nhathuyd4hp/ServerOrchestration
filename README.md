# TaskDistribution

TaskDistribution là một bộ robot tự động hóa (Celery tasks + Playwright + SharePoint) dùng để xử lý và upload dữ liệu từ Excel/PDF lên SharePoint, kèm tracking qua models và migration.

## Tổng quan
- Celery tasks chính:
  - [`src.robot.ShigaToyoChiba.tasks.shiga_toyo_chiba`](src/robot/ShigaToyoChiba/tasks.py)
  - [`src.robot.DrawingClassic.tasks.drawing_classic`](src/robot/DrawingClassic/tasks.py)
- Automation / helpers:
  - [`src.robot.ShigaToyoChiba.automation.SharePoint`](src/robot/ShigaToyoChiba/automation/__init__.py)
  - [`src.robot.DrawingClassic.automation.SharePoint`](src/robot/DrawingClassic/automation/__init__.py)
  - API client: [`src.robot.ShigaToyoChiba.api.APISharePoint`](src/robot/ShigaToyoChiba/api.py)
- Models / DB:
  - [`src.model.runs.Runs`](src/model/runs.py)
  - [`src.model.base.Base`](src/model/base.py)
- Cấu hình: [`src.core.config.settings`](src/core/config.py)
- Entry Celery app: [src/worker.py](src/worker.py)
- Migrations: [alembic.ini](alembic.ini) (migrations nằm trong thư mục alembic)

## Yêu cầu
- Python (x.y) — môi trường được quản lý bởi [pyproject.toml](pyproject.toml)
- Redis, MySQL (cấu hình trong `settings`) — docker-compose có sẵn: [docker-compose.yaml](docker-compose.yaml)
- Các thư viện chính: Celery, Playwright, xlwings, sqlmodel, pandas

## Cài đặt nhanh
1. Tạo virtualenv và cài dependencies:
```sh
python -m venv .venv
.venv/bin/pip install -U pip
.venv/bin/pip install -e .
# hoặc
pip install -r requirements.txt
```

2. Thiết lập biến môi trường (tham khảo [`src.core.config.settings`](src/core/config.py)).

3. Khởi chạy dịch vụ (ví dụ Docker):
```sh
docker-compose up -d
```

4. Chạy migrations (Alembic):
```sh
alembic upgrade head
```
Migrations cấu hình tại [alembic.ini](alembic.ini).

## Chạy Celery worker
Ví dụ chạy worker (tùy cấu trúc app trong [src/worker.py](src/worker.py)):
```sh
celery -A src.worker Worker worker --loglevel=info
```

## Gửi task
Ví dụ gửi task từ ứng dụng Python:
```py
from src.robot.ShigaToyoChiba.tasks import shiga_toyo_chiba

shiga_toyo_chiba.delay("2025/01/01")
```

## Cấu trúc quan trọng
- src/robot/*: các robot theo từng module (ví dụ [`src/robot/ShigaToyoChiba/taks.py`](src/robot/ShigaToyoChiba/tasks.py), [`src/robot/DrawingClassic/tasks.py`](src/robot/DrawingClassic/tasks.py))
- src/robot/*/automation: wrappers cho Playwright / SharePoint
  - [`src.robot.ShigaToyoChiba.automation`](src/robot/ShigaToyoChiba/automation/__init__.py)
  - [`src.robot.DrawingClassic.automation`](src/robot/DrawingClassic/automation/__init__.py)
- src/model: các SQLModel models
  - [`src.model.runs.Runs`](src/model/runs.py)
  - [`src.model.base.Base`](src/model/base.py)

## Debug / Development
- Xem logs Celery để theo dõi task.
- Kiểm tra file Excel/Download trong `downloads/`.
- Nếu gặp lỗi liên quan migration (ví dụ Column reuse), sửa mixin models tại [`src.model.base.Base`](src/model/base.py) rồi tạo revision mới.

## Tài liệu tham khảo trong repo
- [pyproject.toml](pyproject.toml)
- [Makefile](Makefile)
- [docker-compose.yaml](docker-compose.yaml)
- [alembic.ini](alembic.ini)
- [src/worker.py](src/worker.py)
- [`src.robot.ShigaToyoChiba.tasks.shiga_toyo_chiba`](src/robot/ShigaToyoChiba/tasks.py)
- [`src.robot.DrawingClassic.tasks.drawing_classic`](src/robot/DrawingClassic/tasks.py)
- [`src.model.runs.Runs`](src/model/runs.py)
- [`src.model.base.Base`](src/model/base.py)
- [`src.core.config.settings`](src/core/config.py)

Ngắn gọn: đọc các file link ở trên để hiểu chi tiết từng task và cấu hình trước khi chạy.
