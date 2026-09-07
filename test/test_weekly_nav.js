// 最小 DOM stub 验证 weekly.js renderNav 翻期方向：
// issues 按 week_key DESC（最新在前）→「上一期」= 更旧（idx+1）、「下一期」= 更新（idx-1）；
// 边界：最旧一期上一期禁用、最新一期下一期禁用。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", className: "", textContent: "", value: "", disabled: false,
    children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    addEventListener(t, f) { (el._listeners[t] = el._listeners[t] || []).push(f); },
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => el.children.push(c)); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    onclick: null, onchange: null,
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

const els = {};
for (const id of ["weeklyMain", "weeklyEmpty", "issueSelect", "prevIssue", "nextIssue",
  "weeklyDateRange", "weeklyPaper", "authArea"]) {
  els[id] = makeEl(id === "issueSelect" ? "select" : "div");
  els[id].id = id;
}

global.location = { pathname: "/weekly/2026-W34", href: "" };
global.document = {
  createElement: makeEl,
  getElementById: (id) => els[id] || makeEl("div"),
  addEventListener() {},
};

global.fetch = async (path) => {
  if (path === "/api/weekly") return { ok: true, status: 200, json: async () => ({ items: [] }) };
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: "1", display_name: "测", avatar_url: "" }),
  headers: () => ({}),
  renderAuth() {},
};
global.window = { addEventListener() {} };

eval(fs.readFileSync("webapp/static/weekly.js", "utf8"));

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

// DESC：最新在前。当前 W34（中间）→ 上一期 W33（更旧，idx+1）、下一期 W35（更新，idx-1）
const ITEMS = [
  { week_key: "2026-W35", issue: 9, start: "2026-08-24" },
  { week_key: "2026-W34", issue: 8, start: "2026-08-17" },
  { week_key: "2026-W33", issue: 7, start: "2026-08-10" },
];

renderNav(ITEMS);
els.prevIssue.onclick();
check("上一期跳更旧一期", location.href === "/weekly/2026-W33");
location.href = "";
els.nextIssue.onclick();
check("下一期跳更新一期", location.href === "/weekly/2026-W35");
check("中间期两按钮可用", !els.prevIssue.disabled && !els.nextIssue.disabled);

// 边界：最旧（W33）→ 上一期禁用；最新（W35）→ 下一期禁用
(async () => {
  const HEAD = [{ week_key: "2026-W34", issue: 8 }, { week_key: "2026-W33", issue: 7 }];
  const TAIL = [{ week_key: "2026-W35", issue: 9 }, { week_key: "2026-W34", issue: 8 }];
  // weekKey=W34：HEAD 中 idx=0（最新）→ 下一期禁用；TAIL 中 idx=1（最旧）→ 上一期禁用
  els.nextIssue.disabled = false; els.prevIssue.disabled = false;
  renderNav(HEAD);
  check("最新一期下一期禁用", els.nextIssue.disabled === true && els.prevIssue.disabled === false);
  els.nextIssue.disabled = false; els.prevIssue.disabled = false;
  renderNav(TAIL);
  check("最旧一期上一期禁用", els.prevIssue.disabled === true && els.nextIssue.disabled === false);
  process.exit(fail ? 1 : 0);
})();
