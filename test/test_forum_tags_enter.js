// 最小 DOM stub 验证 tag 管理页：tag 名输入框按 Enter 不触发表单提交（只能点「创建」按钮）。

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: String(tag).toUpperCase(), // 真实 DOM 的 tagName 是大写
    id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {}, dataset: {}, href: undefined,
    value: "", disabled: false, hidden: undefined,
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener(type, fn) { (this._listeners = this._listeners || {})[type] = fn; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    classList: { add() {}, remove() {}, contains() { return false; } },
  };
}

function fire(el, key, target) {
  const ev = { key, target: target || el, preventDefault() { ev._prevented = true; } };
  if (el._listeners && el._listeners.keydown) el._listeners.keydown(ev);
  return ev._prevented === true;
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

const els = {};
global.location = { hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/forum/tags" };
global.window = {};
global.fetch = () => Promise.resolve({ ok: true, json: async () => ({ tags: [] }) });
global.document = {
  createElement: (t) => makeEl(t),
  createDocumentFragment: () => makeEl("fragment"),
  getElementById: (id) => els[id] || null,
  body: { appendChild(c) { els[c.id] = c; } },
  head: { appendChild() {} },
  cookie: "",
};
global.localStorage = (() => { let m = {}; return {
  getItem: (k) => (k in m ? m[k] : null),
  setItem: (k, v) => { m[k] = String(v); },
  removeItem: (k) => { delete m[k]; },
}; })();

["tagList", "tagForm", "tagName", "msg", "authArea"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});
els.tagName.value = "";

const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(authSrc);
global.GalleryAuth = window.GalleryAuth;

eval(fs.readFileSync("webapp/static/forum_tags.js", "utf8"));

setTimeout(() => {
  const form = els.tagForm;
  check("表单注册了 keydown 委托监听", typeof form._listeners.keydown === "function");
  check("tag 名输入框 Enter → preventDefault", fire(form, "Enter", makeEl("input")));
  check("按钮 Enter 不拦截（聚焦创建按钮回车仍可提交）", !fire(form, "Enter", makeEl("button")));
  check("输入框普通按键不拦截", !fire(form, "a", makeEl("input")));
  process.exit(fail ? 1 : 0);
}, 50);
