const settingsMain = document.getElementById("settingsMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

let settingsData = null;
let userSettingsData = { privacy: {} };
let searchQuery = "";
let emailMode = "view"; // view | bind | unbind
let emailCooldownTimer = null;

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// 打卡时间线显示状态（与 core/user_settings.py CHECKIN_DISPLAY_STATES 一致）：
// show=显示 / blur=模糊显示 / text=仅打卡信息（不含图片）/ hidden=隐藏
const CHECKIN_DISPLAY_OPTIONS = [
  { value: "show", label: "显示" },
  { value: "blur", label: "模糊显示" },
  { value: "text", label: "仅打卡信息" },
  { value: "hidden", label: "隐藏" },
];

// 网页配色（本浏览器 localStorage，经 theme.js 的 window.BoteroTheme 读写，不走服务端 API）
const THEME_OPTIONS = [
  { value: "", label: "报纸风（默认）" },
  { value: "mono", label: "上班摸鱼" },
  { value: "dark", label: "夜间模式" },
];

function renderThemeSection() {
  const sec = document.createElement("section");
  sec.className = "settings-section";
  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = "<h2>网页配色</h2>";
  sec.appendChild(head);

  const row = document.createElement("div");
  row.className = "privacy-row privacy-row-options";
  const label = document.createElement("span");
  label.textContent = "全站配色";
  row.appendChild(label);

  const current = (window.BoteroTheme && BoteroTheme.get()) || "";
  THEME_OPTIONS.forEach((opt) => {
    const radioLabel = document.createElement("label");
    radioLabel.className = "radio-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "siteTheme";
    input.value = opt.value;
    input.checked = current === opt.value;
    input.addEventListener("change", (e) => {
      if (!e.target.checked || !window.BoteroTheme) return;
      BoteroTheme.set(opt.value);
      showToast(`配色已切换：${opt.label}`);
    });
    radioLabel.appendChild(input);
    const optText = document.createElement("span");
    optText.textContent = opt.label;
    radioLabel.appendChild(optText);
    row.appendChild(radioLabel);
  });
  sec.appendChild(row);

  const hint = document.createElement("p");
  hint.className = "preview-hint";
  hint.textContent =
    "配色保存在当前浏览器（更换设备需重新选择）：「上班摸鱼」为低饱和灰白风并灰化图片；" +
    "「夜间模式」为暗色底，图片均保持原样。";
  sec.appendChild(hint);
  return sec;
}

function buildCheckinDisplayRow(title, groupName, settingKey, currentValue) {
  const row = document.createElement("div");
  row.className = "privacy-row privacy-row-options";
  const label = document.createElement("span");
  label.textContent = title;
  row.appendChild(label);
  CHECKIN_DISPLAY_OPTIONS.forEach((opt) => {
    const radioLabel = document.createElement("label");
    radioLabel.className = "radio-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = groupName;
    input.value = opt.value;
    input.checked = (currentValue || "show") === opt.value;
    input.addEventListener("change", async (e) => {
      try {
        userSettingsData = await apiFetch("/api/me/settings", {
          method: "PUT",
          body: JSON.stringify({ privacy: { [settingKey]: e.target.value } }),
        });
        showToast(`${title}：${opt.label}`);
      } catch (err) {
        showToast(err.message, true);
        renderPage(); // 回滚选中态到服务端值
      }
    });
    radioLabel.appendChild(input);
    const optText = document.createElement("span");
    optText.textContent = opt.label;
    radioLabel.appendChild(optText);
    row.appendChild(radioLabel);
  });
  return row;
}

function maskEmail(email) {
  const at = email.indexOf("@");
  if (at < 1) return email;
  const local = email.slice(0, at);
  return (local.length > 2 ? local.slice(0, 2) : local.slice(0, 1)) + "***" + email.slice(at);
}

function startEmailCooldown(btn, seconds) {
  if (emailCooldownTimer) clearInterval(emailCooldownTimer);
  btn.disabled = true;
  let left = seconds;
  const tick = () => {
    btn.textContent = `${left} 秒后可重发`;
    left -= 1;
    if (left < 0) {
      clearInterval(emailCooldownTimer);
      emailCooldownTimer = null;
      btn.disabled = false;
      btn.textContent = "发送验证码";
    }
  };
  tick();
  emailCooldownTimer = setInterval(tick, 1000);
}

async function sendEmailCode(purpose) {
  const btn = document.getElementById(purpose === "unbind" ? "unbindSendBtn" : "bindSendBtn");
  if (btn && btn.disabled) return;
  const email = purpose === "bind" ? (document.getElementById("bindEmailInput")?.value.trim() || "") : "";
  try {
    const res = await apiFetch("/api/me/email/code", {
      method: "POST",
      body: JSON.stringify({ email, purpose }),
    });
    showToast("验证码已发送，请查收邮箱");
    if (btn) startEmailCooldown(btn, res.cooldown_seconds || 60);
  } catch (err) {
    showToast(err.message, true);
  }
}

async function submitEmailBind() {
  const email = document.getElementById("bindEmailInput").value.trim();
  const code = document.getElementById("bindCodeInput").value.trim();
  try {
    await apiFetch("/api/me/email/bind", {
      method: "POST",
      body: JSON.stringify({ email, code }),
    });
    showToast("邮箱绑定成功");
    await reloadEmailState();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function submitEmailUnbind() {
  const code = document.getElementById("unbindCodeInput").value.trim();
  try {
    await apiFetch("/api/me/email/unbind", {
      method: "POST",
      body: JSON.stringify({ code }),
    });
    showToast("邮箱已解绑");
    await reloadEmailState();
  } catch (err) {
    showToast(err.message, true);
  }
}

async function reloadEmailState() {
  userSettingsData = await apiFetch("/api/me/settings");
  emailMode = "view";
  renderPage();
}

function wireEmailForm(root) {
  const bindSend = root.querySelector("#bindSendBtn");
  const bindSubmit = root.querySelector("#bindSubmitBtn");
  const unbindSend = root.querySelector("#unbindSendBtn");
  const unbindSubmit = root.querySelector("#unbindSubmitBtn");
  const cancel = root.querySelector("#emailCancelBtn");
  if (bindSend) bindSend.addEventListener("click", () => sendEmailCode("bind"));
  if (bindSubmit) bindSubmit.addEventListener("click", submitEmailBind);
  if (unbindSend) unbindSend.addEventListener("click", () => sendEmailCode("unbind"));
  if (unbindSubmit) unbindSubmit.addEventListener("click", submitEmailUnbind);
  if (cancel) cancel.addEventListener("click", () => {
    emailMode = "view";
    renderPage();
  });
}

function renderEmailSection() {
  const sec = document.createElement("section");
  sec.className = "settings-section";
  const bound = userSettingsData.email;
  let body = "";
  if (bound && emailMode === "view") {
    body = `
      <p class="email-bound-info">已绑定：${escapeHtml(maskEmail(bound))}${
        userSettingsData.email_bound_at ? `（${escapeHtml(userSettingsData.email_bound_at)}）` : ""
      }</p>
      <div class="email-actions">
        <button type="button" class="email-btn primary" id="emailRebindBtn">换绑邮箱</button>
        <button type="button" class="email-btn" id="emailUnbindBtn">解绑邮箱</button>
      </div>
    `;
  } else if (emailMode === "unbind" && bound) {
    body = `
      <p class="email-bound-info">将向 ${escapeHtml(maskEmail(bound))} 发送验证码，输入后确认解绑。</p>
      <div class="email-form-row">
        <input type="text" id="unbindCodeInput" placeholder="6 位验证码" maxlength="6" inputmode="numeric" />
        <button type="button" class="email-btn" id="unbindSendBtn">发送验证码</button>
      </div>
      <div class="email-form-row">
        <button type="button" class="email-btn primary" id="unbindSubmitBtn">确认解绑</button>
        <button type="button" class="email-btn" id="emailCancelBtn">取消</button>
      </div>
    `;
  } else {
    body = `
      <div class="email-form-row">
        <input type="email" id="bindEmailInput" placeholder="输入要绑定的邮箱" />
        <button type="button" class="email-btn" id="bindSendBtn">发送验证码</button>
      </div>
      <div class="email-form-row">
        <input type="text" id="bindCodeInput" placeholder="6 位验证码" maxlength="6" inputmode="numeric" />
        <button type="button" class="email-btn primary" id="bindSubmitBtn">绑定</button>
      </div>
      <p class="preview-hint">验证码 10 分钟内有效。${bound ? "换绑成功后旧邮箱即被覆盖。" : ""}</p>
      ${bound ? '<div class="email-form-row"><button type="button" class="email-btn" id="emailCancelBtn">取消</button></div>' : ""}
    `;
  }
  sec.innerHTML = `<div class="section-head"><h2>账号邮箱</h2></div>${body}`;
  wireEmailForm(sec);
  const rebind = sec.querySelector("#emailRebindBtn");
  const unbind = sec.querySelector("#emailUnbindBtn");
  if (rebind) rebind.addEventListener("click", () => {
    emailMode = "bind";
    renderPage();
  });
  if (unbind) unbind.addEventListener("click", () => {
    emailMode = "unbind";
    renderPage();
  });
  return sec;
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
  `;
  settingsMain.appendChild(privacySec);

  privacySec.appendChild(buildCheckinDisplayRow(
    "私聊/网页打卡在时间线上", "checkinDisplayPrivate", "checkin_display_private",
    userSettingsData.privacy.checkin_display_private
  ));
  privacySec.appendChild(buildCheckinDisplayRow(
    "群聊打卡在时间线上", "checkinDisplayGroup", "checkin_display_group",
    userSettingsData.privacy.checkin_display_group
  ));

  const checkinHint = document.createElement("p");
  checkinHint.className = "preview-hint";
  checkinHint.textContent =
    "打卡显示状态分私聊/网页与群聊两类设置：「模糊显示」时其他用户看到高斯模糊图；" +
    "「仅打卡信息」时其他用户只看到打卡文字不显示图片；「隐藏」时其他用户看不到该类打卡。" +
    "任何状态下你本人查看自己的打卡始终是原图与完整内容。";
  privacySec.appendChild(checkinHint);
  settingsMain.appendChild(renderThemeSection());
  settingsMain.appendChild(renderEmailSection());

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
