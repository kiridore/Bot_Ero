const listEl = document.getElementById("activity-list");
const detailEl = document.getElementById("activity-detail");
const TYPE_LABEL = { relay: "接龙", match: "匹配下家" };
const STATUS_LABEL = { done: "已完成", skipped: "超时跳过", missed: "未提交", left: "已退出" };

async function loadList() {
  const res = await fetch("/api/activities");
  const { items } = await res.json();
  listEl.innerHTML = items.map(a => `
    <div class="activity-card" onclick="showDetail(${a.id})">
      <strong>${a.title}</strong>（${TYPE_LABEL[a.type] || a.type}）
      <span>${a.done_count}/${a.member_count} 人完成</span>
      <div class="muted">${a.created_at} ~ ${a.finished_at}</div>
    </div>`).join("") || "<p>暂无归档活动</p>";
}

async function showDetail(id) {
  const res = await fetch(`/api/activities/${id}`);
  const act = await res.json();
  detailEl.hidden = false;
  detailEl.innerHTML = `
    <h2>${act.title}</h2>
    <div class="muted">${TYPE_LABEL[act.type]} · ${act.created_at} ~ ${act.finished_at}</div>
    ${act.theme ? `<p>主题：${act.theme}</p>` : ""}
    ${act.members.map(m => `
      <section class="work-block">
        <h3>${m.nickname}（${m.user_id}）· ${STATUS_LABEL[m.status] || m.status}</h3>
        ${m.submitted_at ? `<div class="muted">${m.submitted_at}</div>` : ""}
        ${m.content ? `<p class="work-content">${m.content.replace(/\n/g, "<br>")}</p>` : ""}
        ${m.images.map(u => `<img class="work-img" src="${u}">`).join("")}
      </section>`).join("")}
    <button onclick="closeDetail()">返回列表</button>`;
}

function closeDetail() { detailEl.hidden = true; }

loadList();
