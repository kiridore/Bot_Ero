// 验证主页 auth 初始化（webapp/homepage/app.js 新增的两行）：
// 登出态 → authArea 渲染出 .btn-login 登录按钮；登录态 → 渲染 .user-chip
const fs = require("fs");

function makeElement(tag) {
  const el = {
    tagName: tag,
    className: "",
    textContent: "",
    innerHTML: "",
    value: "",
    style: {},
    classList: { add() {}, remove() {} },
    children: [],
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    addEventListener() {},
    setAttribute() {},
    querySelector() { return null; },
  };
  return el;
}

let authArea = makeElement("div");
let currentFetchStatus = 401;

global.location = { hostname: "littlero.tech", pathname: "/", protocol: "http:" };
global.window = globalThis;
global.localStorage = {
  _d: {},
  getItem(k) { return k in this._d ? this._d[k] : null; },
  setItem(k, v) { this._d[k] = String(v); },
  removeItem(k) { delete this._d[k]; },
};
global.document = {
  cookie: "",
  createElement: makeElement,
  getElementById(id) {
    if (id === "authArea") return authArea;
    return null;
  },
  head: { appendChild() {} },
  body: { appendChild() {}, insertBefore() {} },
};
global.fetch = async (url) => {
  if (url === "/api/auth/me") {
    if (currentFetchStatus === 200) {
      return { ok: true, json: async () => ({ user_id: "1057613133", display_name: "埃洛Erodis", avatar_url: "" }) };
    }
    return { ok: false };
  }
  return { ok: false };
};

eval(fs.readFileSync("core/web/static/auth.js", "utf8"));

const checks = [];
(async () => {
  // 场景 1：未登录（refreshMe 401 → clear → renderAuth 渲染登录按钮）
  eval(`
    GalleryAuth.refreshMe().finally(() => {
      GalleryAuth.renderAuth(document.getElementById("authArea"));
    });
  `);
  await new Promise((r) => setTimeout(r, 30));
  const btn = authArea.children[0];
  checks.push([
    "未登录渲染登录按钮",
    btn && btn.tagName === "button" && btn.className === "btn-login" && btn.textContent === "登录",
  ]);

  // 场景 2：已登录（refreshMe 200 → 渲染 user-chip）
  authArea = makeElement("div");
  currentFetchStatus = 200;
  global.localStorage.setItem("botero_gallery_session", JSON.stringify({ token: "x", display_name: "埃洛Erodis", user_id: "1057613133" }));
  eval(`
    GalleryAuth.refreshMe().finally(() => {
      GalleryAuth.renderAuth(document.getElementById("authArea"));
    });
  `);
  await new Promise((r) => setTimeout(r, 30));
  const chip = authArea.children[0];
  checks.push([
    "已登录渲染用户卡片",
    chip && chip.tagName === "a" && chip.className === "user-chip",
  ]);

  let fail = 0;
  for (const [name, ok] of checks) {
    console.log(`${ok ? "ok" : "FAIL"} - ${name}`);
    if (!ok) fail++;
  }
  process.exit(fail ? 1 : 0);
})();
