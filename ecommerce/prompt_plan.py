"""提示词方案生成器：把「商品 + 卖点 + 实拍图」展开成 12 页可执行的提示词。

设计原则：
1. 每页都是「画面 + 文案」双完整：详情页必须写明主标题、副标题、3 条利益点和标签，
   并在提示词里逐字给出，避免模型自由发挥导致内容稀薄或跑偏。
2. 结构来自项目内 v3.1 提示词包；换品类时自动剔除样板词（瓶盖、纸盒、底妆等）。
3. 有 DeepSeek Key 时优先让模型看图 + 文字细化；失败依次降级为纯文字 → 模板拼装。
"""
from __future__ import annotations

import base64
import io
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import requests
from PIL import Image

from .config import APP_DIR, load_settings

PACK_PATH = (
    APP_DIR / "prompt_packs" / "industry-prompt-pack-5main-7detail.json"
)

EXPECTED_CODES = ["M01", "M02", "M03", "M04", "M05", "D01", "D02", "D03", "D04", "D05", "D06", "D07"]

# 送给视觉模型前把长边压到这个值，避免 base64 撑爆请求体与 token
VISION_MAX_EDGE = 1024

RATIO_MODES = {"industry", "detail", "main"}

SAMPLE_KEYWORDS = ("粉底", "底妆", "妆前", "遮瑕", "粉饼", "气垫")
SAMPLE_NOUNS = ("瓶盖", "瓶身", "玻璃瓶", "纸盒", "外盒", "包装盒", "标签", "磨砂玻璃", "丝绒", "第二个瓶子", "膏体", "泵头", "滴管")
COPY_BLOCKERS = ("底妆", "粉底", "遮瑕", "持妆", "柔焦", "SPF", "妆前", "妆感", "上妆", "补妆", "服帖")
BLOCKED_TERMS = SAMPLE_NOUNS + COPY_BLOCKERS

# 文字风格与装饰的确定性方案：按 code 轮换，保证 12 页不重复，且用肯定句写进提示词
TYPE_STYLES = [
    {"font": "思源黑体 Heavy 主标题、思源黑体 Regular 副标题", "art": "主标题不做描边和渐变，只放大字号并加 2% 字距", "deco": "画面顶部一条 1px 浅金色细线，长度约为画面宽度的 40%"},
    {"font": "思源宋体 Light 主标题、无衬线小字副标题", "art": "主标题加 1px 细描边，不加渐变", "deco": "标题左侧一条 2px 竖线，右下角一枚柔和圆形光斑"},
    {"font": "无衬线粗体主标题、细体数字与标签", "art": "主标题带 2px 轻微立体投影，投影透明度约 12%", "deco": "文字区下方一块 30% 宽的低饱和小色块"},
    {"font": "现代宋体主标题、无衬线正文", "art": "主标题使用同色系深浅渐变字，不加描边", "deco": "左侧一条 45° 细线，右上角一枚与品类相关的小图标"},
]

GENERIC_NEGATIVE = "不要出现乱码文字、错别字、错误品牌标识、多余产品、虚构认证、夸张功效、人物脸部特写、塑料感、过曝、水印、文字超出画面、文字被裁切、文字压住产品"

# 只有这些页允许出现广告文字；M01 必须纯净，M03 只放一个质地标签
TASK_NAMES = {
    "M01": "视觉锤", "M02": "痛点共鸣", "M03": "质地细节", "M04": "功能具象化", "M05": "信任定妆",
    "D01": "痛点放大海报", "D02": "科技工艺", "D03": "对比可视化", "D04": "沉浸使用",
    "D05": "多维拓展", "D06": "Q&A与参数", "D07": "品牌升华",
}

TEXT_RULES = {
    "M01": "headline_only",
    "M02": "headline_sub",
    "M03": "tag_only",
    "M04": "headline_points",
    "M05": "headline_points",
    "D01": "full",
    "D02": "full",
    "D03": "full",
    "D04": "full",
    "D05": "full",
    "D06": "full",
    "D07": "full",
}

SYSTEM_PROMPT = """【角色设定】
你是全球顶级的电商品牌视觉总监（Art Director）与商业转化策划师。任务是根据用户输入的产品信息与实拍图，策划一套 12 张电商视觉图的提示词（5 张主图 + 7 张详情页）。

【核心视觉原则：大牌感与去同质化】
1. 统一性与差异化并重：12 张共享一套品牌视觉资产（主色调、字体气质、贯穿材质），但严禁每张图使用相同构图；交替使用居中对称、黄金分割、对角平衡、满版微距、大面积留白。
2. 拒绝廉价 AI 感：禁止“绝美、炫彩、极具艺术感、震撼”这类空洞词；必须使用具体摄影与设计术语（伦勃朗光、柔光箱、百微镜头、慢速快门、Pantone 色号、无衬线排版、丝绒/拉丝金属/哑光玻璃质感）。
3. 场景去刻板化：不要总是纯色背景或星空背景；按产品属性给出有生活气息的真实场景，或戏剧张力的光影棚拍，让画面有呼吸感。

【12 张图任务分配（把用户商品代入）】
M01 图1 视觉锤：强视觉冲击的构图（悬浮、微距特写、色彩碰撞），极简排版，主标题字号最大化，1 秒抓住眼球。
M02 图2 痛点共鸣：结合用户痛点构建场景，情绪化光影（冷调职场光 / 暖调居家光），大面积留白给痛点文案。
M03 图3 质地细节：极度放大核心材质（流体质感、金属边缘、织物纹理、食材光泽），对角线构图或特写，像高端杂志内页。
M04 图4 功能具象化：把抽象功能视觉化（防水用水珠、抗压用重物对比、科技感用光路），卡片式或左右分栏排版。
M05 图5 信任定妆：产品全貌 + 外包装的经典定妆照，光影干净利落，居中对齐或徽章式排版。
D01 图6 痛点放大海报：视觉语言锋利，用具体场景物品隐喻痛点，大字报排版。
D02 图7 科技/成分/工艺：抽象光影、微观几何或实验室风格，产品悬浮或置于几何台面，排版有科技感（中英双语可用）。
D03 图8 对比可视化：图形、材质或色彩对比（左反右正），中轴对称或左右分割。
D04 图9 沉浸使用：真实使用瞬间，强调人与场景的参与感，排版像生活方式手账。
D05 图10 多维拓展：一图多景或展示不同形态，多重曝光或分镜式构图。
D06 图11 Q&A 与参数：信息流式图文混排，高度理性，纯净背景 + 图标与色块模块化排版。
D07 图12 品牌升华：最具戏剧性的光影（聚光灯、倒影），大量留白 + 极简 Slogan，高级收尾。

【执行要求】
每条 prompt_full 必须按下面顺序分五段，段首用固定小标题：
【画面构图与版式】版式类型、镜头与机位、产品占比、留白与安全边距
【光影氛围】主光方向与软硬、色温、反差、阴影与倒影
【主体与背景元素】产品呈现方式 + 3-5 个具体道具/材质/背景
【文字排版要求】用肯定句直接给出结论：主标题/副标题/利益点/标签的原文、文字区位置与占比、字号层级、具体字体、是否描边或渐变或立体、加了哪些装饰小元素及其位置、以及“文字完整落在画面内、距四边至少 8%、不超边不裁切”。禁止出现「写明」「说明」「请」「是否」这类指令式措辞。
注意：不要把「主标题」「副标题」「利益点」「要点1/2/3」这些标签字样画进画面，只渲染引号里的文字本身。
【负面约束】乱码、错字、变形、多余产品、水印、过度磨砂等
每个段落都要具体、可执行，禁止空话；整套 12 页合计不超过 4500 字。

【文案规则】
- 主标题 6-14 字，必须是一句有画面的话，不能直接照抄卖点短语。正确示例：主标题「通勤八小时，底妆还在」；副标题「早八到加班，依旧自然不假面」；要点「柔焦遮瑕，毛孔看着更细」。
- 详情页（D01-D07）每页必须有：主标题 + 副标题（10-22 字）+ 3 条利益点（每条 8-18 字）+ 可选标签。
- 主图：M01 只写主标题；M02 主标题 + 副标题；M03 只写 1 个质地标签；M04 主标题 + 2 条要点；M05 主标题 + 2 条要点。
- 标签只写规格、场景、人群、质地短词，禁止「主图/详情页/首屏/承接/收束/痛点/机制」这类页面职责词。
- 不得编造成分、功效、认证、价格、销量、优惠。

【输出格式】
只输出 JSON 数组，不要解释、不要 Markdown 代码块。长度固定 12，code 顺序为 M01, M02, M03, M04, M05, D01, D02, D03, D04, D05, D06, D07。
每个元素字段：code, slot, role, ratio, objective, buyer_question, composition, product_share, scene_elements, lighting_mood,
copy_headline, copy_sub, copy_points, copy_tags, text_layout, prompt_full, prompt_short。
"""


def _clean(text: Any) -> str:
    """去掉首尾空白和句末多余标点，避免拼装出「。。」或「；；」。"""
    return str(text or "").strip().strip("。；;,，、 \t\n")


def _split_list(value: Any) -> list[str]:
    """把用户输入拆成短句列表：支持数组、换行、顿号、逗号、分号。"""
    if isinstance(value, list):
        items = [str(item) for item in value]
    else:
        items = re.split(r"[\n;；,，、]+", str(value or ""))
    return [item for item in (_clean(i) for i in items) if item]


@lru_cache(maxsize=1)
def load_pack() -> dict[str, Any]:
    """读取 v3.1 提示词包；读不到时返回空字典，由调用方走兜底。"""
    try:
        data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("pages"), list) and len(data["pages"]) == 12:
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


FALLBACK_PAGES: list[dict[str, Any]] = [
    {"code": "M01", "slot": "主图 1/5", "role": "白底首图", "ratio": "1:1"},
    {"code": "M02", "slot": "主图 2/5", "role": "核心卖点", "ratio": "1:1"},
    {"code": "M03", "slot": "主图 3/5", "role": "质地细节", "ratio": "1:1"},
    {"code": "M04", "slot": "主图 4/5", "role": "生活场景", "ratio": "1:1"},
    {"code": "M05", "slot": "主图 5/5", "role": "规格与包装", "ratio": "1:1"},
    {"code": "D01", "slot": "详情页 1/7", "role": "首屏承接", "ratio": "4:5"},
    {"code": "D02", "slot": "详情页 2/7", "role": "痛点放大", "ratio": "4:5"},
    {"code": "D03", "slot": "详情页 3/7", "role": "质地机制", "ratio": "4:5"},
    {"code": "D04", "slot": "详情页 4/7", "role": "核心利益", "ratio": "4:5"},
    {"code": "D05", "slot": "详情页 5/7", "role": "使用方法", "ratio": "4:5"},
    {"code": "D06", "slot": "详情页 6/7", "role": "场景覆盖", "ratio": "4:5"},
    {"code": "D07", "slot": "详情页 7/7", "role": "规格收束", "ratio": "4:5"},
]


def normalize_inputs(payload: dict[str, Any] | None) -> dict[str, Any]:
    """把前端传来的原始输入规范成固定结构，缺省值一律给安全默认。"""
    data = payload or {}
    ratio_mode = str(data.get("ratio_mode") or "industry").strip()
    if ratio_mode not in RATIO_MODES:
        ratio_mode = "industry"
    product_type = str(data.get("product_type") or "").strip()
    return {
        "product_type": product_type,
        "audience": str(data.get("audience") or "").strip(),
        "style": str(data.get("style") or "").strip(),
        "selling_points": _split_list(data.get("selling_points")),
        "reference_note": str(data.get("reference_note") or "").strip(),
        "ratio_mode": ratio_mode,
        "sample_ok": (not product_type) or any(word in product_type for word in SAMPLE_KEYWORDS),
    }


def _ratio_for(code: str, mode: str, default: str) -> str:
    """按用户选择的画幅模式返回本页比例。"""
    if mode == "detail":
        return "4:5"
    if mode == "main":
        return "1:1"
    return default or ("1:1" if code.startswith("M") else "4:5")


def _share_range(text: str) -> str:
    """从「整体占画面 38%」这类描述里取百分比，扩成区间。"""
    match = re.search(r"(\d{1,2})\s*%", str(text or ""))
    if not match:
        return "35%–45%"
    value = int(match.group(1))
    return f"{max(15, value - 5)}%–{min(65, value + 5)}%"


def _sanitize_text(text: Any, sample_ok: bool, drop_all_on_hit: bool = False, fallback: str = "") -> str:
    """换品类时剔除样板专用词语；命中文案类关键词时整条丢弃。"""
    cleaned = _clean(text)
    if not cleaned or sample_ok:
        return cleaned or fallback
    if drop_all_on_hit and any(word in cleaned for word in COPY_BLOCKERS):
        return ""
    kept = [
        _clean(clause)
        for clause in re.split(r"[，,；;]", cleaned)
        if not any(term in clause for term in BLOCKED_TERMS)
    ]
    return "，".join(clause for clause in kept if clause) or fallback


def _elements(scene: str, materials: str, include_materials: bool, limit: int = 6) -> list[str]:
    """把场景与材质描述拆成可直接展示的元素清单。"""
    items: list[str] = []
    for raw in re.split(r"[，,。；;]", str(scene or "")):
        item = _clean(raw)
        if not item or item.startswith("无") or "不要" in item:
            continue
        if not include_materials and any(term in item for term in BLOCKED_TERMS):
            continue
        items.append(item)
    if include_materials:
        for raw in re.split(r"[、，,。；;]", str(materials or "")):
            item = _clean(raw)
            if item and item not in items:
                items.append(item)
    if not items:
        items = ["纯净背景", "商品主体", "自然接触阴影"]
    return items[:limit]


def _rotate(points: list[str], offset: int, count: int) -> list[str]:
    """按页轮换卖点，保证 12 页不会反复说同一句。"""
    if not points:
        return []
    result = [points[(offset + i) % len(points)] for i in range(count)]
    return [item for item in result if item]


def _fallback_copy(inputs: dict[str, Any], code: str, role: str, index: int) -> dict[str, Any]:
    """模板兜底文案：把用户卖点按页轮换，保证详情页有主标题/副标题/3 条要点。"""
    points = inputs["selling_points"]
    product = inputs["product_type"] or "商品"
    style = inputs["style"] or "干净商业"
    mode = TEXT_RULES.get(code, "full")
    if mode == "none":
        return {"copy_headline": "", "copy_sub": "", "copy_points": [], "copy_tags": []}
    rotated = _rotate(points, index, 3) or [f"{product}的日常使用"]
    if mode == "headline_only":
        return {"copy_headline": rotated[0][:14], "copy_sub": "", "copy_points": [], "copy_tags": []}
    if mode == "tag_only":
        return {"copy_headline": "", "copy_sub": "", "copy_points": [], "copy_tags": rotated[:1]}
    if mode == "headline_sub":
        return {"copy_headline": rotated[0][:14], "copy_sub": (rotated[1] if len(rotated) > 1 else style)[:22], "copy_points": [], "copy_tags": []}
    if mode == "headline_points":
        return {"copy_headline": (f"{product}｜{rotated[0]}")[:14], "copy_sub": "", "copy_points": rotated[:2], "copy_tags": []}
    headline = (f"{product}｜{rotated[0]}")[:14]
    sub = (rotated[1] if len(rotated) > 1 else f"{product} · {style}")[:22]
    unique_points = []
    for point in rotated:
        if point not in unique_points:
            unique_points.append(point)
    for filler in (f"{role}的真实使用场景", f"{product}的细节质感", "日常使用方式"):
        if len(unique_points) >= 3:
            break
        if filler not in unique_points:
            unique_points.append(filler)
    return {"copy_headline": headline, "copy_sub": sub, "copy_points": unique_points[:3], "copy_tags": []}


def _text_block(copy: dict[str, Any]) -> str:
    """把文案整理成「逐字渲染」段落：先写清画哪些字，再写怎么排。"""
    headline = _clean(copy.get("copy_headline"))
    sub = _clean(copy.get("copy_sub"))
    points = [_clean(p) for p in (copy.get("copy_points") or []) if _clean(p)]
    tags = [_clean(t) for t in (copy.get("copy_tags") or []) if _clean(t)]
    if not (headline or sub or points or tags):
        return "文字内容：除包装自带文字外，不生成任何广告文字、角标或水印。"
    lines = ["文字内容（逐字渲染，错一个字都算不合格）："]
    if headline:
        lines.append("主标题「" + headline + "」")
    if sub:
        lines.append("副标题「" + sub + "」")
    if points:
        lines.append("利益点文案：" + "｜".join("「" + p + "」" for p in points))
    if tags:
        lines.append("标签：" + "、".join("「" + t + "」" for t in tags))
    lines.append("只把引号里的文字画进画面，不要把「主标题」「副标题」「利益点」这些标签字样画出来。")
    lines.append("排版：主标题最大最重，副标题次之，利益点单行左对齐。")
    lines.append("防溢出：所有文字距画面四边至少 8%，不超边、不裁切、不压产品；标题最多两行。")
    code = str(copy.get("code") or "")
    style = TYPE_STYLES[sum(ord(ch) for ch in code) % len(TYPE_STYLES)] if code else TYPE_STYLES[0]
    lines.append("字体与艺术字：" + style["font"] + "；" + style["art"] + "。")
    lines.append("装饰元素：" + style["deco"] + "。")
    return "\n".join(lines)
def _compose_prompt(inputs: dict[str, Any], page: dict[str, Any], copy: dict[str, Any], share: str, elements: list[str], ratio: str) -> tuple[str, str]:
    """按五段结构拼装提示词：画面构图 / 光影 / 主体与背景 / 文字排版 / 负面约束。"""
    product_type = inputs["product_type"] or "商品"
    style = inputs["style"] or "干净商业"
    audience = inputs["audience"]
    sample_ok = inputs["sample_ok"]
    code = str(page.get("code") or "")
    role = str(page.get("role") or "")

    objective = _sanitize_text(page.get("objective"), sample_ok)
    if len(objective) < 8:
        objective = role + "：讲清这一页要解决的购买疑虑，并给出明确画面重点"
    composition = _sanitize_text(page.get("composition"), sample_ok)
    camera = _sanitize_text(page.get("camera"), sample_ok)
    lighting = _sanitize_text(page.get("lighting"), sample_ok) or "柔和侧光，色温 5000K"
    scene = _sanitize_text(page.get("scene"), sample_ok, fallback="干净的台面与浅色墙面")
    negative = GENERIC_NEGATIVE if not sample_ok else (_clean(page.get("negative_specific")) or GENERIC_NEGATIVE)

    layout = "；".join(part for part in (composition, camera, "产品占画面 " + share) if part)
    if "安全边距" not in layout:
        layout = layout + "；四周保留 8% 安全边距" if layout else "四周保留 8% 安全边距"

    extra_elements = [item for item in elements if item not in scene][:5]
    scene_line = scene + (("；" + "、".join(extra_elements)) if extra_elements else "")
    raw_text = _text_block({**copy, "code": code}).replace("文字内容（逐字渲染，错一个字都算不合格）：\n", "")
    text_section = "；".join(part.rstrip("。") for part in raw_text.splitlines() if part.strip())

    kind = "主图" if code.startswith("M") else "详情页"
    parts = [
        "电商" + kind + " " + code + "｜" + role + "｜" + ratio + "｜2K",
        "商品：" + product_type + "。外观、颜色、材质、结构与包装文字必须与参考图完全一致，不得改写品牌和标签。本页任务：" + objective,
        "【画面构图与版式】" + layout,
        "【光影氛围】" + lighting + "；整体色调 " + style + "，明暗过渡自然，不要过曝或脏灰",
        "【主体与背景元素】" + scene_line + "；人群参照：" + (audience or "真实用户场景"),
        "【文字排版要求】" + text_section,
        "【负面约束】" + negative + "；不要出现多余文字、乱码、水印、变形",
    ]
    full = "\n".join(part for part in parts if part)

    headline = _clean(copy.get("copy_headline"))
    sub = _clean(copy.get("copy_sub"))
    short_bits = [
        ratio + " " + role + "。" + product_type + "，外观与参考图一致。",
        "、".join(elements[:2]) + "；产品占 " + share + "。",
        lighting[:20] + "。",
    ]
    if headline:
        short_bits.append("主标题「" + headline + "」" + (("，副标题「" + sub + "」") if sub else "") + "。")
    short_bits.append("避免错字、乱码、多余物体。")
    return full, "".join(short_bits)
def _plan_from_pack(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """用提示词包 + 模板文案做确定性拼装：不联网也能出 12 页完整方案。"""
    pack = load_pack()
    pack_pages = pack.get("pages") if pack else None
    if not isinstance(pack_pages, list) or len(pack_pages) != 12:
        pack_pages = FALLBACK_PAGES
    pages: list[dict[str, Any]] = []
    for index, page in enumerate(pack_pages):
        code = str(page.get("code") or EXPECTED_CODES[index]).upper()
        ratio = _ratio_for(code, inputs["ratio_mode"], str(page.get("ratio") or ""))
        share = _share_range(str(page.get("product") or ""))
        elements = _elements(str(page.get("scene") or ""), str(page.get("materials") or ""), include_materials=bool(inputs["sample_ok"]))
        copy = _fallback_copy(inputs, code, str(page.get("role") or ""), index)
        full, short = _compose_prompt(inputs, page, copy, share, elements, ratio)
        pages.append({
            "code": code,
            "slot": str(page.get("slot") or ""),
            "role": TASK_NAMES.get(code, str(page.get("role") or "")),
            "ratio": ratio,
            "buyer_question": str(page.get("buyer_question") or ""),
            "objective": _sanitize_text(page.get("objective"), inputs["sample_ok"], fallback=f"{page.get('role', '')}：讲清这一页要解决的购买疑虑"),
            "composition": "；".join(p for p in [str(page.get("composition") or ""), str(page.get("camera") or ""), str(page.get("text_zone") or "")] if p),
            "product_share": share,
            "scene_elements": elements,
            "lighting_mood": str(page.get("lighting") or ""),
            "copy_headline": copy["copy_headline"],
            "copy_sub": copy["copy_sub"],
            "copy_points": copy["copy_points"],
            "copy_tags": copy["copy_tags"],
            "text_layout": "文字区固定在上方或左侧安全区，主标题最大、副标题次之、要点等宽左对齐。",
            "prompt_full": full,
            "prompt_short": short,
        })
    return pages


def _ensure_copy(pages: list[dict[str, Any]], inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """代码层兜底：模型少写文案时按卖点补齐，保证详情页一定有主/副标题和 3 条要点。"""
    points = inputs.get("selling_points") or []
    for index, page in enumerate(pages):
        code = page.get("code", "")
        mode = TEXT_RULES.get(code, "full")
        if mode == "none":
            continue
        if mode in ("headline_only", "headline_sub", "headline_points", "full") and not page.get("copy_headline"):
            rotated = _rotate(points, index, 1)
            page["copy_headline"] = (rotated[0] if rotated else page.get("role", ""))[:14]
        if mode in ("headline_sub", "full") and not page.get("copy_sub"):
            rotated = _rotate(points, index + 1, 1)
            page["copy_sub"] = (rotated[0] if rotated else inputs.get("style", ""))[:22]
        if mode == "full" and len(page.get("copy_points") or []) < 3:
            missing = [p for p in points if p not in page["copy_points"]]
            page["copy_points"] = (page.get("copy_points") or []) + _rotate(missing, index, 3 - len(page.get("copy_points") or []))
        # 提示词里没写文字块时补上，避免“只有一页提到文字”
        if mode != "tag_only" and "文字内容" not in page.get("prompt_full", ""):
            page["prompt_full"] = page.get("prompt_full", "") + "\n" + _text_block(page)
    return pages


def _validate_pages(pages: Any) -> list[dict[str, Any]]:
    """校验模型返回的 12 页结构，不合格就抛错交给上层降级。"""
    if not isinstance(pages, list) or len(pages) != 12:
        raise ValueError("页数不是 12")
    result: list[dict[str, Any]] = []
    for index, item in enumerate(pages):
        if not isinstance(item, dict):
            raise ValueError("第 %d 页不是对象" % (index + 1))
        code = str(item.get("code") or "").upper()
        if code != EXPECTED_CODES[index]:
            raise ValueError("第 %d 页 code 应为 %s" % (index + 1, EXPECTED_CODES[index]))
        for field in ("objective", "composition", "product_share", "scene_elements", "lighting_mood", "prompt_full"):
            if not item.get(field):
                raise ValueError("%s 缺少 %s" % (code, field))
        prompt_full = str(item.get("prompt_full") or "")
        if len(prompt_full) < 120 or re.search(r"\{[a-zA-Z_]+\}", prompt_full):
            raise ValueError("%s 的 prompt_full 太短或不合法" % code)
        points = item.get("copy_points") or []
        result.append({
            "code": code,
            "slot": str(item.get("slot") or ""),
            "role": str(item.get("role") or ""),
            "ratio": str(item.get("ratio") or ""),
            "buyer_question": str(item.get("buyer_question") or ""),
            "objective": str(item.get("objective") or ""),
            "composition": str(item.get("composition") or ""),
            "product_share": str(item.get("product_share") or ""),
            "scene_elements": [str(e) for e in (item.get("scene_elements") or [])][:8],
            "lighting_mood": str(item.get("lighting_mood") or ""),
            "copy_headline": _clean(item.get("copy_headline")),
            "copy_sub": _clean(item.get("copy_sub")),
            "copy_points": [_clean(p) for p in points][:4],
            "copy_tags": [t for t in (_clean(x) for x in (item.get("copy_tags") or [])) if t and not any(w in t for w in ("主图", "详情页", "首屏", "承接", "收束", "痛点", "机制", "核心利益", "使用方法", "场景覆盖", "规格"))][:4],
            "text_layout": str(item.get("text_layout") or ""),
            "prompt_full": prompt_full,
            "prompt_short": str(item.get("prompt_short") or prompt_full[:120]),
        })
        page = result[-1]
        if len(page["prompt_full"]) < 300:
            page["prompt_full"] = page["prompt_full"] + "\n" + _text_block(page) + "\n负面约束：" + GENERIC_NEGATIVE + "；不要出现多余文字、乱码、水印、变形。"
    return result


def _image_data_url(path: str) -> str:
    """把本机实拍图压成长边不超过 1024 的 JPEG data URL，供视觉模型读取。"""
    with Image.open(path) as image:
        image = image.convert("RGB")
        width, height = image.size
        scale = min(1.0, VISION_MAX_EDGE / max(width, height))
        if scale < 1.0:
            image = image.resize((max(1, int(width * scale)), max(1, int(height * scale))), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _salvage_pages(content: str) -> list[dict[str, Any]]:
    """模型偶尔在最后几页被截断：按大括号配对逐个抠出完整对象。"""
    items: list[dict[str, Any]] = []
    depth = 0
    start: int | None = None
    for index, char in enumerate(content):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and start is not None:
                try:
                    item = json.loads(content[start:index + 1])
                    if isinstance(item, dict):
                        items.append(item)
                except json.JSONDecodeError:
                    pass
                start = None
    return items


def _plan_with_ai(inputs: dict[str, Any], image_url: str = "") -> list[dict[str, Any]]:
    """调用 DeepSeek 细化 12 页；失败由上层决定降级。"""
    settings = load_settings()
    key = str(settings.get("deepseek_key") or "").strip()
    if not key:
        raise RuntimeError("未配置 DeepSeek Key")
    user_text = (
        "产品类型：%s\n目标人群：%s\n整体风格：%s\n产品卖点：%s\n页面比例模式：%s\n参考图描述：%s"
        % (
            inputs["product_type"],
            inputs["audience"] or "未提供，不要编造",
            inputs["style"] or "未提供，按干净商业写",
            "、".join(inputs["selling_points"]) or "未提供，不要编造功效",
            inputs["ratio_mode"],
            inputs["reference_note"] or "未提供",
        )
    )
    if image_url:
        user_text += "\n附带图片是商品实拍图：先读出器型、材质、颜色、包装结构与包装上的真实文字，再据此写提示词；图中没有的信息不要编造。"
    user_text += (
        "\n每页文案硬性要求："
        "\nM01 不写任何广告文字；M02 主标题+副标题；M03 只写 1 个质地标签；M04 主标题+副标题；M05 主标题+2 条规格要点；"
        "\nD01-D07 每页必须：主标题（6-14 字，写成一句有画面的话，不能照抄卖点短语）+ 副标题（10-22 字，解释主标题）+ 3 条利益点（每条 8-18 字）+ 可选标签。"
    )
    user_text += "\n请输出 12 页方案的 JSON 数组，详情页务必写足文案。"
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
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
                {"role": "user", "content": content if image_url else user_text},
            ],
            "temperature": 0.6,
            "max_tokens": 16000,
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
    if raw.startswith("{") and "pages" in raw:
        raw = raw[raw.find("["):raw.rfind("]") + 1]
    start, end = raw.find("["), raw.rfind("]")
    if start < 0 or end <= start:
        raise RuntimeError("DeepSeek 未返回 JSON 数组（返回 %d 字）" % len(raw))
    try:
        pages = json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        salvaged = _salvage_pages(raw[start:])
        if not salvaged:
            raise RuntimeError("DeepSeek 返回的 JSON 无法解析") from None
        template_pages = _plan_from_pack(inputs)
        by_code = {str(item.get("code") or "").upper(): item for item in salvaged}
        pages = [by_code.get(code) or template_pages[i] for i, code in enumerate(EXPECTED_CODES)]
    return _ensure_copy(_validate_pages(pages), inputs)


def _log(message: str) -> None:
    """把生成失败原因写到 data/logs/ai-日期.log，方便事后排查。"""
    try:
        import datetime
        log_dir = APP_DIR / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        path = log_dir / ("ai-%s.log" % datetime.date.today().isoformat())
        with path.open("a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (datetime.datetime.now().strftime("%H:%M:%S"), message))
    except OSError:
        pass


def build_page_plan(payload: dict[str, Any] | None, use_ai: bool = True) -> dict[str, Any]:
    """对外入口：返回 12 页方案与来源（deepseek-vision / deepseek / template）。"""
    data = payload or {}
    inputs = normalize_inputs(data)
    if not inputs["product_type"]:
        raise ValueError("请先填写产品类型")
    reference_path = str(data.get("reference_path") or "").strip()
    image_url = ""
    note = ""
    if bool(data.get("use_vision", True)) and reference_path:
        try:
            image_url = _image_data_url(reference_path)
        except Exception as exc:
            note = "实拍图读取失败，已改用文字生成（%s）" % exc
            _log("实拍图读取失败: %s" % exc)
    source = "template"
    warning = ""
    pages: list[dict[str, Any]] | None = None
    if use_ai:
        if image_url:
            try:
                pages = _plan_with_ai(inputs, image_url)
                source = "deepseek-vision"
            except Exception as exc:
                note = "看图生成失败，已改用文字生成（%s）" % exc
                _log("看图生成失败: %s" % exc)
        if not pages:
            try:
                pages = _plan_with_ai(inputs)
                source = "deepseek"
            except Exception as exc:
                warning = "AI 细化不可用，已回落到模板方案（%s）" % exc
                _log("文字生成失败: %s" % exc)
    if not pages:
        pages = _plan_from_pack(inputs)
    if note and not warning:
        warning = note
    return {
        "ok": True,
        "source": source,
        "warning": warning,
        "meta": {
            "total": len(pages),
            "ratio_mode": inputs["ratio_mode"],
            "product_type": inputs["product_type"],
            "audience": inputs["audience"],
            "style": inputs["style"],
            "selling_points": inputs["selling_points"],
            "reference_note": inputs["reference_note"],
            "vision": bool(image_url),
            "main_images": sum(1 for page in pages if page["code"].startswith("M")),
            "detail_pages": sum(1 for page in pages if page["code"].startswith("D")),
        },
        "pages": pages,
    }






