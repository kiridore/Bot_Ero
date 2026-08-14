// 最小 DOM stub 验证发新帖/编辑页：title/tags 输入框按 Enter 不触发表单提交

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
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

function fire(el, key) {
  const ev = { key, preventDefault() { ev._prevented = true; } };
  if (el._listeners && el._listeners.keydown) el._listeners.keydown(ev);
  return ev._prevented === true;
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

const els = {};
global.location = { hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/forum/new" };
global.window = {};
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

["msg", "type", "body-section", "poll-section", "poll-options", "body_json", "compose",
 "title", "tags", "editor", "add-option", "deadline", "anonymous", "authArea",
 "pageTitle", "submitBtn"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});
els.title.value = "";
els.tags.value = "";

const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(authSrc);
global.GalleryAuth = window.GalleryAuth;

const newSrc = fs.readFileSync("webapp/static/forum_new.js", "utf8");
eval(newSrc);

(async () => {
  await new Promise((r) => setTimeout(r, 120)); // 等 IIFE 越过 Tiptap 动态 import 失败
  check("title 注册了 keydown 监听", typeof els.title._listeners.keydown === "function");
  check("tags 注册了 keydown 监听", typeof els.tags._listeners.keydown === "function");
  check("title 按 Enter → preventDefault", fire(els.title, "Enter"));
  check("tags 按 Enter → preventDefault", fire(els.tags, "Enter"));
  check("title 按普通键不拦截", !fire(els.title, "a"));
  process.exit(fail ? 1 : 0);
})();
