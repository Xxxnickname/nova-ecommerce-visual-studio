from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from PIL import Image

TEMP = Path(tempfile.mkdtemp(prefix="nova-tests-"))
os.environ["ECOMMERCE_DB_PATH"] = str(TEMP / "data.db")
os.environ["ECOMMERCE_SETTINGS_PATH"] = str(TEMP / "settings.json")
os.environ["ECOMMERCE_RUN_DIR"] = str(TEMP / "runs")
(TEMP / "settings.json").write_text(json.dumps({"approval_threshold": 5.0}), encoding="utf-8")
os.environ.pop("DEEPSEEK_API_KEY", None)
os.environ.pop("ARK_API_KEY", None)

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import app as application  # noqa: E402
from ecommerce import database  # noqa: E402
from ecommerce.prompts import get_template, template_prompt  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(application.app) as test_client:
        yield test_client


def test_pages_and_health(client):
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/studio", follow_redirects=False).status_code in (302, 307)
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["products"] == 12


def test_products_and_settings_are_masked(client):
    products = client.get("/api/products").json()["items"]
    assert len(products) == 12
    assert products[0]["sku"] == "SKU-001"
    settings = client.get("/api/settings").json()
    assert "ark_key" not in settings
    assert "deepseek_key" not in settings
    assert settings["approval_threshold"] == 5.0


def test_template_prompt_has_nine_layers(client):
    products = client.get("/api/products").json()["items"]
    prompt = template_prompt(products[0], get_template("living_room"), "窗边", "温暖自然")
    for index in range(1, 10):
        assert f"{index}. " in prompt
    assert "严格保持" in prompt and "颜色" in prompt


def test_price_approval_rollback_flow(client):
    result = client.post("/api/products/SKU-001/price", json={"new_price": 140}).json()
    assert result["ok"] is True
    assert result["status"] == "pending"
    approvals = client.get("/api/approvals").json()["items"]
    approval = next(item for item in approvals if item["sku"] == "SKU-001" and item["status"] == "待审批")
    task_id = approval["task_id"]
    assert client.post(f"/api/approvals/{approval['id']}/approve").json()["ok"] is True
    assert client.post(f"/api/tasks/{task_id}/rollback").json()["ok"] is True
    product = client.get("/api/products/SKU-001").json()["product"]
    assert float(product["price"]) == 129.0


def test_image_bind_flow(client):
    run_dir = Path(os.environ["ECOMMERCE_RUN_DIR"])
    target = run_dir / "generated" / "SKU-001" / "test.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), "#d8c7b0").save(target)
    conn = database.connect()
    cursor = conn.execute(
        "INSERT INTO generated_images(sku,path,prompt,preset,style,template_id,source,created_at) VALUES(?,?,?,?,?,?,?,?)",
        ("SKU-001", str(target), "test", "white_bg", "温暖自然", "white_bg", "template", database.now()),
    )
    image_id = cursor.lastrowid
    conn.commit()
    conn.close()
    assert client.post(f"/api/images/{image_id}/bind").json()["ok"] is True
    product = client.get("/api/products/SKU-001").json()["product"]
    assert product["image1"].endswith("test.png")


def test_shopify_publish_is_wrapped_in_task(client, monkeypatch):
    class FakeClient:
        def sync_product(self, product, new_image=None):
            return {"product_id": "gid://shopify/Product/1", "handle": "test-product", "status": "ACTIVE", "media": [], "inventory": {"status": "unchanged"}}

    monkeypatch.setattr(application, "ShopifyClient", FakeClient)
    result = client.post("/api/products/SKU-002/publish", json={}).json()
    assert result["ok"] is True
    assert result["result"]["handle"] == "test-product"
    tasks = client.get("/api/tasks").json()["items"]
    assert any(task["type"] == "上架同步" and task["status"] == "成功" for task in tasks)


def test_reference_upload_and_generation_uses_it(client, monkeypatch):
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (640, 640), "#b8a68f").save(buffer, format="PNG")
    uploaded = client.post(
        "/api/upload-reference?category_id=beauty",
        files={"file": ("real-product.png", buffer.getvalue(), "image/png")},
    ).json()
    assert uploaded["ok"] is True
    assert uploaded["width"] == 640 and uploaded["height"] == 640
    assert client.get(uploaded["url"]).status_code == 200

    captured = {}

    def fake_generate(prompt, out_path, reference_path=None, seed=None, model_id=None, resolution=None):
        captured["reference"] = reference_path
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (512, 640), "#d8c7b0").save(target)
        return {"path": str(target), "width": 512, "height": 640, "bytes": target.stat().st_size, "seconds": 0.1}

    monkeypatch.setattr(application, "generate_image", fake_generate)
    created = client.post(
        "/api/generate",
        json={
            "platform_id": "shopify",
            "size_id": "portrait45",
            "model_id": "doubao-seedream-5-0-flash-260915",
            "generation_resolution": "1K",
            "template_id": "beauty_white_bg",
            "style": "清透高级",
            "product_description": "酒红色丝绒口红，金色管身",
            "category_id": "beauty",
            "extras": {"selling_points": "滋润", "must_keep": "金色管身", "props": "大理石台面", "avoid": "人物"},
            "prompt": "保持实拍图商品外观，替换为美妆白底场景",
            "reference_path": uploaded["path"],
            "use_reference": True,
        },
    ).json()
    job = client.get(f"/api/jobs/{created['job_id']}").json()
    assert job["status"] == "success"
    assert uploaded["path"] in captured["reference"]
    assert job["result"]["platform_id"] == "shopify"
    assert job["result"]["size_id"] == "portrait45"
    assert job["result"]["model_id"] == "doubao-seedream-5-0-flash-260915"
    assert job["result"]["generation_resolution"] == "1K"
    assert job["result"]["width"] == 2048 and job["result"]["height"] == 2560

    draft = client.post(
        "/api/products/from-image",
        json={"image_id": job["result"]["image_id"], "category_id": "beauty", "product_description": "酒红色丝绒口红，金色管身"},
    ).json()
    assert draft["ok"] is True
    assert draft["product"]["sku"].startswith("DRAFT-")
    assert draft["product"]["status"] == "草稿"
    assert draft["product"]["target_platform"] == "shopify"
    assert draft["product"]["platform_status"] == "未发布"
    assert draft["product"]["image1"].endswith(".png")


def test_cosmetics_classification_returns_beauty_options(client):
    result = client.post(
        "/api/classify-product",
        json={"sku": "SKU-001", "description": "酒红色丝绒口红，金色管身，滋润质地"},
    ).json()
    assert result["ok"] is True
    assert result["category"]["id"] == "beauty"
    ids = {item["id"] for item in result["templates"]}
    assert "beauty_white_bg" in ids
    assert "beauty_vanity" in ids
    assert any("大理石" in scene for scene in result["scenes"])
    assert any("高级" in style or "优雅" in style for style in result["styles"])


def test_templates_can_be_filtered_by_category(client):
    result = client.get("/api/templates?category=beauty").json()
    assert result["items"]
    assert all(item["category"] == "beauty" for item in result["items"])



def test_manual_category_options_are_available(client):
    categories = client.get("/api/categories").json()["items"]
    beauty = next(item for item in categories if item["id"] == "beauty")
    assert beauty["name"] == "美妆护肤"
    options = client.get("/api/categories/beauty/options").json()
    assert options["source"] == "manual"
    assert any(item["id"] == "beauty_vanity" for item in options["templates"])


def test_prompt_works_with_optional_fields_empty(client):
    result = client.post(
        "/api/prompt",
        json={"template_id": "beauty_white_bg", "category_id": "beauty", "use_ai": True},
    ).json()
    assert result["ok"] is True
    assert result["prompt"]
    assert "美妆" in result["prompt"] or "口红" in result["prompt"] or "商品" in result["prompt"]


def test_platform_catalog_and_soon_rejection(client):
    platforms = client.get("/api/platforms").json()["items"]
    assert {item["id"] for item in platforms} >= {"shopify", "taobao_tmall", "amazon", "tiktok_shop", "jd", "pinduoduo"}
    rejected = client.post(
        "/api/generate",
        json={"platform_id": "amazon", "category_id": "beauty", "template_id": "beauty_white_bg"},
    )
    assert rejected.status_code == 400
    assert "暂未开放" in rejected.json()["message"]


def test_taobao_publish_is_simulated(client):
    updated = client.patch("/api/products/SKU-003", json={"target_platform": "taobao_tmall"}).json()
    assert updated["ok"] is True
    result = client.post("/api/products/SKU-003/publish", json={"platform_id": "taobao_tmall"}).json()
    assert result["ok"] is True
    assert result["simulated"] is True
    product = client.get("/api/products/SKU-003").json()["product"]
    assert product["target_platform"] == "taobao_tmall"
    assert product["platform_status"] == "模拟已发布"


def test_suite_generation_and_product_attaches_12(client, monkeypatch):
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (640, 640), "#d9c8b4").save(buffer, format="PNG")
    uploaded = client.post(
        "/api/upload-reference?category_id=beauty",
        files={"file": ("suite-source.png", buffer.getvalue(), "image/png")},
    ).json()

    def fake_generate(prompt, out_path, reference_path=None, seed=None, model_id=None, resolution=None):
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 900), "#c9ad91").save(target)
        return {"path": str(target), "width": 900, "height": 900, "bytes": target.stat().st_size, "seconds": 0.1}

    def fake_group(prompt, out_dir, prefix, reference_path=None, max_images=12):
        folder = Path(out_dir)
        folder.mkdir(parents=True, exist_ok=True)
        images = []
        for index in range(1, 13):
            target = folder / f"{prefix}-{index:02d}.png"
            Image.new("RGB", (900, 900), ["#c9ad91", "#d8c7b0", "#8c9a86"][index % 3]).save(target)
            images.append({"path": str(target), "width": 900, "height": 900, "bytes": target.stat().st_size, "index": index, "name": f"image-{index}", "description": ""})
        return {"images": images, "count": 12, "requested": 12, "seconds": 0.1}

    monkeypatch.setattr(application, "generate_image", fake_generate)
    monkeypatch.setattr(application, "generate_image_group", fake_group)
    created = client.post(
        "/api/generate-suite",
        json={
            "platform_id": "taobao_tmall",
            "size_id": "portrait34",
            "model_id": "doubao-seedream-5-0-flash-260915",
            "generation_resolution": "1K",
            "category_id": "beauty",
            "template_id": "beauty_white_bg",
            "product_description": "酒红色丝绒口红，金色管身",
            "extras": {"selling_points": "水润、显白、持妆", "must_keep": "金色管身"},
            "reference_path": uploaded["path"],
        },
    ).json()
    job = client.get(f"/api/jobs/{created['job_id']}").json()
    assert job["status"] == "success"
    assert job["result"]["progress"] == 12
    assert job["result"]["model_id"] == "doubao-seedream-5-0-flash-260915"
    assert job["result"]["generation_resolution"] == "1K"
    assert len(job["result"]["items"]) == 12
    assert all(item["width"] == 900 and item["height"] == 1200 for item in job["result"]["items"])
    assert sum(1 for item in job["result"]["items"] if item["kind"] == "image") == 7
    assert sum(1 for item in job["result"]["items"] if item["kind"] == "layout") == 5

    first = job["result"]["items"][0]
    draft = client.post(
        "/api/products/from-image",
        json={"image_id": first["image_id"], "category_id": "beauty", "platform_id": "taobao_tmall", "product_description": "酒红色丝绒口红，金色管身"},
    ).json()
    assert draft["ok"] is True
    detail = client.get(f"/api/products/{draft['product']['sku']}").json()
    assert len(detail["images"]) == 12


def test_suite_plan_has_editable_image_prompts(client):
    result = client.post(
        "/api/suite-plan",
        json={"category_id": "beauty", "product_description": "酒红色丝绒口红", "style": "清透高级", "extras": {"selling_points": "水润、显白"}},
    ).json()
    assert result["ok"] is True
    assert len(result["items"]) == 12
    image_items = [item for item in result["items"] if item["kind"] == "image"]
    layout_items = [item for item in result["items"] if item["kind"] == "layout"]
    assert len(image_items) == 7 and len(layout_items) == 5
    assert all(item["prompt"] for item in image_items)
    assert all(item["render_mode"] == "overlay" for item in layout_items)
    assert all("严禁出现任何新增文字" in item["prompt"] for item in layout_items)


def test_models_catalog(client):
    result = client.get("/api/models").json()
    ids = {item["id"] for item in result["items"]}
    assert "doubao-seedream-5-0-pro-260628" in ids
    assert "doubao-seedream-5-0-flash-260915" in ids
    assert all(item["resolutions"] for item in result["items"])


def test_style_reference_library(client):
    result = client.get("/api/style-refs").json()
    assert len(result["items"]) == 8
    first = result["items"][0]
    assert first["url"].startswith("/assets/style_refs/")
    assert "path" in first


def test_generation_passes_style_reference(client, monkeypatch):
    from io import BytesIO

    buffer = BytesIO()
    Image.new("RGB", (640, 640), "#d8c7b0").save(buffer, format="PNG")
    uploaded = client.post(
        "/api/upload-reference?category_id=beauty",
        files={"file": ("style-source.png", buffer.getvalue(), "image/png")},
    ).json()
    captured = {}

    def fake_generate(prompt, out_path, reference_path=None, seed=None, model_id=None, resolution=None):
        captured["references"] = reference_path
        target = Path(out_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (900, 900), "#d8c7b0").save(target)
        return {"path": str(target), "width": 900, "height": 900, "bytes": target.stat().st_size, "seconds": 0.1}

    monkeypatch.setattr(application, "generate_image", fake_generate)
    created = client.post(
        "/api/generate",
        json={
            "platform_id": "shopify", "size_id": "square",
            "model_id": "doubao-seedream-5-0-flash-260915", "generation_resolution": "1K",
            "template_id": "beauty_white_bg", "category_id": "beauty",
            "product_description": "测试美妆商品", "prompt": "测试画面",
            "reference_path": uploaded["path"], "style_ref_id": "pearl-floral",
        },
    ).json()
    job = client.get(f"/api/jobs/{created['job_id']}").json()
    assert job["status"] == "success"
    assert isinstance(captured["references"], list)
    assert len(captured["references"]) == 2
    assert captured["references"][1].endswith("01-pearl-floral.png")


def test_system_check_and_task_centers(client):
    check = client.get("/api/system-check").json()
    assert check["ok"] is True
    assert "checks" in check and "counts" in check
    assert {item["id"] for item in check["checks"]} >= {"database", "storage", "ark", "templates", "styles", "catalogs"}
    assert "ark_key" not in json.dumps(check)
    jobs = client.get("/api/jobs").json()
    assert "items" in jobs and "summary" in jobs
    operations = client.get("/api/tasks").json()
    assert "items" in operations and "summary" in operations


def test_suite_prompts_follow_style_and_do_not_add_fake_brand(client):
    result = client.post(
        "/api/suite-plan",
        json={
            "category_id": "beauty",
            "product_description": "深蓝色玻璃瓶精华，银色泵头",
            "style": "高级质感",
            "style_ref_id": "navy-gold",
            "extras": {"selling_points": "清爽、保湿、易吸收"},
        },
    ).json()
    prompts = [item["prompt"] for item in result["items"]]
    assert len(prompts) == 12
    assert all("深蓝鎏金奢华" in prompt for prompt in prompts)
    assert all("LUMEN & FORM" not in prompt for prompt in prompts)
    assert all("不添加品牌名" in prompt for prompt in prompts[:1] + prompts[7:])


def test_generated_image_keeps_category_for_later_draft(client):
    run_dir = Path(os.environ["ECOMMERCE_RUN_DIR"])
    target = run_dir / "generated" / "STUDIO" / "category-memory.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (48, 48), "#d6c4ad").save(target)
    conn = database.connect()
    cursor = conn.execute(
        "INSERT INTO generated_images(sku,path,prompt,preset,style,template_id,source,created_at,category_id) VALUES(?,?,?,?,?,?,?,?,?)",
        ("STUDIO", str(target), "test", "beauty_white_bg", "高级质感", "beauty_white_bg", "template", database.now(), "beauty"),
    )
    image_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    result = client.post("/api/products/from-image", json={"image_id": image_id, "product_description": "精华液"}).json()
    assert result["ok"] is True
    assert result["product"]["product_type"] == "美妆护肤"


def test_failed_generation_job_can_retry(client, monkeypatch):
    conn = database.connect()
    cursor = conn.execute(
        "INSERT INTO image_jobs(kind,sku,status,params,error,created_at) VALUES('image','STUDIO','failed',?,?,?)",
        (json.dumps({"category_id": "generic", "platform_id": "shopify", "size_id": "square"}, ensure_ascii=False), "模拟失败", database.now()),
    )
    failed_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()
    monkeypatch.setattr(application, "run_generation_job", lambda job_id: None)
    result = client.post(f"/api/jobs/{failed_id}/retry").json()
    assert result["ok"] is True and result["job_id"] != failed_id
    jobs = client.get("/api/jobs").json()["items"]
    retried = next(item for item in jobs if item["id"] == result["job_id"])
    assert retried["status"] == "queued"



def test_interrupted_job_is_marked_failed_on_restart(client):
    conn = database.connect()
    cursor = conn.execute(
        "INSERT INTO image_jobs(kind,sku,status,params,created_at) VALUES('suite','STUDIO','running','{}',?)",
        (database.now(),),
    )
    job_id = int(cursor.lastrowid)
    conn.commit()
    database._recover_interrupted_jobs(conn)
    conn.commit()
    row = conn.execute("SELECT status,error FROM image_jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    assert row["status"] == "failed"
    assert "重启" in row["error"]


def test_layout_text_wrapping_never_exceeds_width():
    from PIL import Image as PILImage, ImageDraw
    from ecommerce.suite import _font, _wrap_lines

    canvas = PILImage.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(canvas)
    font = _font(48, True)
    max_width = 420
    lines = _wrap_lines(draw, "高级哑光妆效与细腻自然不假面的长期持妆体验", font, max_width, 3)
    assert lines
    assert all(draw.textbbox((0, 0), line, font=font)[2] <= max_width for line in lines)


def test_overlay_renderer_keeps_safe_margins():
    from PIL import Image as PILImage
    from ecommerce.suite import SUITE_ROLES, render_overlay

    base = TEMP / "overlay-base.png"
    PILImage.new("RGB", (1000, 1000), "#eee9df").save(base)
    role = next(item for item in SUITE_ROLES if item["id"] == "08_benefits_1")
    target = TEMP / "overlay-result.png"
    result = render_overlay(
        role, base, target, 1000, 1000,
        "测试商品 30ml", {"brand_name": "测试品牌", "selling_points": "细腻、持妆、清透"}, "beauty", "mineral-crystal",
    )
    with PILImage.open(target) as image:
        assert image.size == (1000, 1000)
    assert result["bytes"] > 1000

def test_prompt_plan_returns_twelve_pages(client):
    """不联网时也要能出 12 页方案：主图 1:1、详情页 4:5，六个子块齐全。"""
    response = client.post(
        "/api/prompt-plan",
        json={
            "product_type": "桌面净水器",
            "audience": "租房党、年轻家庭",
            "style": "日系轻生活、奶油白",
            "selling_points": "即热出水、净化过滤",
            "reference_note": "窗边自然光、木质桌面",
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "template"
    pages = data["pages"]
    assert len(pages) == 12
    assert [page["code"] for page in pages] == ["M01", "M02", "M03", "M04", "M05", "D01", "D02", "D03", "D04", "D05", "D06", "D07"]
    first = pages[0]
    for field in ("objective", "composition", "product_share", "scene_elements", "lighting_mood", "prompt_full", "prompt_short"):
        assert first[field], field
    assert first["ratio"] == "1:1"
    assert pages[5]["ratio"] == "4:5"
    assert "%" in first["product_share"]


def test_prompt_plan_requires_product_type(client):
    """产品类型是唯一必填项，空值必须被拒绝而不是生成一份无用方案。"""
    response = client.post("/api/prompt-plan", json={"product_type": "   ", "use_ai": False})
    assert response.status_code == 400
    assert response.json()["ok"] is False


def test_prompt_plan_has_no_placeholders_and_ratio_modes(client):
    """换品类不能串味（残留瓶盖纸盒），提示词里不能有占位符，比例模式要生效。"""
    response = client.post(
        "/api/prompt-plan",
        json={"product_type": "桌面净水器", "ratio_mode": "detail", "use_ai": False},
    )
    data = response.json()
    assert all(page["ratio"] == "4:5" for page in data["pages"])
    combined = "\n".join(page["prompt_full"] for page in data["pages"])
    for sample_word in ("瓶盖", "纸盒", "膏体", "底妆", "粉底", "遮瑕", "SPF"):
        assert sample_word not in combined, sample_word
    for page in data["pages"]:
        assert "{" not in page["prompt_full"]
        assert "None" not in page["prompt_full"]
        assert len(page["prompt_full"]) >= 80

def test_prompt_plan_encodes_reference_for_vision(client, tmp_path):
    """传了实拍图时应能压图编码（meta.vision=True），没 Key 也要回落模板而不是报错。"""
    image_path = tmp_path / "ref.png"
    Image.new("RGB", (64, 48), (240, 235, 225)).save(image_path)
    response = client.post(
        "/api/prompt-plan",
        json={
            "product_type": "桌面净水器",
            "reference_path": str(image_path),
            "use_vision": True,
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["source"] == "template"
    assert data["meta"]["vision"] is True
    assert len(data["pages"]) == 12


def test_prompt_plan_survives_missing_reference(client):
    """实拍图路径失效时只降级提示，不能影响 12 页方案产出。"""
    response = client.post(
        "/api/prompt-plan",
        json={"product_type": "桌面净水器", "reference_path": "D:/not-exists/ref.png", "use_vision": True, "use_ai": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["meta"]["vision"] is False
    assert len(data["pages"]) == 12

def test_ensure_copy_fills_detail_pages():
    """代码层兜底：模型少写文案时，详情页也必须补齐主标题/副标题/3 条要点并写进提示词。"""
    from ecommerce.prompt_plan import EXPECTED_CODES, TEXT_RULES, _ensure_copy, _validate_pages

    lazy_pages = []
    for index, code in enumerate(EXPECTED_CODES):
        lazy_pages.append({
            "code": code,
            "slot": "slot",
            "role": "角色",
            "ratio": "4:5" if code.startswith("D") else "1:1",
            "objective": "讲清这一页的目标",
            "buyer_question": "",
            "composition": "产品居中，四周留白",
            "product_share": "35%–45%",
            "scene_elements": ["台面", "背景"],
            "lighting_mood": "柔和侧光",
            "copy_headline": "",
            "copy_sub": "",
            "copy_points": [],
            "copy_tags": [],
            "text_layout": "",
            "prompt_full": "电商主图提示词占位内容，用来满足最小长度要求的说明文字，保证校验不会因为太短而失败。" * 4,
            "prompt_short": "精简版",
        })
    inputs = {"selling_points": ["即热出水", "净化过滤", "小体积免安装", "数显水温"], "style": "日系轻生活"}
    pages = _ensure_copy(_validate_pages(lazy_pages), inputs)
    detail = [p for p in pages if TEXT_RULES.get(p["code"]) == "full"]
    assert len(detail) == 7
    for page in detail:
        assert page["copy_headline"]
        assert page["copy_sub"]
        assert len(page["copy_points"]) >= 3
        assert "文字内容" in page["prompt_full"]

