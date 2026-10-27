"""Category-aware prompt templates and DeepSeek product classification."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests

from .config import APP_DIR, load_settings

TEMPLATE_DIR = APP_DIR / "templates" / "prompts"
CATALOG_PATH = APP_DIR / "templates" / "catalog.json"

SYSTEM_PROMPT = """你是资深电商视觉提示词工程师。根据商品描述、商品类型和视觉模板，输出一段可直接用于 Seedream 的中文提示词。
严格按 9 层组织，每层独立成短句：
1. 画面叙事与用途
2. 产品位置与完整状态
3. 材质与结构保真要求
4. 环境、场景与陈设
5. 光线与阴影
6. 镜头、焦段与视角
7. 构图、留白与画幅
8. 色彩、风格与质感
9. 负面约束与输出规格
商品外形、颜色、材质、结构、包装标签位置和比例必须与参考图一致。不要新增文字、水印、品牌 logo，也不要改写参考图中已有的真实包装信息。用户没有提供的品牌、成分、功效、材质或场景细节，不得自行编造；信息不足时使用中性、保守的描述。
只输出提示词正文，不要解释，不要 Markdown。控制在 420 个中文字符以内。"""


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    try:
        data = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and data.get("categories"):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {
        "default_category": "generic",
        "categories": [
            {
                "id": "generic",
                "name": "通用商品",
                "description": "通用商品",
                "keywords": [],
                "default_template": "generic_white_bg",
                "category_guard": "严格保持商品外形、颜色、材质、结构、比例和包装信息",
                "scene_options": ["纯白无缝摄影棚", "浅灰渐变背景", "生活方式场景", "材质细节特写"],
                "style_options": ["干净商业", "清爽简约", "高级质感", "现代杂志感"],
            }
        ],
    }


def get_category(category_id: str | None) -> dict[str, Any]:
    catalog = load_catalog()
    for category in catalog["categories"]:
        if category.get("id") == category_id:
            return category
    fallback = catalog.get("default_category", "generic")
    return next((item for item in catalog["categories"] if item.get("id") == fallback), catalog["categories"][0])


def list_templates(category_id: str | None = None) -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []
    for file in sorted(TEMPLATE_DIR.glob("*.json")):
        try:
            item = json.loads(file.read_text(encoding="utf-8"))
            item["file"] = file.name
            templates.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    if not category_id:
        return templates
    category_templates = [item for item in templates if item.get("category") == category_id]
    if category_templates:
        return category_templates
    return [item for item in templates if item.get("category") == "generic"]


def get_template(template_id: str) -> dict[str, Any]:
    for template in list_templates():
        if template.get("id") == template_id:
            return template
    raise ValueError(f"未知提示词模板：{template_id}")


def _keyword_category(text: str) -> tuple[dict[str, Any], float]:
    normalized = text.casefold()
    best = get_category("generic")
    best_score = 0
    for category in load_catalog()["categories"]:
        score = sum(1 for keyword in category.get("keywords", []) if keyword.casefold() in normalized)
        if score > best_score:
            best = category
            best_score = score
    confidence = min(0.96, 0.62 + best_score * 0.1) if best_score else 0.35
    return best, confidence


def _classification_payload(category: dict[str, Any], description: str, source: str, confidence: float, reason: str) -> dict[str, Any]:
    templates = list_templates(category["id"])
    default_template = category.get("default_template") or (templates[0]["id"] if templates else "")
    return {
        "ok": True,
        "source": source,
        "description": description,
        "category": {"id": category["id"], "name": category["name"], "description": category.get("description", "")},
        "confidence": round(float(confidence), 2),
        "reason": reason,
        "default_template_id": default_template,
        "templates": [
            {"id": item["id"], "name": item.get("name", item["id"]), "description": item.get("description", "")}
            for item in templates
        ],
        "scenes": category.get("scene_options", []),
        "styles": category.get("style_options", []),
        "category_guard": category.get("category_guard", ""),
    }


def category_options(category_id: str) -> dict[str, Any]:
    category = get_category(category_id)
    return _classification_payload(category, "", "manual", 1.0, "手动选择商品类型")


def classify_product(description: str, product: dict[str, Any] | None = None) -> dict[str, Any]:
    description = (description or "").strip()
    if not description and product:
        description = f"{product.get('name', '')} {product.get('description', '')[:400]}".strip()
    fallback_category, fallback_confidence = _keyword_category(description)
    settings = load_settings()
    key = settings.get("deepseek_key", "")
    if not key or not description:
        return _classification_payload(fallback_category, description, "keywords", fallback_confidence, "根据商品关键词匹配")

    categories = [
        {"id": item["id"], "name": item["name"], "description": item.get("description", ""), "keywords": item.get("keywords", [])}
        for item in load_catalog()["categories"]
    ]
    user_prompt = f"""商品描述：{description[:1200]}
可选商品类型：
{json.dumps(categories, ensure_ascii=False)}
请判断最匹配的商品类型。只输出一个 JSON 对象，不要 Markdown：
{{"category_id":"类型 id","confidence":0.0,"reason":"不超过40字的判断依据"}}"""
    base = str(settings.get("deepseek_base") or "https://api.deepseek.com").rstrip("/")
    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": settings.get("deepseek_model", "deepseek-flash"),
                "messages": [
                    {"role": "system", "content": "你只负责商品类型分类。必须从给定 category_id 中选择，只输出 JSON。"},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 180,
            },
            timeout=45,
        )
        if response.status_code == 200:
            content = response.json()["choices"][0]["message"]["content"].strip()
            match = re.search(r"\{.*\}", content, re.S)
            parsed = json.loads(match.group(0) if match else content)
            category = get_category(str(parsed.get("category_id", "")).strip())
            confidence = float(parsed.get("confidence", 0.8))
            reason = str(parsed.get("reason", "AI 商品类型识别"))[:80]
            return _classification_payload(category, description, "deepseek", min(max(confidence, 0.0), 1.0), reason)
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError):
        pass
    return _classification_payload(fallback_category, description, "keywords", fallback_confidence, "AI 分类不可用，已使用关键词匹配")


def template_prompt(
    product: dict[str, Any],
    template: dict[str, Any],
    scene_note: str = "",
    style: str = "温暖自然",
    product_description: str = "",
    category_id: str = "",
    extras: dict[str, Any] | None = None,
) -> str:
    category = get_category(category_id or template.get("category", "generic"))
    extras = extras or {}
    product_name = (product_description or product.get("name") or product.get("sku") or "商品").strip()
    if len(product_name) > 90:
        product_name = product_name[:90] + "…"
    scene = template.get("scene", "")
    if scene_note.strip() and "按模板默认" not in scene_note:
        scene = f"{scene}；首选场景：{scene_note.strip()}"
    guard = category.get("category_guard") or "严格保持参考图中的商品外形、颜色、材质、结构和比例"
    must_keep = str(extras.get("must_keep") or "").strip()
    props = str(extras.get("props") or "").strip()
    selling_points = str(extras.get("selling_points") or "").strip()
    avoid = str(extras.get("avoid") or "").strip()
    if must_keep:
        guard += f"；用户要求必须保留：{must_keep}"
    if props:
        scene += f"；用户指定场景/道具：{props}"
    mood = template.get("mood", "真实、干净、高级")
    if selling_points:
        mood += f"；重点表达：{selling_points}"
    negative = template.get("negative", "人物、文字、水印、变形、额外物体")
    if avoid:
        negative += f"、{avoid}"
    return "\n".join(
        [
            f"1. 叙事与用途：为「{product_name}」生成{template.get('name', '商品图')}，用于电商详情页。",
            f"2. 产品位置：{template.get('product_position', '商品完整居中呈现，主体清晰，不被遮挡')}。",
            f"3. 材质保真：{guard}；不得改变商品款式和包装信息。",
            f"4. 环境场景：{scene}。",
            f"5. 光线阴影：{template.get('lighting', '柔和均匀光，轻微自然阴影')}。",
            f"6. 镜头视角：{template.get('camera', '50mm 中景，平视略俯拍')}。",
            f"7. 构图留白：{template.get('composition', '主体居中，四周保留安全留白')}。",
            f"8. 色彩风格：{style}；{mood}。",
            f"9. 负面与输出：避免{negative}；{template.get('output', '4:5 竖版，2K，高细节')}。",
        ]
    )


def build_prompt(
    product: dict[str, Any],
    template_id: str,
    scene_note: str = "",
    style: str = "温暖自然",
    use_ai: bool = True,
    product_description: str = "",
    category_id: str = "",
    extras: dict[str, Any] | None = None,
) -> dict[str, Any]:
    template = get_template(template_id)
    category = get_category(category_id or template.get("category", "generic"))
    fallback = template_prompt(product, template, scene_note, style, product_description, category["id"], extras)
    settings = load_settings()
    key = settings.get("deepseek_key", "")
    if not use_ai or not key:
        return {"prompt": fallback, "source": "template", "template": template, "category": category}

    user_prompt = f"""用户描述的商品：{product_description or product.get('name', '')}
商品类型：{category['name']}（{category['id']}）
类型保真要求：{category.get('category_guard', '')}
SKU：{product.get('sku', '')}
模板名称：{template.get('name', '')}
模板场景：{template.get('scene', '')}
首选场景：{scene_note or '按模板默认'}
风格：{style}
用户希望突出：{(extras or {}).get('selling_points') or '未提供，不要自行编造功效'}
必须保留：{(extras or {}).get('must_keep') or '严格保持参考图全部外观'}
用户指定场景/道具：{(extras or {}).get('props') or '未提供，不要添加额外道具'}
禁止出现：{(extras or {}).get('avoid') or '无额外要求'}
请以“用户描述的商品”和参考实拍图为准重写提示词；不要沿用与用户描述冲突的旧商品信息，也不要猜测用户没有提供的品牌、成分、功效或场景。"""
    base = str(settings.get("deepseek_base") or "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        f"{base}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": settings.get("deepseek_model", "deepseek-flash"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.6,
            "max_tokens": 700,
        },
        timeout=90,
    )
    if response.status_code != 200:
        raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:240]}")
    try:
        prompt = response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek 返回格式异常") from exc
    if not prompt:
        return {"prompt": fallback, "source": "template", "template": template, "category": category}
    return {"prompt": prompt, "source": "deepseek", "template": template, "category": category}
