// 最小 DOM stub 验证 settings.js 隐私设置渲染：
// 打卡显示状态两组 radio（私聊/网页、群聊）：空 privacy → 各 4 项且 show 选中；
// API 返回 checkin_display_private="text" → 私聊组 text 选中、群聊组仍 show；
// 触发群聊组 hidden radio → 只 PUT 自己的键（char_public 等其它键由服务端深合并保留）。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "", name: "",
    disabled: false, checked: false, children: [], dataset: {}, style: {}, _html: "", _listeners: {},
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
    // renderPage 用模板字符串 innerHTML 生成角色卡开关，getElementById 需从 HTML 片段回建
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

let themeNow = "";
const themeSets = [];
const fakeTheme = { get: () => themeNow, set: (v) => { themeSets.push(v); themeNow = v; } };
global.window.BoteroTheme = fakeTheme;
global.BoteroTheme = fakeTheme;
global.confirm = () => true;

eval(fs.readFileSync("webapp/static/settings.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const radiosOf = (name) => ALL_ELS.filter((e) => e.type === "radio" && e.name === name);
const checkedOf = (name) => {
  const hit = radiosOf(name).filter((e) => e.checked);
  return hit.length ? hit[0].value : "(无)";
};

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150); // refreshMe → loadSettings → renderPage

  // 1. 默认（空 privacy）：两组各 4 项 radio，show 选中；角色卡开关（未受影响）仍默认勾选
  check("私聊组渲染 4 个 radio", radiosOf("checkinDisplayPrivate").length === 4);
  check("群聊组渲染 4 个 radio", radiosOf("checkinDisplayGroup").length === 4);
  check("空 privacy 私聊组默认 show", checkedOf("checkinDisplayPrivate") === "show");
  check("空 privacy 群聊组默认 show", checkedOf("checkinDisplayGroup") === "show");
  check("角色卡开关默认勾选（未被波及）", isChecked("charPublicToggle"));

  // 0. 网页配色：3 个 radio，默认选中"报纸风"
  const themeRadios = radiosOf("siteTheme");
  check("配色组渲染 3 个 radio", themeRadios.length === 3);
  check("配色组默认选中报纸风", checkedOf("siteTheme") === "");

  // 2. checkin_display_private="text"：私聊组 text 选中，群聊组仍 show
  const mark2 = ALL_ELS.length; // 记录批次切点：loadSettings 重渲染后只看新创建的元素
  meSettings = { privacy: { checkin_display_private: "text", char_public: false } };
  settingsData = null;
  await loadSettings();
  await wait(100);
  const radios2Private = ALL_ELS.slice(mark2).filter((e) => e.type === "radio" && e.name === "checkinDisplayPrivate");
  const radios2Group = ALL_ELS.slice(mark2).filter((e) => e.type === "radio" && e.name === "checkinDisplayGroup");
  const pick = (list) => { const hit = list.filter((e) => e.checked); return hit.length ? hit[0].value : "(无)"; };
  check("private=text 时私聊组选中 text", pick(radios2Private) === "text");
  check("private=text 时群聊组仍默认 show", pick(radios2Group) === "show");
  check("char_public=false 时角色卡开关不勾选", !isChecked("charPublicToggle"));

  // 3. 触发群聊组 hidden radio：PUT 只带自己的键（其它键由服务端深合并保留）
  const hiddenRadio = radios2Group.filter((e) => e.value === "hidden")[0];
  if (hiddenRadio && (hiddenRadio._listeners.change || []).length) {
    hiddenRadio.checked = true;
    radios2Group.forEach((e) => { if (e !== hiddenRadio) e.checked = false; });
    await hiddenRadio._listeners.change.shift()({ target: hiddenRadio });
    await wait(50);
  }
  check("PUT 仅含 checkin_display_group 单键",
        puts.length === 1 && puts[0].privacy.checkin_display_group === "hidden"
        && Object.keys(puts[0].privacy).length === 1);

  // 4. 触发配色 mono radio：走本地 BoteroTheme.set，不 PUT 任何 API
  const putsBefore = puts.length;
  const monoRadio = radiosOf("siteTheme").filter((e) => e.value === "mono")[0];
  if (monoRadio && (monoRadio._listeners.change || []).length) {
    monoRadio.checked = true;
    radiosOf("siteTheme").forEach((e) => { if (e !== monoRadio) e.checked = false; });
    await monoRadio._listeners.change.shift()({ target: monoRadio });
    await wait(50);
  }
  check("配色切换调用 BoteroTheme.set(mono)", themeSets.length === 1 && themeSets[0] === "mono");
  check("配色切换不触发 API PUT", puts.length === putsBefore);

  process.exit(fail ? 1 : 0);
})();

function isChecked(id) {
  const hits = ALL_ELS.map((e) => e._html).filter((h) => h.includes(`id="${id}"`));
  return hits.length ? new RegExp(`id="${id}"[^>]*checked`).test(hits[hits.length - 1]) : false;
}
