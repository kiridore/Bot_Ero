const settingsMain = document.getElementById("settingsMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

let settingsData = null;
let userSettingsData = { privacy: {} };
let searchQuery = "";

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  loginDialog.showModal();
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    settingsMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
    openLoginDialog();
    return false;
  }
  return true;
}

function renderAuthChip() {
  const area = document.getElementById("authArea");
  if (!area) return;
  area.innerHTML = "";
  const session = GalleryAuth.load();
  if (!session || !session.token) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-login";
    btn.textContent = "登录";
    btn.addEventListener("click", openLoginDialog);
    area.appendChild(btn);
    return;
  }
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

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...GalleryAuth.headers(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    GalleryAuth.clear();
    requireAuth();
    throw new Error("未登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || "操作失败");
  }
  return data;
}

function showToast(msg, isError = false) {
  let toast = document.getElementById("settingsToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "settingsToast";
    toast.className = "settings-toast";
    settingsMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 2800);
}

function renderEquippedSlots() {
  const box = document.createElement("div");
  box.className = "equipped-slots";
  const max = settingsData.max_equipped;
  for (let slot = 1; slot <= max; slot++) {
    const item = settingsData.equipped.find((t) => t.slot === slot);
    const card = document.createElement("div");
    card.className = `equipped-slot${item ? " filled" : ""}`;
    if (item) {
      card.innerHTML = `
        <span class="slot-label">槽位 ${slot}</span>
        <strong>「${escapeHtml(item.name)}」</strong>
        <span class="rarity">${escapeHtml(item.rarity)}</span>
        <button type="button" class="btn-sm danger" data-unequip="${item.id}">卸下</button>
      `;
    } else {
      card.innerHTML = `<span class="slot-label">槽位 ${slot}</span><span class="empty-hint">空</span>`;
    }
    box.appendChild(card);
  }
  box.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-unequip]");
    if (!btn) return;
    try {
      settingsData = await apiFetch(`/api/me/titles/equip/${btn.dataset.unequip}`, { method: "DELETE" });
      renderPage();
      showToast("已卸下称号");
    } catch (err) {
      showToast(err.message, true);
    }
  });
  return box;
}

function renderUnlockedList() {
  const list = document.createElement("div");
  list.className = "settings-title-list";
  const q = searchQuery.trim().toLowerCase();
  const filtered = settingsData.unlocked.filter((t) => {
    if (!q) return true;
    return (
      String(t.id).includes(q) ||
      t.name.toLowerCase().includes(q) ||
      t.rarity.toLowerCase().includes(q)
    );
  });

  if (!filtered.length) {
    list.innerHTML = "<p class='empty-hint center'>没有匹配的称号</p>";
    return list;
  }

  const equippedCount = settingsData.equipped.length;
  const full = equippedCount >= settingsData.max_equipped;

  for (const t of filtered) {
    const row = document.createElement("article");
    row.className = `settings-title-row${t.equipped ? " is-equipped" : ""}`;
    row.innerHTML = `
      <div class="row-main">
        <strong>[${t.id}] 「${escapeHtml(t.name)}」</strong>
        <span class="rarity">${escapeHtml(t.rarity)}</span>
        <p class="desc">${escapeHtml(t.description)}</p>
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "row-actions";
    if (t.equipped) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-sm danger";
      btn.textContent = "卸下";
      btn.addEventListener("click", async () => {
        try {
          settingsData = await apiFetch(`/api/me/titles/equip/${t.id}`, { method: "DELETE" });
          renderPage();
          showToast("已卸下称号");
        } catch (err) {
          showToast(err.message, true);
        }
      });
      actions.appendChild(btn);
    } else {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-sm primary";
      btn.textContent = "装备";
      btn.disabled = full;
      btn.addEventListener("click", async () => {
        try {
          settingsData = await apiFetch("/api/me/titles/equip", {
            method: "POST",
            body: JSON.stringify({ title_id: t.id }),
          });
          renderPage();
          showToast(`已装备「${t.name}」`);
        } catch (err) {
          showToast(err.message, true);
        }
      });
      actions.appendChild(btn);
    }
    row.appendChild(actions);
    list.appendChild(row);
  }
  return list;
}

function renderPage() {
  settingsMain.innerHTML = "";

  const privacySec = document.createElement("section");
  privacySec.className = "settings-section";
  privacySec.innerHTML = `
    <div class="section-head"><h2>隐私设置</h2></div>
    <label class="privacy-row">
      <span>允许他人查看我的角色卡</span>
      <input type="checkbox" id="charPublicToggle" ${userSettingsData.privacy.char_public === false ? "" : "checked"} />
    </label>
    <p class="preview-hint">关闭后，其他用户无法在网页端查看你的角色卡（跑团车卡页）。</p>
  `;
  settingsMain.appendChild(privacySec);

  document.getElementById("charPublicToggle").addEventListener("change", async (e) => {
    try {
      userSettingsData = await apiFetch("/api/me/settings", {
        method: "PUT",
        body: JSON.stringify({ privacy: { char_public: e.target.checked } }),
      });
      showToast(e.target.checked ? "已允许他人查看角色卡" : "已隐藏角色卡");
    } catch (err) {
      e.target.checked = !e.target.checked;
      showToast(err.message, true);
    }
  });

  const preview = document.createElement("section");
  preview.className = "settings-preview";
  preview.innerHTML = `
    <h2>消息前缀预览</h2>
    <p class="preview-text">${escapeHtml(settingsData.display_prefix || "（未装备称号）")}</p>
    <p class="preview-hint">群聊 @ 你时，机器人会在昵称前显示最多 3 个已装备称号。</p>
  `;
  settingsMain.appendChild(preview);

  const equippedSec = document.createElement("section");
  equippedSec.className = "settings-section";
  equippedSec.innerHTML = `
    <div class="section-head">
      <h2>当前装备 <span class="muted">(${settingsData.equipped.length}/${settingsData.max_equipped})</span></h2>
      <button type="button" class="btn-sm" id="clearAllBtn">全部卸下</button>
    </div>
  `;
  equippedSec.appendChild(renderEquippedSlots());
  settingsMain.appendChild(equippedSec);

  const listSec = document.createElement("section");
  listSec.className = "settings-section";
  listSec.innerHTML = `
    <div class="section-head">
      <h2>已解锁称号 <span class="muted">(${settingsData.unlocked.length})</span></h2>
    </div>
    <input type="search" id="titleSearch" class="settings-search" placeholder="搜索名称、编号或稀有度…" value="${escapeHtml(searchQuery)}" />
  `;
  listSec.appendChild(renderUnlockedList());
  settingsMain.appendChild(listSec);

  document.getElementById("clearAllBtn").addEventListener("click", async () => {
    if (!settingsData.equipped.length) return;
    if (!confirm("确定卸下全部装备称号？")) return;
    try {
      settingsData = await apiFetch("/api/me/titles/equipped", { method: "DELETE" });
      renderPage();
      showToast("已卸下全部称号");
    } catch (err) {
      showToast(err.message, true);
    }
  });

  document.getElementById("titleSearch").addEventListener("input", (e) => {
    searchQuery = e.target.value;
    const old = listSec.querySelector(".settings-title-list, .empty-hint.center");
    const parent = listSec;
    if (old) old.remove();
    parent.appendChild(renderUnlockedList());
  });
}

async function loadSettings() {
  if (!requireAuth()) return;
  settingsMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    const [titleData, userSettings] = await Promise.all([
      apiFetch("/api/me/titles/settings"),
      apiFetch("/api/me/settings"),
    ]);
    settingsData = titleData;
    userSettingsData = userSettings;
    renderPage();
  } catch (err) {
    settingsMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

loginCancel.addEventListener("click", () => loginDialog.close());
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  try {
    await GalleryAuth.login(loginKey.value);
    loginDialog.close();
    loginKey.value = "";
    renderAuthChip();
    loadSettings();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(() => {
  renderAuthChip();
  if (requireAuth()) loadSettings();
});
