const checkinMain = document.getElementById("checkinMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

let statusData = null;
let selectedFiles = [];

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  loginDialog.showModal();
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    checkinMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
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

function formatBytes(n) {
  return `${Math.round(n / (1024 * 1024))} MB`;
}

function renderStatusBox() {
  const box = document.createElement("section");
  box.className = "checkin-status";
  const s = statusData.streaks;
  box.innerHTML = `
    <h2>本周进度</h2>
    <p class="status-line">${statusData.week_start} ~ ${statusData.week_end}</p>
    <p class="status-line">本周已收录 <strong>${statusData.week_image_count}</strong> 张图</p>
    <p class="status-line">连续打卡 <strong>${s.current_weekly}</strong> 周 · 最长 <strong>${s.longest_weekly}</strong> 周</p>
    <p class="status-hint">单次最多 ${statusData.max_images} 张，每张不超过 ${formatBytes(statusData.max_bytes)}</p>
  `;
  return box;
}

function renderPreview() {
  const wrap = document.createElement("div");
  wrap.className = "checkin-preview";
  wrap.id = "previewGrid";
  if (!selectedFiles.length) {
    wrap.innerHTML = "<p class='empty-hint center'>尚未选择图片</p>";
    return wrap;
  }
  for (const file of selectedFiles) {
    const card = document.createElement("div");
    card.className = "preview-card";
    const img = document.createElement("img");
    img.alt = file.name;
    img.src = URL.createObjectURL(file);
    const name = document.createElement("span");
    name.className = "preview-name";
    name.textContent = file.name;
    card.append(img, name);
    wrap.appendChild(card);
  }
  return wrap;
}

function renderForm() {
  const form = document.createElement("section");
  form.className = "checkin-form settings-section";

  const drop = document.createElement("div");
  drop.className = "checkin-drop";
  drop.innerHTML = `
    <p><strong>选择或拖拽图片到此处</strong></p>
    <p class="preview-hint">支持 JPG / PNG / WebP / GIF</p>
  `;
  const input = document.createElement("input");
  input.type = "file";
  input.id = "fileInput";
  input.accept = "image/jpeg,image/png,image/webp,image/gif";
  input.multiple = true;
  input.hidden = true;
  drop.addEventListener("click", () => input.click());
  drop.addEventListener("dragover", (e) => {
    e.preventDefault();
    drop.classList.add("dragover");
  });
  drop.addEventListener("dragleave", () => drop.classList.remove("dragover"));
  drop.addEventListener("drop", (e) => {
    e.preventDefault();
    drop.classList.remove("dragover");
    addFiles(e.dataTransfer.files);
  });
  input.addEventListener("change", () => addFiles(input.files));

  const actions = document.createElement("div");
  actions.className = "checkin-actions";
  const clearBtn = document.createElement("button");
  clearBtn.type = "button";
  clearBtn.className = "btn-sm";
  clearBtn.textContent = "清空";
  clearBtn.addEventListener("click", () => {
    selectedFiles = [];
    input.value = "";
    refreshPreview();
  });
  const submitBtn = document.createElement("button");
  submitBtn.type = "button";
  submitBtn.className = "btn-sm primary";
  submitBtn.id = "submitBtn";
  submitBtn.textContent = "提交打卡";
  submitBtn.addEventListener("click", submitCheckin);
  actions.append(clearBtn, submitBtn);

  form.innerHTML = "<h2>上传打卡图</h2>";
  form.append(drop, input, renderPreview(), actions);
  return form;
}

function addFiles(fileList) {
  const max = statusData?.max_images || 9;
  for (const f of fileList) {
    if (!f.type.startsWith("image/")) continue;
    if (selectedFiles.length >= max) break;
    selectedFiles.push(f);
  }
  refreshPreview();
}

function refreshPreview() {
  const old = document.getElementById("previewGrid");
  if (old) old.replaceWith(renderPreview());
  const btn = document.getElementById("submitBtn");
  if (btn) btn.disabled = selectedFiles.length === 0;
}

function renderResult(data) {
  const old = document.getElementById("checkinSuccessDialog");
  if (old) old.remove();

  const dialog = document.createElement("dialog");
  dialog.id = "checkinSuccessDialog";
  dialog.className = "checkin-success-dialog";

  let bonusHtml = "";
  if (data.bonus_lines?.length) {
    bonusHtml = `<ul class="success-bonus">${data.bonus_lines.map((l) => `<li>${escapeHtml(l)}</li>`).join("")}</ul>`;
  } else if (data.bonus_total > 0) {
    bonusHtml = `<p class="success-bonus-line">获得积分 +${data.bonus_total}</p>`;
  }

  let titlesHtml = "";
  if (data.unlocked_titles?.length) {
    titlesHtml = `<h3>解锁新称号</h3><ul class="success-titles">${data.unlocked_titles
      .map((t) => `<li>[${t.id}] 「${escapeHtml(t.name)}」 (${escapeHtml(t.rarity)})</li>`)
      .join("")}</ul>`;
  }

  const firstHint = data.is_first_this_week ? "<p class=\"success-tag\">本周首次打卡</p>" : "";

  dialog.innerHTML = `
    <div class="success-dialog-body">
      <p class="success-icon" aria-hidden="true">✓</p>
      <h2>打卡成功</h2>
      ${firstHint}
      <p class="success-lead">已成功收录 <strong>${data.image_count}</strong> 张图片</p>
      <p class="success-sub">本周累计 ${data.week_total_images} 张${
        data.streaks?.current_weekly > 1 ? ` · 已连续 ${data.streaks.current_weekly} 周` : ""
      }</p>
      ${bonusHtml}
      ${titlesHtml}
      <button type="button" class="btn-sm primary success-ok">知道了</button>
    </div>
  `;

  dialog.querySelector(".success-ok").addEventListener("click", () => dialog.close());
  document.body.appendChild(dialog);
  dialog.showModal();

  showSuccessToast(`打卡成功！已收录 ${data.image_count} 张图片`);
}

function showSuccessToast(msg) {
  let toast = document.getElementById("checkinSuccessToast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "checkinSuccessToast";
    toast.className = "checkin-success-toast";
    toast.setAttribute("role", "status");
    document.body.appendChild(toast);
  }
  toast.textContent = msg;
  toast.classList.remove("hidden");
  clearTimeout(showSuccessToast._t);
  showSuccessToast._t = setTimeout(() => toast.classList.add("hidden"), 5000);
}

async function loadStatus() {
  const res = await fetch("/api/me/checkin/status", { headers: GalleryAuth.headers() });
  if (res.status === 401) {
    GalleryAuth.clear();
    requireAuth();
    return;
  }
  statusData = await res.json();
  checkinMain.innerHTML = "";
  checkinMain.appendChild(renderStatusBox());
  checkinMain.appendChild(renderForm());
  refreshPreview();
}

async function submitCheckin() {
  if (!selectedFiles.length) return;
  const btn = document.getElementById("submitBtn");
  btn.disabled = true;
  btn.textContent = "提交中…";
  const fd = new FormData();
  for (const f of selectedFiles) {
    fd.append("files", f);
  }
  try {
    const res = await fetch("/api/me/checkin", {
      method: "POST",
      headers: GalleryAuth.headers(),
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "打卡失败");
    selectedFiles = [];
    document.getElementById("fileInput").value = "";
    await loadStatus();
    renderResult(data);
  } catch (err) {
    alert(err.message || "打卡失败");
  } finally {
    btn.textContent = "提交打卡";
    refreshPreview();
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
    loadStatus();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(() => {
  renderAuthChip();
  if (requireAuth()) loadStatus();
});
