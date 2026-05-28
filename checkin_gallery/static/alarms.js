const alarmsMain = document.getElementById("alarmsMain");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    window.location.href = "/";
    return false;
  }
  return true;
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

function showToast(msg, isError = false) {
  let toast = document.getElementById("alarmsToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "alarmsToast";
    toast.className = "settings-toast";
    alarmsMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function renderCreateForm(usageHint) {
  const section = document.createElement("section");
  section.className = "alarm-form settings-section";
  section.innerHTML = `
    <h2>新建闹钟</h2>
    <p class="preview-hint">${escapeHtml(usageHint)}</p>
    <textarea id="alarmBody" class="alarm-input" rows="3" placeholder="例如：每天 8:00 起床"></textarea>
    <div class="alarm-actions">
      <button type="button" class="btn-sm primary" id="alarmCreateBtn">创建</button>
    </div>
  `;
  section.querySelector("#alarmCreateBtn").addEventListener("click", createAlarm);
  return section;
}

function renderAlarmList(items) {
  const section = document.createElement("section");
  section.className = "settings-section";
  section.innerHTML = "<h2>待触发闹钟</h2>";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-hint center";
    empty.textContent = "你还没有待触发的闹钟";
    section.appendChild(empty);
    return section;
  }

  const list = document.createElement("div");
  list.className = "alarm-list";

  for (const item of items) {
    const card = document.createElement("article");
    card.className = "alarm-item";

    const metaParts = [`#${item.id}`, item.scope];
    if (item.recur_desc) metaParts.push(item.recur_desc);
    metaParts.push(item.fire_at);

    card.innerHTML = `
      <div class="alarm-item-main">
        <p class="alarm-meta">${escapeHtml(metaParts.join(" · "))}</p>
        <p class="alarm-content">${escapeHtml(item.content)}</p>
      </div>
    `;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-sm";
    btn.textContent = "取消";
    btn.addEventListener("click", () => cancelAlarm(item.id, btn));
    card.appendChild(btn);
    list.appendChild(card);
  }

  section.appendChild(list);
  return section;
}

function renderAlarms(data) {
  alarmsMain.innerHTML = "";
  alarmsMain.appendChild(renderCreateForm(data.usage_hint));
  alarmsMain.appendChild(renderAlarmList(data.items));
}

async function loadAlarms() {
  alarmsMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  const res = await fetch("/api/me/alarms", { headers: GalleryAuth.headers() });
  if (res.status === 401) {
    GalleryAuth.clear();
    window.location.href = "/";
    return;
  }
  if (!res.ok) {
    alarmsMain.innerHTML = "<p class='loading-msg error'>加载失败</p>";
    return;
  }
  renderAlarms(await res.json());
}

async function createAlarm() {
  const input = document.getElementById("alarmBody");
  const btn = document.getElementById("alarmCreateBtn");
  const body = (input.value || "").trim();
  if (!body) {
    showToast("请填写闹钟内容", true);
    return;
  }
  btn.disabled = true;
  btn.textContent = "创建中…";
  try {
    const res = await fetch("/api/me/alarms", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ body }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "创建失败");
    input.value = "";
    showToast(data.message || "创建成功");
    await loadAlarms();
  } catch (err) {
    showToast(err.message || "创建失败", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "创建";
  }
}

async function cancelAlarm(alarmId, btn) {
  if (!confirm(`确定取消闹钟 #${alarmId}？`)) return;
  btn.disabled = true;
  btn.textContent = "取消中…";
  try {
    const res = await fetch(`/api/me/alarms/${alarmId}`, {
      method: "DELETE",
      headers: GalleryAuth.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "取消失败");
    showToast(data.message || "已取消");
    await loadAlarms();
  } catch (err) {
    showToast(err.message || "取消失败", true);
    btn.disabled = false;
    btn.textContent = "取消";
  }
}

if (requireAuth()) {
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    loadAlarms();
  });
}
