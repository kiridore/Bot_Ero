// 最小 DOM stub 验证工具箱：列表 item.tags 渲染为卡片标签行，编辑表单预填已有标签。

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: String(tag).toUpperCase(),
    id: "", className: "", textContent: "", title: "", value: "",
    children: [], attributes: {}, style: {}, dataset: {},
    href: undefined, src: undefined, alt: "", type: "", disabled: false,
    _html: "", firstChild: null,
    get innerHTML() { return this._html; },
    set innerHTML(v) {
      this._html = String(v);
      // 图标 svgEl 依赖 firstChild；其余场景只做清空/占位
      this.children = [];
      if (this._html) {
        const child = makeEl("svg");
        this.children.push(child);
        this.firstChild = child;
      } else {
        this.firstChild = null;
      }
    },
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener(type, fn) { (this._listeners = this._listeners || {})[type] = fn; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    focus() {},
    showModal() { this.open = true; },
    close() { this.open = false; },
    reset() {},
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); },
    },
  };
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

const els = {};
[
  "toolList", "toolEmpty", "searchInput", "tagFilterRow", "tagFilterName",
  "tagFilterClear", "tagCloud", "addBtn", "sortSelect", "orderToggle",
  "viewToggle", "addDialog", "addDialogTitle", "addForm", "addMsg",
  "addTitle", "addDesc", "addUrl", "addTags", "addCancel", "authArea", "tlNav",
].forEach((id) => { els[id] = makeEl("div"); els[id].id = id; });

global.location = { hostname: "127.0.0.1", protocol: "http:", pathname: "/tools", search: "", href: "http://127.0.0.1/tools" };
global.window = {};
global.document = {
  createElement: (t) => makeEl(t),
  createTextNode: (t) => { const el = makeEl("text"); el.textContent = String(t); return el; },
  getElementById: (id) => els[id] || null,
  body: { appendChild(c) { els[c.id] = c; } },
  head: { appendChild() {} },
  cookie: "",
};
global.localStorage = (() => {
  let m = {};
  return {
    getItem: (k) => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: (k) => { delete m[k]; },
  };
})();

global.localStorage.setItem("botero_gallery_session", JSON.stringify({
  token: "test-token", user_id: "12345601", display_name: "测试用户",
}));

function jsonResponse(body) {
  return Promise.resolve({ ok: true, status: 200, json: async () => body });
}

const ITEM = {
  id: 7, title: "示例链接", description: "描述", url: "https://example.com",
  domain: "example.com", created_by: "12345601", created_by_name: "测试用户",
  created_by_avatar: "", click_count: 3, tags: ["工具", "效率"],
};

global.fetch = (url) => {
  const u = String(url);
  if (u.startsWith("/api/tools/tags")) return jsonResponse({ tags: [{ name: "工具", count: 1 }] });
  if (u.startsWith("/api/tools?")) return jsonResponse({ items: [ITEM] });
  if (u.startsWith("/api/nav")) return jsonResponse([]);
  return jsonResponse({});
};

eval(fs.readFileSync("core/web/static/auth.js", "utf8"));
global.GalleryAuth = window.GalleryAuth;
eval(fs.readFileSync("core/web/static/icons.js", "utf8"));
global.GalleryIcons = window.GalleryIcons;

eval(fs.readFileSync("webapp/static/tools.js", "utf8"));

setTimeout(() => {
  const wrap = els.toolList.children[0];
  check("列表渲染出一条卡片", !!wrap);
  const anchor = wrap && wrap.children[0];
  const tagRow = anchor && anchor.children.find((c) => c.className === "tools-tags-row");
  check("卡片标签行渲染 item.tags", !!tagRow
    && tagRow.children.map((c) => c.textContent).join(",") === "工具,效率");
  const edit = wrap && wrap.children.find((c) => c.className === "tools-edit");
  check("自己提交的卡片有编辑按钮", !!edit);
  if (edit) edit._listeners.click();
  check("编辑表单预填已有标签", els.addTags.value === "工具, 效率");
  process.exit(fail ? 1 : 0);
}, 100);
