"""
atomic_write.py — backend/out 檔案安全寫入工具。

先寫入同資料夾的暫存檔，再用 replace 換成正式檔，避免 API 讀到半寫入內容。
"""

from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(text, encoding=encoding)
    tmp_path.replace(path)
