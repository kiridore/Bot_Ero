// 最小 DOM stub 验证 profile.js 兑换码 tab：
// 1) tab 栏出现「兑换码」且面板默认隐藏；2) 切换后惰性加载历史并渲染行；
// 3) 提交兑换 POST /api/me/redeem，成功行内反馈并刷新历史；失败展示 detail。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", value: "", name: "",
    disabled: false, checked: false, placeholder: "", maxLength: 0, title: "",
    children: [], dataset: {}, style: {}, attributes: {}, _html: "", _listeners: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
    prepend(c) { this.children.unshift(c); return c; },
    querySelector() { return null; },
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
  // 浏览器中 className 字符串与 classList 联动，桩同步二者（textContent 仅存取自身文本）
  Object.defineProperty(el, "className", {
    get() { return Array.from(el.classList._s).join(" "); },
    set(v) { el.classList._s = new Set(String(v).split(/\s+/).filter(Boolean)); },
  });
  Object.defineProperty(el, "textContent", {
    get() { return String(el._text || ""); },
    set(v) { el._text = v; },
  });
  ALL_ELS.push(el);
  return el;
}

const els = {};
for (const id of [
  "profileMain", "dayDialog", "dayDialogTitle", "dayDialogGrid", "dayDialogClose",
  "lightbox", "lightboxImg", "lightboxClose", "lightboxShare", "loginDialog", "loginForm", "loginKey",
  "loginError", "loginCancel", "shareDialog", "shareDialogClose", "shareDownload",
  "authArea",
]) {
  const el = makeEl(id.startsWith("day") || id.includes("Dialog") ? "dialog" : "div");
  el.id = id;
  els[id] = el;
}

global.location = { hostname: "127.0.0.1", pathname: "/profile" };
global.document = {
  createElement: makeEl,
  getElementById(id) {
    if (els[id]) return els[id];
    return ALL_ELS.find((e) => e.id === id) || null; // 渲染后动态创建的面板/输入框
  },
  querySelectorAll(sel) {
    if (sel !== ".profile-tabs button") return [];
    return ALL_ELS.filter((e) => e.tagName === "button" && e.dataset && e.dataset.tab);
  },
  addEventListener() {},
};

const historyCalls = [];
const redeemPosts = [];
let redeemResponse = { ok: true, status: 200, json: async () => ({ success: true, message: "兑换成功，解锁称号：「测试员」" }) };
global.fetch = async (path, options = {}) => {
  if (path === "/api/auth/me") return { ok: true, status: 200, json: async () => ({ user_id: "123456", display_name: "测试", avatar_url: "" }) };
  if (path === "/api/me/profile") {
    return {
      ok: true, status: 200,
      json: async () => ({
        display_name: "测试", user_id: "123456", points: 5,
        titles_unlocked: 0, titles_total: 0, avatar_url: "", year: 2026,
        total_checkin_images: 0, titles: [],
        streaks: { current_daily: 1, longest_daily: 2, current_weekly: 1, longest_weekly: 1 },
        heatmap: [{ date: "2026-10-01", level: 1, count: 1, is_remedy: false }],
      }),
    };
  }
  if (path === "/api/me/redeem/history") {
    historyCalls.push(1);
    return {
      ok: true, status: 200,
      json: async () => ({
        items: [
          { code: "TEST-CODE-TEST", used_at: "2026-10-28 12:00:00", description: "解锁「测试员」称号" },
          { code: "OLD1-CODE-0001", used_at: "2026-01-01 08:00:00", description: "（已下架）" },
        ],
      }),
    };
  }
  if (path === "/api/me/redeem" && options.method === "POST") {
    redeemPosts.push(JSON.parse(options.body));
    return redeemResponse;
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
global.alert = () => {};

eval(fs.readFileSync("webapp/static/profile.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150); // refreshMe → loadProfile → renderProfile

  // 1. tab 渲染与默认隐藏
  const tabBtns = document.querySelectorAll(".profile-tabs button");
  const redeemBtn = tabBtns.find((b) => b.dataset.tab === "redeem");
  check("tab 栏含「兑换码」", !!redeemBtn && redeemBtn.textContent === "兑换码");
  const panel = document.getElementById("panelRedeem");
  check("兑换面板默认隐藏", !!panel && panel.classList.contains("hidden"));
  check("历史惰性未加载", historyCalls.length === 0);

  // 2. 切换 tab：加载历史并渲染行
  switchTab("redeem");
  await wait(80);
  check("切换后面板可见", !panel.classList.contains("hidden"));
  check("历史已请求", historyCalls.length === 1);
  const rows = document.getElementById("redeemHistory").children;
  check("历史渲染 2 行", rows.length === 2);
  check("旧行展示占位说明",
    rows[1].children.length === 3 &&
    rows[1].children[0].textContent === "OLD1-CODE-0001" &&
    rows[1].children[1].textContent === "（已下架）" &&
    rows[1].children[2].textContent === "2026-01-01 08:00:00");

  // 3. 提交兑换：成功反馈 + 历史刷新
  const input = document.getElementById("redeemInput");
  const result = document.getElementById("redeemResult");
  input.value = "test-code-test";
  await submitRedeem();
  await wait(80);
  check("POST 携带原始输入", redeemPosts.length === 1 && redeemPosts[0].code === "test-code-test");
  check("成功反馈行内展示", result.textContent.includes("测试员") && result.classList.contains("ok"));
  check("成功后刷新历史", historyCalls.length === 2);

  // 4. 失败路径：展示服务端 detail
  redeemResponse = { ok: false, status: 400, json: async () => ({ detail: "你已使用过该兑换码" }) };
  input.value = "TEST-CODE-TEST";
  await submitRedeem();
  await wait(50);
  check("失败展示 detail", result.textContent === "你已使用过该兑换码" && result.classList.contains("error"));

  // 5. 空输入本地提示，不发请求
  const postsBefore = redeemPosts.length;
  input.value = "  ";
  await submitRedeem();
  await wait(30);
  check("空输入不发请求", redeemPosts.length === postsBefore && result.textContent === "请输入兑换码");

  process.exit(fail ? 1 : 0);
})();
