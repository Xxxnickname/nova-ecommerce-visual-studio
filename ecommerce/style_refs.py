"""Original style-reference library."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from .config import APP_DIR

STYLE_REF_FILE = APP_DIR / "templates" / "style_refs.json"


@lru_cache(maxsize=1)
def load_style_refs() -> list[dict[str, Any]]:
    try:
        data = json.loads(STYLE_REF_FILE.read_text(encoding="utf-8"))
        items = []
        for item in data.get("styles", []):
            resolved = dict(item)
            resolved["path"] = str((APP_DIR / item["path"]).resolve()) if not Path(item["path"]).is_absolute() else item["path"]
            items.append(resolved)
        return items
    except (OSError, json.JSONDecodeError):
        return []


def get_style_ref(style_id: str | None) -> dict[str, Any] | None:
    if not style_id:
        return None
    for item in load_style_refs():
        if item.get("id") == style_id:
            return item
    return None
