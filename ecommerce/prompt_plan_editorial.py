"""实验版提示词方案：按“视觉总监 + 极简文字”标准生成 12 页。

与现有方案的区别：
- 每页只允许 1 句主标题（4-8 字）+ 1 句副标题（≤10 字），不再排长文案和要点列表；
- 强制把“底图摄影”和“文字版式”一起描述，并按四种版式轮换（中轴穹顶/非对称平衡/模块化信息组/错落悬浮）；
- 输出固定四段：【画面构图与版式】【光影氛围】【主体与背景元素】【文字渲染指令】。

用法：build_editorial_plan(payload, use_ai=True) —— 与现有 build_page_plan 返回结构兼容（多一个 mode 字段）。
"""
from __future__ import annotations

import json
import re
from typing import Any

import requests

from .config import load_settings
from .prompt_plan import _image_data_url, _log

EXPECTED_CODES = ["M01", "M02", "M03", "M04", "M05", "D01", "D02", "D03", "D04", "D05", "D06", "D07"]

# 12 页的版式与任务：保证同一套图里四种版式都出现，且相邻页不重复
LAYOUTS = {
    "M01": ("中轴穹顶式", "品牌定妆：产品居中，上下大留白，主标题巨大"),
    "M02": ("非对称平衡式", "核心卖点：产品占一侧，另一侧纯净渐变光区放文案"),
    "M03": ("非对称平衡式", "细节材质：微距质感 + 侧向排版"),
    "M04": ("错落悬浮式", "生活场景：文字错落在画面上方，与光影融合"),
    "M05": ("中轴穹顶式", "规格包装：产品全貌居中，徽章式小字"),
    "D01": ("模块化信息组", "痛点共鸣：纯净底图 + 模块化文案"),
    "D02": ("模块化信息组", "科技工艺：几何线条 + 细线框信息"),
    "D03": ("非对称平衡式", "对比可视化：左右分栏，一侧产品一侧文案"),
    "D04": ("错落悬浮式", "沉浸使用：生活瞬间，文字轻落"),
    "D05": ("模块化信息组", "多维拓展：分镜式排布 + 模块标签"),
    "D06": ("中轴穹顶式", "参数与 Q&A：居中秩序，极简参数"),
    "D07": ("中轴穹顶式", "品牌升华：聚光灯 + 极简 Slogan"),
}

SYSTEM_PROMPT = """【角色设定】
你是全球顶级电商视觉总监（Art Director）与商业转化策划师。根据用户给的商品信息与实拍图，输出 12 张电商视觉图的精准提示词。
目标：绝对摒弃廉价模板化排版与 AI 塑料感，达到天猫/淘宝大牌旗舰店级别。

【核心设计哲学：版式与底图共生】
严禁把生图当排版软件。每条提示词都要把“底图摄影”和“文字版式”融合，文字必须极简。

1. 底图与光影
- 背景只用干净纯色渐变或极简材质（微光拉丝金属、细腻哑光石材、半透明亚克力/薄纱），不要杂乱生活道具。
- 用具体商业摄影光：有呼吸感的自然侧窗光、戏剧性伦勃朗光、清透冷调科技光；光线要在背景留下干净光斑或阴影，为文字留出呼吸感。
- 品类基因：科技类=几何线条与微光；食品类=诱人高光与自然纹理；家居类=柔和漫反射；美妆类=通透材质。

2. 版式建筑学（用自然语言描述，禁止出现 pt、% 间距这类设计软件参数）
- 中轴穹顶式：产品居中或微倾，上下大面积留白，主标题极致居中，下方一条极细短线引导副标题。
- 非对称平衡式：产品占一侧，另一侧纯净渐变光区，文字严格左对齐或右对齐，用几何色块/极细竖线引导。
- 模块化信息组：底图纯净，文字像 UI 模块，外围极细无填充线框，或用淡淡的半透明底卡衬托。
- 错落悬浮式：主标题带呼吸感地错落在画面上方或侧边，文字与背景光影自然融合。

3. 文字强约束
- 每页只渲染一句主标题（4-8 字）和一句副标题（不超过 10 字），不要长文案、不要要点列表。
- 主标题最大最重，形成绝对视觉焦点；副标题明显更小更轻。
- 字体只用干净无衬线现代字体（类似思源黑体）或优雅现代宋体。
- 可以使用极克制的矢量修饰：一条极细金色/白色线框、一个小圆形徽标、或一块极简标签底色。
- 严禁：花哨艺术字、3D 立体字、乱码、多余标签和色块。

4. 商品完整性（硬性）
- 包装盒必须完整入画：四面透视一致、底部和侧面不裁切，不出现条码、价签、无关小字；盒面文字与参考图一致。
- 参考图里盒子本身不完整时，以瓶身为主体，盒子只作次要陪衬或直接不出现，宁可少一个元素也不要穿帮。

5. 场景与品类匹配（禁止乱配）
- 美妆底妆：晨光梳妆台、浅米石材台面、亚麻布、玻璃杯、柔和窗光；禁止夜店丝绒、暗黑背景、金属反光堆叠。
- 家居：原木、棉麻、漫反射；3C：几何线条、冷调微光；食品：自然纹理、诱人高光。

6. 文字风格（禁止老土）
- 禁止"居中大宋体 + 细金线"这套老派排版；改用现代无衬线粗体，左对齐或非对称排版，字距收紧。
- 主标题与副标题用同一字体家族的不同字重；文字颜色从产品本身取色（深蓝底用象牙白，浅底用墨蓝），不用金色描边和装饰线。

【12 页任务】
M01 中轴穹顶式·品牌定妆；M02 非对称平衡式·核心卖点；M03 非对称平衡式·细节材质；
M04 错落悬浮式·生活场景；M05 中轴穹顶式·规格包装；D01 模块化信息组·痛点共鸣；
D02 模块化信息组·科技工艺；D03 非对称平衡式·对比可视化；D04 错落悬浮式·沉浸使用；
D05 模块化信息组·多维拓展；D06 中轴穹顶式·参数与 Q&A；D07 中轴穹顶式·品牌升华。

【输出格式】
只输出 JSON 数组，不要解释、不要 Markdown。长度固定 12，code 顺序 M01, M02, M03, M04, M05, D01, D02, D03, D04, D05, D06, D07。
每个元素字段：
code, role, layout, headline, subheadline, objective, composition, lighting, subject, prompt_full, prompt_short。
其中 prompt_full 必须严格按这四段写（段首小标题一致）：
【画面构图与版式】…
【光影氛围】…
【主体与背景元素】…
【文字渲染指令】…（写明主标题与副标题原文、字体、对齐方式、位置，以及是否加极简线框/徽标/标签底色）
每页 prompt_full 控制在 150-220 字：四段各 1-2 句，只写结论，不要铺陈。
"""


def _clean(value: Any) -> str:
    """去掉首尾空白与句末标点。"""
    return str(value or "").strip().strip("。；;,，、 \t\n")


def _inputs(payload: dict[str, Any]) -> dict[str, Any]:
    """整理输入：商品、卖点、人群、风格、实拍图。"""
    points = payload.get("selling_points")
    if isinstance(points, list):
        points = [_clean(item) for item in points]
    else:
        points = [_clean(item) for item in re.split(r"[\n;；,，、]+", str(points or ""))]
    return {
        "product_type": _clean(payload.get("product_type")),
        "audience": _clean(payload.get("audience")),
        "style": _clean(payload.get("style")),
        "selling_points": [item for item in points if item],
        "reference_note": _clean(payload.get("reference_note")),
        "reference_path": str(payload.get("reference_path") or "").strip(),
        "use_vision": bool(payload.get("use_vision", True)),
    }


def _fallback_pages(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """不联网时的确定性方案：保证 12 页、四段结构、极简文字。"""
    product = inputs["product_type"] or "商品"
    points = inputs["selling_points"] or [product]
    style = inputs["style"] or "干净商业"
    pages: list[dict[str, Any]] = []
    for index, code in enumerate(EXPECTED_CODES):
        layout, task = LAYOUTS[code]
        headline = points[index % len(points)][:8]
        sub = points[(index + 1) % len(points)][:10]
        role = task.split("：")[0]
        composition = {
            "中轴穹顶式": "产品居中或微倾，上下各留约三成留白；主标题居中压在上方留白区，下方一条极细短线引导副标题",
            "非对称平衡式": "产品占画面一侧，另一侧是纯净渐变光区；文字严格左对齐，用一条极细竖线作为视觉引导",
            "模块化信息组": "纯净底图，文字像 UI 模块排列，外围用极细无填充线框，层级分明",
            "错落悬浮式": "主标题错落在画面上方或侧边，与背景光影自然融合，留出呼吸感",
        }[layout]
        lighting = "模拟清晨透过窗纱的自然侧逆光，色温 5500K，产品边缘有清透高光，阴影柔和"
        subject = f"{product}置于哑光浅色台面上，背景为虚化的微光渐变，无任何杂物"
        prompt_full = "\n".join([
            "【画面构图与版式】采用" + layout + "。" + composition + "。",
            "【光影氛围】" + lighting + "；整体调性" + style + "。",
            "【主体与背景元素】" + subject + "。",
            "【文字渲染指令】画面中用干净无衬线粗体写主标题「" + headline + "」，下方用更小更轻的字写副标题「" + sub + "」；"
            "文字排版有杂志呼吸感，必要时只用一条极细金线或一个小徽标作修饰，不要出现其他任何文字、卡片或色块。",
        ])
        pages.append({
            "code": code,
            "role": role,
            "layout": layout,
            "headline": headline,
            "subheadline": sub,
            "objective": task,
            "composition": composition,
            "lighting": lighting,
            "subject": subject,
            "prompt_full": prompt_full,
            "prompt_short": layout + "；" + product + "；主标题「" + headline + "」副标题「" + sub + "」；" + lighting[:18],
        })
    return pages


def _validate(pages: Any) -> list[dict[str, Any]]:
    """校验：12 页、顺序正确、四段齐全、主标题与副标题字数符合要求。"""
    if not isinstance(pages, list) or len(pages) != 12:
        raise ValueError("页数不是 12")
    sections = ("【画面构图与版式】", "【光影氛围】", "【主体与背景元素】", "【文字渲染指令】")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(pages):
        if not isinstance(item, dict):
            raise ValueError("第 %d 页不是对象" % (index + 1))
        code = str(item.get("code") or "").upper()
        if code != EXPECTED_CODES[index]:
            raise ValueError("第 %d 页 code 应为 %s" % (index + 1, EXPECTED_CODES[index]))
        full = str(item.get("prompt_full") or "")
        for section in sections:
            if section not in full:
                raise ValueError("%s 缺少 %s" % (code, section))
        if "要点" in full or "利益点" in full:
            full = "\n".join(line for line in full.splitlines() if ("要点" not in line and "利益点" not in line))
        headline = _clean(item.get("headline"))[:8]
        sub = _clean(item.get("subheadline"))[:10]
        if not headline:
            raise ValueError("%s 缺少主标题" % code)
        result.append({
            "code": code,
            "role": _clean(item.get("role")),
            "layout": _clean(item.get("layout")),
            "headline": headline,
            "subheadline": sub,
            "objective": _clean(item.get("objective")),
            "composition": _clean(item.get("composition")),
            "lighting": _clean(item.get("lighting")),
            "subject": _clean(item.get("subject")),
            "prompt_full": full,
            "prompt_short": _clean(item.get("prompt_short")),
        })
    return result


def _salvage_objects(text: str) -> list[dict[str, Any]]:
    """输出被截断时逐个抠出完整对象，尽量救回已生成的页。"""
    items: list[dict[str, Any]] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    item = json.loads(text[start:index + 1])
                    if isinstance(item, dict):
                        items.append(item)
                except json.JSONDecodeError:
                    pass
                start = None
    return items


def _request_batch(codes: list[str], inputs: dict[str, Any], image_url: str = "") -> list[dict[str, Any]]:
    """只请求 6 页，降低单次输出长度，减少截断并缩短等待时间。"""
    settings = load_settings()
    key = str(settings.get("deepseek_key") or "").strip()
    if not key:
        raise RuntimeError("未配置 DeepSeek Key")
    text = (
        "商品类型：%s\n目标人群：%s\n整体风格：%s\n产品卖点：%s\n参考图描述：%s\n本批只输出这 6 页：%s"
        % (
            inputs["product_type"],
            inputs["audience"] or "未提供",
            inputs["style"] or "未提供",
            "、".join(inputs["selling_points"]) or "未提供",
            inputs["reference_note"] or "未提供",
            ", ".join(codes),
        )
    )
    if image_url:
        text += "\n附带图片是商品实拍图：先读出器型、材质、颜色、包装结构与真实文字，再据此写提示词；图中没有的信息不要编造。"
    content: list[dict[str, Any]] = [{"type": "text", "text": text}]
    if image_url:
        content.append({"type": "image_url", "image_url": {"url": image_url}})
    base = str(settings.get("deepseek_base") or "https://api.deepseek.com").rstrip("/")
    response = requests.post(
        base + "/chat/completions",
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        json={
            "model": settings.get("deepseek_model", "deepseek-flash"),
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content if image_url else text},
            ],
            "temperature": 0.7,
            "max_tokens": 9000,
        },
        timeout=240,
    )
    if response.status_code != 200:
        raise RuntimeError("DeepSeek HTTP %s" % response.status_code)
    try:
        raw = response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError("DeepSeek 返回格式异常") from exc
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    start, end = raw.find("["), raw.rfind("]")
    if start >= 0 and end > start:
        data = json.loads(raw[start:end + 1])
    else:
        data = _salvage_objects(raw[start:] if start >= 0 else raw)
    if not isinstance(data, list) or len(data) != len(codes):
        raise RuntimeError("本批返回 %d 页，应为 %d 页" % (len(data or []), len(codes)))
    for index, item in enumerate(data):
        item["code"] = str(item.get("code") or codes[index]).upper()
    return data


def _plan_with_ai(inputs: dict[str, Any], image_url: str = "") -> list[dict[str, Any]]:
    """分两批并发请求（每批 6 页），合并后整体校验；单批失败用模板补齐。"""
    from concurrent.futures import ThreadPoolExecutor

    batches = [EXPECTED_CODES[:6], EXPECTED_CODES[6:]]
    fallback = _fallback_pages(inputs)
    collected: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_request_batch, batch, inputs, image_url) for batch in batches]
        for position, future in enumerate(futures):
            try:
                collected.extend(future.result())
            except Exception as exc:
                _log("editorial 分批失败（第 %d 批）: %s" % (position + 1, exc))
                start = position * 6
                collected.extend(fallback[start:start + 6])
    collected.sort(key=lambda item: EXPECTED_CODES.index(str(item.get("code")).upper()) if str(item.get("code")).upper() in EXPECTED_CODES else 99)
    return _validate(collected)
def build_editorial_plan(payload: dict[str, Any] | None, use_ai: bool = True) -> dict[str, Any]:
    """实验入口：返回 12 页极简文字方案。"""
    inputs = _inputs(payload or {})
    if not inputs["product_type"]:
        raise ValueError("请先填写产品类型")
    image_url = ""
    warning = ""
    source = "template"
    pages: list[dict[str, Any]] | None = None
    if inputs["use_vision"] and inputs["reference_path"]:
        try:
            image_url = _image_data_url(inputs["reference_path"])
        except Exception as exc:
            _log("editorial 实拍图读取失败: %s" % exc)
    if use_ai:
        if image_url:
            try:
                pages = _plan_with_ai(inputs, image_url)
                source = "deepseek-vision"
            except Exception as exc:
                _log("editorial 看图生成失败: %s" % exc)
                warning = "看图生成失败，已改用文字生成（%s）" % exc
        if not pages:
            try:
                pages = _plan_with_ai(inputs)
                source = "deepseek"
            except Exception as exc:
                _log("editorial 文字生成失败: %s" % exc)
                warning = "AI 生成失败，已回落到模板方案（%s）" % exc
    if not pages:
        pages = _fallback_pages(inputs)
    return {
        "ok": True,
        "mode": "editorial",
        "source": source,
        "warning": warning,
        "meta": {
            "total": len(pages),
            "product_type": inputs["product_type"],
            "vision": bool(image_url),
            "layouts": sorted({page["layout"] for page in pages if page.get("layout")}),
        },
        "pages": pages,
    }
