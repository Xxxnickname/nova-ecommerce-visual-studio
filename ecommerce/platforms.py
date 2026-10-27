"""Platform presets and deterministic image adaptation."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from .config import APP_DIR

PLATFORM_CATALOG = APP_DIR / "templates" / "platforms.json"


@lru_cache(maxsize=1)
def load_platforms() -> list[dict[str, Any]]:
    try:
        data = json.loads(PLATFORM_CATALOG.read_text(encoding="utf-8"))
        items = data.get("platforms", [])
        if isinstance(items, list) and items:
            return items
    except (OSError, json.JSONDecodeError):
        pass
    return [
        {"id": "shopify", "name": "Shopify", "status": "live", "status_label": "可用", "publishable": True, "image_size": [2048, 2048], "ratio": "1:1", "gallery_ratio": "4:5", "note": ""}
    ]


def get_platform(platform_id: str | None) -> dict[str, Any]:
    for item in load_platforms():
        if item.get("id") == platform_id:
            return item
    raise ValueError(f"未知发布平台：{platform_id}")


def get_size_option(platform_id: str, size_id: str | None = None) -> dict[str, Any]:
    platform = get_platform(platform_id)
    options = platform.get("size_options") or []
    if not options:
        width, height = [int(value) for value in platform.get("image_size", [2048, 2048])]
        return {"id": "default", "label": f"{width}×{height}", "width": width, "height": height}
    wanted = size_id or platform.get("default_size_id") or options[0]["id"]
    for option in options:
        if option.get("id") == wanted:
            return option
    raise ValueError(f"{platform['name']} 不支持该尺寸：{wanted}")


def adapt_image_to_platform(path: str | Path, platform_id: str, size_id: str | None = None) -> dict[str, Any]:
    platform = get_platform(platform_id)
    if platform.get("status") == "soon":
        raise RuntimeError(f"{platform['name']} 暂未开放")
    option = get_size_option(platform_id, size_id)
    width, height = int(option["width"]), int(option["height"])
    target = Path(path)
    with Image.open(target) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        fitted = ImageOps.fit(image, (width, height), method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))
        fitted.save(target, format="PNG", optimize=True)
    return {"path": str(target), "width": width, "height": height, "bytes": target.stat().st_size, "platform_id": platform_id, "size_id": option["id"]}
