// 最小 DOM stub 验证时间线前端（timeline.js）：
// 登录门禁（401 → 登录对话框）、占位符替换、未绑定降级、详情按钮、侧边栏导航
const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    querySelector(sel) {
      const id = sel.replace("#", "");
      const hit = this.children.find((c) => c.id === id);
      if (hit) return hit;
      if (this.innerHTML.includes(`id="${id}"`)) {
        const el = makeEl("div");
        el.id = id;
        return el;
      }
      return null;
    },
    showModal() { this.open = true; },
    close() { this.open = false; },
    classList: { add() {}, remove() {}, contains() { return false; } },
  };
}

let bodyEl = makeEl("body");
const els = {};
global.location = { hostname: "127.0.0.1", protocol: "http:" };
global.window = {};
global.document = {
  createElement: (t) => makeEl(t),
  createDocumentFragment: () => makeEl("fragment"),
  getElementById: (id) => els[id] || null,
  body: { appendChild(c) { bodyEl.children.push(c); els[c.id] = c; } },
  head: { appendChild() {} },
  cookie: "",
};
global.localStorage = (() => { let m = {}; return {
  getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); },
  removeItem: (k) => { delete m[k]; }, }; })();

["feed", "sentinel", "tlStatus", "feedEmpty", "tlNav", "authArea"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});

const entriesPayload = [{ name: "打卡图库", desc: "每日打卡", url: "/gallery" }];
const feedPayload = {
  events: [
    {
      id: "checkin:1", source: "checkin", received_at: "2026-08-10 14:00:00",
      actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "http://a/1.png" },
      target: { type: "url", url: "https://littlero.tech/gallery" },
      title: "{id:123456} 完成打卡", description: "本周第 1 次", data: null,
    },
    {
      id: "quest:2", source: "quest", received_at: "2026-08-10 13:00:00",
      actor: { id: "mc-abc", qq: null, display_name: "未绑定玩家", avatar_url: "" },
      target: null, title: "完成周常任务「随便抽抽」", description: null, data: null,
    },
    {
      id: "checkin:3", source: "checkin", received_at: "2026-08-10 12:00:00",
      actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
      target: null,
      title: "{id:999} 与 {id:123456} 组队", description: null, data: null,
    },
  ],
  users: { "123456": { name: "小明", avatar: "http://a/1.png" } },
  next_cursor: null,
};

let timelineAuthed = false;
// 模拟真实浏览器的触底加载：sentinel 可见 → 触发 loadPage
global.IntersectionObserver = class {
  constructor(cb) { this.cb = cb; }
  observe() { setTimeout(() => this.cb([{ isIntersecting: true }]), 10); }
};
global.window.IntersectionObserver = global.IntersectionObserver;

async function fakeFetch(url, opts) {
  const u = String(url);
  if (u === "/entries.json") {
    return { ok: true, status: 200, json: async () => entriesPayload };
  }
  if (u === "/api/auth/login") {
    const body = JSON.parse((opts && opts.body) || "{}");
    return {
      ok: true, status: 200,
      json: async () => ({ user_id: "123456", display_name: "小明", avatar_url: "", token: body.key }),
    };
  }
  if (u.startsWith("/api/timeline")) {
    if (!timelineAuthed) return { ok: false, status: 401, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => feedPayload };
  }
  return { ok: false, status: 404, json: async () => ({}) };
}
global.fetch = fakeFetch;

const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(authSrc);
global.GalleryAuth = window.GalleryAuth; // eval 作用域隔离，供 timeline.js 的裸引用解析
const tlSrc = fs.readFileSync("webapp/static/timeline.js", "utf8");
eval(tlSrc);

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  // 1. 未登录：feed 请求 401 → 登录对话框弹出
  await new Promise((r) => setTimeout(r, 500));
  const dlg = bodyEl.children.find((c) => c.id === "loginDialog");
  check("未登录弹出登录对话框", dlg && dlg.open === true);
  check("未登录状态提示", els.tlStatus.textContent.includes("请先登录"));

  // 2. 侧边栏导航渲染
  const navLinks = els.tlNav.children.filter((c) => c.className === "tl-nav-link");
  check("侧边栏导航渲染 entries", navLinks.length === 1 && navLinks[0].innerHTML.includes("打卡图库"));

  // 3. 登录后 feed 渲染
  timelineAuthed = true;
  await window.GalleryAuth.login("test-key");
  await new Promise((r) => setTimeout(r, 100)); // 等待 loadPage 异步完成
  const frag = els.feed.children[0];
  check("登录后渲染卡片", Array.isArray(frag.children) && frag.children.length === 3);
  const [c1, c2, c3] = frag.children;

  check("卡片1 占位符替换为昵称", c1.children[1].innerHTML.includes("tl-user") && c1.children[1].innerHTML.includes("小明"));
  check("卡片1 actor 昵称", c1.children[0].children[1].textContent === "小明");
  check("卡片1 详情按钮", c1.children.some((c) => c.className === "tl-detail" && c.href === "https://littlero.tech/gallery"));
  check("卡片1 时间", typeof c1.children[0].children[2].textContent === "string" && c1.children[0].children[2].textContent.length > 0);

  check("卡片2 未绑定 actor", c2.children[0].children[1].textContent === "未绑定玩家");
  check("卡片2 无 target 无详情按钮", !c2.children.some((c) => c.className === "tl-detail"));

  check("卡片3 未知占位符降级未绑定", c3.children[1].innerHTML.includes("未绑定玩家"));
  check("卡片3 已知占位符仍替换", c3.children[1].innerHTML.includes("小明"));

  process.exit(fail ? 1 : 0);
})();
