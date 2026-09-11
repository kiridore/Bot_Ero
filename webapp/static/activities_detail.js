const mainEl = document.getElementById("detailMain");
const TYPE_LABEL = { relay: "接龙", match: "匹配下家", collect: "征集" };
const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
const MEMBER_STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出", pending: "未完成" };
const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}



function richDescHtml(desc) {
  // TipTap JSON → HTML；历史纯文本（JSON 解析失败）兜底转义展示
  let doc = null;
  try { doc = JSON.parse(desc); } catch (_) { /* 历史纯文本 */ }
  if (!doc || !doc.type) return escapeHtml(desc);
  return RichText.render(doc);
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
      ${m.images.length ? `<div class="img-grid">${m.images.map((u) => imgCard(u, undefined, false)).join("")}</div>` : ""}
      ${m.status === "pending" && me.can_submit ? '<div class="muted">尚未提交</div>' : ""}
    </section>`;
}

// 方形缩略图卡片；name 用于已传图的 removed 标识，deletable 控制右上角删除键
function imgCard(src, name, deletable) {
  const dn = name !== undefined ? ` data-name="${escapeHtml(name)}"` : "";
  return `<div class="img-card"${dn}><img src="${escapeHtml(src)}" alt="">`
    + (deletable ? `<button type="button" class="img-del" aria-label="移除图片">×</button>` : "")
    + `</div>`;
}

var pendingRemovals = new Set();  // 已传图待删除文件名（提交时生效）
var pendingImages = [];  // 新选图 {file, url}，提交时 append 到末尾

function renderPreviewGrid() {
  const grid = document.getElementById("previewImages");
  if (!grid) return;
  grid.innerHTML = pendingImages.map((p, i) =>
    `<div class="img-card" data-idx="${i}"><img src="${escapeHtml(p.url)}" alt="">`
    + `<button type="button" class="img-del" aria-label="移除图片">×</button></div>`).join("");
}

function onFilesPicked(e) {
  for (const f of (e.target.files || [])) {
    if (!f) continue;
    pendingImages.push({ file: f, url: URL.createObjectURL(f) });
  }
  e.target.value = "";
  renderPreviewGrid();
}

function onCardClick(e) {
  const btn = e.target.closest(".img-del");
  if (!btn) return;
  const card = btn.closest(".img-card");
  const grid = card.parentElement;
  if (grid.id === "previewImages") {
    const [removed] = pendingImages.splice(Number(card.dataset.idx), 1);
    if (removed) URL.revokeObjectURL(removed.url);
    renderPreviewGrid();
  } else if (grid.id === "savedImages") {
    pendingRemovals.add(card.dataset.name);
    grid.removeChild(card);
  }
}

function resetPendingState() {
  for (const p of pendingImages) URL.revokeObjectURL(p.url);
  pendingImages = [];
  pendingRemovals = new Set();
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
  const existing = me.member.images || [];
  return `
    <section class="detail-section">
      <h2>提交作品</h2>
      <textarea id="myContent" class="work-input" rows="3" maxlength="2000"
        placeholder="作品文字（与图片至少一项）">${escapeHtml(me.member.content || "")}</textarea>
      <input type="file" id="myFiles" class="work-input" accept="image/*" multiple />
      ${existing.length
        ? `<div class="muted" style="margin-top:8px">已上传（点 × 移除，提交时生效）</div>`
          + `<div class="img-grid" id="savedImages">`
          + existing.map((u) => imgCard(u, u.split("/").pop(), true)).join("")
          + `</div>`
        : ""}
      <div class="img-grid" id="previewImages"></div>
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
  if (!content && !pendingImages.length && !pendingRemovals.size) {
    hint.textContent = "请附上作品（文字或图片）"; return;
  }
  const fd = new FormData();
  fd.append("content", content);
  // 增量语义：新图 append 到末尾、removed 单独移除（均提交时生效）；文本总是随表单提交
  for (const p of pendingImages) fd.append("files", p.file);
  for (const name of pendingRemovals) fd.append("removed", name);
  btn.disabled = true;
  btn.textContent = "提交中…";
  try {
    const res = await fetch(`/api/activities/${actCache.id}/submit`, {
      method: "POST", headers: GalleryAuth.headers(), body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "提交失败");
    hint.textContent = data.updated ? "已更新提交" : "提交成功";
    resetPendingState();
    await loadDetail();
  } catch (err) {
    hint.textContent = err.message || "提交失败";
  } finally {
    btn.disabled = false;
    btn.textContent = "提交";
  }
}

function buildShareNode(act) {
  // 离屏克隆：固定 720px 宽浅色报纸风（不跟随暗色主题），内联样式自包含。
  // 色值与 base.css 浅色主题 --paper/--ink 同源。
  const wrap = document.createElement("div");
  wrap.style.cssText = "width:720px;padding:28px;box-sizing:border-box;background:#f5efe0;color:#2c2a24";
  const head = `
    <div style="border-bottom:2px solid #2c2a24;padding-bottom:14px;margin-bottom:18px;">
      <div style="font-size:26px;font-weight:700;">${escapeHtml(act.title)}</div>
      <div style="margin-top:8px;font-size:14px;opacity:.75;">
        ${TYPE_LABEL[act.type] || act.type} · ${escapeHtml(act.created_at || "")} ~ ${escapeHtml(act.finished_at || "")} · ${act.members.length} 人
      </div>
    </div>`;
  const works = act.members.map((m) => `
    <div style="margin:0 0 22px;padding:14px;background:#fffdf4;border:1px solid #e4dcc6;border-radius:8px;">
      <div style="font-size:15px;font-weight:700;">
        ${escapeHtml(m.nickname)}（${escapeHtml(String(m.user_id))}）· ${MEMBER_STATUS_LABEL[m.status] || m.status}
        ${m.submitted_at ? `<span style="font-weight:400;opacity:.6;"> · ${escapeHtml(m.submitted_at)}</span>` : ""}
      </div>
      ${m.content ? `<div style="margin-top:8px;font-size:14px;white-space:pre-wrap;">${escapeHtml(m.content)}</div>` : ""}
      ${m.images.map((u) => `<img src="${u}" style="display:block;max-width:100%;border-radius:6px;margin-top:8px;">`).join("")}
    </div>`).join("");
  wrap.innerHTML = head + works;
  document.body.appendChild(wrap);
  return wrap;
}

async function downloadShareImage() {
  const btn = document.getElementById("shareBtn");
  if (btn) { btn.disabled = true; btn.textContent = "生成中…"; }
  let node = null;
  try {
    node = buildShareNode(actCache);
    // ponytail: pixelRatio 1（720px 宽）——iOS Safari canvas 面积上限 ~16.7M px，图片很多的长活动下 ratio>1 会碰顶；需要更清晰时再分片拼接
    const dataUrl = await htmlToImage.toPng(node, { pixelRatio: 1, backgroundColor: "#f5efe0" });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `activity-${actCache.id}.png`;
    a.click();
  } catch (err) {
    alert(`生成长图失败：${(err && err.message) || err}`);
  } finally {
    if (node) node.remove();
    if (btn) { btn.disabled = false; btn.textContent = "生成分享长图"; }
  }
}

async function joinActivity() {
  const btn = document.getElementById("joinBtn");
  if (btn) btn.disabled = true;
  try {
    const res = await fetch(`/api/activities/${actCache.id}/join`, {
      method: "POST", headers: GalleryAuth.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "加入失败");
    await loadDetail();
  } catch (err) {
    alert(err.message || "加入失败");
    if (btn) btn.disabled = false;
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
    infoRow("详情", act.description ? richDescHtml(act.description) : "—"),
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
        <div class="works-head">
          <h2>作品</h2>
          <button type="button" id="shareBtn" class="primary">生成分享长图</button>
        </div>
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
      <div class="works-head">
        <h2>参加人员</h2>
        ${act.status === "open" && !(meCache && meCache.member)
          ? '<button type="button" id="joinBtn" class="primary">加入活动</button>' : ""}
      </div>
      <div class="member-list">${memberRows}</div>
    </section>
    ${mySubmissionBlock(meCache)}
    ${submitBlock(meCache)}
    ${worksBlock}`;
  const sb = document.getElementById("submitBtn");
  if (sb) sb.addEventListener("click", submitWork);
  const myFiles = document.getElementById("myFiles");
  if (myFiles) myFiles.addEventListener("change", onFilesPicked);
  const savedGrid = document.getElementById("savedImages");
  if (savedGrid) savedGrid.addEventListener("click", onCardClick);
  const prevGrid = document.getElementById("previewImages");
  if (prevGrid) prevGrid.addEventListener("click", onCardClick);
  const shb = document.getElementById("shareBtn");
  if (shb) shb.addEventListener("click", downloadShareImage);
  const jb = document.getElementById("joinBtn");
  if (jb) jb.addEventListener("click", joinActivity);
  if (isRunning && act.type === "relay") {
    setInterval(renderCountdown, 60000);
  }
}

GalleryAuth.renderAuth(document.getElementById("authArea"));
loadDetail();
