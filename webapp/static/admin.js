const adminMain = document.getElementById("adminMain");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

async function api(path, options = {}) {
  const res = await fetch(path, { headers: GalleryAuth.headers(), ...options });
  if (res.status === 403) throw new Error("仅超级用户");
  if (res.status === 401) { GalleryAuth.clear(); location.href = "/login?next=/admin"; throw new Error("未登录"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "请求失败");
  return data;
}

async function boot() {
  adminMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    await api("/api/admin/plugins/scopes");  // 权限探测
  } catch (err) {
    adminMain.innerHTML = `<p class='empty-hint center'>${escapeHtml(err.message)}</p>`;
    return;
  }
  renderSkeleton();
  await Promise.all([loadScopes(), loadConfig()]);
}

function renderSkeleton() {
  adminMain.innerHTML = `
    <section class="settings-section admin-section">
      <h2>插件管理</h2>
      <p class="admin-hint">改动即时生效（bot 每次事件实时读取）；私聊=仅私聊消息生效的插件范围。</p>
      <label class="alarm-field"><span class="alarm-field-label">作用范围</span>
        <select id="scopeSelect" class="alarm-input"></select></label>
      <div id="pluginList"></div>
    </section>
    <section class="settings-section admin-section">
      <h2>配置文件</h2>
      <p class="admin-hint">保存后需重启 bot 与 webapp 进程生效；保存前自动备份为 config.yaml.bak（保留一代）。</p>
      <textarea id="configArea" class="admin-config" spellcheck="false"></textarea>
      <div class="submit-row">
        <button type="button" id="configSave" class="admin-toggle">保存配置</button>
        <span id="configHint" class="admin-hint"></span>
      </div>
      <p id="configError" class="admin-error hidden"></p>
    </section>`;
  document.getElementById("scopeSelect").addEventListener("change", (e) => loadPlugins(Number(e.target.value)));
  document.getElementById("configSave").addEventListener("click", saveConfig);
}

async function loadScopes() {
  const data = await api("/api/admin/plugins/scopes");
  const sel = document.getElementById("scopeSelect");
  sel.innerHTML = "";
  data.scopes.forEach((s) => {
    const opt = document.createElement("option");
    opt.value = s.group_id;
    opt.textContent = s.label + (s.is_default ? "（默认）" : "");
    sel.appendChild(opt);
  });
  if (data.scopes.length) await loadPlugins(data.scopes[0].group_id);
}

async function loadPlugins(gid) {
  const host = document.getElementById("pluginList");
  host.innerHTML = "<p class='admin-hint'>加载中…</p>";
  const data = await api(`/api/admin/plugins?group_id=${gid}`);
  const sys = data.plugins.filter((p) => p.system);
  const normal = data.plugins.filter((p) => !p.system);
  host.innerHTML = "";
  normal.forEach((p) => host.appendChild(pluginRow(p, gid)));
  const lockTitle = document.createElement("p");
  lockTitle.className = "admin-hint";
  lockTitle.textContent = "🔒 系统插件（恒启用，不可修改）";
  host.appendChild(lockTitle);
  sys.forEach((p) => {
    const row = pluginRow(p, gid);
    row.querySelector("button").disabled = true;
    host.appendChild(row);
  });
}

function pluginRow(p, gid) {
  const row = document.createElement("div");
  row.className = "admin-row";
  const key = document.createElement("span");
  key.className = "admin-key";
  key.textContent = p.key;
  const badge = document.createElement("span");
  badge.className = "admin-badge";
  badge.textContent = p.enabled ? "✅ 启用" : "❌ 禁用";
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "admin-toggle" + (p.enabled ? "" : " off");
  btn.textContent = p.enabled ? "禁用" : "启用";
  btn.addEventListener("click", async () => {
    btn.disabled = true;
    try {
      await api("/api/admin/plugins", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ group_id: gid, plugin_key: p.key, enabled: !p.enabled }),
      });
      await loadPlugins(gid);
    } catch (err) {
      alert(err.message);
      btn.disabled = false;
    }
  });
  row.append(key, badge, btn);
  return row;
}

async function loadConfig() {
  const data = await api("/api/admin/config");
  document.getElementById("configArea").value = data.yaml;
}

async function saveConfig() {
  const btn = document.getElementById("configSave");
  const hint = document.getElementById("configHint");
  const errEl = document.getElementById("configError");
  errEl.classList.add("hidden");
  btn.disabled = true;
  try {
    await api("/api/admin/config", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ yaml: document.getElementById("configArea").value }),
    });
    hint.textContent = "已保存（重启进程后生效）";
    await loadConfig();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
  } finally {
    btn.disabled = false;
  }
}

GalleryAuth.refreshMe().finally(() => { GalleryAuth.renderAuth(document.getElementById("authArea")); boot(); });
