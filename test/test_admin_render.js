// 最小 DOM stub 验证 admin.js：
// 范围下拉（私聊+默认群标注）、普通插件行 toggle、系统插件行 disabled、
// 点 toggle 发 PUT、textarea=配置原文、点保存发 PUT config、403 显示仅超级用户。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "",
    disabled: false, children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    addEventListener(t, f) { (el._listeners[t] = el._listeners[t] || []).push(f); },
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => el.children.push(c)); },
    querySelector(sel) {
      if (sel.startsWith("#")) return fromHtml(sel.slice(1));
      if (/^[a-zA-Z][\w-]*$/.test(sel)) { // 标签选择器：在子树内按 tagName 深度查找
        const find = (node) => {
          for (const c of node.children || []) {
            if (c.tagName && c.tagName.toLowerCase() === sel.toLowerCase()) return c;
            const r = find(c);
            if (r) return r;
          }
          return null;
        };
        return find(el);
      }
      return null;
    },
    querySelectorAll() { return []; },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); syncClass(); },
    remove(...cs) { cs.forEach((c) => this._s.delete(c)); syncClass(); },
    toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); syncClass(); },
    contains(c) { return this._s.has(c); },
  };
  // 页面代码用 className 字符串赋值，stub 需双向同步字符串 ↔ 集合
  let _clsStr = "";
  const syncClass = () => { _clsStr = [...el.classList._s].join(" "); };
  Object.defineProperty(el, "className", {
    get() { return _clsStr; },
    set(v) {
      _clsStr = String(v);
      el.classList._s.clear();
      _clsStr.split(/\s+/).filter(Boolean).forEach((c) => el.classList._s.add(c));
    },
  });
  ALL_ELS.push(el);
  return el;
}

const els = {};
for (const id of ["adminMain", "authArea", "loginDialog", "loginForm", "loginKey",
  "loginError", "loginCancel"]) {
  els[id] = makeEl(id === "loginForm" ? "form" : id.endsWith("Dialog") ? "dialog" : "div");
  els[id].id = id;
}

global.location = { hostname: "127.0.0.1", pathname: "/admin", href: "" };
const HTML_ELS = {};
function fromHtml(id) {
  if (els[id]) return els[id];
  if (HTML_ELS[id]) return HTML_ELS[id];
  const direct = ALL_ELS.find((e) => e.id === id);
  if (direct) return direct;
  for (const el of ALL_ELS) {
    if (el._html && new RegExp(`id="${id}"`).test(el._html)) {
      const stub = makeEl("div");
      stub.id = id;
      HTML_ELS[id] = stub;
      return stub;
    }
  }
  return null;
}
global.document = { createElement: makeEl, getElementById: fromHtml, querySelectorAll: () => [] };

const STUB_CONFIG = "bot:\n  qq: \"123\"\nonebot:\n  http_url: http://x\n";
let forbid403 = false; // 后段切换为 403 场景
const calls = [];
global.fetch = async (path, options = {}) => {
  calls.push({ path, method: options.method || "GET", body: options.body });
  if (forbid403 && path === "/api/admin/plugins/scopes") {
    return { ok: false, status: 403, json: async () => ({ detail: "仅超级用户" }) };
  }
  if (path === "/api/admin/plugins/scopes") {
    return { ok: true, status: 200, json: async () => ({ scopes: [
      { group_id: 0, label: "私聊", is_default: false },
      { group_id: 296470819, label: "群 296470819", is_default: true },
    ] }) };
  }
  if (path.startsWith("/api/admin/plugins?")) {
    return { ok: true, status: 200, json: async () => ({ group_id: 0, plugins: [
      { key: "dice", enabled: true, system: false },
      { key: "menu", enabled: true, system: true },
    ] }) };
  }
  if (path === "/api/admin/config" && (!options.method || options.method === "GET")) {
    return { ok: true, status: 200, json: async () => ({ yaml: STUB_CONFIG, path: "config.yaml", restart_hint: true }) };
  }
  if (path === "/api/admin/config" && options.method === "PUT") {
    return { ok: true, status: 200, json: async () => ({ ok: true }) };
  }
  if (path === "/api/admin/plugins" && options.method === "PUT") {
    return { ok: true, status: 200, json: async () => ({ ok: true, key: "dice", enabled: false }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: "1", display_name: "测", avatar_url: "" }),
  headers: () => ({}),
  refreshMe: async () => ({}),
  renderAuth() {},
  clear() {},
};
global.window = { addEventListener() {} };
global.alert = () => {};

eval(fs.readFileSync("webapp/static/admin.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150); // refreshMe → boot → renderSkeleton → loadScopes/loadConfig

  // 1. 范围下拉：2 项、默认群带（默认）、私聊在列
  const sel = document.getElementById("scopeSelect");
  const opts = sel.children.filter((c) => c.tagName === "option");
  check("范围下拉 2 项", opts.length === 2);
  check("默认群标注（默认）", opts.some((o) => o.textContent.includes("（默认）") && o.textContent.includes("296470819"))
    && opts.some((o) => o.textContent === "私聊"));

  // 2. 插件行：dice 有 toggle 按钮；menu（系统）按钮 disabled
  const rows = ALL_ELS.filter((e) => e.classList.contains("admin-row") && e.classList._s.size === 1);
  const diceRow = rows.find((r) => r.children.some((c) => c.textContent === "dice"));
  const menuRow = rows.find((r) => r.children.some((c) => c.textContent === "menu"));
  check("普通插件行渲染", !!diceRow && diceRow.children.some((c) => c.tagName === "button" && !c.disabled));
  check("系统插件行锁定 disabled", !!menuRow && menuRow.children.some((c) => c.tagName === "button" && c.disabled === true));

  // 3. 点 toggle → PUT /api/admin/plugins（body 含 group_id/plugin_key/enabled 取反）
  const diceBtn = diceRow.children.find((c) => c.tagName === "button");
  calls.length = 0;
  await diceBtn._listeners.click[0]();
  const putPlug = calls.find((c) => c.method === "PUT" && c.path === "/api/admin/plugins");
  check("点 toggle 发 PUT 插件", !!putPlug && JSON.parse(putPlug.body).plugin_key === "dice"
    && JSON.parse(putPlug.body).group_id === 0 && JSON.parse(putPlug.body).enabled === false);

  // 4. textarea 值 = 配置原文；点保存 → PUT /api/admin/config
  const area = document.getElementById("configArea");
  check("配置原文载入 textarea", area.value === STUB_CONFIG);
  calls.length = 0;
  await document.getElementById("configSave")._listeners.click[0]();
  const putCfg = calls.find((c) => c.method === "PUT" && c.path === "/api/admin/config");
  check("点保存发 PUT 配置", !!putCfg && JSON.parse(putCfg.body).yaml === STUB_CONFIG);
  check("保存成功提示", document.getElementById("configHint").textContent.includes("已保存"));

  // 5. 403 场景：scopes 返回 403 → 页面显示仅超级用户
  forbid403 = true;
  await boot();
  check("403 显示仅超级用户", els.adminMain._html.includes("仅超级用户"));

  process.exit(fail ? 1 : 0);
})();
