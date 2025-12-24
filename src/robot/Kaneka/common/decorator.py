import functools
import logging
import sys
import time
from typing import Any, Callable, Tuple, Type


def retry_if_exception(
    exceptions: Tuple[Type[BaseException], ...] = (),
    max_retries: int = 5,
    delay: float = 1.0,
    failure_return: Any = None,
) -> Callable:
    """
    Decorator thử lại một hàm nếu nó gây ra các ngoại lệ được chỉ định.

    Args:
        exceptions: Tuple các loại ngoại lệ để bắt và thử lại
        max_retries: Số lần thử lại tối đa
        delay: Thời gian chờ ban đầu giữa các lần thử lại (giây)
        failure_return: Giá trị trả về nếu thất bại
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            logger: logging.Logger = (
                getattr(self, "logger")
                if hasattr(self, "logger")
                else logging.getLogger(__name__)
            )
            retries = 0
            while True:
                try:
                    return func(self, *args, **kwargs)
                except exceptions as e:
                    retries += 1
                    if retries > max_retries:
                        msg = e.msg if hasattr(e, "msg") else str(e)
                        logger.error(
                            f"{func.__name__} failed after {max_retries} retries: {msg}"
                        )
                        return failure_return
                    logger.error(f"RETRY: {func.__name__}, failed: {type(e).__name__}")
                    time.sleep(delay)
                except Exception as e:
                    msg = e.msg if hasattr(e, "msg") else str(e)
                    logger.error(f"{func.__name__}: {msg}")
                    return failure_return

        return wrapper

    return decorator


def error_handling() -> Callable:
    """
    Decorator xử lý các ngoại lệ xảy ra trong hàm.

    Nếu hàm bị dừng (Ctrl+C) hoặc xảy ra ngoại lệ, sẽ ghi lại lỗi
    và trả về False. Nếu hàm thực thi thành công, trả về True.

    Args:
        func: Hàm cần xử lý
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> bool:
            logger: logging.Logger = kwargs.get("logger", logging.getLogger(__name__))
            try:
                func(*args, **kwargs)
                return True
            except KeyboardInterrupt:
                logger.info("Đã dừng chương trình...")
                sys.exit(0)
                return True
            except Exception as e:
                logger.error(e)
                return False

        return wrapper

    return decorator
