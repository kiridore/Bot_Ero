// 跑团记录列表：按开始时间倒序，可只看自己参加的记录。
const listEl = document.getElementById("recordList");
const mineToggle = document.getElementById("mineOnly");

const STATE_LABEL = { recording: "录制中", ended: "已结束·未导出", exported: "已导出" };
const ROLE_LABEL = { dm: "DM", ob: "观察者" };
const STALE_SECONDS = 600; // 录制中最久一条消息距今超 10 分钟 → 可能已中断

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function parseTime(text) {
  return text ? new Date(String(text).replace(" ", "T")).getTime() : NaN;
}

function durationText(r) {
  if (r.state === "recording") return "录制中";
  const start = parseTime(r.start);
  const end = parseTime(r.end);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return "";
  const minutes = Math.round((end - start) / 60000);
  const hours = Math.floor(minutes / 60);
  return hours ? `${hours} 小时 ${minutes % 60} 分` : `${minutes} 分`;
}

function isStale(r) {
  return r.state === "recording" && Boolean(r.last_message_at)
    && Date.now() / 1000 - Number(r.last_message_at) > STALE_SECONDS;
}

function stateBadge(r) {
  const label = (STATE_LABEL[r.state] || r.state) + (isStale(r) ? "（可能已中断）" : "");
  return `<span class="trpg-badge is-${escapeHtml(r.state)}">${escapeHtml(label)}</span>`;
}

function personChip(p) {
  const name = p.char_name ? `${p.char_name}（${p.nickname || p.user_id}）` : (p.nickname || p.user_id);
  const role = ROLE_LABEL[p.role]
    ? `<span class="trpg-role role-${escapeHtml(p.role)}">${ROLE_LABEL[p.role]}</span>`
    : "";
  return `<span class="trpg-person">${escapeHtml(name)}${role}</span>`;
}

function recordCard(r) {
  const meta = [r.start, durationText(r), `${r.message_count} 条消息`].filter(Boolean).join(" · ");
  const href = `/trpg/records/${encodeURIComponent(r.group_id)}/${encodeURIComponent(r.start_dir)}`;
  return `
    <a class="trpg-card" data-reveal href="${href}">
      <div class="trpg-card-head">
        <strong>${escapeHtml(r.group_name || `团 ${r.group_id}`)}</strong>
        ${stateBadge(r)}
        ${r.is_mine ? '<span class="trpg-person member-me">我参加的</span>' : ""}
      </div>
      <p class="trpg-meta">${escapeHtml(meta)}</p>
      <div class="trpg-people">${(r.participants || []).map(personChip).join("")}</div>
    </a>`;
}

function renderList(records) {
  if (!records.length) {
    listEl.innerHTML = '<p class="empty-hint center">还没有跑团记录；群内由 DM 发送 /跑团 记录 开始 即可开始录制</p>';
    return;
  }
  listEl.innerHTML = records.map(recordCard).join("");
}

async function load() {
  const query = mineToggle.checked ? "?mine=1" : "";
  try {
    const res = await fetch(`/api/trpg/records${query}`, { headers: GalleryAuth.headers() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "加载失败");
    renderList(data.records || []);
  } catch (err) {
    listEl.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message || "加载失败")}</p>`;
  }
}

mineToggle.addEventListener("change", load);
GalleryAuth.renderAuth(document.getElementById("authArea"));
GalleryAuth.refreshMe().finally(load);
