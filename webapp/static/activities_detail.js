const mainEl = document.getElementById("detailMain");
const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
const MEMBER_STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出", pending: "未完成" };
const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
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
let meCache = null;
const REASON_TEXT = {
  not_started: "活动未开始，开始后才能提交",
  finished: "活动已结束",
  missed: "已截止或被跳过，无法提交",
  left: "你已退出活动",
  not_my_turn: "还未轮到你提交",
};

function mySubmissionBlock(me) {
  if (!me || !me.member) return "";
  const m = me.member;
  return `
    <section class="detail-section">
      <h2>我的提交${m.status === "done" ? "（已提交，可更新）" : ""}</h2>
      ${m.submitted_at ? `<div class="muted">${m.submitted_at}</div>` : ""}
      ${m.content ? `<p class="work-content">${escapeHtml(m.content)}</p>` : ""}
      ${m.images.map((u) => `<img class="work-img" src="${u}">`).join("")}
      ${m.status === "pending" && me.can_submit ? '<div class="muted">尚未提交</div>' : ""}
    </section>`;
}

function submitBlock(me) {
  if (!me || !me.member) return "";
  if (!me.can_submit) {
    return `
    <section class="detail-section">
      <h2>提交作品</h2>
      <p class="muted">${escapeHtml(me.block_text || REASON_TEXT[me.block_reason] || "当前无法提交")}</p>
    </section>`;
  }
  return `
    <section class="detail-section">
      <h2>提交作品</h2>
      <textarea id="myContent" class="work-input" rows="3" maxlength="2000"
        placeholder="作品文字（与图片至少一项）">${escapeHtml(me.member.content || "")}</textarea>
      <input type="file" id="myFiles" class="work-input" accept="image/*" multiple />
      <div class="submit-row">
        <button type="button" id="submitBtn" class="primary">提交</button>
        <span id="submitHint" class="muted"></span>
      </div>
    </section>`;
}

async function submitWork() {
  const btn = document.getElementById("submitBtn");
  const hint = document.getElementById("submitHint");
  const content = (document.getElementById("myContent")?.value || "").trim();
  const files = document.getElementById("myFiles")?.files || [];
  if (!content && !files.length) { hint.textContent = "请附上作品（文字或图片）"; return; }
  const fd = new FormData();
  fd.append("content", content);
  for (const f of files) fd.append("files", f);
  btn.disabled = true;
  btn.textContent = "提交中…";
  try {
    const res = await fetch(`/api/activities/${actCache.id}/submit`, {
      method: "POST", headers: GalleryAuth.headers(), body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "提交失败");
    hint.textContent = data.updated ? "已更新提交" : "提交成功";
    await loadDetail();
  } catch (err) {
    hint.textContent = err.message || "提交失败";
  } finally {
    btn.disabled = false;
    btn.textContent = "提交";
  }
}

function renderCountdown() {
  if (!actCache || actCache.status !== "running" || actCache.type !== "relay") return;
  const cur = actCache.members.find(m => m.status === "pending");
  // received_at 为空 = 网页提交后等待心跳补推进的窗口，无倒计时可言
  if (!cur || !cur.received_at) return;
  const el = document.getElementById("turnCountdown");
  if (el) el.innerHTML = remainingText(cur, actCache);
}

async function loadDetail() {
  const id = location.pathname.split("/").pop();
  const [res, meRes] = await Promise.all([
    fetch(`/api/activities/${id}`, { headers: GalleryAuth.headers() }),
    fetch(`/api/activities/${id}/me`, { headers: GalleryAuth.headers() }),
  ]);
  if (!res.ok) {
    mainEl.innerHTML = '<p class="muted">活动不存在</p>';
    return;
  }
  actCache = await res.json();
  meCache = meRes.ok ? await meRes.json()
    : { member: null, can_submit: false, block_reason: "not_member" };
  renderDetail();
}

function renderDetail() {
  const act = actCache;
  const session = GalleryAuth.load();
  const myUid = session && session.user_id;
  const nickOf = {};
  for (const m of act.members) nickOf[m.user_id] = m.nickname;
  const isRunning = act.status === "running";
  // 1057613133=SUPER_USER，与 core/base.py 及 activities_manage.js 同步
  const isOwner = session && myUid && (String(act.created_by) === String(myUid) || String(myUid) === "1057613133");

  const rows = [
    infoRow("标题", `<strong>${escapeHtml(act.title)}</strong>${statusBadge(act.status)}`
      + (isOwner && (act.status === "open" || act.status === "running")
        ? ` <a href="/activities/${act.id}/manage">管理</a>` : "")),
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
    // received_at 为空 = 网页提交后等待心跳补推进的窗口，不渲染倒计时
    if (cur && cur.received_at) {
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
    ${mySubmissionBlock(meCache)}
    ${submitBlock(meCache)}
    ${worksBlock}`;
  const sb = document.getElementById("submitBtn");
  if (sb) sb.addEventListener("click", submitWork);
  if (isRunning && act.type === "relay") {
    setInterval(renderCountdown, 60000);
  }
}

GalleryAuth.renderAuth(document.getElementById("authArea"));
loadDetail();
