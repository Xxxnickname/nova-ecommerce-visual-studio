"""Twelve-asset visual suite: AI photography plus deterministic information layouts."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

SUITE_ROLES: list[dict[str, Any]] = [
    {"id": "01_white_main", "name": "白底主图", "kind": "image", "instruction": "电商白底主图，商品完整、居中、无文字无水印"},
    {"id": "02_hero_angle", "name": "45° 主体图", "kind": "image", "instruction": "展示完整商品与包装的第二个专业角度，正面或 45 度"},
    {"id": "03_packaging", "name": "包装展示", "kind": "image", "instruction": "同时展示商品主体和外包装，保持标签和包装结构准确"},
    {"id": "04_scene_a", "name": "场景图 A", "kind": "image", "instruction": "核心生活方式场景，商品自然融入环境"},
    {"id": "05_scene_b", "name": "场景图 B", "kind": "image", "instruction": "第二生活方式场景，氛围与前一张明显不同"},
    {"id": "06_texture", "name": "材质细节", "kind": "image", "instruction": "微距展示材质、表面纹理和真实触感"},
    {"id": "07_craft", "name": "工艺细节", "kind": "image", "instruction": "微距展示边缘、结构、包边或包装工艺细节"},
    {"id": "08_benefits_1", "name": "首屏利益点", "kind": "layout", "layout": "benefits_light"},
    {"id": "09_benefits_2", "name": "痛点与解决方案", "kind": "layout", "layout": "benefits_dark"},
    {"id": "10_size_spec", "name": "尺寸规格", "kind": "layout", "layout": "size"},
    {"id": "11_in_box", "name": "包装与使用", "kind": "layout", "layout": "in_box"},
    {"id": "12_variants", "name": "规格对比", "kind": "layout", "layout": "variants"},
]

IVORY = (246, 241, 232)
INK = (31, 29, 25)
SAGE = (112, 128, 107)
CLAY = (182, 106, 74)
BRASS = (183, 154, 103)
WHITE = (255, 253, 249)


def _font_path(bold: bool = False) -> str | None:
    names = ["msyhbd.ttc", "msyh.ttc"] if bold else ["msyh.ttc", "msyhbd.ttc"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return str(path)
    return None


def _font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _font_path(bold)
    if path:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in text:
        candidate = current + char
        punctuation = "，。；、！？：,.!?:;"
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current or char in punctuation:
            current = candidate
        else:
            lines.append(current)
            current = char
    if current:
        lines.append(current)
    return lines[:4]


def _draw_wrapped(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: ImageFont.ImageFont, fill, max_width: int, spacing: int = 8) -> int:
    x, y = xy
    for line in _wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += draw.textbbox((0, 0), line, font=font)[3] + spacing
    return y


def _brand(draw: ImageDraw.ImageDraw, size: tuple[int, int], dark: bool = False, brand: str = "") -> None:
    width, height = size
    unit = min(width, height)
    font = _font(max(18, int(unit * 0.021)), True)
    small = _font(max(13, int(unit * 0.013)))
    label = _ellipsis(brand, 28) if brand else "PRODUCT EDIT"
    draw.text((int(unit * 0.055), int(unit * 0.045)), label, font=font, fill=(WHITE if dark else INK))
    draw.text((int(unit * 0.055), int(unit * 0.078)), "VISUAL NOTES", font=small, fill=(200, 196, 186) if dark else (126, 116, 103))


def _product_panel(base_path: str | Path, box: tuple[int, int], background=WHITE, pad: int = 34) -> Image.Image:
    width, height = box
    panel = Image.new("RGB", (width, height), background)
    with Image.open(base_path) as source:
        image = ImageOps.exif_transpose(source).convert("RGB")
        image = ImageOps.contain(image, (width - pad * 2, height - pad * 2), Image.Resampling.LANCZOS)
        panel.paste(image, ((width - image.width) // 2, (height - image.height) // 2))
    return panel




def _fit_panel_size(base_path: str | Path, max_width: int, max_height: int) -> tuple[int, int]:
    with Image.open(base_path) as source:
        ratio = source.width / source.height
    if max_width / max_height > ratio:
        height = max_height
        width = max(1, int(height * ratio))
    else:
        width = max_width
        height = max(1, int(width / ratio))
    return width, height

def _round_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius=radius, fill=255)
    return mask


def _points_from_extras(extras: dict[str, Any], category_id: str) -> list[str]:
    raw = str(extras.get("selling_points") or "").strip()
    if raw:
        parts = [item.strip() for item in re.split(r"[、,，;/；]+", raw) if item.strip()]
        if parts:
            return (parts + ["细节设计", "日常好用", "质感呈现"])[:3]
    defaults = {
        "beauty": ["细腻质地", "日常易用", "包装质感"],
        "home_textile": ["柔软触感", "舒适包裹", "细节工艺"],
        "apparel": ["版型利落", "面料舒适", "日常百搭"],
        "food": ["风味清晰", "包装便捷", "分享友好"],
        "electronics": ["操作简洁", "结构精致", "日常高效"],
        "jewelry": ["细节闪耀", "佩戴轻盈", "礼赠友好"],
        "generic": ["设计克制", "使用顺手", "质感真实"],
    }
    return defaults.get(category_id, defaults["generic"])


def suite_copy_points(extras: dict[str, Any], category_id: str) -> list[str]:
    return _points_from_extras(extras, category_id)




STYLE_ACCENTS = {
    "pearl-floral": (166, 129, 151),
    "navy-gold": (190, 157, 94),
    "water-glass": (91, 151, 166),
    "mineral-crystal": (174, 141, 105),
    "champagne-silk": (186, 150, 96),
    "rose-gift": (166, 88, 101),
    "warm-editorial": (128, 102, 78),
    "dark-botanical": (133, 150, 112),
}


def _serif_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    names = ["STZHONGS.TTF", "simsun.ttc", "msyhbd.ttc", "msyh.ttc"]
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if not path.exists():
            continue
        try:
            return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return _font(size, bold)


def _ellipsis(text: str, limit: int) -> str:
    value = " ".join(str(text or "").split())
    return value if len(value) <= limit else value[: max(1, limit - 1)] + "…"


def _wrap_lines(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for char in str(text or ""):
        candidate = current + char
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = char
            if len(lines) >= max_lines - 1:
                break
    if current and len(lines) < max_lines:
        remaining = str(text or "")[sum(len(line) for line in lines):]
        if remaining and draw.textbbox((0, 0), remaining, font=font)[2] > max_width:
            while remaining and draw.textbbox((0, 0), remaining + "…", font=font)[2] > max_width:
                remaining = remaining[:-1]
            current = remaining + "…"
        lines.append(current)
    return lines or [""]


def _draw_fitted(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    max_height: int,
    max_size: int,
    min_size: int,
    fill,
    *,
    bold: bool = False,
    serif: bool = False,
    max_lines: int = 3,
    line_ratio: float = 1.28,
):
    chosen_font = None
    chosen_lines: list[str] = []
    chosen_step = min_size
    for size in range(max_size, min_size - 1, -2):
        font = _serif_font(size, bold) if serif else _font(size, bold)
        lines = _wrap_lines(draw, text, font, max_width, max_lines)
        step = max(size + 2, int(size * line_ratio))
        total_height = step * (len(lines) - 1) + size + 8
        if total_height <= max_height:
            chosen_font, chosen_lines, chosen_step = font, lines, step
            break
    if chosen_font is None:
        chosen_font = _serif_font(min_size, bold) if serif else _font(min_size, bold)
        chosen_lines = _wrap_lines(draw, text, chosen_font, max_width, max_lines)
    for index, line in enumerate(chosen_lines):
        draw.text((x, y + index * chosen_step), line, font=chosen_font, fill=fill)
    return y + len(chosen_lines) * chosen_step


def _panel(canvas: Image.Image, draw: ImageDraw.ImageDraw, box, fill, accent, radius: int) -> None:
    x1, y1, x2, y2 = [int(value) for value in box]
    draw.rounded_rectangle((x1 + 10, y1 + 14, x2 + 10, y2 + 14), radius=radius, fill=(10, 10, 10, 34))
    draw.rounded_rectangle((x1, y1, x2, y2), radius=radius, fill=fill, outline=(*accent, 120), width=max(2, int(radius * 0.08)))


def _brand_line(draw: ImageDraw.ImageDraw, x: int, y: int, brand: str, width: int, ink, accent) -> int:
    label = _ellipsis(brand or "PRODUCT EDIT", 28)
    font = _font(max(22, int(width * 0.031)), True)
    draw.text((x, y), label, font=font, fill=ink)
    draw.rectangle((x, y + int(width * 0.052), x + int(width * 0.19), y + int(width * 0.055)), fill=accent)
    return y + int(width * 0.072)


def render_overlay(role: dict[str, Any], base_path: str | Path, output_path: str | Path, width: int, height: int, description: str, extras: dict[str, Any], category_id: str, style_id: str = "") -> dict[str, Any]:
    """Overlay deterministic, safe-margin typography on a text-free Seedream background."""
    unit = min(width, height)
    with Image.open(base_path) as source:
        canvas = ImageOps.fit(ImageOps.exif_transpose(source).convert("RGBA"), (width, height), method=Image.Resampling.LANCZOS).convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    points = [_ellipsis(value, 18) for value in _points_from_extras(extras, category_id)[:3]]
    brand = str(extras.get("brand_name") or "").strip()
    accent = STYLE_ACCENTS.get(style_id, CLAY)
    safe = max(42, int(unit * 0.045))
    pad = max(48, int(unit * 0.052))
    layout = role["layout"]
    light_panel = (249, 245, 237, 242)
    dark_panel = (24, 30, 35, 242)
    ink = (34, 31, 28, 255)
    pale = (249, 246, 239, 255)
    muted = (104, 96, 88, 255)
    dark_muted = (200, 194, 184, 255)
    radius = max(18, int(unit * 0.024))

    if layout in ("benefits_light", "benefits_dark"):
        dark = layout == "benefits_dark"
        if dark:
            box = (int(width * 0.435), safe, width - safe, height - safe)
            fill = dark_panel
            fg, note = pale, dark_muted
        else:
            box = (safe, safe, int(width * 0.555), height - safe)
            fill = light_panel
            fg, note = ink, muted
        _panel(canvas, draw, box, fill, accent, radius)
        x1, y1, x2, y2 = box
        x = x1 + pad
        inner_w = x2 - x1 - pad * 2
        cursor = _brand_line(draw, x, y1 + pad, brand, inner_w, fg, accent)
        kicker = "WHY IT WORKS" if not dark else "DETAILS MATTER"
        draw.text((x, cursor), kicker, font=_font(max(18, int(unit * 0.018)), True), fill=(*accent, 255))
        cursor += int(unit * 0.042)
        title = "为什么选择它" if not dark else "细节，成就体验"
        subtitle = "从第一眼到每一天" if not dark else "从材质到结构，每一处都值得被看见"
        cursor = _draw_fitted(draw, title, x, cursor, inner_w, int(unit * 0.14), max(64, int(unit * 0.064)), max(46, int(unit * 0.038)), fg, bold=True, serif=True, max_lines=2)
        cursor = _draw_fitted(draw, subtitle, x, cursor + int(unit * 0.008), inner_w, int(unit * 0.08), max(28, int(unit * 0.025)), max(22, int(unit * 0.018)), note, max_lines=2)
        cursor += int(unit * 0.045)
        row_step = min(int(unit * 0.115), max(118, (y2 - pad - cursor) // 3))
        for index, point in enumerate(points, 1):
            cy = cursor + (index - 1) * row_step
            draw.ellipse((x, cy, x + int(unit * 0.043), cy + int(unit * 0.043)), fill=(*accent, 255))
            num_font = _font(max(16, int(unit * 0.017)), True)
            num_bbox = draw.textbbox((0, 0), str(index), font=num_font)
            draw.text((x + (int(unit * 0.043) - (num_bbox[2] - num_bbox[0])) / 2, cy + (int(unit * 0.043) - (num_bbox[3] - num_bbox[1])) / 2 - num_bbox[1]), str(index), font=num_font, fill=pale)
            _draw_fitted(draw, point, x + int(unit * 0.062), cy - 2, inner_w - int(unit * 0.062), int(unit * 0.075), max(28, int(unit * 0.029)), max(22, int(unit * 0.020)), fg, max_lines=2)

    elif layout == "size":
        box = (int(width * 0.635), int(height * 0.075), width - safe, height - safe)
        _panel(canvas, draw, box, light_panel, accent, radius)
        x1, y1, x2, y2 = box
        x = x1 + pad
        inner_w = x2 - x1 - pad * 2
        cursor = _brand_line(draw, x, y1 + pad, brand, inner_w, ink, accent)
        cursor = _draw_fitted(draw, "尺寸与规格", x, cursor, inner_w, int(unit * 0.13), max(58, int(unit * 0.055)), max(38, int(unit * 0.033)), ink, bold=True, serif=True)
        dims = re.findall(r"\d+(?:\.\d+)?\s*[x×*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|ml|g|kg)?", description, flags=re.I)
        spec = dims[0] if dims else "规格以商品详情为准"
        cursor += int(unit * 0.025)
        info = [("适用场景", "日常通勤、重要场合"), ("包装方式", "产品装盒，按实物为准"), ("规格提示", spec)]
        for title, value in info:
            card_h = int(unit * 0.14)
            draw.rounded_rectangle((x, cursor, x + inner_w, cursor + card_h), radius=max(12, int(unit * 0.014)), fill=(255, 253, 249, 220), outline=(*accent, 70), width=2)
            draw.text((x + int(unit * 0.02), cursor + int(unit * 0.020)), title, font=_font(max(20, int(unit * 0.020)), True), fill=(*accent, 255))
            _draw_fitted(draw, value, x + int(unit * 0.02), cursor + int(unit * 0.055), inner_w - int(unit * 0.04), card_h - int(unit * 0.060), max(23, int(unit * 0.022)), max(18, int(unit * 0.016)), ink, max_lines=2)
            cursor += card_h + int(unit * 0.022)

    elif layout == "in_box":
        box = (int(width * 0.455), safe, width - safe, height - safe)
        _panel(canvas, draw, box, dark_panel, accent, radius)
        x1, y1, x2, y2 = box
        x = x1 + pad
        inner_w = x2 - x1 - pad * 2
        cursor = _brand_line(draw, x, y1 + pad, brand, inner_w, pale, accent)
        cursor = _draw_fitted(draw, "包装与使用", x, cursor, inner_w, int(unit * 0.105), max(56, int(unit * 0.052)), max(36, int(unit * 0.032)), pale, bold=True, serif=True)
        cursor += int(unit * 0.028)
        items = ["商品主体 × 1", "包装盒 × 1", "说明卡 × 1"]
        for item in items:
            draw.rounded_rectangle((x, cursor, x + inner_w, cursor + int(unit * 0.070)), radius=max(10, int(unit * 0.012)), fill=(255, 255, 255, 18), outline=(*accent, 100), width=2)
            draw.text((x + int(unit * 0.018), cursor + int(unit * 0.018)), item, font=_font(max(24, int(unit * 0.024))), fill=ink)
            cursor += int(unit * 0.088)
        cursor += int(unit * 0.020)
        draw.text((x, cursor), "使用步骤", font=_font(max(22, int(unit * 0.021)), True), fill=(*accent, 255))
        cursor += int(unit * 0.045)
        steps = ["01 取出商品", "02 展开使用", "03 收纳保存"]
        for item in steps:
            draw.text((x, cursor), item, font=_font(max(21, int(unit * 0.020))), fill=dark_muted)
            cursor += int(unit * 0.045)

    elif layout == "variants":
        labels = ["标准装", "礼盒装", "旅行装"]
        top_box = (safe, safe, int(width * 0.40), int(height * 0.205))
        _panel(canvas, draw, top_box, light_panel, accent, radius)
        cursor = _brand_line(draw, safe + pad, safe + pad, brand, int(width * 0.40) - safe - pad * 2, ink, accent)
        _draw_fitted(draw, "多规格可选", safe + pad, cursor, int(width * 0.40) - safe - pad * 2, int(unit * 0.08), max(48, int(unit * 0.047)), max(32, int(unit * 0.030)), ink, bold=True, serif=True)
        box = (safe, int(height * 0.775), width - safe, height - safe)
        _panel(canvas, draw, box, light_panel, accent, radius)
        gap = int(unit * 0.014)
        inner_w = width - safe * 2 - pad * 2 - gap * 2
        tile_w = inner_w // 3
        for index, label in enumerate(labels):
            x = safe + pad + index * (tile_w + gap)
            draw.rounded_rectangle((x, box[1] + int(unit * 0.018), x + tile_w, box[3] - int(unit * 0.018)), radius=max(10, int(unit * 0.012)), fill=(255, 253, 249, 205), outline=(*accent, 75), width=2)
            draw.text((x + int(unit * 0.016), box[1] + int(unit * 0.035)), label, font=_font(max(22, int(unit * 0.022)), True), fill=ink)
            tagline = ["日常通勤补妆", "节日礼赠优选", "外出便携补妆"][index]
            draw.text((x + int(unit * 0.016), box[1] + int(unit * 0.070)), tagline, font=_font(max(16, int(unit * 0.016))), fill=muted)

    else:
        _panel(canvas, draw, (safe, safe, width - safe, height - safe), light_panel, accent, radius)
        _draw_fitted(draw, "商品视觉", safe + pad, safe + pad, width - safe * 2 - pad * 2, height - safe * 2 - pad * 2, 72, 38, ink, bold=True, serif=True)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(target, format="PNG", optimize=True)
    return {"path": str(target), "width": width, "height": height, "bytes": target.stat().st_size}

def render_layout(role: dict[str, Any], base_path: str | Path, output_path: str | Path, width: int, height: int, description: str, extras: dict[str, Any], category_id: str) -> dict[str, Any]:
    unit = min(width, height)
    canvas = Image.new("RGB", (width, height), IVORY)
    draw = ImageDraw.Draw(canvas)
    layout = role["layout"]
    points = _points_from_extras(extras, category_id)
    title_font = _font(max(48, int(unit * 0.066)), True)
    body_font = _font(max(24, int(unit * 0.028)))
    small_font = _font(max(18, int(unit * 0.020)))
    muted = (112, 102, 90)

    if layout in ("benefits_light", "benefits_dark"):
        dark = layout == "benefits_dark"
        bg = INK if dark else IVORY
        fg = WHITE if dark else INK
        muted = (196, 190, 181) if dark else (112, 102, 90)
        canvas = Image.new("RGB", (width, height), bg)
        draw = ImageDraw.Draw(canvas)
        _brand(draw, (width, height), dark, str(extras.get("brand_name") or ""))
        left_w = int(width * 0.52)
        x = int(unit * 0.06)
        y = int(unit * 0.17)
        draw.text((x, y), "WHY IT WORKS", font=small_font, fill=CLAY if not dark else BRASS)
        y += int(unit * 0.045)
        y = _draw_wrapped(draw, (x, y), description[:32] or "让日常使用更从容", title_font, fg, left_w)
        y += int(unit * 0.04)
        for index, point in enumerate(points, 1):
            circle_y = y + (index - 1) * int(unit * 0.105)
            draw.ellipse((x, circle_y, x + int(unit * 0.045), circle_y + int(unit * 0.045)), fill=CLAY if not dark else BRASS)
            draw.text((x + int(unit * 0.015), circle_y - int(unit * 0.004)), str(index), font=small_font, fill=WHITE)
            draw.text((x + int(unit * 0.065), circle_y), point, font=body_font, fill=fg)
        panel_w, panel_h = _fit_panel_size(base_path, int(width * 0.37), int(height * 0.70))
        panel = _product_panel(base_path, (panel_w, panel_h), bg if dark else WHITE)
        px = width - panel_w - int(unit * 0.055)
        py = int(height * 0.15)
        canvas.paste(panel, (px, py), _round_mask((panel_w, panel_h), int(unit * 0.02)))
    elif layout == "size":
        _brand(draw, (width, height), False, str(extras.get("brand_name") or ""))
        draw.text((int(unit * 0.06), int(unit * 0.14)), "尺寸与规格", font=title_font, fill=INK)
        panel_w, panel_h = _fit_panel_size(base_path, int(width * 0.44), int(height * 0.56))
        panel = _product_panel(base_path, (panel_w, panel_h), WHITE)
        px, py = int(unit * 0.06), int(height * 0.29)
        canvas.paste(panel, (px, py), _round_mask((panel_w, panel_h), int(unit * 0.018)))
        line_x1, line_x2 = px, px + panel_w
        line_y = py + panel_h + int(unit * 0.035)
        draw.line((line_x1, line_y, line_x2, line_y), fill=CLAY, width=max(2, int(unit * 0.003)))
        draw.line((line_x1, line_y - 12, line_x1, line_y + 12), fill=CLAY, width=max(2, int(unit * 0.003)))
        draw.line((line_x2, line_y - 12, line_x2, line_y + 12), fill=CLAY, width=max(2, int(unit * 0.003)))
        dims = re.findall(r"\d+(?:\.\d+)?\s*[x×*]\s*\d+(?:\.\d+)?\s*(?:cm|mm|ml|g|kg)?", description, flags=re.I)
        draw.text((px + int(unit * 0.012), line_y + int(unit * 0.02)), dims[0] if dims else "规格信息以商品详情为准", font=small_font, fill=muted)
        draw.text((int(width * 0.58), int(height * 0.32)), "产品信息", font=small_font, fill=CLAY)
        info = [f"商品：{description[:24] or '待补充'}", "尺寸：以实物与详情页为准", "包装：按实际发货版本为准"]
        yy = int(height * 0.38)
        for item in info:
            yy = _draw_wrapped(draw, (int(width * 0.58), yy), item, body_font, INK, int(width * 0.34))
            yy += int(unit * 0.035)
    elif layout == "in_box":
        _brand(draw, (width, height), True, str(extras.get("brand_name") or ""))
        canvas = Image.new("RGB", (width, height), INK)
        draw = ImageDraw.Draw(canvas)
        _brand(draw, (width, height), True, str(extras.get("brand_name") or ""))
        draw.text((int(unit * 0.06), int(unit * 0.14)), "包装清单", font=title_font, fill=WHITE)
        panel_w, panel_h = _fit_panel_size(base_path, int(width * 0.40), int(height * 0.60))
        panel = _product_panel(base_path, (panel_w, panel_h), WHITE)
        canvas.paste(panel, (int(unit * 0.06), int(height * 0.29)), _round_mask((panel_w, panel_h), int(unit * 0.018)))
        items = ["商品主体 × 1", "包装盒 × 1", "说明卡 × 1"]
        yy = int(height * 0.32)
        for index, item in enumerate(items):
            draw.ellipse((int(width * 0.55), yy, int(width * 0.55) + int(unit * 0.035), yy + int(unit * 0.035)), outline=BRASS, width=max(2, int(unit * 0.002)))
            draw.text((int(width * 0.61), yy), item, font=body_font, fill=WHITE)
            yy += int(unit * 0.11)
        _draw_wrapped(draw, (int(width * 0.55), int(height * 0.72)), "具体配件与包装以实际版本为准", small_font, (192, 187, 178), int(width * 0.36))
    elif layout == "variants":
        _brand(draw, (width, height), False, str(extras.get("brand_name") or ""))
        draw.text((int(unit * 0.06), int(unit * 0.14)), "多规格可选", font=title_font, fill=INK)
        labels = ["标准装", "礼盒装", "旅行装"]
        palette = [(239, 231, 218), (229, 235, 227), (243, 229, 223)]
        gap = int(unit * 0.025)
        tile_w = int((width - int(unit * 0.12) - gap * 2) / 3)
        tile_h = int(height * 0.52)
        for index, label in enumerate(labels):
            x = int(unit * 0.06) + index * (tile_w + gap)
            y = int(height * 0.29)
            draw.rounded_rectangle((x, y, x + tile_w, y + tile_h), radius=int(unit * 0.02), fill=palette[index])
            panel = _product_panel(base_path, (tile_w - int(unit * 0.04), tile_h - int(unit * 0.12)), palette[index])
            canvas.paste(panel, (x + int(unit * 0.02), y + int(unit * 0.04)))
            draw.text((x + int(unit * 0.025), y + tile_h - int(unit * 0.065)), label, font=small_font, fill=INK)
    else:
        _brand(draw, (width, height), False, str(extras.get("brand_name") or ""))
        draw.text((int(unit * 0.06), int(unit * 0.3)), "商品视觉", font=title_font, fill=INK)

    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True)
    return {"path": str(target), "width": width, "height": height, "bytes": target.stat().st_size}

