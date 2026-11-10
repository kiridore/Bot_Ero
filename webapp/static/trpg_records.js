// 跑团记录列表：按开始时间倒序，可只看自己参加的记录。
const listEl = document.getElementById("recordList");
const mineToggle = document.getElementById("mineOnly");

const STATE_LABEL = { recording: "录制中", ended: "已结束" };

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function parseTime(text) {
  return text ? new Date(String(text).replace(" ", "T")).getTime() : NaN;
}

function stateBadge(r) {
  const label = STATE_LABEL[r.state] || r.state;
  return `<span class="trpg-badge is-${escapeHtml(r.state)}">${escapeHtml(label)}</span>`;
}

function myIdentity(r) {
  const mine = r.my_role || {};
  if (!mine.role) return "未参与";
  if (mine.role === "dm") return "我的身份：DM";
  if (mine.role === "ob") return "我的身份：观察者";
  return mine.char_name ? `我的身份：${mine.char_name}（玩家）` : "我的身份：玩家";
}

function timeRange(r) {
  const start = r.start || "";
  return r.end ? `${start} — ${r.end}` : `${start} — 进行中`;
}

function recordRow(r) {
  const href = `/trpg/records/${encodeURIComponent(r.group_id)}/${encodeURIComponent(r.start_dir)}`;
  const details = [
    timeRange(r),
    `${r.player_count || 0} 人`,
    myIdentity(r),
    r.rules_name || "未知规则",
    `${r.message_count || 0} 条消息`,
  ].join(" · ");
  return `
    <a class="trpg-row" data-reveal href="${href}">
      <div class="trpg-row-head">
        <strong>${escapeHtml(r.group_name || `团 ${r.group_id}`)}</strong>
        ${stateBadge(r)}
      </div>
      <p class="trpg-row-meta">${escapeHtml(details)}</p>
    </a>`;
}

function renderList(records) {
  if (!records.length) {
    listEl.innerHTML = '<p class="empty-hint center">还没有跑团记录；群内由 DM 发送 /跑团 记录 开始 即可开始录制</p>';
    return;
  }
  listEl.innerHTML = records.map(recordRow).join("");
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
