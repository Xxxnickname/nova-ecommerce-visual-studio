"""Seedream image generation and DeepSeek connectivity checks."""
from __future__ import annotations

import base64
import io
import mimetypes
import time
from pathlib import Path
from typing import Any

import requests

def friendly_http_error(service: str, status: int, body: str = "") -> str:
    """把上游服务的 HTTP 错误翻译成中文提示，原文只保留很短一段便于排查。"""
    text = (body or "").lower()
    if status in (401, 403):
        return f"{service}密钥无效或没有权限，请到「设置」里重新填写（{status}）"
    if status == 402 or "quota" in text or "balance" in text or "insufficient" in text:
        return f"{service}额度不足或欠费，请到控制台充值后再试（{status}）"
    if status == 429:
        return f"{service}请求太频繁，请等一分钟再试（429）"
    if status >= 500:
        return f"{service}服务暂时不可用，请稍后重试（{status}）"
    if not (body or "").strip():
        return f"{service}调用失败（{status}）"
    snippet = (body or "")[:100]
    return f"{service}调用失败（{status}）：{snippet}"

from PIL import Image

from .config import load_settings


def _data_url(path: str | Path) -> str:
    source = Path(path)
    mime = mimetypes.guess_type(source.name)[0] or "image/png"
    return f"data:{mime};base64,{base64.b64encode(source.read_bytes()).decode()}"


def generate_image(prompt: str, out_path: str | Path, reference_path: str | Path | list[str | Path] | None = None, seed: int | None = None, model_id: str | None = None, resolution: str = "2K") -> dict[str, Any]:
    settings = load_settings()
    key = settings.get("ark_key", "")
    model = model_id or settings.get("ark_model", "")
    if not key:
        raise RuntimeError("未配置 Seedream / Ark API Key")
    if not model:
        raise RuntimeError("未配置 Seedream 模型名")

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": str(resolution or "2K").upper(),
        "response_format": "url",
        "watermark": False,
    }
    references = reference_path if isinstance(reference_path, (list, tuple)) else ([reference_path] if reference_path else [])
    valid_references = [Path(item) for item in references if item and Path(item).exists()]
    if valid_references:
        payload["image"] = [_data_url(item) for item in valid_references]
    if seed is not None:
        payload["seed"] = int(seed)

    base = str(settings.get("ark_base") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    started = time.time()
    response = requests.post(
        f"{base}/images/generations",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=300,
    )
    if response.status_code != 200:
        raise RuntimeError(friendly_http_error("Seedream 生图", response.status_code, response.text))
    body = response.json()
    item = (body.get("data") or [{}])[0]
    raw: bytes | None = None
    if item.get("b64_json"):
        raw = base64.b64decode(item["b64_json"])
    elif item.get("url"):
        download = requests.get(item["url"], timeout=120)
        download.raise_for_status()
        raw = download.content
    if not raw:
        raise RuntimeError("Seedream 未返回图片")

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
    except Exception as exc:
        raise RuntimeError("Seedream 返回的文件不是有效图片") from exc

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(raw)
    return {
        "path": str(target),
        "width": width,
        "height": height,
        "bytes": len(raw),
        "seconds": round(time.time() - started, 1),
        "request_id": body.get("id") or body.get("request_id"),
    }


def generate_image_group(prompt: str, out_dir: str | Path, prefix: str, reference_path: str | Path | None = None, max_images: int = 12, model_id: str | None = None, resolution: str = "2K") -> dict[str, Any]:
    """Use Ark's native sequential image generation to keep a multi-image set coherent."""
    settings = load_settings()
    key = settings.get("ark_key", "")
    model = model_id or settings.get("ark_model", "")
    if not key or not model:
        raise RuntimeError("未配置 Seedream / Ark API Key 或模型名")
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": str(resolution or "2K").upper(),
        "response_format": "url",
        "watermark": False,
        "sequential_image_generation": "auto",
        "sequential_image_generation_options": {"max_images": max(1, min(int(max_images), 15))},
    }
    if reference_path and Path(reference_path).exists():
        payload["image"] = [_data_url(reference_path)]
    base = str(settings.get("ark_base") or "https://ark.cn-beijing.volces.com/api/v3").rstrip("/")
    started = time.time()
    response = requests.post(
        f"{base}/images/generations",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json=payload,
        timeout=900,
    )
    if response.status_code != 200:
        raise RuntimeError(friendly_http_error("Seedream 套图", response.status_code, response.text))
    body = response.json()
    target_dir = Path(out_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for index, item in enumerate(body.get("data") or [], 1):
        raw = None
        if item.get("b64_json"):
            raw = base64.b64decode(item["b64_json"])
        elif item.get("url"):
            download = requests.get(item["url"], timeout=120)
            download.raise_for_status()
            raw = download.content
        if not raw:
            continue
        try:
            with Image.open(io.BytesIO(raw)) as image:
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                width, height = image.size
        except Exception:
            continue
        target = target_dir / f"{prefix}-{index:02d}.png"
        target.write_bytes(raw)
        results.append({
            "path": str(target), "width": width, "height": height, "bytes": len(raw),
            "index": index, "name": item.get("name") or "", "description": item.get("description") or "",
        })
    if not results:
        raise RuntimeError("Seedream 组图未返回有效图片")
    return {
        "images": results,
        "count": len(results),
        "requested": max_images,
        "seconds": round(time.time() - started, 1),
        "request_id": body.get("id") or body.get("request_id"),
    }


def test_deepseek() -> dict[str, Any]:
    settings = load_settings()
    key = settings.get("deepseek_key", "")
    if not key:
        raise RuntimeError("未配置 DeepSeek API Key")
    base = str(settings.get("deepseek_base") or "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": settings.get("deepseek_model", "deepseek-flash"),
            "messages": [{"role": "user", "content": "只回复：连接成功"}],
            "max_tokens": 16,
            "temperature": 0,
        },
        timeout=30,
    )
    if response.status_code != 200:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:200]}")
    reply = response.json()["choices"][0]["message"]["content"].strip()
    return {"reply": reply, "model": settings.get("deepseek_model")}

