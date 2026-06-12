"""
watchlist_store.py — 觀察清單的 JSON 儲存層

資料格式（backend/data/watchlists.json）：
{
  "groups": [
    {
      "name": "科技股",
      "stocks": [
        {"code": "2330", "name": "台積電", "added_at": "2026-04-14"}
      ]
    }
  ]
}

公開介面：
  get_all_groups()                     -> list[dict]
  create_group(name)                   -> dict
  delete_group(name)                   -> None
  add_stock(group_name, code, name)    -> dict  (回傳更新後的 group)
  remove_stock(group_name, code)       -> dict  (回傳更新後的 group)
"""

import json
from datetime import date
from pathlib import Path

from app.storage.atomic_write import atomic_write_text

_DATA_DIR        = Path(__file__).resolve().parent.parent.parent / "data"
_WATCHLISTS_PATH = _DATA_DIR / "watchlists.json"

_FORBIDDEN_CHARS = set("/\\?#")  # 不允許出現在 group name 中的字元


def _validate_name(name: str) -> None:
    if not name or not name.strip():
        raise ValueError("群組名稱不能為空")
    if any(c in name for c in _FORBIDDEN_CHARS):
        raise ValueError(f"群組名稱不可包含以下字元：{''.join(sorted(_FORBIDDEN_CHARS))}")


def _load() -> dict:
    if not _WATCHLISTS_PATH.exists():
        return {"groups": []}
    with _WATCHLISTS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _save(data: dict) -> None:
    _DATA_DIR.mkdir(exist_ok=True)
    atomic_write_text(
        _WATCHLISTS_PATH,
        json.dumps(data, ensure_ascii=False, indent=2),
    )


def get_all_groups() -> list[dict]:
    return _load()["groups"]


def create_group(name: str) -> dict:
    _validate_name(name)
    name = name.strip()
    data = _load()
    if any(g["name"] == name for g in data["groups"]):
        raise ValueError(f"群組「{name}」已存在")
    group: dict = {"name": name, "stocks": []}
    data["groups"].append(group)
    _save(data)
    return group


def delete_group(name: str) -> None:
    data = _load()
    before = len(data["groups"])
    data["groups"] = [g for g in data["groups"] if g["name"] != name]
    if len(data["groups"]) == before:
        raise KeyError(f"群組「{name}」不存在")
    _save(data)


def add_stock(group_name: str, code: str, stock_name: str) -> dict:
    """加入股票；若股票已在群組中，靜默跳過（冪等）。"""
    data  = _load()
    group = next((g for g in data["groups"] if g["name"] == group_name), None)
    if group is None:
        raise KeyError(f"群組「{group_name}」不存在")
    # 冪等：已有則跳過
    if not any(s["code"] == code for s in group["stocks"]):
        group["stocks"].append({
            "code":     code,
            "name":     stock_name,
            "added_at": date.today().isoformat(),
        })
        _save(data)
    return group


def remove_stock(group_name: str, code: str) -> dict:
    data  = _load()
    group = next((g for g in data["groups"] if g["name"] == group_name), None)
    if group is None:
        raise KeyError(f"群組「{group_name}」不存在")
    group["stocks"] = [s for s in group["stocks"] if s["code"] != code]
    _save(data)
    return group
