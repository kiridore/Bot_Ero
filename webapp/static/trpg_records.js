// 跑团记录列表：按开始时间倒序，可只看自己参加的记录。
const listEl = document.getElementById("recordList");
const partySection = document.getElementById("partySection");
const partyList = document.getElementById("partyList");
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

const ROLE_LABEL = { dm: "DM", ob: "观察者" };

function partyMemberRow(party, member) {
  const role = member.role ? ROLE_LABEL[member.role] || member.role : "";
  const badge = role ? `<span class="trpg-role role-${escapeHtml(member.role)}">${escapeHtml(role)}</span>` : "";
  const name = `<span class="trpg-party-name">${escapeHtml(member.nickname)}${badge}</span>` +
    `<span class="trpg-party-char">${escapeHtml(member.char_name || "未选角色卡")}</span>`;
  if (member.char_id == null) {
    return `<div class="trpg-party-member">${name}<span class="trpg-party-hint">等待准备</span></div>`;
  }
  // 整行可点：只做成小按钮时玩家会去点名字，感觉「点不开」
  const href = `/trpg/char/${encodeURIComponent(member.user_id)}/` +
    `${encodeURIComponent(member.char_id)}?party=${encodeURIComponent(party.group_id)}`;
  return `<a class="trpg-party-member is-link" href="${href}">${name}` +
    `<span class="btn-sm">查看角色卡</span></a>`;
}

function partyCard(party) {
  const partyTitle = party.group_name || `群 ${party.group_id}`;
  const head = `${escapeHtml(partyTitle)} · ${escapeHtml(party.rules_name)} · ` +
    `DM ${escapeHtml(party.dm_name || party.dm)} · 已准备 ${party.prepared_count}/${party.member_count}`;
  let review = "";
  if (party.is_dm) {
    review = '<p class="trpg-party-hint">你是本群 DM，可点开每张角色卡审核</p>';
  } else if (party.is_super) {
    review = '<p class="trpg-party-hint">你是超级用户，可点开每张角色卡审核</p>';
  }
  return `
    <div class="trpg-party">
      <div class="trpg-row-head"><strong>${escapeHtml(partyTitle)}</strong>
        <span class="trpg-badge is-recording">准备中</span></div>
      <p class="trpg-row-meta">${head}</p>
      ${review}
      <div class="trpg-party-members">${(party.members || []).map((m) => partyMemberRow(party, m)).join("")}</div>
    </div>`;
}

function renderParties(parties) {
  if (!partySection || !partyList) return;
  const list = parties || [];
  partySection.hidden = list.length === 0;
  partyList.innerHTML = list.map(partyCard).join("");
}

async function loadParties() {
  if (!partySection) return;
  try {
    const res = await fetch("/api/trpg/parties", { headers: GalleryAuth.headers() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "加载失败");
    renderParties(data.parties || []);
  } catch (err) {
    partySection.hidden = false;
    partyList.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message || "加载失败")}</p>`;
  }
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
GalleryAuth.refreshMe().finally(() => {
  loadParties();
  load();
});
