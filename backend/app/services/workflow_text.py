"""Small text helpers shared by PM workflow scripts and services."""

from __future__ import annotations

import re


def preview_numbered_lines(text: str, limit: int = 5) -> list[str]:
    items: list[str] = []
    for line in text.splitlines():
        match = re.match(r"\s*\d+\.\s+(.+?)(?:\s+-\s+.*)?$", line)
        if match:
            items.append(match.group(1).strip())
            if len(items) >= limit:
                break
    return items
