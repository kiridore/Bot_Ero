// 最小 DOM stub 验证时间线前端（timeline.js）：
// 登录门禁（401 → 登录对话框）、占位符替换、未绑定降级、详情按钮、侧边栏导航、
// 30s 轮询「查看 N 条新事件」pill（去重 prepend/滚动）、逐卡未读/已读（enter→exit 批量回执、
// >100 分批 drain、失败保留、pagehide 兜底、401 停止/重登重建）
const fs = require("fs");

function makeEl(tag) {
  const el = {
    tagName: tag, id: "", className: "", textContent: "",
    children: [], attributes: {}, style: {}, dataset: {},
    _classes: new Set(), _html: "", _listeners: {}, _scrolled: false,
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
    insertBefore(newNode, refNode) {
      if (!refNode) { this.children.push(newNode); return newNode; }
      const idx = this.children.indexOf(refNode);
      if (idx === -1) { this.children.push(newNode); return newNode; }
      this.children.splice(idx, 0, newNode);
      return newNode;
    },
    get firstChild() { return this.children[0] || null; },
    get firstElementChild() { return this.children[0] || null; },
    scrollIntoView() { this._scrolled = true; },
    querySelector(sel) {
      const id = sel.replace("#", "");
      const hit = this.children.find((c) => c.id === id);
      if (hit) return hit;
      if (this._html.includes(`id="${id}"`)) {
        const e = makeEl("div");
        e.id = id;
        return e;
      }
      return null;
    },
    showModal() { this.open = true; },
    close() { this.open = false; },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    add(c) { el._classes.add(c); },
    remove(c) { el._classes.delete(c); },
    contains(c) { return el._classes.has(c); },
  };
  return el;
}

let bodyEl = makeEl("body");
const els = {};
global.location = { hostname: "127.0.0.1", protocol: "http:" };
global.window = {};
global.window.addEventListener = function (type, fn) {
  const l = (global.window._listeners = global.window._listeners || {});
  (l[type] = l[type] || []).push(fn);
};
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

["feed", "sentinel", "tlStatus", "feedEmpty", "tlNav", "authArea", "tlNewEvents"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});

const entriesPayload = [{ name: "打卡图库", desc: "每日打卡", url: "/gallery" }];
const feedPayload = {
  events: [
    {
      seq: 5, id: "checkin:1", source: "checkin", received_at: "2026-08-10 14:00:00", unread: true,
      actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "http://a/1.png" },
      target: { type: "url", url: "https://littlero.tech/gallery" },
      title: "{id:123456} 完成打卡", description: "本周第 1 次",
      data: { images: ["/thumb/123456/abc.image", "/thumb/123456/def.image"] },
    },
    {
      seq: 4, id: "quest:2", source: "quest", received_at: "2026-08-10 13:00:00", unread: false,
      actor: { id: "mc-abc", qq: null, display_name: "未绑定玩家", avatar_url: "" },
      target: null, title: "完成周常任务「随便抽抽」", description: null, data: null,
    },
    {
      seq: 3, id: "checkin:3", source: "checkin", received_at: "2026-08-10 12:00:00", unread: false,
      actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
      target: null,
      title: "{id:999} 与 {id:123456} 组队", description: null, data: null,
    },
  ],
  users: { "123456": { name: "小明", avatar: "http://a/1.png" } },
  next_cursor: null,
};

let timelineAuthed = false;
let pollResult = { count: 0 };
let pollFail = false;
let poll401 = false;
let readFail = false;
let newPages = [];
const readRequests = [];
const fetchedUrls = [];

// 可控 IntersectionObserver：按元素触发相交/离开
const ioInstances = [];
global.IntersectionObserver = class {
  constructor(cb) { this.cb = cb; this.targets = new Set(); ioInstances.push(this); }
  observe(el) { this.targets.add(el); }
  unobserve(el) { this.targets.delete(el); }
  disconnect() { this.targets.clear(); }
};
global.window.IntersectionObserver = global.IntersectionObserver;

function fireIO(el, isIntersecting) {
  const io = ioInstances.find((i) => i.targets.has(el));
  if (!io) return false;
  io.cb([{ target: el, isIntersecting }]);
  return true;
}

// 捕获 interval（轮询 timer），不接管 setTimeout（防抖走真实等待）
const intervals = [];
const _setInterval = global.setInterval.bind(global);
const _clearInterval = global.clearInterval.bind(global);
global.setInterval = function (fn, ms) {
  const t = { fn, ms, cleared: false };
  intervals.push(t);
  return t;
};
global.clearInterval = function (t) { if (t) t.cleared = true; };

async function fakeFetch(url, opts) {
  const u = String(url);
  const method = (opts && opts.method) || "GET";
  fetchedUrls.push(u);
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
  if (u.startsWith("/api/timeline/poll")) {
    if (!timelineAuthed || poll401) return { ok: false, status: 401, json: async () => ({}) };
    if (pollFail) return { ok: false, status: 500, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => pollResult };
  }
  if (u.startsWith("/api/timeline/new")) {
    if (!timelineAuthed) return { ok: false, status: 401, json: async () => ({}) };
    const page = newPages.shift();
    if (!page) return { ok: true, status: 200, json: async () => ({ events: [], users: {}, next_after: null }) };
    return { ok: true, status: 200, json: async () => page };
  }
  if (u.startsWith("/api/timeline/read")) {
    if (!timelineAuthed) return { ok: false, status: 401, json: async () => ({}) };
    if (readFail) return { ok: false, status: 500, json: async () => ({}) };
    readRequests.push(JSON.parse((opts && opts.body) || "{}"));
    return { ok: true, status: 200, json: async () => ({ ok: true, remaining: 0 }) };
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
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  // 1. 未登录：模拟触底 → loadPage → 401 → 登录对话框 + 状态提示
  await wait(50);
  fireIO(els.sentinel, true); // 触发首屏加载（未登录 401）
  await wait(500);
  const dlg = bodyEl.children.find((c) => c.id === "loginDialog");
  check("未登录弹出登录对话框", dlg && dlg.open === true);
  check("未登录状态提示", els.tlStatus.textContent.includes("请先登录"));

  // 2. 侧边栏导航渲染
  const navLinks = els.tlNav.children.filter((c) => c.className === "tl-nav-link");
  check("侧边栏导航渲染 entries", navLinks.length === 1 && navLinks[0].innerHTML.includes("打卡图库"));

  // 3. 登录后首屏渲染（unread 高亮 + 唯一 30s timer + topCursor=seq）
  timelineAuthed = true;
  await window.GalleryAuth.login("test-key");
  await wait(100);
  const frag = els.feed.children[0];
  check("登录后渲染卡片", Array.isArray(frag.children) && frag.children.length === 3);
  const [c1, c2, c3] = frag.children;
  check("未读卡有 tl-unread", c1.classList.contains("tl-unread"));
  check("已读卡无 tl-unread", !c2.classList.contains("tl-unread") && !c3.classList.contains("tl-unread"));
  check("未读卡带 data-event-id", c1.dataset.eventId === "checkin:1");
  check("首次加载注册唯一 30s timer",
        intervals.length === 1 && intervals[0].ms === 30000 && intervals[0].cleared === false);

  // 4. 轮询 2 条新事件 → pill 出现，feed 与位置不变；再次轮询 0 → pill 隐藏
  pollResult = { count: 2 };
  intervals[0].fn();
  await wait(80);
  check("poll 带 after=topCursor", fetchedUrls.some((u) => u.includes("/api/timeline/poll?after=5")));
  check("pill 显示查看 2 条新事件", els.tlNewEvents.textContent === "查看 2 条新事件");
  check("pill 可见", !els.tlNewEvents.classList.contains("hidden"));
  check("轮询不改变 feed", els.feed.children.length === 1 && els.feed.children[0].children.length === 3);
  pollResult = { count: 0 };
  intervals[0].fn();
  await wait(80);
  check("无新事件时 pill 隐藏", els.tlNewEvents.classList.contains("hidden"));

  // 5. 普通 poll 失败保留现有 pill
  pollResult = { count: 3 };
  intervals[0].fn();
  await wait(80);
  pollFail = true;
  intervals[0].fn();
  await wait(80);
  check("poll 失败保留 pill", els.tlNewEvents.textContent === "查看 3 条新事件");
  pollFail = false;
  pollResult = { count: 0 };
  intervals[0].fn();
  await wait(80);

  // 6. 点击 pill：多页拉新、去重、一次 prepend、更新 topCursor、滚动定位
  const eNew1 = {
    seq: 6, id: "checkin:new1", source: "checkin", received_at: "2026-08-10 15:00:00", unread: true,
    actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
    target: null, title: "新事件一", description: null, data: null,
  };
  const eNew2 = {
    seq: 7, id: "checkin:new2", source: "checkin", received_at: "2026-08-10 15:01:00", unread: true,
    actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
    target: null, title: "新事件二", description: null, data: null,
  };
  newPages = [
    { events: [eNew1, feedPayload.events[0]], users: {}, next_after: 6 }, // 含与首屏重叠 id 的 dup
    { events: [eNew2], users: {}, next_after: null },
  ];
  const urlCountBefore = fetchedUrls.filter((u) => u.includes("/api/timeline/new")).length;
  (els.tlNewEvents._listeners.click || []).forEach((fn) => fn());
  await wait(150);
  const newFrag = els.feed.children[0];
  check("新卡按新→旧一次 prepend", Array.isArray(newFrag.children) && newFrag.children.length === 2
        && newFrag.children[0].dataset.eventId === "checkin:new2"
        && newFrag.children[1].dataset.eventId === "checkin:new1");
  check("重叠 id 去重（首屏卡不重复渲染）",
        els.feed.children.length === 2 && els.feed.children[1].children.length === 3);
  check("点击后 pill 隐藏", els.tlNewEvents.classList.contains("hidden"));
  check("新卡滚动定位", els.feed.firstElementChild._scrolled === true);
  check("多页拉取次数", fetchedUrls.filter((u) => u.includes("/api/timeline/new")).length
        === urlCountBefore + 2);

  // 7. 逐卡已读：初始离开不上报；只进入不上报；enter→exit 批量上报并移除高亮
  const readCount0 = readRequests.length;
  fireIO(c1, false); // 初始未相交
  await wait(350); // 防抖窗口
  check("初始离开不上报", readRequests.length === readCount0);
  fireIO(c1, true); // 进入
  await wait(80);
  check("只进入不上报", readRequests.length === readCount0);
  fireIO(c1, false); // 完全离开 → 已读
  await wait(350);
  check("enter→exit 上报已读", readRequests.length === readCount0 + 1
        && (readRequests[readCount0].event_ids || []).includes("checkin:1"));
  check("成功移除未读高亮", !c1.classList.contains("tl-unread"));
  check("已读后停止观察", !ioInstances.some((i) => i.targets.has(c1)));

  // 8. 失败保留高亮与待提交；pagehide 兜底重提
  readFail = true;
  const nc1 = newFrag.children[0]; // prepend 后最上方的未读新卡（checkin:new2）
  const nc1Id = nc1.dataset.eventId;
  fireIO(nc1, true);
  fireIO(nc1, false);
  await wait(350);
  check("失败保留未读高亮", nc1.classList.contains("tl-unread"));
  readFail = false;
  const readCount1 = readRequests.length;
  (global.window._listeners.pagehide || []).forEach((fn) => fn());
  await wait(50);
  check("pagehide 兜底重提", readRequests.length === readCount1 + 1
        && (readRequests[readCount1].event_ids || []).includes(nc1Id));

  // 9. >100 张新卡：成功响应后循环 drain，直到待提交清空
  const bigEvents = [];
  for (let i = 0; i < 120; i++) {
    bigEvents.push({
      seq: 8 + i, id: "checkin:big" + i, source: "checkin",
      received_at: "2026-08-11 08:" + String(Math.floor(i / 60)).padStart(2, "0") + ":"
        + String(i % 60).padStart(2, "0"),
      unread: true,
      actor: { id: "123456", qq: "123456", display_name: "小明", avatar_url: "" },
      target: null, title: "批量事件" + i, description: null, data: null,
    });
  }
  newPages = [{ events: bigEvents, users: {}, next_after: null }];
  (els.tlNewEvents._listeners.click || []).forEach((fn) => fn());
  await wait(150);
  const bigFrag = els.feed.children[0];
  check("批量新卡一次 prepend", bigFrag.children.length === 120);
  const readCount2 = readRequests.length;
  for (const card of bigFrag.children) { fireIO(card, true); fireIO(card, false); }
  await wait(350); // 批次 1（100）
  await wait(350); // 批次 2（20 + 遗留 new1）
  const drainBatches = readRequests.slice(readCount2);
  const drainSizes = drainBatches.map((b) => (b.event_ids || []).length);
  check(">100 分批 drain 至清空",
        drainSizes.length === 2 && drainSizes[0] === 100 && drainSizes[1] === 21, JSON.stringify(drainSizes));
  const allDrainIds = drainBatches.flatMap((b) => b.event_ids || []);
  check("drain 无重复 id", new Set(allDrainIds).size === allDrainIds.length);
  check("drain 后无残留高亮", bigFrag.children.every((c) => !c.classList.contains("tl-unread")));

  // 10. poll 401：停止 timer + 登录框；重新登录清空状态并只重建一个 timer
  poll401 = true;
  intervals[intervals.length - 1].fn();
  await wait(80);
  check("poll 401 停止轮询", intervals[intervals.length - 1].cleared === true);
  check("poll 401 弹出登录框", bodyEl.children.find((c) => c.id === "loginDialog").open === true);
  poll401 = false;
  const intervalsBefore = intervals.length;
  await window.GalleryAuth.login("test-key");
  await wait(100);
  check("重新登录只重建一个 timer",
        intervals.length === intervalsBefore + 1
        && intervals[intervals.length - 1].cleared === false
        && intervals[intervals.length - 2].cleared === true);
  check("重登后 pill 清空隐藏", els.tlNewEvents.classList.contains("hidden"));
  const reFrag = els.feed.children[0];
  check("重登后首屏重渲染", reFrag && reFrag.children.length === 3);

  // 11. 原有渲染契约回归
  const [r1] = reFrag.children;
  check("卡片1 占位符替换为昵称", r1.children[1].innerHTML.includes("tl-user") && r1.children[1].innerHTML.includes("小明"));
  check("卡片1 actor 昵称", r1.children[0].children[1].textContent === "小明");
  check("卡片1 详情按钮", r1.children.some((c) => c.className === "tl-detail" && c.href === "https://littlero.tech/gallery"));
  check("卡片1 具体时间戳", r1.children[0].children[2].textContent === "2026-08-10 14:00:00");
  const strip = r1.children.find((c) => c.className === "tl-images");
  check("卡片1 图片条渲染", strip && strip.children.length === 2);
  check("卡片1 图片缩略图 URL", strip && strip.children[0].children[0].src === "/thumb/123456/abc.image");
  check("卡片1 原图链接 /thumb→/media", strip && strip.children[0].href === "/media/123456/abc.image");
  const [r2, r3] = reFrag.children.slice(1);
  check("卡片2 未绑定 actor", r2.children[0].children[1].textContent === "未绑定玩家");
  check("卡片2 无 target 无详情按钮", !r2.children.some((c) => c.className === "tl-detail"));
  check("卡片3 未知占位符降级未绑定", r3.children[1].innerHTML.includes("未绑定玩家"));
  check("卡片3 已知占位符仍替换", r3.children[1].innerHTML.includes("小明"));

  process.exit(fail ? 1 : 0);
})();
