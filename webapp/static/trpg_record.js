// 跑团记录详情：聊天气泡 + 录制中每 5 秒增量轮询 + 暗骰开关 + 场外发言开关。
const listEl = document.getElementById("messageList");
const hintEl = document.getElementById("threadHint");
const titleEl = document.getElementById("recordTitle");
const metaEl = document.getElementById("recordMeta");
const stateEl = document.getElementById("recordState");
const revealToggle = document.getElementById("revealToggle");
const oocToggle = document.getElementById("oocToggle");
const fabTop = document.getElementById("fabTop");
const fabSecret = document.getElementById("fabSecret");
const fabOoc = document.getElementById("fabOoc");
const sheetBox = document.getElementById("sheetBox");
const sheetList = document.getElementById("sheetList");

const PATH_PARTS = location.pathname.split("/").filter(Boolean); // trpg / records / <群号> / <目录>
const GROUP_ID = decodeURIComponent(PATH_PARTS[2] || "");
const START_DIR = decodeURIComponent(PATH_PARTS[3] || "");
const API_URL = `/api/trpg/records/${GROUP_ID}/${START_DIR}`;

const STATE_LABEL = { recording: "录制中", paused: "已暂停", ended: "已结束" };
const ROLE_LABEL = { dm: "DM", ob: "观察者" };
const POLL_MS = 5000;
const HIDE_OOC_KEY = "botero_trpg_hide_ooc";
// 整条消息都用全角/半角括号包起来 → 视为场外发言（OOC）
const OOC_RE = /^[（(][\s\S]*[）)]$/;

let me = null;
let cursor = 0;          // 已消费到 messages.jsonl 第几条（含被过滤的暗骰，口径由服务端 total 给出）
let recordState = "";
let lastSeen = 0;        // 已渲染消息里的最大时间戳，用于判定残留录制
let nickByQQ = {};        // QQ → 显示名（优先实时解析，回落消息里的昵称）
let avatarByQQ = {};      // QQ → 头像地址（与论坛/时间线同一取法）
let personByQQ = {};      // QQ → 参与者（含 char_id 与起止角色卡快照）
let pollTimer = null;
let secretHidden = true;     // 暗骰默认隐藏
let oocHidden = false;       // 场外发言默认显示
const TOP_FAB_THRESHOLD = 300;   // 向下滚过这么多像素才显示「回到顶部」

function makeEl(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function showError(message) {
  hintEl.className = "loading-msg error";
  hintEl.textContent = message;
}

function parseTime(text) {
  return text ? new Date(String(text).replace(" ", "T")).getTime() : NaN;
}

function formatTime(seconds) {
  const d = new Date(Number(seconds || 0) * 1000);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

function durationText(data) {
  if (data.state === "recording") return "录制中";
  const start = parseTime(data.start);
  const end = parseTime(data.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "";
  const minutes = Math.round((end - start) / 60000);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours} 小时 ${minutes % 60} 分` : `${minutes} 分`;
}

function isSelf(m) {
  return Boolean(me) && String(m.user_id) === String(me.user_id);
}

function displayName(m) {
  const qq = String(m.user_id || "");
  const who = nickByQQ[qq] || m.nickname || qq;
  if (m.char_name) return `${m.char_name}（${who}）`;
  return who;
}

function rebuildNickMap(participants) {
  nickByQQ = {};
  avatarByQQ = {};
  personByQQ = {};
  for (const p of participants || []) {
    if (!p || p.user_id == null) continue;
    const qq = String(p.user_id);
    nickByQQ[qq] = p.display_name || p.nickname || qq;
    avatarByQQ[qq] = p.avatar_url || "";
    personByQQ[qq] = p;
  }
}

function charUrl(person) {
  if (!person || !person.char_id) return "";
  return `/trpg/char/${encodeURIComponent(person.user_id)}/${person.char_id}`;
}

// 悬停概要：角色名 + 职业/种族职业等级 + 关键数值（取开录快照，没有就用结束快照）
function cardSummary(person) {
  const sheet = person.sheet_start || person.sheet_end || null;
  const head = person.char_name || person.nickname || String(person.user_id || "");
  if (!sheet) return `${head}（本场没有角色卡快照）`;
  if (sheet.rules === "coc7th") {
    const bits = [head];
    if (sheet.occupation) bits.push(sheet.occupation);
    if (sheet.age) bits.push(`${sheet.age}岁`);
    bits.push(`HP ${sheet.current_hp}/${sheet.hp}`,
      `SAN ${sheet.current_san}/${sheet.san}`,
      `MP ${sheet.current_mp}/${sheet.mp}`);
    return bits.join(" · ");
  }
  const who = [head, sheet.race, sheet.class_name].filter(Boolean).join(" ");
  const bits = [sheet.level != null ? `${who} Lv.${sheet.level}` : who];
  bits.push(`HP ${sheet.current_hp}/${sheet.hp}`, `AC ${sheet.ac}`);
  return bits.join(" · ");
}

// 没有角色卡的成员（机器人、未建档）不做外链
function linkToCard(node, person) {
  const url = charUrl(person);
  if (!url) return node;
  const link = makeEl("a", "trpg-card-link");
  link.href = url;
  link.title = cardSummary(person);
  link.appendChild(node);
  return link;
}

// 头像：有 QQ 头像就用图片，取不到（或没参与名单）回落到名字首字；有角色卡时点进详情
function renderAvatar(m) {
  return linkToCard(buildAvatar(m), personByQQ[String(m.user_id || "")]);
}

function buildAvatar(m) {
  const qq = String(m.user_id || "");
  const url = avatarByQQ[qq] || "";
  const fallback = (m.char_name || nickByQQ[qq] || m.nickname || "?").slice(0, 1);
  if (!url) return makeEl("div", "trpg-avatar", fallback);
  const img = document.createElement("img");
  img.className = "trpg-avatar";
  img.src = url;
  img.alt = "";
  img.loading = "lazy";
  img.onerror = () => {
    const node = makeEl("div", "trpg-avatar", fallback);
    if (img.parentNode) img.parentNode.replaceChild(node, img);
  };
  return img;
}

function renderSegment(seg) {
  if (seg.type === "text") return makeEl("span", "trpg-text", seg.text || "");
  if (seg.type === "image") {
    if (seg.unavailable || !seg.url) return makeEl("span", "trpg-img-missing", "图片获取失败");
    // img.trpg-img 由 /shared/lightbox.js 的全局点击监听接管放大
    const img = makeEl("img", "trpg-img");
    img.src = seg.url;
    img.alt = "跑团记录图片";
    img.loading = "lazy";
    return img;
  }
  if (seg.type === "at") {
    return makeEl("span", "trpg-mention", `@${nickByQQ[String(seg.qq)] || seg.qq || ""}`);
  }
  return makeEl("span", "trpg-other", "[暂不支持的附件]");
}

function isOoc(m) {
  // 只认纯文本消息：带图片、@ 之类的消息即使文字被括号包着也不算场外
  const segments = m.segments || [];
  if (!segments.length) return false;
  if (segments.some((seg) => seg.type !== "text")) return false;
  const joined = segments.map((seg) => seg.text || "").join("").trim();
  return joined.length > 2 && OOC_RE.test(joined);
}

function applyOocFilter(hidden) {
  if (hidden) listEl.classList.add("hide-ooc");
  else listEl.classList.remove("hide-ooc");
}

function renderMessage(m) {
  const isBot = m.sender_type === "bot";
  const classes = ["trpg-msg"];
  if (isBot) classes.push("is-bot");
  else if (isSelf(m)) classes.push("is-self");
  if (m.secret) classes.push("is-secret");
  if (isOoc(m)) classes.push("is-ooc");
  const node = makeEl("div", classes.join(" "));

  if (!isBot && !isSelf(m)) {
    node.appendChild(renderAvatar(m));
  }

  const body = makeEl("div", "trpg-msg-body");
  const head = makeEl("div", "trpg-msg-name");
  head.appendChild(makeEl("span", "trpg-msg-who", isBot ? (m.nickname || "机器人") : displayName(m)));
  if (ROLE_LABEL[m.role]) head.appendChild(makeEl("span", `trpg-role role-${m.role}`, ROLE_LABEL[m.role]));
  if (m.secret) head.appendChild(makeEl("span", "trpg-role role-secret", "暗骰"));
  head.appendChild(makeEl("time", "trpg-msg-time", formatTime(m.time)));
  body.appendChild(head);

  const bubble = makeEl("div", "trpg-bubble");
  for (const seg of m.segments || []) bubble.appendChild(renderSegment(seg));
  body.appendChild(bubble);
  node.appendChild(body);
  return node;
}

function renderHeader(data) {
  titleEl.textContent = data.group_name || `团 ${data.group_id}`;
  metaEl.textContent = [data.start, durationText(data), data.rules_name, `${data.total} 条消息`].filter(Boolean).join(" · ");
  recordState = data.state;
  stateEl.className = `trpg-badge is-${recordState}`;
  stateEl.textContent = STATE_LABEL[recordState] || recordState;
}

function sheetLine(sheet) {
  if (!sheet) return "";
  if (sheet.rules === "coc7th") {
    return `HP ${sheet.current_hp}/${sheet.hp} · SAN ${sheet.current_san}/${sheet.san}` +
      ` · MP ${sheet.current_mp}/${sheet.mp} · MOV ${sheet.mov} · DB ${sheet.db}` +
      ` · 技能 ${Object.keys(sheet.skills || {}).length} 项`;
  }
  return `Lv.${sheet.level} · HP ${sheet.current_hp}/${sheet.hp} · AC ${sheet.ac}` +
    ` · 熟练 +${sheet.prof_bonus} · 被动感知 ${sheet.passive_perception}`;
}

function sheetDelta(start, end) {
  if (!start || !end) return "";
  const parts = [];
  if (start.level != null && end.level != null && start.level !== end.level) {
    parts.push(`Lv ${start.level}→${end.level}`);
  }
  if (start.hp != null && end.hp != null && start.hp !== end.hp) parts.push(`HP上限 ${start.hp}→${end.hp}`);
  if (start.current_san != null && end.current_san != null && start.current_san !== end.current_san) {
    parts.push(`SAN ${start.current_san}→${end.current_san}`);
  }
  if (start.current_hp != null && end.current_hp != null && start.current_hp !== end.current_hp) {
    parts.push(`HP ${start.current_hp}→${end.current_hp}`);
  }
  return parts.length ? `本场变化：${parts.join("，")}` : "";
}

function renderSheets(participants) {
  if (!sheetBox || !sheetList) return;
  // 有角色卡（char_id）或有快照的参与者都列出来，机器人等无卡成员不列
  const rows = (participants || []).filter((p) => p && (p.char_id || p.sheet_start || p.sheet_end));
  sheetList.innerHTML = "";
  sheetBox.hidden = rows.length === 0;
  if (!rows.length) return;
  for (const person of rows) {
    const chip = makeEl("span", "trpg-person", person.char_name || person.nickname || person.user_id);
    if (person.role === "dm" || person.role === "ob") {
      chip.appendChild(makeEl("span", `trpg-role role-${person.role}`, ROLE_LABEL[person.role] || person.role));
    }
    const url = charUrl(person);
    const card = makeEl(url ? "a" : "div", url ? "trpg-sheet is-link" : "trpg-sheet");
    if (url) {
      card.href = url;
      card.title = cardSummary(person);
    }
    card.appendChild(chip);
    const startLine = sheetLine(person.sheet_start);
    const endLine = sheetLine(person.sheet_end);
    if (startLine) card.appendChild(makeEl("p", "trpg-sheet-line", `开始：${startLine}`));
    if (endLine) card.appendChild(makeEl("p", "trpg-sheet-line", `结束：${endLine}`));
    if (url) card.appendChild(makeEl("span", "trpg-sheet-link", "查看角色卡 →"));
    const delta = sheetDelta(person.sheet_start, person.sheet_end);
    if (delta) card.appendChild(makeEl("p", "trpg-sheet-delta", delta));
    if (!endLine && person.sheet_start) {
      card.appendChild(makeEl("p", "trpg-sheet-line", "结束：角色卡已删除或未记录"));
    }
    sheetList.appendChild(card);
  }
}

function currentScrollY() {
  return typeof window.scrollY === "number" ? window.scrollY : 0;
}

// 记录当前视口里第一条消息及其相对视口顶部的位置，刷新后按它还原滚动
function topVisibleAnchor() {
  const nodes = listEl.children || [];
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    if (typeof node.getBoundingClientRect !== "function") return null;
    const rect = node.getBoundingClientRect();
    if (rect.top >= 0) return { index, offset: rect.top };
  }
  return null;
}

function restoreAnchor(anchor) {
  if (!anchor) return;
  const node = (listEl.children || [])[anchor.index];
  if (!node || typeof node.getBoundingClientRect !== "function") return;
  if (typeof window.scrollTo !== "function") return;
  const top = node.getBoundingClientRect().top + currentScrollY() - anchor.offset;
  window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
}

function isAtBottom() {
  const doc = document.documentElement;
  if (!doc || typeof window.scrollY !== "number") return true;
  return doc.scrollHeight - window.scrollY - window.innerHeight < 80;
}

function scrollToBottom() {
  if (typeof window.scrollTo !== "function") return;
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: "smooth" });
}

function syncPolling() {
  // 暂停时也轮询：恢复录制后徽标要能自己变回来
  if (recordState !== "recording" && recordState !== "paused") {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    return;
  }
  if (pollTimer) return;
  pollTimer = setInterval(() => {
    if (document.hidden) return;
    load(false).catch(() => {});
  }, POLL_MS);
}

async function load(reset, options) {
  // keepPosition：切换暗骰这类「同一批消息重排」时留在原处，别把读者甩到最底部
  const keepPosition = Boolean(options && options.keepPosition);
  const atBottom = isAtBottom();
  const keep = keepPosition && !atBottom;
  const anchor = keep ? topVisibleAnchor() : null;
  const params = new URLSearchParams();
  params.set("from", reset ? "0" : String(cursor));
  if (revealToggle.checked) params.set("reveal", "1");
  const res = await fetch(`${API_URL}?${params.toString()}`, { headers: GalleryAuth.headers() });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "加载失败");
  if (reset) {
    listEl.innerHTML = "";
    lastSeen = 0;
  }
  const stick = atBottom || (reset && !keep);
  rebuildNickMap(data.participants);
  for (const m of data.messages || []) {
    listEl.appendChild(renderMessage(m));
    if (Number(m.time) > lastSeen) lastSeen = Number(m.time);
  }
  cursor = Number(data.total) || 0; // 客户端游标统一取服务端 total，被过滤的暗骰不会让增量错位
  renderHeader(data);
  renderSheets(data.participants);
  syncPolling();
  hintEl.className = "empty-hint center";
  hintEl.textContent = listEl.children.length ? "" : "还没有消息";
  if (keep) {
    // 等浏览器完成布局再按锚点还原（新增/移除的暗骰会改变上方高度）
    if (typeof requestAnimationFrame === "function") requestAnimationFrame(() => restoreAnchor(anchor));
    else restoreAnchor(anchor);
  } else if (stick) {
    scrollToBottom();
  }
}

// 头部勾选框与底部悬浮按钮共用同一份状态
function setFabState(btn, pressed) {
  if (!btn) return;
  btn.setAttribute("aria-pressed", pressed ? "true" : "false");
  if (pressed) btn.classList.add("is-active");
  else btn.classList.remove("is-active");
}

function setSecretHidden(hidden, reload = true) {
  secretHidden = hidden;
  revealToggle.checked = !hidden;
  setFabState(fabSecret, hidden);
  if (reload) load(true, { keepPosition: true }).catch((err) => showError(err.message || "加载失败"));
}

function setOocHidden(hidden) {
  oocHidden = hidden;
  if (oocToggle) oocToggle.checked = hidden;
  applyOocFilter(hidden);
  setFabState(fabOoc, hidden);
  try {
    localStorage.setItem(HIDE_OOC_KEY, hidden ? "1" : "0");
  } catch (err) {
    /* 隐私模式下存不了，仅本次生效 */
  }
}

// 「回到顶部」只在往下翻了一段之后出现，避免占着位置却没意义
function syncTopFab() {
  if (!fabTop) return;
  const y = typeof window.scrollY === "number" ? window.scrollY : 0;
  const hidden = y < TOP_FAB_THRESHOLD;
  if (hidden) fabTop.classList.add("is-hidden");
  else fabTop.classList.remove("is-hidden");
  fabTop.tabIndex = hidden ? -1 : 0;
}

function mountFabs() {
  const icons = typeof GalleryIcons !== "undefined" ? GalleryIcons : null;
  const paint = (btn, icon, label) => {
    if (!btn) return;
    if (icons) btn.innerHTML = icons.svgHTML(icon);
    btn.title = label;
    btn.setAttribute("aria-label", label);
  };
  paint(fabTop, "arrow-up", "回到顶部");
  paint(fabSecret, "eye-off", "隐藏暗骰");
  paint(fabOoc, "message-off", "隐藏场外发言");

  if (fabTop) {
    fabTop.addEventListener("click", () => {
      if (typeof window.scrollTo === "function") window.scrollTo({ top: 0, behavior: "smooth" });
    });
    if (typeof window.addEventListener === "function") {
      window.addEventListener("scroll", syncTopFab, { passive: true });
    }
    syncTopFab();
  }
  if (fabSecret) fabSecret.addEventListener("click", () => setSecretHidden(!secretHidden));
  if (fabOoc) fabOoc.addEventListener("click", () => setOocHidden(!oocHidden));
}

revealToggle.addEventListener("change", () => setSecretHidden(!revealToggle.checked));
if (oocToggle) {
  try {
    oocToggle.checked = localStorage.getItem(HIDE_OOC_KEY) === "1";
  } catch (err) {
    oocToggle.checked = false;
  }
  oocToggle.addEventListener("change", () => setOocHidden(oocToggle.checked));
}

mountFabs();
setSecretHidden(!revealToggle.checked, false);
if (oocToggle) setOocHidden(oocToggle.checked);

(async function init() {
  if (!GROUP_ID || !START_DIR) {
    showError("记录地址不完整");
    return;
  }
  me = await GalleryAuth.refreshMe();
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  await load(true);
})().catch((err) => showError(err.message || "加载失败"));
