"""Generation model catalog."""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from .config import APP_DIR, load_settings

MODEL_CATALOG = APP_DIR / "templates" / "models.json"


@lru_cache(maxsize=1)
def load_models() -> list[dict[str, Any]]:
    try:
        data = json.loads(MODEL_CATALOG.read_text(encoding="utf-8"))
        items = data.get("models", [])
        if items:
            return items
    except (OSError, json.JSONDecodeError):
        pass
    return [{"id": "doubao-seedream-5-0-flash-260915", "name": "Seedream 5.0 Flash", "tier": "旗舰", "resolutions": ["1K", "2K", "4K"], "note": ""}]


def get_model(model_id: str | None) -> dict[str, Any]:
    configured = str(model_id or load_settings().get("ark_model") or "")
    for item in load_models():
        if item.get("id") == configured:
            return item
    return {"id": configured, "name": configured or "自定义模型", "tier": "自定义", "resolutions": ["1K", "2K", "4K"], "note": "设置页自定义模型"}


def validate_resolution(model_id: str | None, resolution: str | None) -> str:
    model = get_model(model_id)
    allowed = model.get("resolutions") or ["1K", "2K", "4K"]
    value = str(resolution or "2K").upper()
    return value if value in allowed else allowed[0]

