// 最小 DOM stub 验证发新帖/编辑页：表单内单行输入（标题/tag/投票问题/投票选项）按 Enter 不触发表单提交。
// 防护挂在 form 上做事件委托，覆盖动态创建的投票输入框。

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: String(tag).toUpperCase(), // 真实 DOM 的 tagName 是大写 id: "", className: "", textContent: "", innerHTML: "",
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

["msg", "type", "body-section", "poll-section", "polls", "body_json", "compose",
 "title", "tags", "editor", "add-poll", "deadline", "anonymous", "authArea",
 "pageTitle", "submitBtn"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});
els.title.value = "";
els.tags.value = "";

const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(authSrc);
global.GalleryAuth = window.GalleryAuth;

const richSrc = fs.readFileSync("core/web/static/richtext.js", "utf8");
eval(richSrc);
global.RichText = window.RichText;

const newSrc = fs.readFileSync("webapp/static/forum_new.js", "utf8");
eval(newSrc);

(async () => {
  await new Promise((r) => setTimeout(r, 120)); // 等 IIFE 越过 Tiptap 动态 import 失败
  const form = els.compose;
  check("表单注册了 keydown 委托监听", typeof form._listeners.keydown === "function");
  check("单行输入框 Enter → preventDefault（覆盖 title/tags/投票问题/投票选项/截止时间）", fire(form, "Enter", makeEl("input")));
  check("富文本编辑器 Enter 不拦截（正常换行）", !fire(form, "Enter", makeEl("div")));
  check("按钮 Enter 不拦截（聚焦发布按钮回车仍可提交）", !fire(form, "Enter", makeEl("button")));
  check("输入框普通按键不拦截", !fire(form, "a", makeEl("input")));
  process.exit(fail ? 1 : 0);
})();
