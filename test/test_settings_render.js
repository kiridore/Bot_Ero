// 最小 DOM stub 验证 settings.js 隐私开关渲染：
// 默认（空 privacy）两个新开关勾选；API 返回 private_checkin_public=false 时对应开关不勾选；
// 触发开关只 PUT 自己的键（char_public 等其它键由服务端深合并保留，不被覆盖）。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "", disabled: false,
    checked: false, children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    setAttribute(k, v) { this.attributes = this.attributes || {}; this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
    prepend(c) { this.children.unshift(c); return c; },
    querySelector(sel) { return null; },
    showModal() { this.open = true; },
    close() { this.open = false; },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); },
    remove(...cs) { cs.forEach((c) => this._s.delete(c)); },
    toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
    contains(c) { return this._s.has(c); },
  };
  ALL_ELS.push(el);
  return el;
}

const els = {
  settingsMain: makeEl("main"), loginDialog: makeEl("dialog"), loginForm: makeEl("form"),
  loginKey: makeEl("input"), loginError: makeEl("p"), loginCancel: makeEl("button"),
  authArea: makeEl("div"),
};
els.settingsMain.id = "settingsMain";
els.loginDialog.id = "loginDialog";
els.loginForm.id = "loginForm";
els.loginKey.id = "loginKey";
els.loginError.id = "loginError";
els.loginCancel.id = "loginCancel";
els.authArea.id = "authArea";

global.location = { hostname: "127.0.0.1", pathname: "/profile/settings" };
global.document = {
  createElement: makeEl,
  getElementById(id) {
    if (els[id]) return els[id];
    // renderPage 用模板字符串 innerHTML 生成开关，getElementById 需从 HTML 片段回建
    for (const el of ALL_ELS) {
      const m = new RegExp(`id="${id}"([^>]*)`).exec(el._html);
      if (!m) continue;
      const stub = makeEl("input");
      stub.type = "checkbox";
      stub.checked = /(^|\s)checked(\s|$|\/)/.test(m[1]);
      els[id] = stub;
      return stub;
    }
    return null;
  },
};

let meSettings = { privacy: {} }; // 可在用例间切换
const puts = [];
global.fetch = async (path, options = {}) => {
  if (path === "/api/me/settings" && (!options.method || options.method === "GET")) {
    return { ok: true, status: 200, json: async () => meSettings };
  }
  if (path === "/api/me/settings" && options.method === "PUT") {
    puts.push(JSON.parse(options.body));
    meSettings = { privacy: Object.assign({}, meSettings.privacy, JSON.parse(options.body).privacy) };
    return { ok: true, status: 200, json: async () => meSettings };
  }
  if (path === "/api/me/titles/settings") {
    return {
      ok: true, status: 200,
      json: async () => ({ max_equipped: 3, equipped: [], unlocked: [], display_prefix: "" }),
    };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: "123456", display_name: "测试", avatar_url: "" }),
  headers: () => ({}),
  refreshMe: async () => ({}),
};
global.window = { addEventListener() {} };
global.confirm = () => true;

eval(fs.readFileSync("webapp/static/settings.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const toggleHtml = (id) => {
  const hits = ALL_ELS.map((e) => e._html).filter((h) => h.includes(`id="${id}"`));
  return hits.length ? hits[hits.length - 1] : "";
};
const isChecked = (id) => new RegExp(`id="${id}"[^>]*checked`).test(toggleHtml(id));

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150); // refreshMe → loadSettings → renderPage

  // 1. 默认（空 privacy）：两个新开关勾选
  check("私聊打卡开关默认勾选", isChecked("optPrivateCheckinPublic"));
  check("打卡图片开关默认勾选", isChecked("optCheckinImagePublic"));

  // 2. private_checkin_public=false：对应开关不勾选，图片开关仍勾选
  meSettings = { privacy: { private_checkin_public: false, char_public: false } };
  settingsData = null;
  await loadSettings();
  await wait(100);
  check("private=false 时私聊打卡开关不勾选", !isChecked("optPrivateCheckinPublic"));
  check("private=false 时图片开关仍勾选", isChecked("optCheckinImagePublic"));
  check("char_public=false 时角色卡开关不勾选", !isChecked("charPublicToggle"));

  // 3. 触发私聊打卡开关：PUT 只带自己的键（其它键由服务端深合并保留）
  const toggle = document.getElementById("optPrivateCheckinPublic");
  if (toggle && (toggle._listeners.change || []).length) {
    toggle.checked = false;
    await toggle._listeners.change.shift()({ target: toggle });
    await wait(50);
  }
  check("PUT 仅含 private_checkin_public 单键",
        puts.length === 1 && puts[0].privacy.private_checkin_public === false
        && Object.keys(puts[0].privacy).length === 1);

  process.exit(fail ? 1 : 0);
})();
