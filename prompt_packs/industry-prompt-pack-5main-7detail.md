# 粉底液行业标准套图提示词包

> 结构：5 张主图 + 7 张详情页 = 12 张。
> 模型：`doubao-seedream-5-0-flash-260915`。
> 主图 1:1，详情页 4:5，统一使用 2K。

## Campaign Style Lock

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]
```

## M01｜主图 1/5｜白底首图与商品识别

- 买家问题：这是什么商品，外观是否真实？
- 页面目标：平台搜索和列表第一眼完整识别商品，保持白底、干净、无广告字。
- 画幅：1:1 / 2K
- 产品占比：瓶身与外盒完整居中偏右，整体占画面 38%，不裁切，不重叠，外盒在瓶身后侧。
- 文案：无广告文字，仅保留包装自带文字。
- 文字策略：不生成广告文字。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
M01｜主图 1/5｜白底首图与商品识别
买家问题：这是什么商品，外观是否真实？
页面目标：平台搜索和列表第一眼完整识别商品，保持白底、干净、无广告字。

画幅比例：1:1，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身与外盒完整居中偏右，整体占画面 38%，不裁切，不重叠，外盒在瓶身后侧。
场景环境：纯白无缝背景 #FFFFFF，无道具，无纹理，底层仅保留商品与自然接触阴影。
构图方式：商品居中略偏右，顶部中央预留 12% 平台叠加区，四周安全边距 8%，画面干净。
镜头与景别：85mm 镜头，平视正 3/4，f/8，商品前后清晰，边缘准确。
光影氛围：均匀柔光棚拍，顶部偏左主光，右侧低强度补光，阴影极浅。
材质质感：磨砂玻璃、拉丝金色瓶盖、哑光深蓝纸盒、完整标签。
文案内容：无广告文字，仅保留包装自带文字。
文字与留白区域：顶部中央 200×100 像素视觉区域保持干净；不生成任何叠加文案。
文字策略：不生成广告文字。
证据与合规：Double Wear、30ml、SPF 10/PA+++ 来自实拍包装。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要出现道具、阴影过重、灰底、第二个瓶子、平台角标或宣传词。
```

## M02｜主图 2/5｜核心卖点图

- 买家问题：它最值得继续了解的特点是什么？
- 页面目标：用一张短文案主图承接消费者的第一购买理由。
- 画幅：1:1 / 2K
- 产品占比：瓶身与外盒完整放在左下，整体占 32%，右下留出文字区。
- 文案：主标题「柔焦质地」；副标题「轻盈贴合」。
- 文字策略：只直接生成这两个短标题，不生成正文。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
M02｜主图 2/5｜核心卖点图
买家问题：它最值得继续了解的特点是什么？
页面目标：用一张短文案主图承接消费者的第一购买理由。

画幅比例：1:1，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身与外盒完整放在左下，整体占 32%，右下留出文字区。
场景环境：暖象牙无缝背景 #F3EEE6，一条极细古金线从左下延伸到右侧，无其他道具。
构图方式：产品左下、标题右上，采用非对称平衡；留白至少 45%。
镜头与景别：85mm 镜头，平视 3/4，f/6.3，商品清晰，背景纯净。
光影氛围：左上大柔光，右侧轻微反射光，阴影柔和，5000K。
材质质感：磨砂玻璃、哑光纸盒、细金线、暖象牙背景。
文案内容：主标题「柔焦质地」；副标题「轻盈贴合」。
文字与留白区域：右上 38% 宽、20% 高，左对齐，标题与副标题两行。
文字策略：只直接生成这两个短标题，不生成正文。
证据与合规：质地与轻盈为体验语言，待品牌确认。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要使用夸张对比、24H、零瑕疵等未经证据支持的字样。
```

## M03｜主图 3/5｜质地细节图

- 买家问题：它看起来是什么质地？
- 页面目标：用质地微距建立产品记忆点和品质感。
- 画幅：1:1 / 2K
- 产品占比：瓶身位于右上后景，占 20%，轻微虚化；膏体占视觉主体 55%。
- 文案：主标题「一推即融」；副标题「柔焦质地」。
- 文字策略：只直接生成短标题和副标题。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
M03｜主图 3/5｜质地细节图
买家问题：它看起来是什么质地？
页面目标：用质地微距建立产品记忆点和品质感。

画幅比例：1:1，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身位于右上后景，占 20%，轻微虚化；膏体占视觉主体 55%。
场景环境：浅米色磨砂玻璃板上一道顺滑粉底涂抹，边缘自然延展，背景暖象牙色。
构图方式：膏体横向占据下半部，瓶身从右上进入，文案在左下；不使用居中摆拍。
镜头与景别：100mm 微距，45° 侧向视角，f/5.6，焦点落在膏体边缘。
光影氛围：左上窄柔光擦过表面，突出奶油纹理和薄厚变化。
材质质感：奶油状粉底、磨砂玻璃、细腻膏体、磨砂瓶身。
文案内容：主标题「一推即融」；副标题「柔焦质地」。
文字与留白区域：左下 30% 宽、18% 高，两行左对齐，避开膏体主体。
文字策略：只直接生成短标题和副标题。
证据与合规：质地与柔焦为体验描述，待品牌确认。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要人脸、手部、飞溅水花、夸张拉丝或虚假前后对比。
```

## M04｜主图 4/5｜生活场景图

- 买家问题：它在真实生活里怎么使用？
- 页面目标：用克制的通勤/梳妆场景增强代入感，不出现人物。
- 画幅：1:1 / 2K
- 产品占比：瓶身从米色手袋露出，占 22%，包装盒在下方露出边角，轮廓清晰。
- 文案：主标题「随身补妆」；副标题「轻盈不占空间」。
- 文字策略：直接生成短标题与副标题，不写参数。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
M04｜主图 4/5｜生活场景图
买家问题：它在真实生活里怎么使用？
页面目标：用克制的通勤/梳妆场景增强代入感，不出现人物。

画幅比例：1:1，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身从米色手袋露出，占 22%，包装盒在下方露出边角，轮廓清晰。
场景环境：灰米色皮革手袋与浅米石材台面，右上留白，亚麻布作为小面积柔和材质。
构图方式：手袋占下方 55%，产品在包口左上，文案右上；留白至少 45%。
镜头与景别：50mm 镜头，平视微俯，f/4.5，包体清晰，背景轻微虚化。
光影氛围：自然窗光从左上进入，皮革纹理和瓶盖高光真实。
材质质感：细纹皮革、亚麻布、浅米石材、磨砂玻璃。
文案内容：主标题「随身补妆」；副标题「轻盈不占空间」。
文字与留白区域：右上 34% 宽、20% 高，标题与副标题左对齐。
文字策略：直接生成短标题与副标题，不写参数。
证据与合规：便携为场景表达，不写尺寸承诺。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要人物、杂乱包内物、手部、价格标签或促销角标。
```

## M05｜主图 5/5｜规格与包装图

- 买家问题：包装里有什么，规格是什么？
- 页面目标：用规格与包装信息降低购买不确定性，作为主图购买的收口。
- 画幅：1:1 / 2K
- 产品占比：瓶身与外盒并列，整体占 45%，正面 3/4，标签可读。
- 文案：主标题「30 ML」；副标题「SPF 10 / PA+++」；标签「包装盒 × 1」。
- 文字策略：只直接生成已核实规格与短标签。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
M05｜主图 5/5｜规格与包装图
买家问题：包装里有什么，规格是什么？
页面目标：用规格与包装信息降低购买不确定性，作为主图购买的收口。

画幅比例：1:1，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身与外盒并列，整体占 45%，正面 3/4，标签可读。
场景环境：深海军蓝丝绒台面与象牙石材窄边，背景克制，无多余道具。
构图方式：产品在中右，左侧留出三条规格信息位；顶部预留平台安全区。
镜头与景别：85mm 镜头，平视，f/8，包装文字清晰，无透视畸变。
光影氛围：左上柔光，右侧窄金边轮廓光，阴影稳定，5000K。
材质质感：磨砂玻璃、金属瓶盖、深蓝纸盒、丝绒、浅米石材。
文案内容：主标题「30 ML」；副标题「SPF 10 / PA+++」；标签「包装盒 × 1」。
文字与留白区域：左侧 34% 宽、30% 高，三个信息块等距排列。
文字策略：只直接生成已核实规格与短标签。
证据与合规：30ml、SPF 10/PA+++、包装盒来自实拍参考。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要虚构赠品、认证、批准文号、检测报告或额外规格。
```

## D01｜详情页 1/7｜首屏承接

- 买家问题：为什么我要继续看这瓶粉底液？
- 页面目标：承接主图，建立底妆定位与第一购买理由。
- 画幅：4:5 / 2K
- 产品占比：瓶身在前、外盒在后，整体占 38%，位于右下三分线。
- 文案：主标题「底妆的底气」；副标题「从容在线」。
- 文字策略：只直接生成标题与副标题。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D01｜详情页 1/7｜首屏承接
买家问题：为什么我要继续看这瓶粉底液？
页面目标：承接主图，建立底妆定位与第一购买理由。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身在前、外盒在后，整体占 38%，位于右下三分线。
场景环境：深海军蓝丝绒背景，一块低矮象牙石台从左侧进入，窄金色轮廓光。
构图方式：产品右下，标题左上，留白 42%；斜线约 8 度。
镜头与景别：70mm 镜头，略低机位，3/4 角度，f/5.6。
光影氛围：左上大面积柔光，右侧极窄金色轮廓光，5000K。
材质质感：磨砂玻璃、拉丝金盖、哑光纸盒、丝绒、象牙石材。
文案内容：主标题「底妆的底气」；副标题「从容在线」。
文字与留白区域：左上 58% 宽、25% 高，标题左对齐。
文字策略：只直接生成标题与副标题。
证据与合规：Double Wear 为包装可见信息；其余为情绪表达。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要复制主图构图，不要额外产品，不要夸张高光。
```

## D02｜详情页 2/7｜痛点放大

- 买家问题：我为什么需要换一种底妆体验？
- 页面目标：用可观察的厚重/薄透材质对照提出需求，不虚构竞品数据。
- 画幅：4:5 / 2K
- 产品占比：瓶身位于画面右侧，占 24%，完整可见；左侧为两块不同质地的材质样本。
- 文案：主标题「底妆，不必将就」；副标题「厚重 · 假面 · 不贴肤」；标签「质地对照」。
- 文字策略：短标题与短标签直出，解释文案后期叠加。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D02｜详情页 2/7｜痛点放大
买家问题：我为什么需要换一种底妆体验？
页面目标：用可观察的厚重/薄透材质对照提出需求，不虚构竞品数据。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身位于画面右侧，占 24%，完整可见；左侧为两块不同质地的材质样本。
场景环境：灰米色纸张背景，左侧一块厚实不透的膏体、右侧一块薄透延展的膏体，均无品牌。
构图方式：上方标题横跨，左右两块质地对照，产品压在右下；不使用人物脸部。
镜头与景别：90mm 镜头，近距俯拍，f/6.3，材质边缘清晰。
光影氛围：左上柔光，右侧弱补光，保持低对比。
材质质感：厚膏体、薄透膏体、灰米纸、磨砂玻璃瓶。
文案内容：主标题「底妆，不必将就」；副标题「厚重 · 假面 · 不贴肤」；标签「质地对照」。
文字与留白区域：顶部 55% 宽、16% 高；左右材质块各留 8% 间隔。
文字策略：短标题与短标签直出，解释文案后期叠加。
证据与合规：痛点语言需品牌确认；不写竞品数据或绝对化结论。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要前后脸对比、不要贬低其他品牌、不要写零瑕疵。
```

## D03｜详情页 3/7｜质地机制

- 买家问题：它为什么会有这种轻盈、柔焦的触感？
- 页面目标：用微距膏体和表面光泽解释质地，而不是只堆功效词。
- 画幅：4:5 / 2K
- 产品占比：瓶身右上，占 18%，轻微虚化；膏体微距占 58%。
- 文案：主标题「细腻质地」；副标题「轻盈延展」；标签「01 / TEXTURE」。
- 文字策略：只直出短标题与标签。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D03｜详情页 3/7｜质地机制
买家问题：它为什么会有这种轻盈、柔焦的触感？
页面目标：用微距膏体和表面光泽解释质地，而不是只堆功效词。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身右上，占 18%，轻微虚化；膏体微距占 58%。
场景环境：浅米磨砂玻璃板与暖象牙背景，膏体在光下形成细致纹理和薄层边缘。
构图方式：斜向涂抹贯穿画面，产品从右上进入，标题在左下纵向排列。
镜头与景别：100mm 微距，45° 侧视，f/5.6，焦点在膏体边缘。
光影氛围：左上擦光，强调表面细腻和薄厚变化，5000K。
材质质感：奶油膏体、磨砂玻璃、瓶身磨砂质感。
文案内容：主标题「细腻质地」；副标题「轻盈延展」；标签「01 / TEXTURE」。
文字与留白区域：左下 28% 宽、22% 高。
文字策略：只直出短标题与标签。
证据与合规：质地与延展为体验描述，待品牌确认。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要拉丝夸张、水滴飞溅、人物皮肤或过度锐化。
```

## D04｜详情页 4/7｜核心利益

- 买家问题：它最值得记住的三个利益是什么？
- 页面目标：用行业标准三段式信息图呈现 Top 3 利益，支持扫读。
- 画幅：4:5 / 2K
- 产品占比：瓶身与外盒在右侧，整体占 30%，完整可见。
- 文案：标题「三个理由」；三项「01 柔焦遮瑕」「02 轻盈贴合」「03 长效持妆」。
- 文字策略：只直出短标题与三项标签，详细解释后期叠加。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D04｜详情页 4/7｜核心利益
买家问题：它最值得记住的三个利益是什么？
页面目标：用行业标准三段式信息图呈现 Top 3 利益，支持扫读。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身与外盒在右侧，整体占 30%，完整可见。
场景环境：暖象牙纸面背景，左侧三条细金线与编号，右侧产品陈列，无多余道具。
构图方式：纵向三段式信息带，编号 01/02/03，文案左对齐，产品在右；与痛点页的左右对照明显不同。
镜头与景别：85mm 镜头，平视，f/8，产品与文字区都清晰。
光影氛围：均匀柔光，阴影很浅，保持信息图干净。
材质质感：哑光纸面、磨砂玻璃、深蓝纸盒、金色细线。
文案内容：标题「三个理由」；三项「01 柔焦遮瑕」「02 轻盈贴合」「03 长效持妆」。
文字与留白区域：左侧 46% 宽，三项等距，每项不超过 10 字。
文字策略：只直出短标题与三项标签，详细解释后期叠加。
证据与合规：柔焦/轻盈为体验语言；长效持妆待品牌证据。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要图标混用、不要检测数字、不要写成绝对功效。
```

## D05｜详情页 5/7｜使用方法

- 买家问题：第一次用应该怎么上妆？
- 页面目标：用三步法减少使用门槛，动作清晰可执行。
- 画幅：4:5 / 2K
- 产品占比：产品位于右上，占 20%；三步动作占主体。
- 文案：主标题「三步上妆」；步骤「01 取适量点涂」「02 由内向外推开」「03 局部叠加」。
- 文字策略：只直出短标题和步骤标签；详细说明后期排版。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D05｜详情页 5/7｜使用方法
买家问题：第一次用应该怎么上妆？
页面目标：用三步法减少使用门槛，动作清晰可执行。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：产品位于右上，占 20%；三步动作占主体。
场景环境：暖灰纸面俯拍，三块浅米/柔粉材质卡从左到右，分别配粉底滴、海绵、薄纱。
构图方式：横向三分步骤，每块有编号和短动作；标题在底部居中。
镜头与景别：90° 正俯拍，50mm，f/8，全部清晰，轻微自然投影。
光影氛围：顶左柔光，低对比，卡片之间不互相遮挡。
材质质感：纸面、粉底滴、海绵、薄纱、磨砂玻璃瓶。
文案内容：主标题「三步上妆」；步骤「01 取适量点涂」「02 由内向外推开」「03 局部叠加」。
文字与留白区域：每块材质卡上方 8-10 字，标题底部占 18% 高。
文字策略：只直出短标题和步骤标签；详细说明后期排版。
证据与合规：通用使用方法，不涉及功效数据。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要手部、人体、复杂箭头、化妆棉堆叠或过密小字。
```

## D06｜详情页 6/7｜场景覆盖

- 买家问题：哪些日常时刻适合用它？
- 页面目标：用三列场景帮助用户判断适配度，不虚构规格或套装。
- 画幅：4:5 / 2K
- 产品占比：同一瓶产品在底部中央，占 28%，包装盒在右侧完整可见。
- 文案：主标题「适合每一种时刻」；三项「日常通勤」「约会补妆」「旅行随行」。
- 文字策略：只直出场景标签与标题。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D06｜详情页 6/7｜场景覆盖
买家问题：哪些日常时刻适合用它？
页面目标：用三列场景帮助用户判断适配度，不虚构规格或套装。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：同一瓶产品在底部中央，占 28%，包装盒在右侧完整可见。
场景环境：三块纵向场景板：浅灰晨光、柔粉梳妆台、深蓝旅行皮革，共享同一色温。
构图方式：三列纵向排列，产品跨越底部中缝，场景标签在每列顶部。
镜头与景别：50mm 镜头，平视，f/6.3，三列透视一致。
光影氛围：统一左上柔光，三列亮度差不超过一档。
材质质感：浅灰玻璃、柔粉布料、深蓝皮革、磨砂玻璃、暖米石材。
文案内容：主标题「适合每一种时刻」；三项「日常通勤」「约会补妆」「旅行随行」。
文字与留白区域：每列顶部 20% 高，标签不超过 6 字；底部产品区保持干净。
文字策略：只直出场景标签与标题。
证据与合规：场景为使用建议，不是功效承诺。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要人物、第二个 SKU、旅行装或虚构赠品。
```

## D07｜详情页 7/7｜规格选择与收束

- 买家问题：规格是什么，我是否要选择它？
- 页面目标：用规格、包装内容和品牌收束完成最终决策，不虚构价格或优惠。
- 画幅：4:5 / 2K
- 产品占比：瓶身与外盒居中偏左，整体占 42%，包装完整，标签清晰。
- 文案：主标题「底妆，从容在线」；规格「30 ML / 1 FL. OZ.」「SPF 10 / PA+++」「包装盒 × 1」。
- 文字策略：只直射已核实规格与短标题，不直出长篇说明。

### 可直接执行的提示词

```text
[CAMPAIGN LOCK — campaign_id: FOUNDATION-CN-INDUSTRY-20261026]
Visual direction: premium beauty editorial + commercial product photography; tactile, calm, believable materials.
Color palette: warm ivory #F3EEE6; deep navy #13213B; antique gold #C9A36A; warm taupe #D8C6B8; pure white #FFFFFF; text #1E1E1E.
Color temperature: warm-neutral 5000K; consistent white balance; no yellow cast, no blue cast.
Typography: headings Noto Serif SC / Songti Light-Regular; body Noto Sans SC / PingFang SC Light; strict hierarchy; direct image text limited to short labels.
Background system: one warm-neutral family, but materials alternate by page: white sweep, ivory paper, pale limestone, deep navy velvet, blush plaster, frosted glass. No repeated pedestal or repeated layout.
Lighting: large soft window light from 10 o'clock, gentle falloff, natural shadows; macro pages may use grazing side light; contrast and color temperature stay consistent.
Camera: commercial photography with 50–100mm lens, f/4–f/8, accurate product geometry, controlled depth of field, no wide-angle distortion.
Layout: industry ecommerce grid with 8% safe margin, one primary focal point, copy-safe zones declared per page; composition and copy position must change across pages.
Product presentation: Image 1 is the exact product reference. Preserve bottle shape, frosted glass, gold cap, navy carton, logo placement, label typography and SPF 10/PA+++ without deformation.
LOCKED across entire set: product identity, color palette, color temperature, type system, material language, light quality, commercial tone.
Allowed variation: listing-image role, camera scale, background material, product percentage, subject arrangement, copy zone, short copy.
[/CAMPAIGN LOCK]

[REFERENCE ROLE] Image 1 = real product photo. Preserve exact bottle and carton; no redraw of logo, label text, SPF mark, proportions or cap.

[PAGE CONTRACT]
D07｜详情页 7/7｜规格选择与收束
买家问题：规格是什么，我是否要选择它？
页面目标：用规格、包装内容和品牌收束完成最终决策，不虚构价格或优惠。

画幅比例：4:5，2K，完整画面，不裁掉标题、产品与关键信息。
产品位置与占比：瓶身与外盒居中偏左，整体占 42%，包装完整，标签清晰。
场景环境：暖象牙背景，右侧垂落海军蓝丝绒，底部一条金色水平线，极简收束。
构图方式：产品中左，右侧三行规格信息，底部一行品牌短句；留白 50% 以上。
镜头与景别：70mm 镜头，平视，f/7.1，商品清晰。
光影氛围：左上大面积柔光，丝绒保留细节，阴影轻。
材质质感：哑光纸盒、磨砂玻璃、海军蓝丝绒、暖象牙背景。
文案内容：主标题「底妆，从容在线」；规格「30 ML / 1 FL. OZ.」「SPF 10 / PA+++」「包装盒 × 1」。
文字与留白区域：右侧 32% 宽，三行规格左对齐；底部中央留一行品牌短句。
文字策略：只直射已核实规格与短标题，不直出长篇说明。
证据与合规：规格来自实拍包装；不写价格、优惠、认证或承诺。
负面限制：不要出现乱码文字、错别字、错误品牌标识、瓶身变形、瓶盖变形、包装结构变化、额外产品、虚构 SKU、虚构认证、夸张功效、人物脸部特写、塑料感、过度磨皮、过饱和、脏乱背景、重复文案、水印、明显 AI 拼接痕迹。
本页额外禁止：不要二维码、价格、促销角标、CTA 按钮、认证徽章或额外赠品。
```
