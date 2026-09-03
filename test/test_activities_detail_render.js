// 最小 DOM stub 验证 activities_detail.js：
// 我的提交区块（文字+图+可更新徽章）、can_submit 表单态、not_my_turn 原因态、非成员隐藏。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "",
    children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    addEventListener(t, f) { (el._listeners[t] = el._listeners[t] || []).push(f); },
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => el.children.push(c)); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    scrollIntoView() {},
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

const mainEl = makeEl("main");
mainEl.id = "detailMain";
const authArea = makeEl("div");
authArea.id = "authArea";
const els = { detailMain: mainEl, authArea, submitForm: null };
global.document = {
  createElement: makeEl,
  getElementById(id) {
    if (els[id]) return els[id];
    for (const el of ALL_ELS) {
      if (el.id === id) return el;
      if (el._html && new RegExp(`id="${id}"`).test(el._html)) {
        const stub = makeEl("div");
        stub.id = id;
        els[id] = stub;
        return stub;
      }
    }
    return null;
  },
};

global.location = { pathname: "/activities/3", search: "" };
const myUid = "333";
let meData = {
  member: { status: "done", seq: 1, content: "我的文字作品", submitted_at: "2026-09-02 10:00:00",
            images: ["/archive/3/media/1-1.png"] },
  can_submit: true, block_reason: null, block_text: null,
};
let actData = {
  id: 3, type: "relay", title: "接龙三", status: "running", hours_per_user: 48,
  members: [
    { user_id: "333", nickname: "成员甲", seq: 1, status: "done", content: "我的文字作品",
      images: ["/archive/3/media/1-1.png"], submitted_at: "2026-09-02 10:00:00" },
    { user_id: "444", nickname: "成员乙", seq: 2, status: "pending", images: [], content: null },
  ],
};
const posts = [];
global.fetch = async (path, options = {}) => {
  if (path === "/api/activities/3") return { ok: true, status: 200, json: async () => actData };
  if (path === "/api/activities/3/me") return { ok: true, status: 200, json: async () => meData };
  if (path.endsWith("/submit")) { posts.push(options); return { ok: true, status: 200, json: async () => ({ ok: true, updated: true }) }; }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: myUid, display_name: "甲", avatar_url: "" }),
  headers: () => ({}),
  renderAuth() {},
};
global.window = { addEventListener() {} };
global.FormData = class { constructor() { this._d = {}; } append(k, v) { this._d[k] = v; } };
global.confirm = () => true;
global.alert = () => {};

eval(fs.readFileSync("webapp/static/activities_detail.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150);
  const html = mainEl._html;

  // 1. 我的提交区块：内容 + 图片 + 可更新徽章
  check("含我的提交区块", html.includes("我的提交"));
  check("显示我的文字", html.includes("我的文字作品"));
  check("显示我的图片", html.includes("/archive/3/media/1-1.png"));
  check("可更新徽章", /已提交|可更新/.test(html));

  // 2. can_submit=true → 表单渲染（textarea + file + 按钮）
  check("含提交表单", html.includes("提交作品") && /textarea|work-input/.test(html));

  // 3. not_my_turn → 原因替代表单
  meData = { member: { status: "pending", seq: 2, content: null, submitted_at: null, images: [] },
             can_submit: false, block_reason: "not_my_turn", block_text: "还未轮到你提交" };
  actData.members[0].status = "done";
  loadDetail();
  await wait(100);
  const html2 = mainEl._html;
  check("原因提示替代表单", html2.includes("还未轮到你提交") && !/id="submitBtn"/.test(html2));

  // 4. not_member → 两块隐藏
  meData = { member: null, can_submit: false, block_reason: "not_member", block_text: null };
  loadDetail();
  await wait(100);
  const html3 = mainEl._html;
  check("非成员隐藏提交区", !html3.includes("我的提交") && !html3.includes("提交作品"));

  process.exit(fail ? 1 : 0);
})();
