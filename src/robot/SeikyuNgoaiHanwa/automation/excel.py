import logging
import os
from typing import Any, Iterator, Literal, Optional, Tuple

import pandas as pd
import xlwings as xw
from xlwings.main import Range, Sheet


class Excel:
    logger: logging.Logger = logging.getLogger("Excel")
    supported_file_extension = [".xlsm", ".xlsx", ".xls"]

    @classmethod
    def exists(cls, file_path: str, sheet_name: str) -> bool:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File Not Found: {file_path}")
        if os.path.splitext(file_path)[1].lower() not in cls.supported_file_extension:
            raise ValueError(f"Unsupported file extension: {file_path}")
        try:
            app = xw.App(visible=False)
            wb = app.books.open(
                file_path,
                read_only=True,
            )
            return sheet_name in wb.sheet_names
        finally:
            wb.close()
            app.quit()

    @classmethod
    def read(
        cls,
        file_path: str,
        return_type: Literal["data", "background_color"] = "data",
        cell_range: Optional[str] = None,
        visible: Any | None = None,
    ) -> Iterator[Tuple[str, pd.DataFrame]]:
        cls.logger.info(f"Read {return_type} {file_path}")
        # ✅ Kiểm tra file tồn tại
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File Not Found: {file_path}")
        # ✅ Kiểm tra phần mở rộng hợp lệ
        if os.path.splitext(file_path)[1].lower() not in cls.supported_file_extension:
            raise ValueError(f"Unsupported file extension: {file_path}")
        # ✅ Khởi tạo Excel App an toàn
        app = None
        wb = None
        try:
            app = xw.App(visible=visible)
            # app.display_alerts = False
            app.screen_updating = False
            wb = app.books.open(
                file_path,
                update_links=False,
                read_only=True,
            )
            for name in wb.sheet_names:
                sheet: Sheet = wb.sheets[name]
                if not sheet.api.Visible:
                    continue
                if cell_range:
                    data = sheet.range(cell_range)
                else:
                    last_row = sheet.cells(1048576, 1).end("up").row
                    last_col = sheet.cells(1, 16384).end("left").column
                    if last_row < 1 or last_col < 1:
                        cls.logger.warning(f"Invalid file: {file_path}")
                        return pd.DataFrame()
                    data = sheet.range((1, 1), (last_row, last_col))
                if return_type == "data":
                    result = pd.DataFrame(data.value)
                if return_type == "background_color":
                    result = []
                    for r in range(data.rows.count):
                        row = []
                        for c in range(data.columns.count):
                            cell: Range = data[r, c]
                            row.append(cell.color)
                        result.append(row)
                    result = pd.DataFrame(result)
                yield name, result
        except Exception as e:
            cls.logger.warning(e)
        finally:
            if wb:
                wb.close()
            if app:
                app.quit()

    @classmethod
    def write(
        cls,
        file_path: str,
        data: Any,
        cell_range: str = "A1",
        sheet_name: str | None = None,
        visible: bool = True,
    ):
        cls.logger.info(f"Load data into {file_path} (sheet: {sheet_name})")
        if os.path.splitext(file_path)[1].lower() not in cls.supported_file_extension:
            raise ValueError(f"This method only supports {cls.supported_file_extension} files.")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File Not Found {file_path}")
        app = xw.App(visible=visible)
        try:
            wb = app.books.open(file_path)
            if sheet_name not in [s.name for s in wb.sheets]:
                wb.sheets.add(sheet_name)
            sheet: Sheet = wb.sheets[sheet_name]
            sheet.api.AutoFilterMode = False
            sheet.range(cell_range).value = data
            wb.app.calculate()
            wb.save()
            wb.close()
        finally:
            app.quit()
        return True

    @classmethod
    def clear_contents(
        cls,
        file_path: str,
        cell_range: str | None = None,
        sheet_name: str | None = None,
        visible: bool = True,
    ):
        cls.logger.info(f"Clear content in {file_path} (sheet: {sheet_name}, range: {cell_range})")
        if os.path.splitext(file_path)[1].lower() not in cls.supported_file_extension:
            raise ValueError(f"This method only supports {cls.supported_file_extension} files.")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File Not Found {file_path}")
        app = xw.App(visible=visible)
        try:
            wb = app.books.open(file_path)
            if sheet_name is None:
                sheet = wb.sheets[0]
            else:
                if sheet_name not in [s.name for s in wb.sheets]:
                    raise ValueError(f"Sheet '{sheet_name}' not found in file: {file_path}")
                sheet = wb.sheets[sheet_name]
            if cell_range:
                sheet.range(cell_range).clear_contents()
            else:
                sheet.cells.clear_contents()
            wb.save()
        except Exception as e:
            cls.logger.error(e)
            return False
        finally:
            wb.close()
            app.quit()
        return True

    @classmethod
    def macro(
        cls,
        file_path: str,
        name: str,
        visible: bool = True,
    ) -> Literal[True]:
        cls.logger.info(f"{os.path.basename(file_path)} run macro: {name}")
        if os.path.splitext(file_path)[1].lower() != ".xlsm":
            raise ValueError(f"Cannot run macro '{name}': '{file_path}' is not a .xlsm file.")
        app = xw.App(visible=visible)
        try:
            wb = app.books.open(file_path)
            macro = wb.macro(name)
            macro()
            wb.save()
            wb.close()
        finally:
            app.quit()
        return True
