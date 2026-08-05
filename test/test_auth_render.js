// 最小 DOM stub 验证 auth.js renderAuth / ensureLoginDialog
const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, open: false, style: {},
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
global.location = { hostname: "gallery.littlero.tech", protocol: "https:" };
global.window = {};
global.document = {
  createElement: (t) => makeEl(t),
  getElementById: (id) => els[id] || null,
  body: { appendChild(c) { bodyEl.children.push(c); els[c.id] = c; } },
  head: { appendChild() {} },
  cookie: "",
};
global.localStorage = (() => { let m = {}; return {
  getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); },
  removeItem: (k) => { delete m[k]; }, }; })();

const src = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(src);

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

// 1. 未登录 → 登录按钮
els.authArea = makeEl("div");
window.GalleryAuth.renderAuth(els.authArea);
check("未登录渲染登录按钮", els.authArea.children.length === 1 && els.authArea.children[0].className === "btn-login");

// 2. ensureLoginDialog 注入（页面无 dialog 时）
const dlg = window.GalleryAuth.ensureLoginDialog();
check("无 dialog 时自动注入", dlg.id === "loginDialog" && bodyEl.children.some((c) => c.id === "loginDialog"));
check("已有 dialog 时复用", window.GalleryAuth.ensureLoginDialog() === dlg);

// 3. 已登录 → user-chip
els.authArea2 = makeEl("div");
window.GalleryAuth.save({ user_id: "123", display_name: "<埃洛>", token: "k" });
window.GalleryAuth.renderAuth(els.authArea2);
check("已登录渲染 user-chip", els.authArea2.children.length === 1 && els.authArea2.children[0].className === "user-chip");
check("display_name 转义", els.authArea2.children[0].children[1].innerHTML.includes("&lt;埃洛&gt;"));

// 4. 清除后恢复未登录
window.GalleryAuth.clear();
els.authArea3 = makeEl("div");
window.GalleryAuth.renderAuth(els.authArea3);
check("登出后回到登录按钮", els.authArea3.children.length === 1 && els.authArea3.children[0].className === "btn-login");

process.exit(fail ? 1 : 0);
