const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
const MEMBER_STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出", pending: "未完成" };
const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };

const myEl = document.getElementById("myActivities");
const activeEl = document.getElementById("activeActivities");
const archiveEl = document.getElementById("archiveActivities");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}



function formatHours(h) {
  h = Number(h);
  return h % 24 === 0 ? `${h / 24} 天` : `${h} 小时`;
}

function statusBadge(status) {
  const cls = status === "open" ? "badge-open" : status === "running" ? "badge-running"
    : status === "finished" ? "badge-done" : "badge-cancelled";
  return `<span class="status-badge ${cls}">${STATUS_LABEL[status] || status}</span>`;
}

function progressText(a) {
  return `${a.done_count}/${a.member_count} 人完成`;
}

async function loadMyActivities() {
  if (!GalleryAuth.isLoggedIn()) {
    myEl.innerHTML = "<p class=\"muted\">登录后可查看你参加的活动</p>";
    return;
  }
  try {
    const res = await fetch("/api/me/activities", { headers: GalleryAuth.headers() });
    if (!res.ok) {
      myEl.innerHTML = "<p class=\"muted\">登录状态失效，请重新登录</p>";
      return;
    }
    const { items } = await res.json();
    myEl.innerHTML = items.length ? items.map(a => `
      <div class="activity-card" data-reveal>
        <div class="activity-card-head">
          <strong>${escapeHtml(a.title)}</strong>（${TYPE_LABEL[a.type] || a.type}）
          ${statusBadge(a.status)}
        </div>
        <div class="muted">我的状态：${MEMBER_STATUS_LABEL[a.my_status] || a.my_status} · ${progressText(a)}</div>
        ${a.my_status === "pending" && a.status === "running"
          ? "<div class=\"activity-todo\">你还有作品未提交，请私聊机器人 /提交</div>" : ""}
      </div>`).join("") : "<p class=\"muted\">你还没有参加过活动</p>";
  } catch {
    myEl.innerHTML = "<p class=\"muted\">加载失败</p>";
  }
}

async function loadActiveActivities() {
  const res = await fetch("/api/activities");
  const { items } = await res.json();
  const active = items.filter(a => a.status === "open" || a.status === "running");
  if (!active.length) {
    activeEl.innerHTML = "<p class=\"muted\">暂无进行中的活动</p>";
    return;
  }
  const session = GalleryAuth.load();
  const myUid = session && session.user_id;
  activeEl.innerHTML = active.map(a => `
    <a class="activity-card activity-link" data-reveal href="/activities/${a.id}">
      <div class="activity-card-head">
        <strong>${escapeHtml(a.title)}</strong>（${TYPE_LABEL[a.type] || a.type}）
        ${statusBadge(a.status)}
        <span class="activity-progress">${progressText(a)}</span>
      </div>
      ${a.description ? `<div class="activity-desc">${escapeHtml(a.description)}</div>` : ""}
      <div class="muted">
        ${a.signup_deadline ? `报名截止：${a.signup_deadline}` : ""}
        ${a.signup_deadline && a.deadline ? " · " : ""}
        ${a.deadline ? `截止：${a.deadline}` : ""}
      </div>
      ${a.type === "relay" && a.hours_per_user ? `<div class="muted">每人限时：${formatHours(a.hours_per_user)}</div>` : ""}
      <div class="member-list">
        ${a.members.map(m => `
          <span class="member-chip ${m.user_id === myUid ? "member-me" : ""}" title="${escapeHtml(MEMBER_STATUS_LABEL[m.status] || m.status)}">
            ${m.seq}. ${escapeHtml(m.nickname)} ${MEMBER_STATUS_ICON[m.status] || ""}${m.user_id === myUid ? "（我）" : ""}
          </span>`).join("")}
      </div>
    </a>`).join("");
}

async function loadArchiveActivities() {
  const res = await fetch("/api/activities");
  const { items } = await res.json();
  const archived = items.filter(a => a.status === "finished");
  archiveEl.innerHTML = archived.length ? archived.map(a => `
    <a class="activity-card activity-link" data-reveal href="/activities/${a.id}">
      <div class="activity-card-head">
        <strong>${escapeHtml(a.title)}</strong>（${TYPE_LABEL[a.type] || a.type}）
        ${statusBadge(a.status)}
        <span class="activity-progress">${progressText(a)}</span>
      </div>
      <div class="muted">${a.created_at} ~ ${a.finished_at}</div>
    </a>`).join("") : "<p class=\"muted\">暂无归档活动</p>";
}

GalleryAuth.renderAuth(document.getElementById("authArea"));
loadMyActivities();
loadActiveActivities();
loadArchiveActivities();
