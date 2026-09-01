// 最小 DOM stub 验证 schedule.js：
// 月历网格 42 格、周一起始偏移、过去日 past、今天 today、
// 我的/别人的 chip 类名、+N 折叠、点格子预填表单日期。
const fs = require("fs");

const FIXED = new Date(2026, 8, 15, 10, 0, 0); // 2026-09-15 周二
class FakeDate extends Date {
  constructor(...a) { a.length ? super(...a) : super(FIXED.getTime()); }
  static now() { return FIXED.getTime(); }
}

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", textContent: "", value: "", name: "",
    disabled: false, checked: false, children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    setAttribute(k, v) { this.attributes = this.attributes || {}; this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
    prepend(c) { this.children.unshift(c); return c; },
    querySelector(sel) { return fromHtml(sel.replace("#", "")); },
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
    add(c) { this._s.add(c); syncClass(); },
    remove(...cs) { cs.forEach((c) => this._s.delete(c)); syncClass(); },
    toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); syncClass(); },
    contains(c) { return this._s.has(c); },
  };
  // 页面代码用 className 字符串赋值（如 cell.className="cal-cell"），
  // stub 需双向同步字符串 ↔ classList 集合，byClass 才能命中
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
for (const id of ["scheduleMain", "loginDialog", "loginForm", "loginKey", "loginError",
  "loginCancel", "alarmDialog", "dayDialog", "alarmDlgClose", "dayDlgClose",
  "alarmDlgEdit", "alarmDlgCancel", "alarmDlgBody", "alarmDlgActions", "dayDlgList", "dayDlgTitle", "authArea"]) {
  els[id] = makeEl(id === "loginForm" ? "form" : id.endsWith("Dialog") ? "dialog" : "div");
  els[id].id = id;
}

global.Date = FakeDate;
global.location = { hostname: "127.0.0.1", pathname: "/profile/schedule" };
// 从 innerHTML 片段回建带 id 的元素（缓存），供 getElementById/querySelector 使用
const HTML_ELS = {};
function fromHtml(id) {
  if (els[id]) return els[id];
  if (HTML_ELS[id]) return HTML_ELS[id];
  const direct = ALL_ELS.find((e) => e.id === id);
  if (direct) return direct; // createElement 建的真实节点直接返回，读写不丢
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

const CAL_DAYS = {
  "2026-09-15": [
    { id: 1, time: "08:00", content: "我的每天", date: "2026-09-15", is_mine: true, scope: "private",
      is_recurring: true, recur_kind: 1, recur_a: 1, recur_b: 0, recur_desc: "每天", creator_name: "我" },
    { id: 2, time: "09:00", content: "别人的群", date: "2026-09-15", is_mine: false, scope: "group",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "别人" },
    { id: 3, time: "10:00", content: "第三条", date: "2026-09-15", is_mine: true, scope: "group",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "我" },
    { id: 4, time: "11:00", content: "第四条", date: "2026-09-15", is_mine: true, scope: "private",
      is_recurring: false, recur_kind: 0, recur_a: 0, recur_b: 0, recur_desc: null, creator_name: "我" },
  ],
};
global.fetch = async (path) => {
  if (path.startsWith("/api/me/calendar")) {
    return { ok: true, status: 200, json: async () => ({ month: "2026-09", days: CAL_DAYS, min_lead_minutes: 5 }) };
  }
  if (path === "/api/me/alarms") {
    return { ok: true, status: 200, json: async () => ({ items: [], min_lead_minutes: 5 }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: "1", display_name: "测试", avatar_url: "" }),
  headers: () => ({}),
  refreshMe: async () => ({}),
};
global.window = { addEventListener() {} };
global.confirm = () => true;

eval(fs.readFileSync("webapp/static/schedule.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }
const byClass = (cls) => ALL_ELS.filter((e) => e.classList && e.classList.contains(cls));

(async () => {
  await wait(150); // boot → loadAll → renderAll

  // 1. 网格 42 格，2026-09-01 为周二 → 首格 2026-08-31（周一）dim
  const cells = byClass("cal-cell");
  check("月历 42 格", cells.length === 42);
  check("首格为上月末且 dim", cells[0].dataset.date === "2026-08-31" && cells[0].classList.contains("dim"));

  // 2. 过去日 past、今天 today
  const cellOf = (key) => cells.find((c) => c.dataset.date === key);
  check("过去日 past", cellOf("2026-09-01").classList.contains("past"));
  check("今天 today", cellOf("2026-09-15").classList.contains("today"));

  // 3. chip：3 条上限 + mine/other 类名
  const chips = cellOf("2026-09-15").children.filter((c) => c.classList.contains("cal-chip"));
  check("chip 最多 3 条 + +N 折叠", chips.length === 4 && chips[3].classList.contains("more") && chips[3].textContent === "+1 更多");
  check("我的 chip mine", chips[0].classList.contains("mine"));
  check("别人的 chip other", chips[1].classList.contains("other"));

  // 4. 点未来日空白 → 预填 once_date + 日期（selectDay 会重建日历，重新取节点）
  const target = cellOf("2026-09-20");
  const click = target._listeners.click[0];
  await click();
  const cellsAfter = byClass("cal-cell").slice(-42); // 重渲染后新批次（旧节点仍在 ALL_ELS）
  const dateInput = [...ALL_ELS].reverse().find((e) => e.id === "alarmDate");
  check("点格预填指定日期", formState.scheduleType === "once_date" && dateInput && dateInput.value === "2026-09-20");
  check("选中格高亮", cellsAfter.find((c) => c.dataset.date === "2026-09-20").classList.contains("selected"));

  // 5. 我的 chip 点击 → 详情悬浮窗含编辑入口（合成事件：listener 里调 e.stopPropagation）
  const ev = { stopPropagation() {} };
  const mineChip = chips[0];
  await mineChip._listeners.click[0](ev);
  check("详情悬浮窗打开", els.alarmDialog.open === true);
  check("我的闹钟显示编辑入口", !els.alarmDlgActions.classList.contains("hidden"));
  check("详情含创建人", els.alarmDlgBody._html.includes("我（"));

  // 6. 别人的闹钟 → 编辑入口隐藏
  await chips[1]._listeners.click[0](ev);
  check("别人的闹钟隐藏编辑入口", els.alarmDlgActions.classList.contains("hidden"));

  process.exit(fail ? 1 : 0);
})();
