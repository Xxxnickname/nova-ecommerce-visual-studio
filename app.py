from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import re
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

import requests
import uvicorn
from PIL import Image, ImageOps
from fastapi import BackgroundTasks, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool

from ecommerce.ai import generate_image, generate_image_group, test_deepseek
from ecommerce.config import APP_DIR, SETTINGS_PATH, load_settings, public_settings, save_settings
from ecommerce.database import DB_PATH, add_log, add_task, connect, finish_task, init_db, now, one, rows
from ecommerce.models import get_model, load_models, validate_resolution
from ecommerce.notifications import notify
from ecommerce.platforms import adapt_image_to_platform, get_platform, get_size_option, load_platforms
from ecommerce.prompts import build_prompt, category_options, classify_product, get_category, get_template, list_templates, load_catalog, template_prompt
from ecommerce.prompt_plan import build_page_plan
from ecommerce.shopify import ShopifyClient
from ecommerce.style_refs import get_style_ref, load_style_refs
from ecommerce.suite import SUITE_ROLES, render_layout, render_overlay, suite_copy_points

RUN_DIR = Path(os.getenv("ECOMMERCE_RUN_DIR", APP_DIR / "data" / "runs"))
GEN_DIR = RUN_DIR / "generated"
UPLOAD_DIR = RUN_DIR / "uploads"
STATIC_DIR = APP_DIR / "static"
GEN_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RUN_DIR.mkdir(parents=True, exist_ok=True)
init_db()

app = FastAPI(title="NOVA 商品自动化中台", version="3.2.0")
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")
app.mount("/generated", StaticFiles(directory=GEN_DIR), name="generated")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


def _product_payload(product: dict[str, Any]) -> dict[str, Any]:
    item = dict(product)
    item["image1_url"] = f"/product-image/{item['sku']}/1?v={item.get('updated_at', '')}" if item.get("image1") and Path(item["image1"]).exists() else ""
    item["image2_url"] = f"/product-image/{item['sku']}/2?v={item.get('updated_at', '')}" if item.get("image2") and Path(item["image2"]).exists() else ""
    item["shopify_live"] = bool(item.get("shopify_id"))
    item["published"] = bool(item.get("shopify_id")) or item.get("platform_status") in ("已发布", "模拟已发布")
    return item


def _display_error(exc: Exception) -> str:
    text = re.sub(r"https?://\S+", "外部上传地址", str(exc))
    return text[:500]


def _friendly_error(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    lowered = raw.lower()
    if "invalidendpointormodel" in lowered or "model or endpoint" in lowered or "model not found" in lowered:
        return "当前模型不可用或账号无权限，请切换模型后重试。"
    if "401" in raw or "unauthorized" in lowered:
        return "API Key 无效或没有权限，请在设置中检查。"
    if "403" in raw or "forbidden" in lowered:
        return "平台拒绝访问，请检查账号权限和 API 配置。"
    if "timeout" in lowered or "timed out" in lowered:
        return "请求超时，请稍后重试。"
    clean = re.sub(r"\s*Request id:.*$", "", raw, flags=re.I)
    clean = re.sub(r"\s*\{.*$", "", clean, flags=re.S)
    return (clean or raw)[:220]


def _managed_image(path_value: str) -> Path:
    path = Path(path_value).resolve()
    root = GEN_DIR.resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="只允许使用本系统生成的图片")
    if not path.exists():
        raise HTTPException(status_code=404, detail="图片文件不存在")
    return path




def _image_category_id(image: dict[str, Any]) -> str:
    if image.get("category_id"):
        return str(image["category_id"])
    template_id = str(image.get("template_id") or image.get("preset") or "")
    if template_id.startswith("beauty_"):
        return "beauty"
    if template_id in {"living_room", "bedroom", "sofa", "window"}:
        return "home_textile"
    return "generic"


def _managed_upload(path_value: str) -> Path:
    path = Path(path_value).resolve()
    root = UPLOAD_DIR.resolve()
    if root not in path.parents:
        raise HTTPException(status_code=400, detail="参考图必须来自本系统上传")
    if not path.exists():
        raise HTTPException(status_code=404, detail="上传图片不存在")
    return path


def _to_shopify(product: dict[str, Any], image_path: str | None = None, gallery_images: list[str] | None = None) -> dict[str, Any]:
    candidates = ([image_path] if image_path else []) + (gallery_images or []) + [product.get("image1"), product.get("image2")]
    images = []
    for candidate in candidates:
        if candidate and Path(candidate).exists() and candidate not in images:
            images.append(candidate)
    return {
        "sku": product["sku"],
        "title": product["name"],
        "description_html": product.get("description") or f"<p>{product['name']}</p>",
        "vendor": product.get("vendor") or "NOVA Studio",
        "product_type": product.get("product_type") or "Home",
        "tags": (product.get("tags") or "").split(",") if product.get("tags") else [],
        "seo_title": product.get("seo_title") or product["name"],
        "seo_description": product.get("seo_description") or "",
        "price": f"{float(product['price']):.2f}",
        "compare_at_price": f"{float(product['compare_at']):.2f}" if product.get("compare_at") else None,
        "cost": f"{float(product.get('cost') or 0):.2f}",
        "stock": int(product.get("stock") or 0),
        "weight_kg": float(product.get("weight_kg") or 1.0),
        "images": images,
        "category": product.get("category") or "",
        "packed_length": float(product.get("packed_length") or 35),
        "packed_width": float(product.get("packed_width") or 25),
        "packed_height": float(product.get("packed_height") or 8),
        "packed_unit": product.get("packed_unit") or "CENTIMETERS",
        "shopify_id": product.get("shopify_id"),
    }


def _apply_price(conn, task_id: int, sku: str, new_price: float) -> None:
    product = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
    old_price = float(product["price"])
    remote = None
    if product.get("shopify_id"):
        remote = ShopifyClient().update_price(product, new_price)
    conn.execute("UPDATE products SET price=?,updated_at=? WHERE sku=?", (new_price, now(), sku))
    conn.execute(
        "INSERT INTO price_history(sku,old_price,new_price,task_id,created_at) VALUES(?,?,?,?,?)",
        (sku, old_price, new_price, task_id, now()),
    )
    finish_task(conn, task_id, "成功", f"¥{old_price:.2f} → ¥{new_price:.2f}")
    add_log(conn, task_id, "apply", f"{sku} {old_price:.2f} -> {new_price:.2f}" + (f"；Shopify {remote['price']}" if remote else "；仅本地"))


def change_price(sku: str, new_price: float, source: str = "页面") -> dict[str, Any]:
    conn = connect()
    try:
        product = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
        if not product:
            return {"ok": False, "status": "error", "message": "SKU 不存在"}
        if new_price <= 0:
            return {"ok": False, "status": "error", "message": "价格必须大于 0"}
        if new_price < float(product["cost"]):
            notify(f"⚠️ 改价被拦截：{sku} 新价低于成本价")
            return {"ok": False, "status": "error", "message": "价格不能低于成本价"}
        old_price = float(product["price"])
        delta = abs(new_price - old_price) / old_price * 100 if old_price else 0
        task_id = add_task(conn, "改价", sku, f"¥{old_price:.2f}", f"¥{new_price:.2f}", "待执行")
        add_log(conn, task_id, "create", f"{source} 发起改价 {old_price} -> {new_price}")
        threshold = float(load_settings().get("approval_threshold", 5.0))
        if delta > threshold:
            conn.execute("UPDATE tasks SET status='待审批' WHERE id=?", (task_id,))
            conn.execute(
                "INSERT INTO approvals(task_id,sku,old_price,new_price,delta_pct,status,created_at) VALUES(?,?,?,?,?,?,?)",
                (task_id, sku, old_price, new_price, delta, "待审批", now()),
            )
            conn.commit()
            notify(f"⏳ 待审批：{sku} ¥{old_price:.2f} → ¥{new_price:.2f}（{delta:.1f}%）")
            return {"ok": True, "status": "pending", "task_id": task_id, "message": f"幅度 {delta:.1f}% 超过 {threshold:g}%，已提交审批"}
        try:
            _apply_price(conn, task_id, sku, new_price)
        except Exception as exc:
            safe_error = _display_error(exc)
            finish_task(conn, task_id, "失败", safe_error)
            add_log(conn, task_id, "error", safe_error)
            conn.commit()
            notify(f"⚠️ 改价失败：{sku}，{safe_error[:120]}")
            return {"ok": False, "status": "error", "task_id": task_id, "message": f"改价失败：{safe_error}"}
        conn.commit()
        notify(f"✅ 改价成功：{sku} ¥{old_price:.2f} → ¥{new_price:.2f}")
        return {"ok": True, "status": "success", "task_id": task_id, "message": "改价成功"}
    finally:
        conn.close()


def publish_product(sku: str, image_path: str | None = None, source: str = "页面", image_id: int | None = None, platform_id: str | None = None) -> dict[str, Any]:
    conn = connect()
    try:
        product = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
        if not product:
            return {"ok": False, "message": "SKU 不存在"}
        platform = get_platform(platform_id or product.get("target_platform") or "shopify")
        if platform.get("status") == "soon":
            return {"ok": False, "message": f"{platform['name']} 暂未开放"}
        missing = []
        if not str(product.get("name") or "").strip():
            missing.append("商品名称")
        if float(product.get("price") or 0) <= 0:
            missing.append("售价")
        if not product.get("image1") or not Path(product["image1"]).exists():
            missing.append("商品图")
        if int(product.get("stock") or 0) < 0:
            missing.append("库存")
        if missing:
            return {"ok": False, "message": "上架前请补全：" + "、".join(missing)}

        if platform["id"] == "taobao_tmall":
            task_id = add_task(conn, "模拟上架", sku, "", "淘宝/天猫")
            finish_task(conn, task_id, "成功", "已模拟发布到淘宝/天猫（未调用真实平台接口）")
            add_log(conn, task_id, "simulated_publish", "模拟发布，无外部请求")
            conn.execute(
                "UPDATE products SET target_platform=?,platform_status=?,status=?,updated_at=? WHERE sku=?",
                (platform["id"], "模拟已发布", "在售", now(), sku),
            )
            conn.commit()
            notify(f"🧪 模拟发布完成：{sku} → 淘宝/天猫（未调用真实接口）")
            return {"ok": True, "simulated": True, "task_id": task_id, "message": "已模拟发布到淘宝/天猫（未调用真实平台接口）"}

        gallery = rows(conn, "SELECT path FROM product_images WHERE product_sku=? ORDER BY sort_order,id", (sku,))
        gallery_paths = [item["path"] for item in gallery]
        if image_id:
            generated = one(conn, "SELECT * FROM generated_images WHERE id=?", (image_id,))
            if generated and generated.get("published_media_id"):
                return {"ok": True, "task_id": None, "message": "这张图已经同步过 Shopify", "skipped": True}
        task_id = add_task(conn, "上架同步", sku, "", "Shopify ACTIVE")
        add_log(conn, task_id, "create", f"{source} 发起 Shopify 同步")
        conn.commit()
        try:
            client = ShopifyClient()
            result = client.sync_product(_to_shopify(product, image_path, gallery_paths), image_path)
            conn.execute(
                "UPDATE products SET shopify_id=?,shopify_status=?,target_platform=?,platform_status=?,status=?,updated_at=? WHERE sku=?",
                (result["product_id"], result["status"], "shopify", "已发布", "在售", now(), sku),
            )
            finish_task(conn, task_id, "成功", f"Shopify {result.get('handle', '')} / {result['status']}")
            add_log(conn, task_id, "shopify", json.dumps(result, ensure_ascii=False))
            if image_id and result.get("media"):
                conn.execute("UPDATE generated_images SET published_media_id=?,published_at=? WHERE id=?", (str(result["media"][0]), now(), image_id))
            conn.commit()
            notify(f"✅ 商品已同步 Shopify：{sku} → {result.get('handle', '')}")
            return {"ok": True, "task_id": task_id, "message": "已发布到 Shopify", "result": result}
        except Exception as exc:
            safe_error = _display_error(exc)
            finish_task(conn, task_id, "失败", safe_error)
            add_log(conn, task_id, "error", safe_error)
            conn.commit()
            notify(f"⚠️ Shopify 同步失败：{sku}，{safe_error[:120]}")
            return {"ok": False, "task_id": task_id, "message": f"同步失败：{safe_error}"}
    finally:
        conn.close()


def run_generation_job(job_id: int) -> None:
    conn = connect()
    job = one(conn, "SELECT * FROM image_jobs WHERE id=?", (job_id,))
    if not job:
        conn.close()
        return
    try:
        conn.execute("UPDATE image_jobs SET status='running' WHERE id=?", (job_id,))
        conn.commit()
        params = json.loads(job.get("params") or "{}")
        product = {
            "sku": "",
            "name": params.get("product_description", "")[:80],
            "description": "",
        }
        template = get_template(params.get("template_id", "generic_white_bg"))
        prompt = (params.get("prompt") or "").strip()
        prompt_source = params.get("prompt_source") or "manual"
        if not prompt:
            generated = build_prompt(
                product,
                template["id"],
                params.get("scene", ""),
                params.get("style", "干净商业"),
                use_ai=True,
                product_description=params.get("product_description", ""),
                category_id=params.get("category_id", ""),
                extras=params.get("extras") or {},
            )
            prompt = generated["prompt"]
            prompt_source = generated["source"]
        reference = None
        if params.get("reference_path"):
            reference = str(_managed_upload(params["reference_path"]))
        style_ref = get_style_ref(params.get("style_ref_id"))
        references = [reference] if reference else []
        if style_ref:
            references.append(style_ref["path"])
            prompt += "\n参考图角色：第一张为产品身份参考；最后一张仅参考背景、光线、配色和装饰语言，不复制其中的物体或文字。"
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        target = GEN_DIR / "STUDIO" / f"STUDIO-{stamp}-{job_id}.png"
        model_id = str(params.get("model_id") or load_settings().get("ark_model") or "")
        generation_resolution = str(params.get("generation_resolution") or "2K").upper()
        result = generate_image(prompt, target, references, model_id=model_id, resolution=generation_resolution)
        platform_id = params.get("platform_id", "shopify")
        size_id = params.get("size_id")
        adapted = adapt_image_to_platform(result["path"], platform_id, size_id)
        result.update({"width": adapted["width"], "height": adapted["height"], "bytes": adapted["bytes"]})
        image_row = conn.execute(
            """INSERT INTO generated_images(
              sku,path,prompt,preset,style,template_id,source,width,height,file_size,job_id,created_at,platform_id,model_id,generation_resolution,category_id
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "STUDIO", result["path"], prompt, template["id"], params.get("style", "干净商业"),
                template["id"], prompt_source, result["width"], result["height"], result["bytes"],
                job_id, now(), platform_id, model_id, generation_resolution, params.get("category_id", ""),
            ),
        )
        image_id = int(image_row.lastrowid)
        result_payload = {
            "image_id": image_id,
            "path": result["path"],
            "url": f"/generated/{Path(result['path']).relative_to(GEN_DIR).as_posix()}",
            "prompt": prompt,
            "prompt_source": prompt_source,
            "seconds": result["seconds"],
            "width": result["width"],
            "height": result["height"],
            "platform_id": platform_id,
            "size_id": adapted.get("size_id"),
            "model_id": model_id,
            "generation_resolution": generation_resolution,
            "category_id": params.get("category_id", ""),
        }
        conn.execute(
            "UPDATE image_jobs SET status='success',result=?,finished_at=? WHERE id=?",
            (json.dumps(result_payload, ensure_ascii=False), now(), job_id),
        )
        conn.commit()
        notify(f"🖼️ 生图完成：{job['sku']} · {template['name']}")
    except Exception as exc:
        conn.execute(
            "UPDATE image_jobs SET status='failed',error=?,finished_at=? WHERE id=?",
            (_display_error(exc), now(), job_id),
        )
        conn.commit()
    finally:
        conn.close()


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/studio")
def studio_redirect():
    return RedirectResponse("/#studio")


@app.get("/settings")
def settings_redirect():
    return RedirectResponse("/#settings")


@app.get("/agent")
def agent_redirect():
    return RedirectResponse("/#agent")


@app.post("/api/upload-reference")
async def upload_reference(category_id: str, file: UploadFile = File(...)):
    category = get_category(category_id)
    if not category or category.get("id") != category_id:
        return JSONResponse({"ok": False, "message": "请先选择有效的商品类型"}, status_code=400)
    raw = await file.read()
    if not raw:
        return JSONResponse({"ok": False, "message": "图片为空"}, status_code=400)
    if len(raw) > 20 * 1024 * 1024:
        return JSONResponse({"ok": False, "message": "图片不能超过 20MB"}, status_code=413)
    try:
        with Image.open(io.BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            width, height = image.size
            if width < 300 or height < 300:
                return JSONResponse({"ok": False, "message": "图片分辨率过低，请上传至少 300×300 的实拍图"}, status_code=400)
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            folder = UPLOAD_DIR / "STUDIO" / category_id
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"{category_id}-实拍-{stamp}-{uuid.uuid4().hex[:10]}.png"
            image.save(target, format="PNG", optimize=True)
    except Exception as exc:
        return JSONResponse({"ok": False, "message": f"无法识别图片，请使用 JPG、PNG 或 WebP：{str(exc)[:120]}"}, status_code=400)
    relative = target.relative_to(UPLOAD_DIR).as_posix()
    return {
        "ok": True,
        "category_id": category_id,
        "path": str(target),
        "url": f"/uploads/{relative}",
        "width": width,
        "height": height,
        "name": Path(file.filename or "实拍图").name,
    }


def _suite_templates(category: dict[str, Any]) -> list[dict[str, Any]]:
    templates = []
    for template_id in category.get("suite_template_ids") or []:
        try:
            templates.append(get_template(template_id))
        except ValueError:
            continue
    if not templates:
        templates = list_templates(category["id"])
    while len(templates) < 7:
        templates.append(templates[-1])
    return templates


def _suite_style_lock(params: dict[str, Any]) -> str:
    extras = params.get("extras") or {}
    brand = str(extras.get("brand_name") or "").strip()
    brand_rule = (
        f"品牌/系列名只允许使用用户提供的“{brand}”，不得新增其他品牌名或 logo。"
        if brand else "不添加品牌名、额外 logo、虚构系列名或水印。"
    )
    style_ref = get_style_ref(params.get("style_ref_id"))
    if style_ref:
        palette = "、".join(style_ref.get("palette") or [])
        direction = (
            f"统一视觉母版“{style_ref['name']}”：{style_ref.get('description', '')}；"
            f"主色为{palette or '按参考图'}；以参考图的光线、背景、材质和装饰语言为准。"
        )
    else:
        style = str(params.get("style") or "干净商业").strip()
        direction = f"统一视觉方向“{style}”：统一背景、光线、配色、字体气质和装饰语言。"
    return (
        f"CAMPAIGN STYLE LOCK：{direction} 12 张必须像同一套 campaign；"
        "柔和真实接触阴影，高级纸感与细腻材质，12 栏网格，充足留白；"
        "中文使用清晰现代无衬线体，英文使用简洁几何无衬线体；"
        "禁止霓虹色、玻璃拟态、厚重渐变、廉价金色、杂乱贴纸和额外水印。"
        f"{brand_rule}"
    )


def _suite_prompt(role: dict[str, Any], template: dict[str, Any], product: dict[str, Any], params: dict[str, Any], category: dict[str, Any]) -> str:
    scene_note = role["instruction"]
    selected_scene = str(params.get("scene") or "").strip()
    if selected_scene and selected_scene != "按模板默认":
        scene_note += f"；用户偏好场景：{selected_scene}"
    base = template_prompt(
        product, template, scene_note, params.get("style") or "干净商业",
        str(params.get("product_description") or ""), category["id"], params.get("extras") or {},
    )
    return f"{_suite_style_lock(params)}\n{base}"


def _suite_layout_prompt(role: dict[str, Any], params: dict[str, Any], category: dict[str, Any]) -> str:
    """Prompts for text-free backgrounds; typography is added safely by the renderer."""
    style_lock = _suite_style_lock(params)
    common = (
        f"{style_lock} 这是一张用于电商详情页的摄影背景，画面中严禁出现任何新增文字、数字、表格、"
        "标签、按钮、标注线、水印或图标；商品包装上原有的真实标签和 logo 保持原样，不新增、不改写。"
        "需要预留干净、无杂物的负空间供后续排版，主体边缘完整，不要裁切商品。"
    )
    if role["id"] == "08_benefits_1":
        return (
            f"生成一张高级电商首屏背景摄影。{common} "
            "商品与包装置于画面右侧 55% 区域，左侧 45% 保持干净、低细节的浅色负空间；"
            "左上方留出品牌与标题区域，左侧中下部留出三层文字区域；柔和自然光，商品与背景有真实接触阴影。"
        )
    if role["id"] == "09_benefits_2":
        return (
            f"生成一张高级电商细节背景摄影。{common} "
            "商品与包装置于画面左侧 45% 区域，右侧 55% 保持干净的深色或低饱和负空间；"
            "右侧上方留标题区，中下部留三段信息区；使用有层次但不过曝的侧逆光。"
        )
    if role["id"] == "10_size_spec":
        return (
            f"生成一张电商规格展示背景摄影。{common} "
            "商品完整置于画面左侧偏中，右侧 33% 保持低细节浅色负空间用于三块规格信息；"
            "不要画尺寸线、数字或箭头，商品比例真实，正面结构清楚，背景干净。"
        )
    if role["id"] == "11_in_box":
        return (
            f"生成一张电商包装与使用背景摄影。{common} "
            "商品主体和外包装盒置于画面左侧 42% 区域，右侧 55% 保持干净的深色负空间用于清单与步骤；"
            "包装盒结构完整，商品标签清楚，材质高级。"
        )
    return (
        f"生成一张电商多规格背景摄影。{common} "
        "同款商品以标准装、礼盒装、旅行装的陈列关系置于画面中部，底部 20% 留出低细节浅色负空间用于规格标签；"
        "商品外观保持同款一致，仅陈列数量与包装组合变化，不出现任何文字或数字。"
    )


def _suite_plan(params: dict[str, Any]) -> dict[str, Any]:
    category = get_category(params.get("category_id", "generic"))
    templates = _suite_templates(category)
    product = {"sku": "", "name": str(params.get("product_description") or "")[:80], "description": ""}
    plan = []
    image_index = 0
    for role in SUITE_ROLES:
        if role["kind"] == "image":
            template = templates[min(image_index, len(templates) - 1)]
            image_index += 1
            prompt = _suite_prompt(role, template, product, params, category)
            plan.append({"role": role["id"], "name": role["name"], "kind": "image", "render_mode": "photo", "template_id": template["id"], "prompt": prompt})
        else:
            plan.append({"role": role["id"], "name": role["name"], "kind": "layout", "render_mode": "overlay", "template_id": role.get("layout", ""), "prompt": _suite_layout_prompt(role, params, category), "note": "Seedream 生成无文字背景，系统叠加安全边距文字"})
    return {"ok": True, "category": category["id"], "items": plan}


def _suite_group_prompt(params: dict[str, Any], category: dict[str, Any], plan: list[dict[str, Any]]) -> str:
    points = suite_copy_points(params.get("extras") or {}, category["id"])
    dimensions = re.findall(r"\d+(?:\.\d+)?\s*[x×*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|ml|g|kg)?", str(params.get("product_description") or ""), flags=re.I)
    dimension_text = dimensions[0] if dimensions else "规格信息以商品详情为准"
    brand = str((params.get("extras") or {}).get("brand_name") or "").strip()
    brand_line = f"品牌/系列名仅使用“{brand}”，不得新增其他品牌。" if brand else "不添加品牌名、额外 logo 或虚构系列名。"
    lines = [
        f"{brand_line} 生成一套风格高度统一的电商商品视觉组图，共 12 张。",
        "统一要求：同一款商品、同一套配色、同一光线语言、同一摄影质感；严格保持参考图中的商品外形、颜色、材质、结构、标签位置和比例。",
        "每张图独立输出，不要拼贴成长图，不要加外框。除信息版式外，不在照片型画面上添加文字。",
        "输出顺序必须严格对应下面的 01-12：",
    ]
    for item in plan:
        if item["kind"] == "image":
            lines.append(f"{item['role']} {item['name']}：{item['prompt']}")
    lines.extend([
        f"08 核心卖点 A：米白编辑式信息版式，左侧品牌标题，右侧商品图；三个卖点必须逐字准确：{points[0]} / {points[1]} / {points[2]}。",
        f"09 核心卖点 B：深色高级信息版式，左侧商品图，右侧三个卖点；文字必须逐字准确：{points[0]} / {points[1]} / {points[2]}。",
        f"10 尺寸规格：浅色信息版式，商品居中，清晰尺寸线和规格文字；核心文字必须准确：{dimension_text}；不要乱码。",
        "11 包装清单：深色礼盒式信息版式，商品与包装整齐陈列；文字必须准确：商品主体 ×1 / 包装盒 ×1 / 说明卡 ×1。",
        "12 多规格展示：三格网格版式，展示标准装 / 礼盒装 / 旅行装三种规格，商品保持同一款外观；文字必须准确。",
        "所有中文文字必须清晰、可读、无错字、无乱码、无额外水印。",
    ])
    return "\n".join(lines)


def run_suite_job(job_id: int) -> None:
    conn = connect()
    job = one(conn, "SELECT * FROM image_jobs WHERE id=?", (job_id,))
    if not job:
        conn.close()
        return
    suite_id = uuid.uuid4().hex[:12]
    try:
        conn.execute("UPDATE image_jobs SET status='running' WHERE id=?", (job_id,))
        params = json.loads(job.get("params") or "{}")
        category = get_category(params.get("category_id", "generic"))
        description = str(params.get("product_description") or "")
        extras = params.get("extras") or {}
        platform_id = params.get("platform_id", "shopify")
        size_id = params.get("size_id")
        size = get_size_option(platform_id, size_id)
        model_id = str(params.get("model_id") or load_settings().get("ark_model") or "")
        generation_resolution = str(params.get("generation_resolution") or "2K").upper()
        reference = str(_managed_upload(params["reference_path"])) if params.get("reference_path") else None
        if not reference:
            raise RuntimeError("套图必须上传产品实拍图")
        style_ref = get_style_ref(params.get("style_ref_id"))
        templates = _suite_templates(category)
        provided_prompts = params.get("prompts") or {}
        plan = _suite_plan(params)["items"]
        plan_by_role = {item["role"]: item for item in plan}
        seed = int(hashlib.sha256(f"{description}|{platform_id}|{params.get('style')}".encode("utf-8")).hexdigest()[:8], 16)
        result_payload = {
            "suite_id": suite_id, "platform_id": platform_id, "size_id": size["id"],
            "width": int(size["width"]), "height": int(size["height"]), "progress": 0,
            "total": len(SUITE_ROLES), "items": [], "strategy": "shared_reference_seed", "seed": seed,
            "model_id": model_id, "generation_resolution": generation_resolution,
            "category_id": params.get("category_id", ""),
        }
        conn.execute("UPDATE image_jobs SET result=? WHERE id=?", (json.dumps(result_payload, ensure_ascii=False), job_id))
        conn.commit()
        main_path = None
        image_index = 0
        for role in SUITE_ROLES:
            plan_item = plan_by_role[role["id"]]
            prompt = str(provided_prompts.get(role["id"]) or plan_item.get("prompt") or "")
            references = [reference] + ([main_path] if main_path else []) + ([style_ref["path"]] if style_ref else [])
            target = GEN_DIR / "STUDIO" / f"{suite_id}-{role['id']}.png"
            try:
                if role["kind"] == "layout":
                    background_target = GEN_DIR / "STUDIO" / f"{suite_id}-{role['id']}-background.png"
                    try:
                        generated = generate_image(prompt, background_target, references, seed=seed, model_id=model_id, resolution=generation_resolution)
                        adapted = adapt_image_to_platform(generated["path"], platform_id, size_id)
                        rendered = render_overlay(
                            role, adapted["path"], target, int(size["width"]), int(size["height"]),
                            description, extras, category["id"], style_ref["id"] if style_ref else "",
                        )
                    finally:
                        background_target.unlink(missing_ok=True)
                    item = {**rendered, "prompt": prompt, "template_id": role.get("layout", ""), "source": "seedream_background_overlay"}
                else:
                    generated = generate_image(prompt, target, references, seed=seed, model_id=model_id, resolution=generation_resolution)
                    adapted = adapt_image_to_platform(generated["path"], platform_id, size_id)
                    item = {**adapted, "prompt": prompt, "template_id": plan_item.get("template_id", ""), "source": "seedream"}
            except Exception:
                if role["kind"] != "layout" or not main_path:
                    raise
                rendered = render_layout(role, main_path, target, int(size["width"]), int(size["height"]), description, extras, category["id"])
                item = {**rendered, "prompt": prompt, "template_id": role.get("layout", ""), "source": "layout_fallback"}
            if main_path is None:
                main_path = item["path"]
            image_row = conn.execute(
                """INSERT INTO generated_images(
                  sku,path,prompt,preset,style,template_id,source,width,height,file_size,job_id,created_at,platform_id,suite_id,asset_role,model_id,generation_resolution,category_id
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "STUDIO", item["path"], item.get("prompt", ""), item.get("template_id", ""),
                    params.get("style") or "干净商业", item.get("template_id", ""), item.get("source", "suite"),
                    item["width"], item["height"], item["bytes"], job_id, now(), platform_id, suite_id, role["id"],
                    model_id, generation_resolution, params.get("category_id", ""),
                ),
            )
            image_id = int(image_row.lastrowid)
            result_payload["items"].append({
                "image_id": image_id, "role": role["id"], "name": role["name"], "kind": role["kind"],
                "path": item["path"], "url": f"/generated/{Path(item['path']).relative_to(GEN_DIR).as_posix()}",
                "width": item["width"], "height": item["height"], "source": item.get("source"),
            })
            result_payload["progress"] = len(result_payload["items"])
            conn.execute("UPDATE image_jobs SET result=? WHERE id=?", (json.dumps(result_payload, ensure_ascii=False), job_id))
            conn.commit()
        conn.execute("UPDATE image_jobs SET status='success',finished_at=? WHERE id=?", (now(), job_id))
        conn.commit()
        notify(f"🖼️ 12 张套图完成：{description[:30] or category['name']}")
    except Exception as exc:
        safe_error = _display_error(exc)
        try:
            current = one(conn, "SELECT result FROM image_jobs WHERE id=?", (job_id,))
            result_payload = json.loads(current["result"]) if current and current.get("result") else {}
            result_payload["error"] = safe_error
            conn.execute("UPDATE image_jobs SET status='failed',result=?,error=?,finished_at=? WHERE id=?", (json.dumps(result_payload, ensure_ascii=False), safe_error, now(), job_id))
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


@app.get("/product-image/{sku}/{slot}")
def product_image(sku: str, slot: int):
    conn = connect()
    product = one(conn, "SELECT image1,image2 FROM products WHERE sku=?", (sku,))
    conn.close()
    if not product:
        raise HTTPException(status_code=404)
    path_value = product.get("image1") if slot == 1 else product.get("image2")
    if not path_value or not Path(path_value).exists():
        raise HTTPException(status_code=404)
    return FileResponse(path_value)


@app.get("/api/health")
def health():
    conn = connect()
    product_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    conn.close()
    return {"ok": True, "products": product_count, "time": now()}


def _writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".nova-write-", delete=True):
            return True
    except OSError:
        return False


@app.get("/api/system-check")
def system_check():
    settings = load_settings()
    conn = connect()
    try:
        db_ok = conn.execute("SELECT 1").fetchone()[0] == 1
        counts = {
            "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
            "drafts": conn.execute("SELECT COUNT(*) FROM products WHERE shopify_id IS NULL OR shopify_id=''").fetchone()[0],
            "images": conn.execute("SELECT COUNT(*) FROM generated_images").fetchone()[0],
            "jobs_running": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status IN ('queued','running')").fetchone()[0],
            "jobs_failed": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status='failed'").fetchone()[0],
        }
    finally:
        conn.close()
    templates = list_templates()
    styles = load_style_refs()
    style_files_ok = len(styles) >= 8 and all(Path(item.get("path", "")).exists() for item in styles)
    models = load_models()
    platforms = load_platforms()
    storage_ok = all(_writable_dir(path) for path in (RUN_DIR, GEN_DIR, UPLOAD_DIR))
    settings_ok = _writable_dir(SETTINGS_PATH.parent)
    checks = [
        {"id": "database", "label": "SQLite 数据库", "ok": db_ok, "required": True, "detail": f"可读写，{counts['products']} 个商品"},
        {"id": "storage", "label": "本地图片目录", "ok": storage_ok, "required": True, "detail": "上传图与生成图目录可写" if storage_ok else "目录不可写，请检查权限"},
        {"id": "settings_file", "label": "本机配置文件", "ok": settings_ok, "required": True, "detail": str(SETTINGS_PATH) if settings_ok else "设置目录不可写"},
        {"id": "ark", "label": "Seedream / Ark", "ok": bool(settings.get("ark_key")), "required": True, "detail": "API Key 已配置" if settings.get("ark_key") else "未配置，无法生成图片"},
        {"id": "deepseek", "label": "DeepSeek", "ok": bool(settings.get("deepseek_key")), "required": False, "detail": "API Key 已配置" if settings.get("deepseek_key") else "未配置；仍可用模板提示词，但无法 AI 识别"},
        {"id": "shopify", "label": "Shopify", "ok": bool(settings.get("shopify_store") and settings.get("shopify_token")), "required": False, "detail": "店铺与 Token 已配置" if settings.get("shopify_store") and settings.get("shopify_token") else "未配置；真实发布不可用"},
        {"id": "templates", "label": "提示词模板", "ok": len(templates) >= 10, "required": True, "detail": f"{len(templates)} 个模板已加载"},
        {"id": "styles", "label": "风格图库", "ok": style_files_ok, "required": True, "detail": f"{len(styles)} 套原创参考已加载" if style_files_ok else "风格参考文件缺失"},
        {"id": "catalogs", "label": "模型与平台目录", "ok": bool(models and platforms), "required": True, "detail": f"{len(models)} 个模型，{len(platforms)} 个平台"},
    ]
    ready = all(item["ok"] for item in checks if item["required"])
    return {"ok": True, "ready": ready, "checks": checks, "counts": counts, "generated_at": now(), "runtime": {"python": sys.version.split()[0], "app_dir": str(APP_DIR), "db_path": str(DB_PATH)}}


@app.get("/api/dashboard")
def dashboard():
    conn = connect()
    metrics = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "live": conn.execute("SELECT COUNT(*) FROM products WHERE platform_status IN ('已发布','模拟已发布')").fetchone()[0],
        "drafts": conn.execute("SELECT COUNT(*) FROM products WHERE shopify_id IS NULL OR shopify_id = ''").fetchone()[0],
        "pending": conn.execute("SELECT COUNT(*) FROM approvals WHERE status='待审批'").fetchone()[0],
        "images": conn.execute("SELECT COUNT(*) FROM generated_images").fetchone()[0],
        "tasks": conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0],
    }
    recent_tasks = rows(conn, "SELECT * FROM tasks ORDER BY id DESC LIMIT 8")
    recent_images = rows(conn, "SELECT * FROM generated_images ORDER BY id DESC LIMIT 6")
    conn.close()
    for image in recent_images:
        path = Path(image["path"])
        image["url"] = f"/generated/{path.relative_to(GEN_DIR).as_posix()}" if path.exists() and GEN_DIR in path.parents else ""
    return {"metrics": metrics, "recent_tasks": recent_tasks, "recent_images": recent_images}


@app.get("/api/products")
def products():
    conn = connect()
    items = rows(conn, "SELECT * FROM products ORDER BY sku")
    conn.close()
    return {"items": [_product_payload(item) for item in items]}


@app.get("/api/products/{sku}")
def product_detail(sku: str):
    conn = connect()
    item = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
    logs = rows(conn, "SELECT * FROM logs WHERE task_id IN (SELECT id FROM tasks WHERE sku=?) ORDER BY id DESC LIMIT 12", (sku,))
    gallery = rows(conn, "SELECT * FROM product_images WHERE product_sku=? ORDER BY sort_order,id", (sku,))
    conn.close()
    if not item:
        raise HTTPException(status_code=404, detail="SKU 不存在")
    for gallery_item in gallery:
        gallery_path = Path(gallery_item["path"])
        gallery_item["url"] = f"/generated/{gallery_path.relative_to(GEN_DIR).as_posix()}" if gallery_path.exists() and GEN_DIR in gallery_path.parents else ""
    return {"product": _product_payload(item), "logs": logs, "images": gallery}


@app.patch("/api/products/{sku}")
async def update_product(sku: str, request: Request):
    payload = await request.json()
    allowed = {
        "sku", "name", "cost", "price", "stock", "status", "description", "vendor", "product_type",
        "tags", "seo_title", "seo_description", "weight_kg", "compare_at",
        "category", "packed_length", "packed_width", "packed_height", "packed_unit", "target_platform",
    }
    updates = {key: value for key, value in payload.items() if key in allowed}
    if not updates:
        return JSONResponse({"ok": False, "message": "没有可更新字段"}, status_code=400)
    if "cost" in updates and float(updates["cost"]) < 0:
        return JSONResponse({"ok": False, "message": "成本不能为负数"}, status_code=400)
    conn = connect()
    try:
        existing = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
        if not existing:
            raise HTTPException(status_code=404, detail="SKU 不存在")
        final_cost = float(updates.get("cost", existing.get("cost") or 0))
        final_price = float(updates.get("price", existing.get("price") or 0))
        if final_cost < 0 or final_price < 0:
            return JSONResponse({"ok": False, "message": "价格和成本不能为负数"}, status_code=400)
        if final_price and final_cost > final_price:
            return JSONResponse({"ok": False, "message": "成本不能高于售价"}, status_code=400)
        new_sku = str(updates.pop("sku", "") or "").strip()
        if new_sku and new_sku != sku:
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{2,63}", new_sku):
                return JSONResponse({"ok": False, "message": "SKU 只能使用字母、数字、下划线或连字符"}, status_code=400)
            if one(conn, "SELECT 1 FROM products WHERE sku=?", (new_sku,)):
                return JSONResponse({"ok": False, "message": "SKU 已存在"}, status_code=409)
            updates["sku"] = new_sku
        assignments = ", ".join(f"{key}=?" for key in updates)
        conn.execute(f"UPDATE products SET {assignments},updated_at=? WHERE sku=?", (*updates.values(), now(), sku))
        target_sku = new_sku or sku
        if new_sku:
            for table in ("tasks", "approvals", "price_history", "generated_images", "image_jobs"):
                conn.execute(f"UPDATE {table} SET sku=? WHERE sku=?", (new_sku, sku))
        task_id = add_task(conn, "商品资料", target_sku, "", ", ".join(updates.keys()))
        finish_task(conn, task_id, "成功", "商品资料已更新")
        add_log(conn, task_id, "update", json.dumps(updates, ensure_ascii=False))
        conn.commit()
        return {"ok": True, "product": _product_payload(one(conn, "SELECT * FROM products WHERE sku=?", (target_sku,)))}
    finally:
        conn.close()


@app.post("/api/products/{sku}/price")
async def product_price(sku: str, request: Request):
    data = await request.json()
    try:
        new_price = float(data["new_price"])
    except (KeyError, TypeError, ValueError):
        return JSONResponse({"ok": False, "message": "请输入有效价格"}, status_code=400)
    return change_price(sku, new_price)


@app.post("/api/products/from-image")
async def product_from_image(request: Request):
    data = await request.json()
    image_id = int(data.get("image_id") or 0)
    if not image_id:
        return JSONResponse({"ok": False, "message": "缺少生成图片"}, status_code=400)
    conn = connect()
    try:
        image = one(conn, "SELECT * FROM generated_images WHERE id=?", (image_id,))
        if not image:
            return JSONResponse({"ok": False, "message": "生成图片不存在"}, status_code=404)
        existing = one(conn, "SELECT * FROM products WHERE sku=?", (image["sku"],)) if image["sku"] != "STUDIO" else None
        if existing:
            return {"ok": True, "product": _product_payload(existing), "existing": True}
        category = get_category(str(data.get("category_id") or _image_category_id(image)))
        platform_id = str(data.get("platform_id") or image.get("platform_id") or "shopify")
        platform = get_platform(platform_id)
        description = str(data.get("product_description") or "").strip()
        name = str(data.get("name") or "").strip() or (description[:42] or f"{category['name']}新品")
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        base_sku = f"DRAFT-{stamp}"
        draft_sku = base_sku
        suffix = 2
        while one(conn, "SELECT 1 FROM products WHERE sku=?", (draft_sku,)):
            draft_sku = f"{base_sku}-{suffix}"
            suffix += 1
        if category["id"] == "beauty":
            weight, dims = 0.4, (10, 8, 6)
        elif category["id"] == "home_textile":
            weight, dims = 1.2, (35, 25, 8)
        else:
            weight, dims = 1.0, (20, 15, 10)
        conn.execute(
            """INSERT INTO products(
              sku,name,cost,price,stock,status,updated_at,description,vendor,product_type,
              tags,seo_title,seo_description,image1,image2,weight_kg,compare_at,
              shopify_id,shopify_status,category,packed_length,packed_width,packed_height,packed_unit,target_platform,platform_status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                draft_sku, name, 0, 0, 0, "草稿", now(), description, "", category["name"],
                category["name"], name, "", image["path"], "", weight, 0, "", "", "",
                dims[0], dims[1], dims[2], "CENTIMETERS", platform_id, "未发布",
            ),
        )
        suite_images = rows(conn, "SELECT * FROM generated_images WHERE suite_id=? ORDER BY asset_role", (image.get("suite_id"),)) if image.get("suite_id") else [image]
        for order, generated_image in enumerate(suite_images):
            conn.execute("UPDATE generated_images SET sku=? WHERE id=?", (draft_sku, generated_image["id"]))
            conn.execute(
                "INSERT INTO product_images(product_sku,path,role,sort_order,created_at) VALUES(?,?,?,?,?)",
                (draft_sku, generated_image["path"], generated_image.get("asset_role") or "", order, now()),
            )
        if suite_images:
            second_path = suite_images[1]["path"] if len(suite_images) > 1 else ""
            conn.execute("UPDATE products SET image1=?,image2=? WHERE sku=?", (suite_images[0]["path"], second_path, draft_sku))
        task_id = add_task(conn, "创建商品草稿", draft_sku, "", Path(image["path"]).name)
        finish_task(conn, task_id, "成功", "已从生成图创建商品草稿")
        add_log(conn, task_id, "create_draft", f"image_id={image_id}; category={category['id']}")
        conn.commit()
        product = one(conn, "SELECT * FROM products WHERE sku=?", (draft_sku,))
        notify(f"🆕 商品草稿已创建：{draft_sku} {name}")
        return {"ok": True, "product": _product_payload(product)}
    finally:
        conn.close()


@app.post("/api/products/{sku}/publish")
async def product_publish(sku: str, request: Request):
    data = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    image_path = data.get("image_path")
    platform_id = str(data.get("platform_id") or "").strip() or None
    if image_path:
        image_path = str(_managed_image(image_path))
    return await run_in_threadpool(publish_product, sku, image_path, "页面", None, platform_id)


@app.get("/api/approvals")
def approvals():
    conn = connect()
    items = rows(conn, "SELECT * FROM approvals ORDER BY CASE status WHEN '待审批' THEN 0 ELSE 1 END, id DESC LIMIT 50")
    conn.close()
    return {"items": items}


@app.post("/api/approvals/{approval_id}/approve")
def approve(approval_id: int):
    conn = connect()
    try:
        item = one(conn, "SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not item or item["status"] != "待审批":
            return JSONResponse({"ok": False, "message": "审批不存在或已处理"}, status_code=409)
        try:
            _apply_price(conn, item["task_id"], item["sku"], float(item["new_price"]))
        except Exception as exc:
            safe_error = _display_error(exc)
            add_log(conn, item["task_id"], "error", safe_error)
            conn.commit()
            notify(f"⚠️ 审批执行失败：{item['sku']}，{safe_error[:120]}")
            return JSONResponse({"ok": False, "message": f"审批执行失败：{safe_error}"}, status_code=502)
        conn.execute("UPDATE approvals SET status='通过',decided_at=? WHERE id=?", (now(), approval_id))
        conn.commit()
        notify(f"✅ 审批通过并执行：{item['sku']} → ¥{item['new_price']:.2f}")
        return {"ok": True, "message": "已通过并执行"}
    finally:
        conn.close()


@app.post("/api/approvals/{approval_id}/reject")
def reject(approval_id: int):
    conn = connect()
    try:
        item = one(conn, "SELECT * FROM approvals WHERE id=?", (approval_id,))
        if not item or item["status"] != "待审批":
            return JSONResponse({"ok": False, "message": "审批不存在或已处理"}, status_code=409)
        conn.execute("UPDATE approvals SET status='驳回',decided_at=? WHERE id=?", (now(), approval_id))
        finish_task(conn, item["task_id"], "已驳回", "审批驳回，未执行")
        add_log(conn, item["task_id"], "reject", "审批驳回")
        conn.commit()
        notify(f"❌ 审批驳回：{item['sku']}，未执行")
        return {"ok": True, "message": "已驳回，未执行"}
    finally:
        conn.close()


@app.get("/api/tasks")
def tasks(limit: int = 50):
    conn = connect()
    items = rows(conn, "SELECT * FROM tasks ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),))
    for item in items:
        item["can_rollback"] = bool(one(conn, "SELECT 1 FROM price_history WHERE task_id=? LIMIT 1", (item["id"],)))
        if item.get("status") in ("失败", "中断"):
            item["message"] = _friendly_error(item.get("message") or "")
    summary = {
        "running": conn.execute("SELECT COUNT(*) FROM tasks WHERE status='执行中'").fetchone()[0],
        "failed": conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('失败','中断')").fetchone()[0],
        "success": conn.execute("SELECT COUNT(*) FROM tasks WHERE status IN ('成功','已回滚')").fetchone()[0],
    }
    conn.close()
    return {"items": items, "summary": summary}


@app.post("/api/tasks/{task_id}/rollback")
def rollback(task_id: int):
    conn = connect()
    try:
        history = one(conn, "SELECT * FROM price_history WHERE task_id=? ORDER BY id DESC LIMIT 1", (task_id,))
        if not history:
            return JSONResponse({"ok": False, "message": "没有可回滚的价格记录"}, status_code=409)
        product = one(conn, "SELECT * FROM products WHERE sku=?", (history["sku"],))
        if product and product.get("shopify_id"):
            try:
                ShopifyClient().update_price(product, float(history["old_price"]))
            except Exception as exc:
                safe_error = _display_error(exc)
                add_log(conn, task_id, "error", f"rollback: {safe_error}")
                conn.commit()
                return JSONResponse({"ok": False, "message": f"Shopify 回滚失败：{safe_error}"}, status_code=502)
        conn.execute("UPDATE products SET price=?,updated_at=? WHERE sku=?", (history["old_price"], now(), history["sku"]))
        finish_task(conn, task_id, "已回滚", f"恢复 ¥{history['old_price']:.2f}")
        add_log(conn, task_id, "rollback", f"{history['sku']} {history['new_price']} -> {history['old_price']}")
        conn.commit()
        notify(f"↩️ 已回滚：{history['sku']} → ¥{history['old_price']:.2f}")
        return {"ok": True, "message": "已回滚到改价前"}
    finally:
        conn.close()


@app.get("/api/templates")
def templates(category: str | None = None):
    return {"items": list_templates(category)}


@app.get("/api/style-refs")
def style_refs():
    return {"items": load_style_refs()}


@app.get("/api/models")
def models():
    configured = str(load_settings().get("ark_model") or "")
    return {
        "items": [
            {**item, "configured": item["id"] == configured}
            for item in load_models()
        ],
        "configured_model": configured,
    }


@app.get("/api/platforms")
def platforms():
    return {"items": load_platforms()}


@app.get("/api/categories")
def categories():
    items = [
        {"id": item["id"], "name": item["name"], "description": item.get("description", "")}
        for item in load_catalog()["categories"]
    ]
    return {"items": items}


@app.get("/api/categories/{category_id}/options")
def category_option_list(category_id: str):
    return category_options(category_id)


@app.post("/api/classify-product")
async def classify(request: Request):
    data = await request.json()
    description = str(data.get("description") or "").strip()
    sku = str(data.get("sku") or "").strip()
    product = None
    if sku:
        conn = connect()
        product = one(conn, "SELECT * FROM products WHERE sku=?", (sku,))
        conn.close()
    if not description and not product:
        return JSONResponse({"ok": False, "message": "请先输入商品是什么"}, status_code=400)
    try:
        result = await run_in_threadpool(classify_product, description, product)
        return result
    except Exception as exc:
        category = get_category("generic")
        return {
            "ok": True,
            "source": "fallback",
            "description": description,
            "category": {"id": category["id"], "name": category["name"], "description": category.get("description", "")},
            "confidence": 0.35,
            "reason": f"分类失败，已使用通用模板：{str(exc)[:120]}",
            "default_template_id": category.get("default_template"),
            "templates": [{"id": item["id"], "name": item.get("name", item["id"]), "description": item.get("description", "")} for item in list_templates("generic")],
            "scenes": category.get("scene_options", []),
            "styles": category.get("style_options", []),
            "category_guard": category.get("category_guard", ""),
        }


@app.post("/api/prompt")
async def prompt(request: Request):
    data = await request.json()
    if not str(data.get("category_id") or "").strip():
        return JSONResponse({"ok": False, "message": "请先选择商品类型"}, status_code=400)
    product = {"sku": "", "name": str(data.get("product_description") or "")[:80], "description": ""}
    try:
        result = await run_in_threadpool(
            build_prompt,
            product,
            data.get("template_id", "generic_white_bg"),
            data.get("scene", ""),
            data.get("style", "干净商业"),
            bool(data.get("use_ai", True)),
            product_description=str(data.get("product_description") or "")[:1200],
            category_id=str(data.get("category_id") or ""),
            extras=data.get("extras") or {},
        )
        return {"ok": True, "prompt": result["prompt"], "source": result["source"], "category": result.get("category", {}).get("id")}
    except Exception as exc:
        fallback = template_prompt(
            product,
            get_template(data.get("template_id", "generic_white_bg")),
            data.get("scene", ""),
            data.get("style", "干净商业"),
            str(data.get("product_description") or "")[:1200],
            str(data.get("category_id") or ""),
            data.get("extras") or {},
        )
        return {"ok": True, "prompt": fallback, "source": "template", "warning": f"DeepSeek 调用失败，已使用模板：{str(exc)[:180]}"}


@app.post("/api/generate")
async def generate(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    if not str(data.get("category_id") or "").strip():
        return JSONResponse({"ok": False, "message": "请先选择商品类型"}, status_code=400)
    platform_id = str(data.get("platform_id") or "shopify")
    try:
        platform = get_platform(platform_id)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    if platform.get("status") == "soon":
        return JSONResponse({"ok": False, "message": f"{platform['name']} 暂未开放"}, status_code=400)
    try:
        size = get_size_option(platform_id, data.get("size_id"))
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    model_id = str(data.get("model_id") or load_settings().get("ark_model") or "")
    model = get_model(model_id)
    generation_resolution = validate_resolution(model_id, data.get("generation_resolution"))
    params = {
        "platform_id": platform_id,
        "size_id": size["id"],
        "model_id": model["id"],
        "generation_resolution": generation_resolution,
        "template_id": data.get("template_id", "generic_white_bg"),
        "scene": data.get("scene", ""),
        "style": data.get("style", "干净商业"),
        "prompt": data.get("prompt", ""),
        "prompt_source": data.get("prompt_source", "manual"),
        "use_reference": bool(data.get("use_reference", True)),
        "reference_path": str(_managed_upload(data["reference_path"])) if data.get("reference_path") else "",
        "style_ref_id": str(data.get("style_ref_id") or ""),
        "product_description": str(data.get("product_description") or "")[:1200],
        "category_id": str(data.get("category_id") or ""),
        "extras": data.get("extras") or {},
    }
    conn = connect()
    cursor = conn.execute(
        "INSERT INTO image_jobs(kind,sku,status,params,created_at) VALUES('image',?,?,?,?)",
        ("STUDIO", "queued", json.dumps(params, ensure_ascii=False), now()),
    )
    job_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    background_tasks.add_task(run_generation_job, job_id)
    return {"ok": True, "job_id": job_id, "status": "queued"}


@app.post("/api/suite-plan")
async def suite_plan(request: Request):
    data = await request.json()
    category_id = str(data.get("category_id") or "").strip()
    if not category_id:
        return JSONResponse({"ok": False, "message": "请先选择商品类型"}, status_code=400)
    data["category_id"] = category_id
    return await run_in_threadpool(_suite_plan, data)


@app.post("/api/prompt-plan")
async def prompt_plan(request: Request):
    """生成 12 页提示词方案：产品类型必填，其余输入选填；AI 不可用时自动回落模板。"""
    data = await request.json()
    try:
        return await run_in_threadpool(build_page_plan, data, bool(data.get("use_ai", True)))
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    except Exception as exc:
        print(f"[prompt-plan] {type(exc).__name__}: {exc}")
        return JSONResponse({"ok": False, "message": "提示词方案生成失败，请稍后重试（详细原因已写入程序窗口日志）"}, status_code=500)


@app.post("/api/generate-suite")
async def generate_suite(request: Request, background_tasks: BackgroundTasks):
    data = await request.json()
    category_id = str(data.get("category_id") or "").strip()
    if not category_id:
        return JSONResponse({"ok": False, "message": "请先选择商品类型"}, status_code=400)
    reference_path = data.get("reference_path")
    if not reference_path:
        return JSONResponse({"ok": False, "message": "套图必须上传产品实拍图"}, status_code=400)
    platform_id = str(data.get("platform_id") or "shopify")
    try:
        platform = get_platform(platform_id)
    except ValueError as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)
    if platform.get("status") == "soon":
        return JSONResponse({"ok": False, "message": f"{platform['name']} 暂未开放"}, status_code=400)
    try:
        size = get_size_option(platform_id, data.get("size_id"))
        reference = str(_managed_upload(reference_path))
    except (ValueError, HTTPException) as exc:
        message = exc.detail if isinstance(exc, HTTPException) else str(exc)
        return JSONResponse({"ok": False, "message": message}, status_code=400)
    model_id = str(data.get("model_id") or load_settings().get("ark_model") or "")
    model = get_model(model_id)
    generation_resolution = validate_resolution(model_id, data.get("generation_resolution"))
    params = {
        "platform_id": platform_id, "size_id": size["id"],
        "model_id": model["id"], "generation_resolution": generation_resolution,
        "template_id": data.get("template_id", "generic_white_bg"),
        "scene": data.get("scene", ""), "style": data.get("style", "干净商业"),
        "product_description": str(data.get("product_description") or "")[:1200],
        "category_id": category_id, "extras": data.get("extras") or {},
        "reference_path": reference, "style_ref_id": str(data.get("style_ref_id") or ""),
        "prompts": data.get("prompts") or {},
    }
    conn = connect()
    cursor = conn.execute(
        "INSERT INTO image_jobs(kind,sku,status,params,created_at) VALUES('suite','STUDIO','queued',?,?)",
        (json.dumps(params, ensure_ascii=False), now()),
    )
    job_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    background_tasks.add_task(run_suite_job, job_id)
    return {"ok": True, "job_id": job_id, "status": "queued", "total": len(SUITE_ROLES)}


def _job_public(item: dict[str, Any], conn) -> dict[str, Any]:
    params = item.get("params") or {}
    result = item.get("result") or {}
    if isinstance(params, str):
        try:
            params = json.loads(params)
        except json.JSONDecodeError:
            params = {}
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except json.JSONDecodeError:
            result = {}
    outputs = conn.execute("SELECT COUNT(*) FROM generated_images WHERE job_id=?", (item["id"],)).fetchone()[0]
    preview = one(conn, "SELECT path FROM generated_images WHERE job_id=? ORDER BY id LIMIT 1", (item["id"],))
    preview_url = ""
    if preview and preview.get("path"):
        preview_path = Path(preview["path"])
        if preview_path.exists() and GEN_DIR in preview_path.parents:
            preview_url = f"/generated/{preview_path.relative_to(GEN_DIR).as_posix()}"
    total = int(result.get("total") or (len(SUITE_ROLES) if item.get("kind") == "suite" else 1))
    progress = int(result.get("progress") or (outputs if item.get("status") == "success" else 0))
    return {
        "id": item["id"],
        "kind": item.get("kind"),
        "kind_label": "12 张套图" if item.get("kind") == "suite" else "单图生成",
        "sku": item.get("sku"),
        "status": item.get("status"),
        "created_at": item.get("created_at"),
        "finished_at": item.get("finished_at"),
        "error": _friendly_error(item.get("error") or result.get("error") or ""),
        "platform_id": params.get("platform_id", "shopify"),
        "model_id": params.get("model_id", ""),
        "generation_resolution": params.get("generation_resolution", ""),
        "category_id": params.get("category_id", ""),
        "prompt_count": len(params.get("prompts") or {}),
        "progress": min(progress, total),
        "total": total,
        "outputs": outputs,
        "preview_url": preview_url,
        "can_retry": item.get("status") == "failed",
    }


@app.get("/api/jobs")
def jobs(limit: int = 50):
    conn = connect()
    items = rows(conn, "SELECT * FROM image_jobs ORDER BY id DESC LIMIT ?", (max(1, min(limit, 200)),))
    items = [_job_public(item, conn) for item in items]
    summary = {
        "queued": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status='queued'").fetchone()[0],
        "running": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status='running'").fetchone()[0],
        "failed": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status='failed'").fetchone()[0],
        "success": conn.execute("SELECT COUNT(*) FROM image_jobs WHERE status='success'").fetchone()[0],
    }
    conn.close()
    return {"items": items, "summary": summary}


@app.post("/api/jobs/{job_id}/retry")
async def retry_job(job_id: int, background_tasks: BackgroundTasks):
    conn = connect()
    try:
        item = one(conn, "SELECT * FROM image_jobs WHERE id=?", (job_id,))
        if not item:
            return JSONResponse({"ok": False, "message": "任务不存在"}, status_code=404)
        if item.get("status") != "failed":
            return JSONResponse({"ok": False, "message": "只有失败任务可以重试"}, status_code=409)
        params = item.get("params") or "{}"
        try:
            json.loads(params)
        except json.JSONDecodeError:
            return JSONResponse({"ok": False, "message": "任务参数已损坏，无法重试"}, status_code=409)
        cursor = conn.execute(
            "INSERT INTO image_jobs(kind,sku,status,params,created_at) VALUES(?,?, 'queued', ?, ?)",
            (item.get("kind"), item.get("sku"), params, now()),
        )
        new_id = int(cursor.lastrowid)
        conn.commit()
    finally:
        conn.close()
    if item.get("kind") == "suite":
        background_tasks.add_task(run_suite_job, new_id)
    else:
        background_tasks.add_task(run_generation_job, new_id)
    return {"ok": True, "job_id": new_id, "status": "queued", "message": "已创建重试任务"}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: int):
    conn = connect()
    item = one(conn, "SELECT * FROM image_jobs WHERE id=?", (job_id,))
    conn.close()
    if not item:
        raise HTTPException(status_code=404, detail="任务不存在")
    for field in ("params", "result"):
        if item.get(field):
            try:
                item[field] = json.loads(item[field])
            except json.JSONDecodeError:
                pass
    return item


@app.get("/api/images")
def images(sku: str | None = None, studio: bool = False):
    conn = connect()
    if studio:
        items = rows(conn, "SELECT * FROM generated_images WHERE sku='STUDIO' ORDER BY id DESC LIMIT 100")
    elif sku:
        items = rows(conn, "SELECT * FROM generated_images WHERE sku=? ORDER BY id DESC LIMIT 100", (sku,))
    else:
        items = rows(conn, "SELECT * FROM generated_images ORDER BY id DESC LIMIT 100")
    conn.close()
    for item in items:
        path = Path(item["path"])
        item["url"] = f"/generated/{path.relative_to(GEN_DIR).as_posix()}" if path.exists() and GEN_DIR in path.parents else ""
    return {"items": items}


@app.delete("/api/images/{image_id}")
def delete_image(image_id: int, suite: bool = False):
    """删除一张或整套生成图：先清数据库记录，再尽量删文件，文件被占用也不影响记录清理。"""
    conn = connect()
    targets: list[dict[str, Any]] = []
    try:
        image = one(conn, "SELECT * FROM generated_images WHERE id=?", (image_id,))
        if not image:
            return JSONResponse({"ok": False, "message": "这张图不存在，可能已经被删除过了"}, status_code=404)
        targets = [image]
        if suite and image.get("suite_id"):
            targets = rows(conn, "SELECT * FROM generated_images WHERE suite_id=?", (image["suite_id"],)) or [image]
        for item in targets:
            conn.execute("DELETE FROM generated_images WHERE id=?", (item["id"],))
        conn.commit()
    finally:
        conn.close()
    removed = 0
    for item in targets:
        try:
            path = Path(str(item.get("path") or ""))
            if path.exists() and GEN_DIR in path.parents:
                path.unlink()
                removed += 1
        except OSError:
            continue
    message = f"已删除 {len(targets)} 张图" if suite else "已删除这张图"
    if removed < len(targets):
        message += "（部分文件被占用，记录已清理）"
    return {"ok": True, "message": message, "deleted": len(targets)}


@app.post("/api/images/{image_id}/bind")
def bind_image(image_id: int):
    conn = connect()
    try:
        image = one(conn, "SELECT * FROM generated_images WHERE id=?", (image_id,))
        if not image:
            return JSONResponse({"ok": False, "message": "图片记录不存在"}, status_code=404)
        product = one(conn, "SELECT * FROM products WHERE sku=?", (image["sku"],))
        old_main = product.get("image1") if product else ""
        conn.execute(
            "UPDATE products SET image2=?,image1=?,updated_at=? WHERE sku=?",
            (old_main or product.get("image2", ""), image["path"], now(), image["sku"]),
        )
        task_id = add_task(conn, "绑定商品图", image["sku"], "", Path(image["path"]).name)
        finish_task(conn, task_id, "成功", "已设为 Shopify 主图候选")
        add_log(conn, task_id, "bind", image["path"])
        conn.commit()
        return {"ok": True, "message": "已设为该 SKU 的主图"}
    finally:
        conn.close()


@app.post("/api/images/{image_id}/publish")
async def publish_image(image_id: int):
    conn = connect()
    image = one(conn, "SELECT * FROM generated_images WHERE id=?", (image_id,))
    conn.close()
    if not image:
        return JSONResponse({"ok": False, "message": "图片不存在"}, status_code=404)
    path = str(_managed_image(image["path"]))
    return await run_in_threadpool(publish_product, image["sku"], path, "生图工坊", image_id)


@app.get("/api/settings")
def get_settings():
    return public_settings()


@app.post("/api/settings")
async def update_settings(request: Request):
    payload = await request.json()
    save_settings(payload)
    return {"ok": True, "settings": public_settings()}


@app.post("/api/settings/test-deepseek")
async def settings_test_deepseek():
    try:
        return {"ok": True, **(await run_in_threadpool(test_deepseek))}
    except Exception as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)


@app.post("/api/settings/test-shopify")
async def settings_test_shopify():
    try:
        result = await run_in_threadpool(lambda: ShopifyClient().test())
        return {"ok": True, "shop": result}
    except Exception as exc:
        return JSONResponse({"ok": False, "message": str(exc)}, status_code=400)


@app.post("/api/report")
def report():
    conn = connect()
    stats = {
        "products": conn.execute("SELECT COUNT(*) FROM products").fetchone()[0],
        "live": conn.execute("SELECT COUNT(*) FROM products WHERE platform_status IN ('已发布','模拟已发布')").fetchone()[0],
        "drafts": conn.execute("SELECT COUNT(*) FROM products WHERE shopify_id IS NULL OR shopify_id = ''").fetchone()[0],
        "success": conn.execute("SELECT COUNT(*) FROM tasks WHERE status='成功'").fetchone()[0],
        "failed": conn.execute("SELECT COUNT(*) FROM tasks WHERE status='失败'").fetchone()[0],
        "images": conn.execute("SELECT COUNT(*) FROM generated_images").fetchone()[0],
    }
    conn.close()
    text = (
        f"📊 NOVA 商品自动化日报\n商品：{stats['products']}｜已上架：{stats['live']}｜草稿：{stats['drafts']}\n"
        f"成功任务：{stats['success']}｜失败任务：{stats['failed']}\n"
        f"今日生成图：{stats['images']}\n时间：{now()}"
    )
    result = notify(text)
    return {"ok": bool(result.get("sent")), "message": "日报已发送" if result.get("sent") else "未配置飞书 Webhook", "text": text}


AGENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_product",
            "description": "查询 SKU 的名称、成本、售价、库存和 Shopify 状态",
            "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "publish_product",
            "description": "同步商品资料、价格、库存、图片到 Shopify，并设为 ACTIVE",
            "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_inventory",
            "description": "查询 SKU 的本地库存",
            "parameters": {"type": "object", "properties": {"sku": {"type": "string"}}, "required": ["sku"]},
        },
    },
]


def _agent_tool(name: str, args: dict[str, Any]) -> str:
    conn = connect()
    product = one(conn, "SELECT * FROM products WHERE sku=?", (args.get("sku"),))
    conn.close()
    if name == "get_product":
        return json.dumps(_product_payload(product), ensure_ascii=False) if product else json.dumps({"error": "SKU 不存在"})
    if name == "query_inventory":
        return json.dumps({"sku": args.get("sku"), "stock": product.get("stock") if product else None}, ensure_ascii=False)
    if name == "publish_product":
        return json.dumps(publish_product(args["sku"], source="Agent"), ensure_ascii=False)
    return json.dumps({"error": "unknown tool"})


def _agent_chat(message: str) -> dict[str, Any]:
    settings = load_settings()
    key = settings.get("deepseek_key", "")
    if not key:
        raise RuntimeError("未配置 DeepSeek API Key")
    base = str(settings.get("deepseek_base") or "https://api.deepseek.com").rstrip("/")
    system = """你是 NOVA 商品自动化中台的运营助理。你可以查询商品、同步 Shopify、查询库存。
规则：上架属于高风险管理动作，只有用户明确要求时才调用；资料不完整时先提示用户到商品中心补全；中文简洁回答并说明工具结果。"""
    messages: list[dict[str, Any]] = [{"role": "system", "content": system}, {"role": "user", "content": message}]
    steps: list[dict[str, Any]] = []
    for _ in range(7):
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": settings.get("deepseek_model", "deepseek-flash"),
                "messages": messages,
                "tools": AGENT_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
            },
            timeout=120,
        )
        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek HTTP {response.status_code}: {response.text[:240]}")
        msg = response.json()["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            answer = msg.get("content") or ""
            log_path = RUN_DIR / f"agent-{dt.date.today().isoformat()}.jsonl"
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps({"time": dt.datetime.now().isoformat(), "message": message, "answer": answer, "steps": steps}, ensure_ascii=False) + "\n")
            return {"answer": answer, "steps": steps}
        for call in calls:
            name = call["function"]["name"]
            try:
                args = json.loads(call["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = _agent_tool(name, args)
            steps.append({"tool": name, "args": args, "result": result[:1200]})
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
    return {"answer": "达到最大工具调用次数，已停止。", "steps": steps}


@app.post("/api/agent")
async def agent(request: Request):
    data = await request.json()
    message = str(data.get("message") or "").strip()
    if not message:
        return JSONResponse({"ok": False, "message": "请输入问题"}, status_code=400)
    try:
        result = await run_in_threadpool(_agent_chat, message)
        return {"ok": True, **result}
    except Exception as exc:
        return JSONResponse({"ok": False, "message": str(exc)[:500]}, status_code=400)


if __name__ == "__main__":
    uvicorn.run("app:app", host="127.0.0.1", port=int(os.getenv("ECOMMERCE_PORT", "8000")), reload=False)





