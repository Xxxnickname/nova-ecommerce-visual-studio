"""Local-first configuration for the ecommerce automation console."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_PATH = Path(os.getenv("ECOMMERCE_SETTINGS_PATH", APP_DIR / "settings.json"))
ENV_PATH = Path(os.getenv("ECOMMERCE_ENV_PATH", APP_DIR / ".env"))

DEFAULTS: dict[str, Any] = {
    "ark_base": "https://ark.cn-beijing.volces.com/api/v3",
    "ark_model": "doubao-seedream-5-0-flash-260915",
    "deepseek_base": "https://api.deepseek.com",
    "deepseek_model": "deepseek-flash",
    "shopify_store": "",
    "shopify_token": "",
    "feishu_webhook": "",
    "approval_threshold": 5.0,
}

SECRET_FIELDS = {"ark_key", "deepseek_key", "shopify_token", "feishu_webhook"}
ENV_ALIASES = {
    "ARK_API_KEY": "ark_key",
    "ARK_BASE_URL": "ark_base",
    "ARK_MODEL_IMAGE": "ark_model",
    "DEEPSEEK_API_KEY": "deepseek_key",
    "DEEPSEEK_BASE_URL": "deepseek_base",
    "DEEPSEEK_MODEL": "deepseek_model",
    "SHOPIFY_STORE": "shopify_store",
    "SHOPIFY_TOKEN": "shopify_token",
    "FEISHU_WEBHOOK": "feishu_webhook",
}


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_settings() -> dict[str, Any]:
    """Load defaults, then .env, settings.json, and process environment."""
    result = dict(DEFAULTS)

    for key, value in _read_env(ENV_PATH).items():
        mapped = ENV_ALIASES.get(key, key.lower())
        if mapped in DEFAULTS or mapped in SECRET_FIELDS:
            result[mapped] = value

    if SETTINGS_PATH.exists():
        try:
            stored = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                result.update(stored)
        except (OSError, json.JSONDecodeError):
            pass

    for env_key, field in ENV_ALIASES.items():
        if os.getenv(env_key):
            result[field] = os.environ[env_key]

    try:
        result["approval_threshold"] = float(result.get("approval_threshold", 5.0))
    except (TypeError, ValueError):
        result["approval_threshold"] = 5.0
    return result


def save_settings(payload: dict[str, Any]) -> dict[str, Any]:
    """Persist editable fields. Empty secret fields keep the current secret."""
    current = load_settings()
    editable = set(DEFAULTS) | SECRET_FIELDS
    for key, value in payload.items():
        if key not in editable:
            continue
        if key in SECRET_FIELDS and (value is None or str(value).strip() == ""):
            continue
        if key == "approval_threshold":
            try:
                value = max(0.0, float(value))
            except (TypeError, ValueError):
                continue
        current[key] = str(value).strip() if isinstance(value, str) else value

    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SETTINGS_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(SETTINGS_PATH)
    try:
        os.chmod(SETTINGS_PATH, 0o600)
    except OSError:
        pass
    return current


def public_settings() -> dict[str, Any]:
    settings = load_settings()
    result: dict[str, Any] = {}
    for key, value in settings.items():
        if key in SECRET_FIELDS:
            secret = str(value or "")
            result[f"{key}_set"] = bool(secret)
            result[f"{key}_length"] = len(secret)
        else:
            result[key] = value
    return result

