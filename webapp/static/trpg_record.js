// 跑团记录详情：聊天气泡 + 录制中每 5 秒增量轮询 + 暗骰开关。
const listEl = document.getElementById("messageList");
const hintEl = document.getElementById("threadHint");
const titleEl = document.getElementById("recordTitle");
const metaEl = document.getElementById("recordMeta");
const stateEl = document.getElementById("recordState");
const revealToggle = document.getElementById("revealToggle");
const sheetBox = document.getElementById("sheetBox");
const sheetList = document.getElementById("sheetList");

const PATH_PARTS = location.pathname.split("/").filter(Boolean); // trpg / records / <群号> / <目录>
const GROUP_ID = decodeURIComponent(PATH_PARTS[2] || "");
const START_DIR = decodeURIComponent(PATH_PARTS[3] || "");
const API_URL = `/api/trpg/records/${GROUP_ID}/${START_DIR}`;

const STATE_LABEL = { recording: "录制中", ended: "已结束" };
const ROLE_LABEL = { dm: "DM", ob: "观察者" };
const POLL_MS = 5000;

let me = null;
let cursor = 0;          // 已消费到 messages.jsonl 第几条（含被过滤的暗骰，口径由服务端 total 给出）
let recordState = "";
let lastSeen = 0;        // 已渲染消息里的最大时间戳，用于判定残留录制
let nickByQQ = {};
let pollTimer = null;

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
  if (m.char_name) return `${m.char_name}（${m.nickname || m.user_id}）`;
  return m.nickname || String(m.user_id || "");
}

function rebuildNickMap(participants) {
  nickByQQ = {};
  for (const p of participants || []) {
    if (p && p.user_id != null) nickByQQ[String(p.user_id)] = p.nickname || String(p.user_id);
  }
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

function renderMessage(m) {
  const isBot = m.sender_type === "bot";
  const classes = ["trpg-msg"];
  if (isBot) classes.push("is-bot");
  else if (isSelf(m)) classes.push("is-self");
  if (m.secret) classes.push("is-secret");
  const node = makeEl("div", classes.join(" "));

  if (!isBot && !isSelf(m)) {
    const who = m.char_name || m.nickname || String(m.user_id || "?");
    node.appendChild(makeEl("div", "trpg-avatar", who.slice(0, 1)));
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
  const rows = (participants || []).filter((p) => p && (p.sheet_start || p.sheet_end));
  sheetList.innerHTML = "";
  sheetBox.hidden = rows.length === 0;
  if (!rows.length) return;
  for (const person of rows) {
    const chip = makeEl("span", "trpg-person", person.char_name || person.nickname || person.user_id);
    if (person.role === "dm" || person.role === "ob") {
      chip.appendChild(makeEl("span", `trpg-role role-${person.role}`, ROLE_LABEL[person.role] || person.role));
    }
    const card = makeEl("div", "trpg-sheet");
    card.appendChild(chip);
    const startLine = sheetLine(person.sheet_start);
    const endLine = sheetLine(person.sheet_end);
    if (startLine) card.appendChild(makeEl("p", "trpg-sheet-line", `开始：${startLine}`));
    if (endLine) card.appendChild(makeEl("p", "trpg-sheet-line", `结束：${endLine}`));
    const delta = sheetDelta(person.sheet_start, person.sheet_end);
    if (delta) card.appendChild(makeEl("p", "trpg-sheet-delta", delta));
    if (!endLine && person.sheet_start) {
      card.appendChild(makeEl("p", "trpg-sheet-line", "结束：角色卡已删除或未记录"));
    }
    sheetList.appendChild(card);
  }
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
  if (recordState !== "recording") {
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

async function load(reset) {
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
  const stick = reset || isAtBottom();
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
  if (stick) scrollToBottom();
}

revealToggle.addEventListener("change", () => {
  load(true).catch((err) => showError(err.message || "加载失败"));
});

(async function init() {
  if (!GROUP_ID || !START_DIR) {
    showError("记录地址不完整");
    return;
  }
  me = await GalleryAuth.refreshMe();
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  await load(true);
})().catch((err) => showError(err.message || "加载失败"));
