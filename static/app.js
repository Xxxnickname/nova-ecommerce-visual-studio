const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
  products: [],
  categories: [],
  platforms: [],
  platformId: "shopify",
  sizeId: "",
  models: [],
  modelId: "",
  generationResolution: "2K",
  styleRefs: [],
  styleRefId: "",
  generationMode: "single",
  categoryResult: null,
  classifyMode: "ai",
  uploadedReference: null,
  lastImage: null,
  settings: {},
  activeView: "dashboard",
  agentBusy: false,
  galleryGroups: {},
  viewerItems: [],
  viewerIndex: 0,
};

const viewTitles = {
  dashboard: "运营总览",
  products: "商品中心",
  tasks: "任务中心",
  studio: "生图工坊",
  agent: "Agent 助手",
  settings: "本机设置",
};


function platformById(platformId) {
  return state.platforms.find((item) => item.id === platformId);
}

function platformName(platformId) {
  return platformById(platformId)?.name || (platformId === "taobao_tmall" ? "淘宝 / 天猫" : "Shopify");
}

function platformOptionsHtml(selectedId, disableSoon = false) {
  return state.platforms.map((item) => `<option value="${escapeHtml(item.id)}" ${disableSoon && item.status === "soon" ? "disabled" : ""}>${escapeHtml(item.name)} · ${escapeHtml(item.status_label)}</option>`).join("").replace(`value="${escapeHtml(selectedId)}"`, `value="${escapeHtml(selectedId)}" selected`);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function money(value) {
  return `¥${Number(value || 0).toFixed(2)}`;
}
async function api(path, options = {}) {
  const config = { ...options, headers: { ...(options.headers || {}) } };
  if (config.body && typeof config.body !== "string" && !(config.body instanceof FormData)) {
    config.headers["Content-Type"] = "application/json";
    config.body = JSON.stringify(config.body);
  }
  let response;
  try {
    response = await fetch(path, config);
  } catch (_) {
    throw new Error("连不上本地程序，请确认「电商自动化中台」还在运行");
  }
  let data = {};
  try { data = await response.json(); } catch (_) { /* 无 JSON 响应体 */ }
  if (!response.ok) throw new Error(friendlyError(data, response.status));
  return data;
}

// 把接口错误翻译成中文：后端已经是中文的直接用，否则按状态码给结论
function friendlyError(data, status) {
  const detail = data && (data.message || data.detail);
  const raw = typeof detail === "string" ? detail.trim() : "";
  if (raw && /[\u4e00-\u9fa5]/.test(raw)) return raw;
  if (status === 401 || status === 403) return "没有权限或密钥无效，请到「设置」里检查 API Key";
  if (status === 404) return "这个功能在当前运行的程序里还不存在，请重启程序后再试";
  if (status === 422) return "填写的内容格式不对，请检查必填项";
  if (status === 429) return "请求太频繁或额度不足，请稍等再试";
  if (status >= 500) return "程序内部出错了，请查看程序窗口里的日志";
  return `请求失败（状态码 ${status}）`;
}

// 把生图任务里的英文报错翻译成中文人话
function friendlyJobError(text) {
  const raw = String(text || "").trim();
  if (!raw) return "生成失败，请重试";
  if (/[\u4e00-\u9fa5]/.test(raw) && !/HTTP\s*\d{3}/i.test(raw)) return raw;
  if (/401|403|unauthorized|invalid.?api.?key/i.test(raw)) return "生图密钥无效或已过期，请到「设置」里重新填写 Ark Key";
  if (/402|quota|insufficient|balance/i.test(raw)) return "生图额度不足或欠费，请到火山方舟控制台充值后再试";
  if (/429|too many|rate.?limit/i.test(raw)) return "请求太频繁，请等一分钟再试";
  if (/timeout|timed out/i.test(raw)) return "生成超时，请稍后重试";
  if (/50[0234]/.test(raw)) return "模型服务暂时不可用，请稍后重试";
  return "生成失败，请重试（详细原因可查看程序窗口日志）";
}

let toastTimer = null;
function toast(message, type = "ok") {
  const element = $("#toast");
  element.textContent = message;
  element.className = `toast show ${type === "error" ? "error" : ""}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { element.className = "toast"; }, 4500);
}

function statusTag(status, live = false) {
  let value = String(status || "");
  if (!value) value = live ? "已发布" : "草稿";
  if (live && ["草稿", "未发布", "在售"].includes(value)) value = "已发布";
  value = ({ queued: "排队中", running: "执行中", success: "已完成", failed: "失败" })[value] || value;
  let cls = "tag";
  if (["草稿", "模拟已发布", "待审批", "执行中", "排队中"].includes(value)) cls += " tag-warm";
  else if (["失败", "已驳回", "中断"].includes(value)) cls += " tag-danger";
  else if (["已回滚", "未同步"].includes(value)) cls += " tag-muted";
  return `<span class="${cls}">${escapeHtml(value)}</span>`;
}

function productThumb(product) {
  return product.image1_url
    ? `<img class="thumb" src="${escapeHtml(product.image1_url)}" alt="${escapeHtml(product.name)}">`
    : `<span class="thumb-placeholder">◇</span>`;
}

function emptyState(text) {
  return `<div class="empty">${escapeHtml(text)}</div>`;
}

async function checkHealth() {
  const chip = $("#health-chip");
  try {
    const data = await api("/api/health");
    chip.innerHTML = `<span class="dot"></span>运行中 · ${data.products} 个商品`;
  } catch (_) {
    chip.innerHTML = '<span class="dot" style="background:#9e3f36"></span>连接失败';
  }
}

function navigate(view) {
  if (!viewTitles[view]) view = "dashboard";
  if (location.hash !== `#${view}`) {
    location.hash = view;
    return;
  }
  renderRoute();
}

async function renderRoute() {
  const view = (location.hash || "#dashboard").slice(1) || "dashboard";
  state.activeView = viewTitles[view] ? view : "dashboard";
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === state.activeView));
  $$(".view").forEach((section) => { section.hidden = section.id !== `view-${state.activeView}`; });
  $("#page-title").textContent = viewTitles[state.activeView];
  try {
    if (state.activeView === "dashboard") await loadDashboard();
    if (state.activeView === "products") await loadProducts();
    if (state.activeView === "tasks") await loadTaskCenter();
    if (state.activeView === "studio") await loadStudio();
    if (state.activeView === "agent") initializeAgent();
    if (state.activeView === "settings") await loadSettings();
  } catch (error) {
    toast(error.message, "error");
  }
}

async function loadDashboard() {
  const data = await api("/api/dashboard");
  $("#metrics").innerHTML = [
    ["商品总数", data.metrics.products, "包含商品草稿与已上架商品"],
    ["已上架", data.metrics.live, "Shopify 店铺正在销售"],
    ["待完善草稿", data.metrics.drafts, "补全资料后可一键上架"],
    ["生成图片", data.metrics.images, "已归档的商品视觉资产"],
  ].map(([label, value, note]) => `<article class="metric"><span class="metric-label">${label}</span><strong class="metric-value">${value}</strong><span class="metric-note">${note}</span></article>`).join("");

  $("#dashboard-tasks").innerHTML = data.recent_tasks.length
    ? data.recent_tasks.slice(0, 8).map((task) => `<div class="list-row"><div class="list-main"><strong>${escapeHtml(task.type)} · ${escapeHtml(task.sku)}</strong><small>${escapeHtml(task.message || `${task.old_value || ""} ${task.old_value ? "→" : ""} ${task.new_value || ""}`)}</small></div><div class="list-side">${statusTag(task.status)}<span class="mono">${escapeHtml(task.created_at)}</span></div></div>`).join("")
    : emptyState("还没有操作记录");

  $("#dashboard-images").innerHTML = data.recent_images.filter((image) => image.url).length
    ? data.recent_images.filter((image) => image.url).slice(0, 6).map((image) => `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.sku)} 生成图" loading="lazy">`).join("")
    : '<div class="empty empty-mini">还没有生成图</div>';
}

async function loadProducts(force = false) {
  if (!state.platforms.length) state.platforms = (await api("/api/platforms")).items;
  if (force || !state.products.length) state.products = (await api("/api/products")).items;
  renderProductRows();
}

function renderProductRows() {
  const keyword = ($("#product-search")?.value || "").trim().toLowerCase();
  const filter = $("#product-filter")?.value || "";
  const items = state.products.filter((product) => {
    const matchesText = !keyword || `${product.sku} ${product.name}`.toLowerCase().includes(keyword);
    const matchesFilter = !filter || (filter === "live" ? product.published : !product.published);
    return matchesText && matchesFilter;
  });
  $("#product-rows").innerHTML = items.map((product) => `<tr>
    <td><div class="product-cell">${productThumb(product)}<div><div class="product-name">${escapeHtml(product.name)}</div><div class="product-sku mono">${escapeHtml(product.sku)}</div></div></div></td>
    <td class="price">${Number(product.price) > 0 ? money(product.price) : '<span class="hint">待填写</span>'}</td>
    <td>${escapeHtml(product.stock)}</td>
    <td><div class="platform-status-line">${statusTag(product.platform_status || product.status, product.published)}<span class="hint">${escapeHtml(platformName(product.target_platform))}</span></div></td>
    <td class="mono">${escapeHtml(product.updated_at || "—")}</td>
    <td class="right product-actions">
      <button class="btn btn-small" data-product="${escapeHtml(product.sku)}">编辑</button>
      ${product.published ? "" : `<button class="btn btn-small btn-primary" data-publish-product="${escapeHtml(product.sku)}" data-platform="${escapeHtml(product.target_platform || "shopify")}">${product.target_platform === "taobao_tmall" ? "模拟上架" : "一键上架"}</button>`}
    </td>
  </tr>`).join("");
  $("#products-empty").hidden = items.length > 0;
}

async function publishProduct(sku, button = null, platformId = "shopify") {
  const label = platformName(platformId);
  if (!confirm(`确认把 ${sku} 发布到 ${label} 吗？${platformId === "taobao_tmall" ? "\n这是模拟发布，不会调用真实平台接口。" : ""}`)) return;
  if (button) { button.disabled = true; button.innerHTML = '<span class="spin"></span>上架中'; }
  try {
    const result = await api(`/api/products/${encodeURIComponent(sku)}/publish`, { method: "POST", body: { platform_id: platformId } });
    toast(result.message, result.ok ? "ok" : "error");
    if (result.ok) await loadProducts(true);
  } catch (error) {
    toast(error.message, "error");
  } finally {
    if (button) { button.disabled = false; button.textContent = platformId === "taobao_tmall" ? "模拟上架" : "一键上架"; }
  }
}

async function openProduct(sku) {
  const data = await api(`/api/products/${encodeURIComponent(sku)}`);
  const product = data.product;
  $("#modal-title").textContent = product.name || "商品草稿";
  const image = product.image1_url ? `<img class="modal-image" src="${escapeHtml(product.image1_url)}" alt="${escapeHtml(product.name)}">` : '<div class="modal-image" style="display:grid;place-items:center;font-size:32px;color:#aa9c8a">◇</div>';
  const logHtml = data.logs.length ? data.logs.map((log) => `<div class="list-row"><div class="list-main"><strong>${escapeHtml(log.step)}</strong><small>${escapeHtml(log.detail)}</small></div><span class="mono">${escapeHtml(log.created_at)}</span></div>`).join("") : '<p class="hint">暂无操作记录</p>';
  const galleryHtml = data.images?.length ? `<div class="settings-section"><h4>商品图片 ${data.images.length} 张</h4><div class="mini-gallery">${data.images.map((image) => image.url ? `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.role || "")}" loading="lazy">` : "").join("")}</div></div>` : "";
  $("#modal-body").innerHTML = `<div class="modal-product">${image}<div>
    <div class="product-sku mono">${escapeHtml(product.sku)}</div>
    <p class="hint">${escapeHtml(platformName(product.target_platform))} · ${escapeHtml(product.platform_status || (product.published ? "已发布" : "未发布"))} · 更新于 ${escapeHtml(product.updated_at)}</p>
    <form id="product-form">
      <div class="form-grid"><label>SKU<input name="sku" value="${escapeHtml(product.sku)}"></label><label>商品名称<input name="name" value="${escapeHtml(product.name)}"></label></div>
      <div class="form-grid"><label>售价<input name="price" type="number" min="0" step="0.01" value="${escapeHtml(product.price)}"></label><label>成本价<input name="cost" type="number" min="0" step="0.01" value="${escapeHtml(product.cost)}"></label></div>
      <div class="form-grid"><label>库存<input name="stock" type="number" step="1" value="${escapeHtml(product.stock)}"></label><label>划线价<input name="compare_at" type="number" step="0.01" value="${escapeHtml(product.compare_at)}"></label></div>
      <div class="form-grid"><label>重量 kg<input name="weight_kg" type="number" step="0.01" value="${escapeHtml(product.weight_kg)}"></label><label>商品类型<input name="product_type" value="${escapeHtml(product.product_type)}"></label></div>
      <label>发布平台<select id="product-platform" name="target_platform">${platformOptionsHtml(product.target_platform || "shopify", true)}</select></label>
      <div class="form-grid"><label>Packed L<input name="packed_length" type="number" step="0.1" value="${escapeHtml(product.packed_length)}"></label><label>Packed W<input name="packed_width" type="number" step="0.1" value="${escapeHtml(product.packed_width)}"></label></div>
      <div class="form-grid"><label>Packed H<input name="packed_height" type="number" step="0.1" value="${escapeHtml(product.packed_height)}"></label><label>Shopify 类目 GID<input name="category" value="${escapeHtml(product.category)}" placeholder="可选，例如 gid://shopify/TaxonomyCategory/..."></label></div>
      <label>标签<input name="tags" value="${escapeHtml(product.tags)}" placeholder="逗号分隔"></label>
      <label>商品描述<textarea name="description" rows="5">${escapeHtml(product.description)}</textarea></label>
      <button class="btn" type="submit">保存商品资料</button>
    </form></div></div>
    <div class="platform-note" id="modal-platform-note">${escapeHtml(platformById(product.target_platform)?.note || "")}</div>
    <div class="modal-actions"><button class="btn btn-primary" id="modal-publish">${product.target_platform === "taobao_tmall" ? "模拟发布到淘宝/天猫" : "一键上架 Shopify"}</button><button class="btn btn-quiet" id="modal-close-secondary">关闭</button></div>
    ${galleryHtml}
    <div class="settings-section"><h4>最近操作</h4>${logHtml}</div>`;
  $("#modal").hidden = false;

  $("#product-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      const result = await api(`/api/products/${encodeURIComponent(sku)}`, { method: "PATCH", body: payload });
      toast("商品资料已保存");
      await loadProducts(true);
      $("#modal").hidden = true;
      await openProduct(result.product.sku);
    } catch (error) { toast(error.message, "error"); }
  });
  $("#product-platform").addEventListener("change", (event) => {
    const selected = event.target.value;
    const info = platformById(selected);
    $("#modal-platform-note").textContent = info?.note || "";
    $("#modal-publish").textContent = selected === "taobao_tmall" ? "模拟发布到淘宝/天猫" : "一键上架 Shopify";
  });
  $("#modal-publish").addEventListener("click", async (event) => {
    const button = event.currentTarget;
    const selectedPlatform = $("#product-platform").value;
    button.disabled = true;
    button.innerHTML = '<span class="spin"></span>发布中';
    try {
      const result = await api(`/api/products/${encodeURIComponent(sku)}/publish`, { method: "POST", body: { platform_id: selectedPlatform } });
      toast(result.message, result.ok ? "ok" : "error");
      if (result.ok) { await loadProducts(true); $("#modal").hidden = true; }
    } catch (error) { toast(error.message, "error"); }
    finally { button.disabled = false; button.textContent = selectedPlatform === "taobao_tmall" ? "模拟发布到淘宝/天猫" : "一键上架 Shopify"; }
  });
  $("#modal-close-secondary").addEventListener("click", closeModal);
}

function closeModal() { $("#modal").hidden = true; }

async function loadStudio() {
  if (!state.categories.length) state.categories = (await api("/api/categories")).items;
  if (!state.platforms.length) state.platforms = (await api("/api/platforms")).items;
  if (!state.styleRefs.length) state.styleRefs = (await api("/api/style-refs")).items;
  renderStyleRefs();
  if (!state.models.length) {
    const modelData = await api("/api/models");
    state.models = modelData.items;
    state.modelId = modelData.configured_model || modelData.items[0]?.id || "";
  }
  populateModelOptions();
  const platformSelect = $("#studio-platform");
  platformSelect.innerHTML = platformOptionsHtml(state.platformId);
  state.platformId = platformSelect.value || "shopify";
  populateSizeOptions();
  updateGenerationMode(state.generationMode, false);
  updatePlatformNote();
  const manual = $("#manual-category");
  if (manual.options.length <= 1) {
    manual.innerHTML = '<option value="">请选择产品类型</option>' + state.categories.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${escapeHtml(item.description || "")}</option>`).join("");
  }
  switchClassifyMode(state.classifyMode, false);
  if (state.categoryResult) applyCategory(state.categoryResult);
  else resetCategory();
  updateReference(false);
  await loadStudioGallery();
}


function currentPlatform() {
  return platformById(state.platformId) || state.platforms[0];
}




function renderStyleRefs() {
  const grid = $("#style-ref-grid");
  if (!grid) return;
  grid.innerHTML = `<button type="button" class="style-ref-none ${state.styleRefId ? "" : "active"}" data-style-ref="">不使用</button>` + state.styleRefs.map((item) => `<button type="button" class="style-ref-option ${state.styleRefId === item.id ? "active" : ""}" data-style-ref="${escapeHtml(item.id)}" title="${escapeHtml(item.description)}"><img src="${escapeHtml(item.url)}" alt="${escapeHtml(item.name)}" loading="lazy"><span>${escapeHtml(item.name)}</span></button>`).join("");
}

function populateModelOptions() {
  const select = $("#studio-model");
  if (!select) return;
  const allowed = state.models.some((item) => item.id === state.modelId);
  if (!allowed) state.modelId = state.models[0]?.id || "";
  select.innerHTML = state.models.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.name)} · ${escapeHtml(item.tier)}</option>`).join("");
  select.value = state.modelId;
  populateResolutionOptions();
}

function currentModel() {
  return state.models.find((item) => item.id === state.modelId) || state.models[0];
}

function populateResolutionOptions() {
  const select = $("#studio-resolution");
  const model = currentModel();
  if (!select || !model) return;
  const options = model.resolutions || ["1K", "2K", "4K"];
  if (!options.includes(state.generationResolution)) state.generationResolution = options.includes("2K") ? "2K" : options[0];
  select.innerHTML = options.map((item) => `<option value="${item}">${item}</option>`).join("");
  select.value = state.generationResolution;
}

function populateSizeOptions() {
  const platform = currentPlatform();
  const select = $("#studio-size");
  if (!platform || !select) return;
  const options = platform.size_options || [{ id: "default", label: `${platform.image_size?.[0] || 2048}×${platform.image_size?.[1] || 2048}`, width: platform.image_size?.[0] || 2048, height: platform.image_size?.[1] || 2048 }];
  const allowed = options.some((item) => item.id === state.sizeId);
  select.innerHTML = options.map((item) => `<option value="${escapeHtml(item.id)}">${escapeHtml(item.label)} · ${item.width}×${item.height}</option>`).join("");
  select.value = allowed ? state.sizeId : (platform.default_size_id || options[0].id);
  state.sizeId = select.value;
}

function currentSize() {
  const platform = currentPlatform();
  return (platform?.size_options || []).find((item) => item.id === state.sizeId) || (platform?.size_options || [])[0];
}

function platformReady() {
  return currentPlatform()?.status !== "soon";
}

function updatePlatformNote() {
  const platform = currentPlatform();
  const note = $("#platform-note");
  if (!platform) return;
  note.textContent = `${platform.name}（${platform.status_label}）：${platform.note || ""}`;
  note.classList.toggle("soon", platform.status === "soon");
  updateStudioButtons();
}


function updateGenerationMode(mode, resetPreview = true) {
  state.generationMode = mode === "suite" ? "suite" : "single";
  $$("#generation-mode-switch .mode-btn").forEach((button) => button.classList.toggle("active", button.dataset.generationMode === state.generationMode));
  $("#single-prompt-block").hidden = state.generationMode === "suite";
  $("#copy-prompt-btn").hidden = state.generationMode === "suite";
  $("#suite-note").hidden = state.generationMode !== "suite";
  $("#suite-plan-block").hidden = state.generationMode !== "suite";
  $("#generate-btn").textContent = state.generationMode === "suite" ? "生成 12 张套图" : "生成商品图";
  $("#save-draft-btn").textContent = state.generationMode === "suite" ? "保存整套为商品草稿" : "保存为商品草稿";
  if (resetPreview) {
    state.lastImage = null;
    $("#preview-actions").hidden = true;
    $("#image-preview").innerHTML = '<div class="preview-placeholder"><span>✦</span><p>新图会出现在这里</p></div>';
    $("#preview-meta").textContent = "等待生成";
  }
  updateStudioButtons();
}

function switchClassifyMode(mode, reset = true) {
  state.classifyMode = mode === "manual" ? "manual" : "ai";
  $$('.mode-btn[data-mode]').forEach((button) => button.classList.toggle("active", button.dataset.mode === state.classifyMode));
  $("#ai-classify-panel").hidden = state.classifyMode !== "ai";
  $("#manual-classify-panel").hidden = state.classifyMode !== "manual";
  if (reset) {
    resetCategory();
    if (state.classifyMode === "ai") $("#classify-status").textContent = "描述商品，AI 会自动匹配类型和视觉方案";
    else $("#classify-status").textContent = "选择类型后，自动加载对应模板、场景和风格";
  }
}

function resetCategory() {
  state.categoryResult = null;
  $("#category-result").hidden = true;
  $("#studio-template").innerHTML = '<option value="">先确定商品类型</option>';
  $("#studio-template").disabled = true;
  $("#studio-scene").innerHTML = '<option value="">先确定商品类型</option>';
  $("#studio-scene").disabled = true;
  $("#studio-style").innerHTML = '<option value="">先确定商品类型</option>';
  $("#studio-style").disabled = true;
  $("#custom-scene-label").hidden = true;
  $("#upload-name").textContent = "请先确定商品类型";
  $("#prompt-source").textContent = "先确定商品类型";
  $("#suite-plan-list").innerHTML = "";
  updateStudioButtons();
}

const supplementHints = {
  beauty: { selling: "例如：水润不拔干、显白、持妆、清透", must: "例如：管身颜色、logo 位置、包装文字、瓶体比例", props: "例如：大理石台面、花瓣、水珠、香槟色台座", avoid: "例如：人物、手模、额外产品、虚构文字" },
  home_textile: { selling: "例如：加厚、柔软、亲肤、包边工艺", must: "例如：颜色、绒面纹理、包边、尺寸比例", props: "例如：浅灰沙发、木地板、窗边自然光", avoid: "例如：人物、额外家具、商品变形" },
  apparel: { selling: "例如：版型、面料、垂感、保暖", must: "例如：版型、缝线、五金、颜色", props: "例如：极简试衣间、城市街景", avoid: "例如：人物正脸、额外服装、版型改变" },
  food: { selling: "例如：新鲜、酥脆、浓郁、礼赠", must: "例如：包装形状、标签、内容物、份量", props: "例如：木质餐桌、食材、餐具", avoid: "例如：人物、虚构食材、包装文字变化" },
  electronics: { selling: "例如：轻薄、续航、专业音质", must: "例如：机身结构、接口、屏幕、logo 位置", props: "例如：深色科技台面、办公桌", avoid: "例如：人物、多余线材、虚构按钮" },
  jewelry: { selling: "例如：闪耀、镶嵌工艺、轻奢", must: "例如：金属颜色、宝石切面、链条形态", props: "例如：丝绒台面、礼盒、缎带", avoid: "例如：人物、额外首饰、宝石变形" },
  generic: { selling: "例如：核心卖点、材质、使用场景", must: "例如：颜色、结构、logo、包装文字", props: "例如：台面、背景、陪衬物", avoid: "例如：人物、额外物体、虚构文字" },
};

function applyCategory(result) {
  state.categoryResult = result;
  $("#plan-product-type").value = result.category.name;  // 分类结果同步给提示词生成器，避免重复选择
  $("#category-result").hidden = false;
  $("#category-name").textContent = `识别为：${result.category.name} · ${Math.round(Number(result.confidence || 1) * 100)}%`;
  $("#category-reason").textContent = result.reason || "";
  $("#classify-status").textContent = result.source === "deepseek" ? "DeepSeek 已完成识别" : result.source === "manual" ? "已手动选择类型" : "已按关键词匹配类型";
  $("#studio-template").innerHTML = result.templates.map((template) => `<option value="${escapeHtml(template.id)}">${escapeHtml(template.name)} · ${escapeHtml(template.description || "")}</option>`).join("");
  if (result.default_template_id) $("#studio-template").value = result.default_template_id;
  $("#studio-template").disabled = false;
  $("#studio-scene").innerHTML = '<option value="按模板默认">按模板默认场景</option>' + result.scenes.map((scene) => `<option value="${escapeHtml(scene)}">${escapeHtml(scene)}</option>`).join("") + '<option value="自定义场景">自定义场景</option>';
  $("#studio-scene").disabled = false;
  $("#studio-style").innerHTML = result.styles.map((style) => `<option value="${escapeHtml(style)}">${escapeHtml(style)}</option>`).join("");
  $("#studio-style").disabled = false;
  $("#upload-name").textContent = "类型已确定，请上传产品实拍图";
  $("#prompt-source").textContent = `${result.category.name}方案已加载，可生成提示词`;
  const hints = supplementHints[result.category.id] || supplementHints.generic;
  $("#studio-must-keep").placeholder = hints.must;
  $("#studio-extra-props").placeholder = hints.props;
  $("#studio-avoid").placeholder = hints.avoid;
  updateStudioButtons();
}

function updateStudioButtons() {
  const ready = platformReady() && Boolean(state.modelId) && Boolean(state.generationResolution);
  $("#prompt-btn").disabled = !(state.categoryResult && ready && state.sizeId);
  $("#suite-plan-btn").disabled = !(state.categoryResult && ready);
  $("#generate-btn").disabled = !(state.categoryResult && state.uploadedReference && ready && state.sizeId);
}

async function classifyProduct() {
  const description = $("#studio-product-desc").value.trim();
  if (!description) return toast("请先填写商品具体信息", "error");
  const button = $("#classify-btn");
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>AI 识别中';
  $("#classify-status").textContent = "正在判断商品类型并匹配视觉方案…";
  try {
    const result = await api("/api/classify-product", { method: "POST", body: { description } });
    if (!result.ok) throw new Error(result.message || "识别失败");
    applyCategory(result);
    toast(`已识别为 ${result.category.name}`);
  } catch (error) {
    toast(error.message, "error");
    resetCategory();
  } finally { button.disabled = false; button.textContent = "AI 识别商品类型"; }
}

async function chooseManualCategory(categoryId) {
  if (!categoryId) return resetCategory();
  try {
    const result = await api(`/api/categories/${encodeURIComponent(categoryId)}/options`);
    applyCategory(result);
    toast(`已选择 ${result.category.name}`);
  } catch (error) { toast(error.message, "error"); }
}

function updateReference(showToast = true) {
  const target = $("#reference-thumb");
  const uploaded = state.uploadedReference;
  target.innerHTML = uploaded ? `<img src="${escapeHtml(uploaded.url)}" alt="产品实拍图">` : "待上传";
  $("#upload-name").textContent = uploaded ? `${uploaded.name} · ${uploaded.width}×${uploaded.height}` : "请上传产品实拍图";
  $("#upload-title").textContent = uploaded ? "实拍图已上传，可更换" : "上传一张产品实拍图";
  if (showToast && uploaded) toast("实拍图已上传");
}

async function uploadReference(file) {
  if (!file) return;
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  const zone = $("#upload-zone");
  zone.classList.add("uploading");
  $("#upload-title").textContent = "正在上传实拍图…";
  try {
    const form = new FormData();
    form.append("file", file);
    const result = await api(`/api/upload-reference?category_id=${encodeURIComponent(state.categoryResult.category.id)}`, { method: "POST", body: form });
    state.uploadedReference = result;
    updateReference(true);
    updateStudioButtons();
    updateStudioButtons();
  } catch (error) {
    toast(error.message, "error");
    $("#upload-title").textContent = "上传失败，请重试";
  } finally {
    zone.classList.remove("uploading");
    $("#upload-input").value = "";
  }
}

function selectedScene() {
  const value = $("#studio-scene").value;
  return value === "自定义场景" ? $("#studio-scene-custom").value.trim() : value;
}
// 安全取值：元素不存在时返回空串，避免 "Cannot read properties of null"
function fieldValue(selector) {
  const element = $(selector);
  return element && typeof element.value === "string" ? element.value.trim() : "";
}

function collectExtras() {
  return {
    brand_name: fieldValue("#studio-brand-name"),
    selling_points: fieldValue("#plan-selling-points"),   // 卖点已合并到方案输入
    must_keep: fieldValue("#studio-must-keep"),
    props: fieldValue("#studio-extra-props"),
    avoid: fieldValue("#studio-avoid"),
  };
}

async function generatePrompt() {
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  const button = $("#prompt-btn");
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>DeepSeek 思考中';
  try {
    const result = await api("/api/prompt", {
      method: "POST",
      body: {
        platform_id: state.platformId,
        size_id: state.sizeId,
        style_ref_id: state.styleRefId,
        model_id: state.modelId,
        generation_resolution: state.generationResolution,
        template_id: $("#studio-template").value,
        scene: selectedScene(),
        style: $("#studio-style").value,
        product_description: $("#studio-product-desc").value.trim(),
        category_id: state.categoryResult.category.id,
        extras: collectExtras(),
        use_ai: true,
      },
    });
    $("#studio-prompt").value = result.prompt;
    $("#prompt-source").textContent = result.source === "deepseek" ? "DeepSeek 已生成 9 层提示词" : "模板提示词";
    if (result.warning) toast(result.warning, "error");
    else toast("提示词已生成");
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; button.textContent = "生成 9 层提示词"; }
}

/* ==== 提示词生成器：左侧输入，右侧 12 页主从视图 ==== */
const PLAN_SAMPLE = {
  product_type: "粉底液",
  audience: "25–35 岁通勤女性",
  style: "暖象牙色、克制高级、柔和晨光",
  selling_points: "柔焦遮瑕、轻盈不闷、长效持妆",
  reference_note: "象牙石台、深蓝丝绒背景、窄金色轮廓光",
};

// 当前 12 页方案与选中页
let planPages = [];
let planActiveCode = "";
let planIndex = 0;
let planPrompts = {};

// 12 页方案 → Seedream 套图角色的映射（套图接口按 role id 取提示词）
const PLAN_ROLE_MAP = {
  M01: "01_white_main", M02: "02_hero_angle", M03: "06_texture", M04: "04_scene_a", M05: "03_packaging",
  D01: "08_benefits_1", D02: "09_benefits_2", D03: "07_craft", D04: "10_size_spec", D05: "11_in_box",
  D06: "05_scene_b", D07: "12_variants",
};

// 把 12 页提示词整理成套图接口要的 {roleId: prompt}
function buildPlanPrompts(pages) {
  const out = {};
  (pages || []).forEach((page) => {
    const role = PLAN_ROLE_MAP[page.code];
    if (role && page.prompt_full) out[role] = page.prompt_full;
  });
  return out;
}

// 复制文本：优先 Clipboard API，失败时退回 execCommand（本地 127.0.0.1 下常被浏览器拒绝）
async function copyPlanText(text, label) {
  const value = String(text || "").trim();
  if (!value) return toast("没有可复制的内容", "error");
  try {
    await navigator.clipboard.writeText(value);
    return toast(label || "已复制");
  } catch (_) { /* 继续走兜底方案 */ }
  const area = document.createElement("textarea");
  area.value = value;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.top = "-1000px";
  document.body.appendChild(area);
  area.select();
  try {
    document.execCommand("copy");
    toast(label || "已复制");
  } catch (error) {
    toast("复制失败，请手动选择文本", "error");
  } finally {
    document.body.removeChild(area);
  }
}

// 一页的文案拼成纯文本
function planCopyText(page) {
  const lines = [];
  if (page.copy_headline) lines.push(`主标题：${page.copy_headline}`);
  if (page.copy_sub) lines.push(`副标题：${page.copy_sub}`);
  (page.copy_points || []).forEach((point, index) => lines.push(`要点${index + 1}：${point}`));
  if ((page.copy_tags || []).length) lines.push(`标签：${page.copy_tags.join("、")}`);
  return lines.join("\\n");
}

// 一页的非提示词信息，拼成纯文本，方便贴到文档或聊天里讨论
function planModuleText(page) {
  const elements = (page.scene_elements || []).join("、");
  return [
    `${page.code} · ${page.role}（${page.ratio}）`,
    `画面目标：${page.objective}`,
    page.buyer_question ? `买家疑问：${page.buyer_question}` : "",
    `构图建议：${page.composition}`,
    `产品占比：${page.product_share}`,
    `场景元素：${elements}`,
    `光影氛围：${page.lighting_mood}`,
    page.copy_headline ? `文案：${page.copy_headline}｜${page.copy_sub || ""}` : "",
    page.copy ? `文案：${page.copy}` : "",
  ].filter(Boolean).join("\n");
}

// 左侧 12 页导航项
function planNavHtml(page) {
  return `<button class="plan-page-item" type="button" data-plan-page="${escapeHtml(page.code)}">
    <span class="plan-page-code">${escapeHtml(page.code)}</span>
    <span class="plan-page-role">${escapeHtml(page.role)}</span>
    <span class="plan-page-ratio">${escapeHtml(page.ratio)}</span>
  </button>`;
}

// 右侧选中页详情
function planDetailHtml(page) {
  const code = escapeHtml(page.code);
  const elements = (page.scene_elements || []).map((item) => escapeHtml(item)).join(" · ");
  const buyer = page.buyer_question ? ` · ${escapeHtml(page.buyer_question)}` : "";
  const points = (page.copy_points || []).filter(Boolean);
  const tags = (page.copy_tags || []).filter(Boolean);
  const hasCopy = Boolean(page.copy_headline || page.copy_sub || points.length || tags.length);
  const copyHtml = hasCopy
    ? `<div class="plan-copy-row"><span>主标题</span><strong>${escapeHtml(page.copy_headline || "—")}</strong></div>
       <div class="plan-copy-row"><span>副标题</span><p>${escapeHtml(page.copy_sub || "—")}</p></div>
       ${points.length ? `<div class="plan-copy-row"><span>利益点</span><ol>${points.map((point) => `<li>${escapeHtml(point)}</li>`).join("")}</ol></div>` : ""}
       ${tags.length ? `<div class="plan-copy-row"><span>标签</span><p>${tags.map((tag) => escapeHtml(tag)).join(" · ")}</p></div>` : ""}`
    : `<p class="hint">本页不生成广告文字，只保留包装自带文字。</p>`;
  return `
    <header class="plan-detail-head">
      <div><strong>${escapeHtml(page.code)} · ${escapeHtml(page.role)}</strong><small>${escapeHtml(page.slot || "")}${buyer}</small></div>
      <div class="inline-actions">
        <button class="btn btn-small" type="button" data-plan-copy="${code}">复制本页信息</button>
        <button class="btn btn-small btn-primary" type="button" data-plan-copy-prompt="${code}">复制提示词</button>
      </div>
    </header>
    <div class="plan-facts">
      <div class="plan-fact"><span>画面目标</span><p>${escapeHtml(page.objective)}</p></div>
      <div class="plan-fact"><span>构图建议</span><p>${escapeHtml(page.composition)}</p></div>
      <div class="plan-fact"><span>产品占比</span><p class="plan-strong">${escapeHtml(page.product_share)}</p></div>
      <div class="plan-fact"><span>光影氛围</span><p>${escapeHtml(page.lighting_mood)}</p></div>
      <div class="plan-fact plan-fact-wide"><span>场景元素</span><p>${elements}</p></div>
    </div>
    <div class="plan-prompt">
      <div class="plan-prompt-head">
        <span>AI 生图提示词 · 可直接复制</span>
        <button class="btn btn-small" type="button" data-plan-copy-short="${code}">复制精简版</button>
      </div>
      <pre>${escapeHtml(page.prompt_full)}</pre>
    </div>`;
}

// 翻页渲染：一次只显示一页，页码 + 标题 + 上一页/下一页
function renderPlanPage() {
  const page = planPages[planIndex];
  $("#plan-page-no").textContent = `${planPages.length ? planIndex + 1 : 0} / ${planPages.length}`;
  $("#plan-page-no").textContent = `${planPages.length ? planIndex + 1 : 0} / ${planPages.length}`;
  $("#plan-detail").innerHTML = page ? planDetailHtml(page) : "";
  $("#plan-prev").disabled = planIndex <= 0;
  $("#plan-next").disabled = planIndex >= planPages.length - 1;
}

// 按 code 跳到某一页（保留给未来深链用）
function selectPlanPage(code) {
  const index = planPages.findIndex((item) => item.code === code);
  if (index >= 0) { planIndex = index; renderPlanPage(); }
}

// 渲染整份方案：左侧导航 + 默认选中第一页
function renderPlan(result) {
  planPages = result.pages || [];
  $("#plan-empty").hidden = planPages.length > 0;
  $("#plan-workbench").hidden = planPages.length === 0;
  $("#plan-copy-all").hidden = planPages.length === 0;
  planIndex = 0;
  renderPlanPage();
}
// 把产品类型回填到出图参数，避免同一份信息让用户填两遍
function syncPlanToStudio() {
  const type = ($("#plan-product-type").value || "").trim();
  if (type && !$("#studio-product-desc").value.trim()) $("#studio-product-desc").value = type;
}

function fillPlanSample() {
  $("#plan-product-type").value = PLAN_SAMPLE.product_type;
  $("#plan-audience").value = PLAN_SAMPLE.audience;
  $("#plan-style").value = PLAN_SAMPLE.style;
  $("#plan-selling-points").value = PLAN_SAMPLE.selling_points;
  $("#plan-reference-note").value = PLAN_SAMPLE.reference_note;
  $("#plan-ratio-mode").value = "industry";
  $("#plan-status").textContent = "已填入示例，点「生成方案」即可";
}
async function generatePlan() {
  // 产品类型优先取分类结果，其次取方案输入，避免两个入口各填一遍
  const productType = ($("#plan-product-type").value || state.categoryResult?.category?.name || "").trim();
  if (!productType) return toast("请先确定商品类型（AI 识别或手动选择）", "error");
  const button = $("#plan-generate-btn");
  const status = $("#plan-status");
  status.style.color = "";
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>生成中';
  status.textContent = "正在展开 12 页…";
  try {
    const result = await api("/api/prompt-plan", {
      method: "POST",
      body: {
        product_type: productType,
        audience: $("#plan-audience").value.trim(),
        style: $("#plan-style").value.trim(),
        selling_points: $("#plan-selling-points").value.trim(),
        reference_note: $("#plan-reference-note").value.trim(),
        reference_path: state.uploadedReference?.path || "",
        use_vision: $("#plan-use-vision") ? $("#plan-use-vision").checked : true,
        ratio_mode: $("#plan-ratio-mode").value,
        use_ai: true,
      },
    });
    renderPlan(result);
    syncPlanToStudio();
    planPrompts = buildPlanPrompts(planPages);
    $("#plan-run-single").disabled = planPages.length === 0;
    $("#plan-run-suite").disabled = planPages.length === 0 || !state.uploadedReference;
    $("#plan-run-meta").textContent = `${planPages.length} 页提示词已就绪 · 参考图${state.uploadedReference ? "已上传" : "未上传"}`;
    status.textContent = result.source === "deepseek-vision" ? "已看图细化 12 页" : result.source === "deepseek" ? "DeepSeek 已细化 12 页" : "模板生成 12 页";
    $("#plan-result-meta").textContent = `${result.pages.length} 页 · ${result.meta.main_images} 主图 / ${result.meta.detail_pages} 详情页 · ${result.source === "deepseek-vision" ? "看图生成" : result.source === "deepseek" ? "文字生成" : "模板生成"}`;
    if (result.warning) toast(result.warning, "error"); else toast("12 页方案已生成");
  } catch (error) {
    const message = (error && error.message) ? error.message : "生成方案失败，请查看服务端日志";
    status.textContent = `失败：${message}`;
    status.style.color = "var(--danger)";
    console.error("[prompt-plan]", error);
    toast(message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "生成方案";
  }
}

async function generateImage() {
  if (state.generationMode === "suite") return generateSuite();
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  if (!state.uploadedReference) return toast("请先上传产品实拍图", "error");
  const button = $("#generate-btn");
  const prompt = $("#studio-prompt").value.trim();
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>Seedream 出图中';
  const status = $("#job-status");
  status.hidden = false;
  status.className = "job-status";
  status.textContent = "任务已提交，通常需要 30–90 秒。";
  try {
    const created = await api("/api/generate", {
      method: "POST",
      body: {
        template_id: $("#studio-template").value,
        scene: selectedScene(),
        style: $("#studio-style").value,
        product_description: $("#studio-product-desc").value.trim(),
        category_id: state.categoryResult.category.id,
        extras: collectExtras(),
        prompt,
        prompt_source: prompt ? "manual" : "template",
        use_reference: true,
        reference_path: state.uploadedReference.path,
      },
    });
    for (let attempt = 0; attempt < 180; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const job = await api(`/api/jobs/${created.job_id}`);
      if (job.status === "success") {
        state.lastImage = job.result;
        $("#image-preview").innerHTML = `<img src="${escapeHtml(job.result.url)}?t=${Date.now()}" alt="生成结果">`;
        $("#preview-meta").textContent = `${job.result.width}×${job.result.height} · ${job.result.seconds}s`;
        $("#preview-actions").hidden = false;
        $("#draft-status").hidden = true;
        status.className = "job-status";
        status.textContent = `出图完成：${job.result.path}`;
        await loadStudioGallery();
        toast("商品图生成完成，可保存为商品草稿");
        return;
      }
      if (job.status === "failed") throw new Error(friendlyJobError(job.error));
      status.textContent = `Seedream 正在生成… ${(attempt + 1) * 2}s`;
    }
    throw new Error("等待超时，请稍后到暂存区查看");
  } catch (error) {
    status.className = "job-status failed";
    status.textContent = error.message;
    toast(error.message, "error");
  } finally { button.disabled = false; button.textContent = "生成商品图"; }
}

async function loadSuitePlan() {
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  const button = $("#suite-plan-btn");
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>生成提示词';
  try {
    const result = await api("/api/suite-plan", {
      method: "POST",
      body: {
        category_id: state.categoryResult.category.id,
        template_id: $("#studio-template").value,
        scene: selectedScene(), style: $("#studio-style").value,
        product_description: $("#studio-product-desc").value.trim(), extras: collectExtras(),
      },
    });
    $("#suite-plan-list").innerHTML = result.items.map((item, index) => `<details class="suite-prompt-card" ${index === 0 ? "open" : ""}><summary>${escapeHtml(item.role)} · ${escapeHtml(item.name)} · ${item.kind === "layout" ? "背景图提示词（不写文字）" : "商品图提示词"}</summary><textarea rows="${item.kind === "layout" ? 7 : 6}" data-suite-prompt="${escapeHtml(item.role)}">${escapeHtml(item.prompt)}</textarea>${item.note ? `<p class="hint">${escapeHtml(item.note)}</p>` : ""}</details>`).join("");
    toast("套图提示词已生成，可逐张修改");
  } catch (error) {
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "重新生成套图提示词";
  }
}

async function generateSuite() {
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  if (!state.uploadedReference) return toast("请先上传产品实拍图", "error");
  const button = $("#generate-btn");
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>套图生成中';
  const status = $("#job-status");
  status.hidden = false;
  status.className = "job-status";
  status.textContent = "套图任务已提交：7 张照片型素材 + 5 张信息版式图，约 6–12 分钟。";
  try {
    const created = await api("/api/generate-suite", {
      method: "POST",
      body: {
        platform_id: state.platformId, size_id: state.sizeId,
        style_ref_id: state.styleRefId,
        model_id: state.modelId, generation_resolution: state.generationResolution,
        template_id: $("#studio-template").value, scene: selectedScene(), style: $("#studio-style").value,
        product_description: $("#studio-product-desc").value.trim(), category_id: state.categoryResult.category.id,
        extras: collectExtras(), reference_path: state.uploadedReference.path,
        prompts: { ...Object.fromEntries([...document.querySelectorAll('[data-suite-prompt]')].map((el) => [el.dataset.suitePrompt, el.value.trim()]).filter(([, value]) => value)), ...planPrompts },
      },
    });
    for (let attempt = 0; attempt < 900; attempt += 1) {
      await new Promise((resolve) => setTimeout(resolve, 2000));
      const job = await api(`/api/jobs/${created.job_id}`);
      const progress = job.result?.progress || 0;
      const total = job.result?.total || 12;
      if (job.status === "running" || job.status === "queued") {
        status.textContent = `套图生成中 ${progress}/${total} · 预计还需 ${Math.max(0, Math.ceil((total - progress) * 1.2))} 分钟`;
        if (progress > 0) {
          await loadStudioGallery();
          const first = job.result?.items?.[0];
          if (first && !state.lastImage) {
            state.lastImage = first;
            $("#image-preview").innerHTML = `<img src="${escapeHtml(first.url)}?t=${Date.now()}" alt="套图主图">`;
            $("#preview-meta").textContent = `${first.width}×${first.height} · ${total} 张套图`;
            $("#preview-actions").hidden = false;
          }
        }
      }
      if (job.status === "success") {
        const first = job.result.items[0];
        state.lastImage = first;
        $("#image-preview").innerHTML = `<img src="${escapeHtml(first.url)}?t=${Date.now()}" alt="套图主图">`;
        $("#preview-meta").textContent = `${first.width}×${first.height} · 12 张套图`;
        $("#preview-actions").hidden = false;
        status.className = "job-status";
        status.textContent = "12 张套图已生成，可保存为商品草稿。";
        await loadStudioGallery();
        toast("12 张套图生成完成");
        return;
      }
      if (job.status === "failed") throw new Error(friendlyJobError(job.error || job.result?.error));
    }
    throw new Error("套图等待超时，请稍后到暂存区查看");
  } catch (error) {
    status.className = "job-status failed";
    status.textContent = error.message;
    toast(error.message, "error");
  } finally {
    button.disabled = false;
    button.textContent = "生成 12 张套图";
    updateStudioButtons();
  }
}

async function loadStudioGallery() {
  const data = await api("/api/images?studio=1");
  const groups = [];
  const byKey = new Map();
  for (const image of data.items) {
    const key = image.suite_id || `single-${image.id}`;
    if (!byKey.has(key)) {
      const group = { key, suite: Boolean(image.suite_id), items: [] };
      byKey.set(key, group);
      groups.push(group);
    }
    byKey.get(key).items.push(image);
  }
  for (const group of groups) group.items.sort((a, b) => String(a.asset_role || "").localeCompare(String(b.asset_role || "")));
  state.galleryGroups = Object.fromEntries(groups.map((group) => [group.key, group]));
  const suiteCount = groups.filter((group) => group.suite).length;
  $("#gallery-count").textContent = `${data.items.length} 张 · ${suiteCount} 套`;
  $("#studio-gallery").innerHTML = groups.length ? groups.map((group) => {
    if (group.suite) {
      const previews = group.items.slice(0, 3).reverse().map((image) => `<img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.asset_role || "")}" loading="lazy">`).join("");
      return `<article class="suite-stack-card" data-viewer-group="${escapeHtml(group.key)}">
        <div class="suite-stack-preview">${previews}<span class="suite-stack-count">${group.items.length} 张套图</span></div>
        <div class="suite-stack-body"><small>${escapeHtml(platformName(group.items[0].platform_id))}<br>双击查看整套</small><div class="image-card-actions"><button data-draft-image="${group.items[0].id}">转为商品草稿</button><button class="danger-link" data-delete-image="${group.items[0].id}" data-delete-suite="1">删除整套</button></div></div>
      </article>`;
    }
    const image = group.items[0];
    return `<article class="image-card" data-viewer-group="${escapeHtml(group.key)}">
      <img src="${escapeHtml(image.url)}" alt="${escapeHtml(image.asset_role || image.template_id)}" loading="lazy">
      <div class="image-card-body"><small>${escapeHtml(image.asset_role || image.template_id)} · ${escapeHtml(platformName(image.platform_id))}</small><div class="image-card-actions"><button data-draft-image="${image.id}">转为商品草稿</button><button class="danger-link" data-delete-image="${image.id}">删除</button></div></div>
    </article>`;
  }).join("") : emptyState("生成的图片会先放在这里，确认后再转为商品草稿");
}

function openViewer(groupKey, index = 0) {
  const group = state.galleryGroups[groupKey];
  if (!group || !group.items.length) return;
  state.viewerItems = group.items;
  state.viewerIndex = Math.max(0, Math.min(index, group.items.length - 1));
  $("#image-viewer").hidden = false;
  document.body.style.overflow = "hidden";
  updateViewer();
}

function updateViewer() {
  const item = state.viewerItems[state.viewerIndex];
  if (!item) return;
  $("#viewer-image").src = item.url;
  const count = state.viewerItems.length;
  $("#viewer-caption").textContent = `${item.asset_role ? item.asset_role + " · " : ""}${item.name || item.template_id || ""} · ${state.viewerIndex + 1} / ${count}`;
  $("#viewer-prev").hidden = count <= 1;
  $("#viewer-next").hidden = count <= 1;
}

function closeViewer() {
  $("#image-viewer").hidden = true;
  state.viewerItems = [];
  state.viewerIndex = 0;
  document.body.style.overflow = "";
}

function stepViewer(delta) {
  if (!state.viewerItems.length) return;
  state.viewerIndex = (state.viewerIndex + delta + state.viewerItems.length) % state.viewerItems.length;
  updateViewer();
}

async function createDraftFromImage(imageId) {
  const button = $(`[data-draft-image="${imageId}"]`);
  if (button) { button.disabled = true; button.innerHTML = '<span class="spin"></span>'; }
  const box = $("#draft-status");
  box.hidden = false;
  box.className = "job-status";
  box.textContent = "正在创建商品草稿…";
  try {
    const result = await api("/api/products/from-image", {
      method: "POST",
      body: {
        image_id: imageId,
        category_id: state.categoryResult?.category.id || "",
        product_description: $("#studio-product-desc").value.trim(),
      },
    });
    toast(state.generationMode === "suite" ? "整套已保存到商品中心草稿" : "已保存到商品中心草稿");
    box.textContent = `草稿已创建：${result.product.sku}`;
    await loadProducts(true);
    location.hash = "products";
    setTimeout(() => openProduct(result.product.sku).catch((error) => toast(error.message, "error")), 250);
  } catch (error) {
    toast(error.message, "error");
    box.className = "job-status failed";
    box.textContent = error.message;
  } finally { if (button) { button.disabled = false; button.textContent = "转为商品草稿"; } }
}

async function retryJob(jobId) {
  try {
    const result = await api(`/api/jobs/${encodeURIComponent(jobId)}/retry`, { method: "POST" });
    toast(`已创建重试任务 #${result.job_id}`);
    await loadTaskCenter();
  } catch (error) { toast(error.message, "error"); }
}

async function rollbackTask(taskId) {
  if (!window.confirm("确认回滚这次改价？系统会同时恢复本地价格与已连接的 Shopify 价格。")) return;
  try {
    const result = await api(`/api/tasks/${encodeURIComponent(taskId)}/rollback`, { method: "POST" });
    toast(result.message);
    await loadTaskCenter();
  } catch (error) { toast(error.message, "error"); }
}

async function loadTaskCenter() {
  const [jobs, operations] = await Promise.all([api("/api/jobs?limit=80"), api("/api/tasks?limit=80")]);
  const js = jobs.summary || {};
  const os = operations.summary || {};
  $("#task-metrics").innerHTML = [
    ["生图执行中", Number(js.queued || 0) + Number(js.running || 0), "排队与正在生成的单图 / 套图"],
    ["生图失败", js.failed || 0, "可保留原参数直接重试"],
    ["发布执行中", os.running || 0, "上架、改价与同步任务"],
    ["失败 / 中断", Number(os.failed || 0), "需要人工检查的任务"],
  ].map(([title, value, desc]) => `<article class="metric"><span class="metric-label">${escapeHtml(title)}</span><strong class="metric-value">${escapeHtml(value)}</strong><small class="metric-note">${escapeHtml(desc)}</small></article>`).join("");
  $("#job-list").innerHTML = jobs.items.length ? jobs.items.map((job) => {
    const progress = job.kind === "suite" ? `${job.progress} / ${job.total} 张` : `${job.outputs} 张输出`;
    const preview = job.preview_url ? `<img class="thumb" src="${escapeHtml(job.preview_url)}" alt="生成预览">` : `<span class="thumb-placeholder">✦</span>`;
    return `<div class="list-row"><div style="display:flex;gap:10px;align-items:center;min-width:0">${preview}<div class="list-main"><strong>#${job.id} ${escapeHtml(job.kind_label)} · ${escapeHtml(job.platform_id)}</strong><small>${escapeHtml(job.model_id || "模型未记录")} · ${escapeHtml(job.generation_resolution || "")} · ${escapeHtml(progress)}${job.error ? ` · ${escapeHtml(job.error)}` : ""}</small><small>${escapeHtml(job.created_at || "")}${job.finished_at ? ` → ${escapeHtml(job.finished_at)}` : ""}</small></div></div><div class="list-side">${statusTag(job.status)}${job.can_retry ? `<button class="btn btn-small" data-retry-job="${job.id}">重试</button>` : ""}</div></div>`;
  }).join("") : emptyState("还没有生图任务");
  $("#task-list").innerHTML = operations.items.length ? operations.items.map((task) => `<div class="list-row"><div class="list-main"><strong>${escapeHtml(task.type)} · ${escapeHtml(task.sku)}</strong><small>${escapeHtml(task.message || `${task.old_value || ""} ${task.old_value ? "→" : ""} ${task.new_value || ""}`)}</small><small>${escapeHtml(task.created_at || "")}${task.finished_at ? ` → ${escapeHtml(task.finished_at)}` : ""}</small></div><div class="list-side">${statusTag(task.status)}${task.can_rollback && task.status !== "已回滚" ? `<button class="btn btn-small" data-rollback-task="${task.id}">回滚</button>` : ""}</div></div>`).join("") : emptyState("还没有商品或发布任务");
}

async function runSystemCheck() {
  const box = $("#system-check-results");
  box.innerHTML = '<div class="hint">正在检查…</div>';
  try {
    const result = await api("/api/system-check");
    const head = `<div class="note">${result.ready ? "核心配置完整，可以开始生成。" : "核心配置不完整，请先处理标红的项目。"} 检查时间：${escapeHtml(result.generated_at)}</div>`;
    const rows = result.checks.map((item) => `<div class="list-row"><div class="list-main"><strong>${escapeHtml(item.label)}</strong><small>${escapeHtml(item.detail)}</small></div><div class="list-side">${item.ok ? statusTag("正常") : `<span class="tag ${item.required ? "tag-danger" : "tag-warm"}">${item.required ? "必须处理" : "待配置"}</span>`}</div></div>`).join("");
    box.innerHTML = head + rows;
    toast(result.ready ? "系统自检通过" : "系统自检发现待处理项", result.ready ? "ok" : "error");
  } catch (error) {
    box.innerHTML = `<div class="job-status failed">${escapeHtml(error.message)}</div>`;
    toast(error.message, "error");
  }
}

async function loadSettings() {
  const settings = await api("/api/settings");
  state.settings = settings;
  const field = (id) => $(`#${id}`);
  field("ark_base").value = settings.ark_base || "";
  field("ark_model").value = settings.ark_model || "";
  field("deepseek_base").value = settings.deepseek_base || "";
  field("deepseek_model").value = settings.deepseek_model || "";
  field("shopify_store").value = settings.shopify_store || "";
  for (const id of ["ark_key", "deepseek_key", "shopify_token", "feishu_webhook"]) field(id).value = "";
  field("ark_key").placeholder = settings.ark_key_set ? `已配置（长度 ${settings.ark_key_length}）` : "请输入 Ark API Key";
  field("deepseek_key").placeholder = settings.deepseek_key_set ? `已配置（长度 ${settings.deepseek_key_length}）` : "请输入 DeepSeek API Key";
  field("shopify_token").placeholder = settings.shopify_token_set ? `已配置（长度 ${settings.shopify_token_length}）` : "请输入 Shopify Token";
  field("feishu_webhook").placeholder = settings.feishu_webhook_set ? `已配置（长度 ${settings.feishu_webhook_length}）` : "可选";
}

async function saveSettings(event) {
  event.preventDefault();
  const ids = ["ark_key", "ark_base", "ark_model", "deepseek_key", "deepseek_base", "deepseek_model", "shopify_store", "shopify_token", "feishu_webhook"];
  const payload = Object.fromEntries(ids.map((id) => [id, $(`#${id}`).value]));
  try {
    const result = await api("/api/settings", { method: "POST", body: payload });
    state.settings = result.settings;
    $("#settings-status").textContent = "已保存到本机";
    toast("设置已保存");
    await loadSettings();
  } catch (error) { toast(error.message, "error"); }
}

async function testSetting(type) {
  const button = type === "deepseek" ? $("#test-deepseek") : $("#test-shopify");
  const original = button.textContent;
  button.disabled = true;
  button.innerHTML = '<span class="spin"></span>测试中';
  try {
    const result = type === "deepseek" ? await api("/api/settings/test-deepseek", { method: "POST" }) : await api("/api/settings/test-shopify", { method: "POST" });
    toast(type === "deepseek" ? `DeepSeek 连接成功：${result.reply}` : `Shopify 店铺：${result.shop?.name || "连接成功"}`);
  } catch (error) { toast(error.message, "error"); }
  finally { button.disabled = false; button.textContent = original; }
}

function addAgentMessage(role, text, meta = "") {
  const chat = $("#agent-chat");
  const element = document.createElement("div");
  element.className = `message ${role}`;
  element.innerHTML = `<div class="message-role">${role === "user" ? "你" : "NOVA Agent"}${meta ? ` · ${escapeHtml(meta)}` : ""}</div><div>${escapeHtml(text)}</div>`;
  chat.appendChild(element);
  chat.scrollTop = chat.scrollHeight;
}

function initializeAgent() { $("#agent-chat").scrollTop = $("#agent-chat").scrollHeight; }

async function sendAgent(message) {
  if (!message || state.agentBusy) return;
  state.agentBusy = true;
  addAgentMessage("user", message);
  addAgentMessage("assistant", "正在分析并调用工具…");
  const loading = $("#agent-chat").lastElementChild;
  try {
    const result = await api("/api/agent", { method: "POST", body: { message } });
    const tools = (result.steps || []).map((step) => step.tool).join(" · ");
    loading.remove();
    addAgentMessage("assistant", result.answer, tools ? `调用 ${tools}` : "");
  } catch (error) {
    loading.remove();
    addAgentMessage("assistant", `操作失败：${error.message}`);
  } finally { state.agentBusy = false; }
}

function bindEvents() {
  $$(".nav-item").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
  document.addEventListener("click", (event) => {
    const go = event.target.closest("[data-go]");
    if (go) navigate(go.dataset.go);
  });
  window.addEventListener("hashchange", renderRoute);
  $("#product-search").addEventListener("input", renderProductRows);
  $("#product-filter").addEventListener("change", renderProductRows);
  $("#product-rows").addEventListener("click", async (event) => {
    const detail = event.target.closest("[data-product]");
    const publish = event.target.closest("[data-publish-product]");
    if (detail) openProduct(detail.dataset.product).catch((error) => toast(error.message, "error"));
    if (publish) await publishProduct(publish.dataset.publishProduct, publish, publish.dataset.platform || "shopify");
  });
  $("#modal-close").addEventListener("click", closeModal);
  $("#modal").addEventListener("click", (event) => { if (event.target === $("#modal")) closeModal(); });
  document.addEventListener("keydown", (event) => {
    if (!$("#image-viewer").hidden) {
      if (event.key === "Escape") closeViewer();
      if (event.key === "ArrowLeft") stepViewer(-1);
      if (event.key === "ArrowRight") stepViewer(1);
      return;
    }
    if (event.key === "Escape") closeModal();
  });

  $$("#generation-mode-switch .mode-btn").forEach((button) => button.addEventListener("click", () => updateGenerationMode(button.dataset.generationMode)));
  $$('.mode-btn[data-mode]').forEach((button) => button.addEventListener("click", () => switchClassifyMode(button.dataset.mode)));
  $("#style-ref-grid").addEventListener("click", (event) => { const button = event.target.closest("[data-style-ref]"); if (!button) return; state.styleRefId = button.dataset.styleRef || ""; renderStyleRefs(); });
  $("#studio-model").addEventListener("change", (event) => { state.modelId = event.target.value; populateResolutionOptions(); updateStudioButtons(); });
  $("#studio-resolution").addEventListener("change", (event) => { state.generationResolution = event.target.value; updateStudioButtons(); });
  $("#studio-platform").addEventListener("change", (event) => { state.platformId = event.target.value; state.sizeId = ""; populateSizeOptions(); updatePlatformNote(); });
  $("#studio-size").addEventListener("change", (event) => { state.sizeId = event.target.value; updateStudioButtons(); });
  $("#manual-category").addEventListener("change", (event) => chooseManualCategory(event.target.value));
  $("#classify-btn").addEventListener("click", classifyProduct);
$("#plan-generate-btn").addEventListener("click", generatePlan);
$("#plan-prev").addEventListener("click", () => { if (planIndex > 0) { planIndex -= 1; renderPlanPage(); } });
$("#plan-next").addEventListener("click", () => { if (planIndex < planPages.length - 1) { planIndex += 1; renderPlanPage(); } });
$("#plan-copy-all").addEventListener("click", () => {
  const text = planPages.map((page) => `${page.code} ${page.role}\n${page.prompt_full}`).join("\n\n---\n\n");
  copyPlanText(text, "12 页提示词已全部复制");
});
$("#plan-run-suite").addEventListener("click", () => {
  if (!planPages.length) return toast("先生成 12 页方案", "error");
  if (!state.categoryResult) return toast("请先确定商品类型", "error");
  if (!state.uploadedReference) return toast("请先上传产品实拍图", "error");
  updateGenerationMode("suite");
  generateSuite();
});
$("#plan-run-single").addEventListener("click", () => {
  const page = planPages[planIndex];
  if (!page) return toast("先生成 12 页方案", "error");
  $("#studio-prompt").value = page.prompt_full;
  updateGenerationMode("single");
  generateImage();
});
$(".plan-stage-card").addEventListener("click", (event) => {
  const findByCode = (code) => planPages.find((page) => page.code === code);
  const infoButton = event.target.closest("[data-plan-copy]");
  if (infoButton) { const page = findByCode(infoButton.dataset.planCopy); if (page) copyPlanText(planModuleText(page), `${page.code} 信息已复制`); return; }
  const promptButton = event.target.closest("[data-plan-copy-prompt]");
  if (promptButton) { const page = findByCode(promptButton.dataset.planCopyPrompt); if (page) copyPlanText(page.prompt_full, `${page.code} 提示词已复制`); return; }
  const copyTextButton = event.target.closest("[data-plan-copy-text]");
  if (copyTextButton) { const page = findByCode(copyTextButton.dataset.planCopyText); if (page) copyPlanText(planCopyText(page), `${page.code} 文案已复制`); return; }
  const shortButton = event.target.closest("[data-plan-copy-short]");
  if (shortButton) { const page = findByCode(shortButton.dataset.planCopyShort); if (page) copyPlanText(page.prompt_short, `${page.code} 精简版已复制`); }
});
  $("#studio-product-desc").addEventListener("input", updateStudioButtons);
  $("#upload-button").addEventListener("click", () => $("#upload-input").click());
  $("#upload-input").addEventListener("change", (event) => uploadReference(event.target.files[0]));
  $("#upload-zone").addEventListener("click", (event) => { if (!event.target.closest("#upload-button")) $("#upload-input").click(); });
  $("#upload-zone").addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); $("#upload-input").click(); } });
  $("#upload-zone").addEventListener("dragover", (event) => { event.preventDefault(); $("#upload-zone").classList.add("dragging"); });
  $("#upload-zone").addEventListener("dragleave", () => $("#upload-zone").classList.remove("dragging"));
  $("#upload-zone").addEventListener("drop", (event) => { event.preventDefault(); $("#upload-zone").classList.remove("dragging"); uploadReference(event.dataTransfer.files[0]); });
  $("#studio-scene").addEventListener("change", () => { $("#custom-scene-label").hidden = $("#studio-scene").value !== "自定义场景"; });
  $("#prompt-btn").addEventListener("click", generatePrompt);
  $("#suite-plan-btn").addEventListener("click", loadSuitePlan);
  $("#generate-btn").addEventListener("click", generateImage);
  $("#regenerate-btn").addEventListener("click", generateImage);
  $("#save-draft-btn").addEventListener("click", () => state.lastImage && createDraftFromImage(state.lastImage.image_id));
  $("#copy-prompt-btn").addEventListener("click", async () => {
    const prompt = $("#studio-prompt").value;
    if (!prompt) return toast("还没有提示词", "error");
    try { await navigator.clipboard.writeText(prompt); toast("提示词已复制"); } catch (_) { toast("复制失败，请手动选择", "error"); }
  });
  $("#studio-gallery").addEventListener("click", (event) => {
    const button = event.target.closest("[data-draft-image]");
    if (button) createDraftFromImage(button.dataset.draftImage);
  });
  $("#studio-gallery").addEventListener("dblclick", (event) => {
    if (event.target.closest("[data-draft-image]")) return;
    const card = event.target.closest("[data-viewer-group]");
    if (card) openViewer(card.dataset.viewerGroup, 0);
  });
  $("#viewer-close").addEventListener("click", closeViewer);
  $("#viewer-prev").addEventListener("click", () => stepViewer(-1));
  $("#viewer-next").addEventListener("click", () => stepViewer(1));
  $("#image-viewer").addEventListener("click", (event) => { if (event.target === $("#image-viewer")) closeViewer(); });

  $("#agent-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("#agent-input");
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    sendAgent(message);
  });
  $("#agent-suggestions").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (button) sendAgent(button.textContent.trim());
  });
  $("#tasks-refresh").addEventListener("click", loadTaskCenter);
  $("#job-list").addEventListener("click", (event) => { const button = event.target.closest("[data-retry-job]"); if (button) retryJob(button.dataset.retryJob); });
  $("#task-list").addEventListener("click", (event) => { const button = event.target.closest("[data-rollback-task]"); if (button) rollbackTask(button.dataset.rollbackTask); });
  $("#settings-form").addEventListener("submit", saveSettings);
  $("#test-deepseek").addEventListener("click", () => testSetting("deepseek"));
  $("#test-shopify").addEventListener("click", () => testSetting("shopify"));
  $("#system-check-btn").addEventListener("click", runSystemCheck);
  $("#report-btn").addEventListener("click", async () => {
    try {
      const result = await api("/api/report", { method: "POST" });
      toast(result.message, result.ok ? "ok" : "error");
    } catch (error) { toast(error.message, "error"); }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  bindEvents();
  await checkHealth();
  if (!location.hash) location.hash = "dashboard";
  await renderRoute();
});









