const mainEl = document.getElementById("detailMain");
const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
const MEMBER_STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出", pending: "未完成" };
const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderAuthChip() {
  const session = GalleryAuth.load();
  const area = document.getElementById("authArea");
  if (!session) return;
  area.innerHTML = "";
  const link = document.createElement("a");
  link.className = "user-chip";
  link.href = "/profile";
  const img = document.createElement("img");
  img.src = session.avatar_url || "";
  img.alt = session.display_name;
  img.onerror = () => { img.style.display = "none"; };
  const wrap = document.createElement("span");
  wrap.innerHTML = `<strong>${escapeHtml(session.display_name)}</strong><br><span class="uid">${session.user_id}</span>`;
  link.append(img, wrap);
  area.appendChild(link);
}

function statusBadge(status) {
  const cls = status === "open" ? "badge-open" : status === "running" ? "badge-running"
    : status === "finished" ? "badge-done" : "badge-cancelled";
  return `<span class="status-badge ${cls}">${STATUS_LABEL[status] || status}</span>`;
}

function formatHours(h) {
  h = Number(h);
  return h % 24 === 0 ? `${h / 24} 天` : `${h} 小时`;
}

function infoRow(label, value) {
  return `<tr><td>${label}</td><td>${value}</td></tr>`;
}

function remainingText(member, act) {
  const start = new Date(member.received_at.replace(" ", "T"));
  const hours = Number(act.hours_per_user) || 0;
  const end = start.getTime() + hours * 3600 * 1000;
  const remainMs = end - Date.now();
  if (remainMs <= 0) return '<span class="countdown">已超时，等待跳过</span>';
  const totalMin = Math.floor(remainMs / 60000);
  const h = Math.floor(totalMin / 60);
  const min = totalMin % 60;
  return `<span class="countdown">剩余 ${h} 小时 ${min} 分</span>`;
}

let actCache = null;

function renderCountdown() {
  if (!actCache || actCache.status !== "running" || actCache.type !== "relay") return;
  const cur = actCache.members.find(m => m.status === "pending");
  if (!cur) return;
  const el = document.getElementById("turnCountdown");
  if (el) el.innerHTML = remainingText(cur, actCache);
}

async function loadDetail() {
  const id = location.pathname.split("/").pop();
  const res = await fetch(`/api/activities/${id}`);
  if (!res.ok) {
    mainEl.innerHTML = '<p class="muted">活动不存在</p>';
    return;
  }
  const act = await res.json();
  actCache = act;
  const session = GalleryAuth.load();
  const myUid = session && session.user_id;
  const nickOf = {};
  for (const m of act.members) nickOf[m.user_id] = m.nickname;
  const isRunning = act.status === "running";

  const rows = [
    infoRow("标题", `<strong>${escapeHtml(act.title)}</strong>${statusBadge(act.status)}`),
    infoRow("类型", TYPE_LABEL[act.type] || act.type),
    infoRow("发起时间", escapeHtml(act.created_at || "-")),
    infoRow("报名结束", escapeHtml(act.signup_deadline || "—")),
    infoRow("截止时间", escapeHtml(act.deadline || "—")),
    infoRow("当前状态", STATUS_LABEL[act.status] || act.status),
    infoRow("详情", escapeHtml(act.description || "—")),
    infoRow("参加人员", `${act.members.length} 人`),
  ];
  if (act.type === "relay" && act.hours_per_user) {
    rows.push(infoRow("每人限时", formatHours(act.hours_per_user)));
  }

  let turnBlock = "";
  if (isRunning && act.type === "relay") {
    const cur = act.members.find(m => m.status === "pending");
    if (cur) {
      turnBlock = `
        <div class="turn-highlight">
          当前轮到：<strong>${escapeHtml(cur.nickname)}</strong>
          ${cur.user_id === myUid ? "（我）" : ""} ·
          <span id="turnCountdown">${remainingText(cur, act)}</span>
        </div>`;
    }
  }

  let memberRows = act.members.map(m => {
    const isMe = m.user_id === myUid;
    let next = "";
    if (isRunning && act.type === "match" && m.next_user_id) {
      const label = nickOf[m.next_user_id] || m.next_user_id;
      next = `<span class="member-next">下家：${escapeHtml(label)}</span>`;
    }
    return `
      <div class="member-row ${isMe ? "member-me" : ""}">
        <span class="seq">${m.seq}.</span>
        <span>${escapeHtml(m.nickname)}${isMe ? "（我）" : ""}</span>
        <span title="${escapeHtml(MEMBER_STATUS_LABEL[m.status] || m.status)}">
          ${MEMBER_STATUS_ICON[m.status] || ""}
        </span>
        ${next}
      </div>`;
  }).join("");

  let worksBlock = "";
  if (act.status === "finished") {
    worksBlock = `
      <section class="detail-section">
        <h2>作品</h2>
        ${act.members.map(m => `
          <div class="work-block">
            <h3>${escapeHtml(m.nickname)}（${m.user_id}）· ${MEMBER_STATUS_LABEL[m.status] || m.status}</h3>
            ${m.submitted_at ? `<div class="muted">${m.submitted_at}</div>` : ""}
            ${m.content ? `<p class="work-content">${escapeHtml(m.content).replace(/\n/g, "<br>")}</p>` : ""}
            ${m.images.map(u => `<img class="work-img" src="${u}">`).join("")}
          </div>`).join("")}
      </section>`;
  }

  mainEl.innerHTML = `
    <section class="detail-section">
      <h2>活动信息</h2>
      <div class="activity-card">
        <table class="info-table">${rows.join("")}</table>
      </div>
    </section>
    ${turnBlock ? `<section class="detail-section">${turnBlock}</section>` : ""}
    <section class="detail-section">
      <h2>参加人员</h2>
      <div class="member-list">${memberRows}</div>
    </section>
    ${worksBlock}`;
  if (isRunning && act.type === "relay") {
    setInterval(renderCountdown, 60000);
  }
}

renderAuthChip();
loadDetail();
