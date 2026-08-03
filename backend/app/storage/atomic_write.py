"""
atomic_write.py — 檔案安全寫入工具。

先寫入同資料夾的暫存檔，再用 replace 換成正式檔，避免讀到半寫入內容。

CSV 全檔重寫特別需要這個：`open("w")` 會先清空再寫，中途被中斷就留下截斷的
檔案，而截斷處的殘值可能剛好通過下一次合併的欄位檢查，被當成一筆真資料保存
下來（2026-08-03 在 ohlcv_us.csv 第 2 行發現過一筆這樣的垃圾）。
"""

import csv
from pathlib import Path
from typing import Iterable, Mapping


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding=encoding)
    tmp_path.replace(path)


def atomic_write_csv(
    path: Path,
    fieldnames: list[str],
    rows: Iterable[Mapping[str, object]],
    *,
    encoding: str = "utf-8",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    with tmp_path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    tmp_path.replace(path)
