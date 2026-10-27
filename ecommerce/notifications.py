"""Optional Feishu group-bot notifications."""
from __future__ import annotations

import requests

from .config import load_settings


def notify(text: str) -> dict[str, object]:
    url = load_settings().get("feishu_webhook", "")
    if not url:
        return {"sent": False, "reason": "not_configured"}
    try:
        response = requests.post(
            url,
            json={"msg_type": "text", "content": {"text": text}},
            timeout=8,
        )
        return {"sent": response.ok, "status": response.status_code}
    except requests.RequestException as exc:
        return {"sent": False, "reason": str(exc)[:200]}
