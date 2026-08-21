// 模拟浏览器环境验证 auth.js 的跨子域 cookie 逻辑
let fakeHost = "gallery.littlero.tech";
let fakeProto = "https:";
let cookieStore = {};

global.location = {
  get hostname() { return fakeHost; },
  get protocol() { return fakeProto; },
  origin: "https://gallery.littlero.tech",
  pathname: "/forum",
  search: "",
  href: "",
};
global.document = {
  get cookie() {
    return Object.entries(cookieStore)
      .filter(([, v]) => v !== "")
      .map(([k, v]) => `${k}=${v}`)
      .join("; ");
  },
  set cookie(str) {
    const [pair, ...attrs] = str.split("; ");
    const [k, v] = pair.split("=");
    const isDelete = attrs.some((a) => a.startsWith("max-age=0"));
    if (isDelete || v === "") delete cookieStore[k];
    else cookieStore[k] = v;
  },
};
global.localStorage = (() => {
  let m = {};
  return {
    getItem: (k) => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: (k) => { delete m[k]; },
  };
})();

const fs = require("fs");
global.window = {};
// fetch 打桩：auth.js 挂载 401 拦截包装时捕获本 mock
global.window.fetch = async () => ({ status: 401 });
eval(fs.readFileSync("core/web/static/auth.js", "utf8"));

// 1. cookieDomain: 生产子域 → .littlero.tech
assertEq(cookieDomain(), ".littlero.tech", "子域 domain");
// 2. cookieDomain: IP → 空
fakeHost = "192.168.1.5";
assertEq(cookieDomain(), "", "IP 无 domain");
// 3. cookieDomain: localhost → 空
fakeHost = "localhost";
assertEq(cookieDomain(), "", "localhost 无 domain");
// 4. 登录种 cookie
fakeHost = "gallery.littlero.tech";
window.GalleryAuth.save({ user_id: "123", token: "abc:def" });
assertEq(readCookie("botero_key"), "abc:def", "cookie 写入");
// 5. 模拟另一子域（同 cookie store）→ load 从 cookie 恢复
localStorage.removeItem("botero_gallery_session");
fakeHost = "profile.littlero.tech";
const s = window.GalleryAuth.load();
assertEq(s.token, "abc:def", "跨子域 cookie 恢复");
assertEq(window.GalleryAuth.isLoggedIn(), true, "跨子域已登录");
assertEq(window.GalleryAuth.headers().Authorization, "Bearer abc:def", "header 带 token");
// 6. clear 双清
window.GalleryAuth.clear();
assertEq(readCookie("botero_key"), "", "cookie 清除");
assertEq(window.GalleryAuth.load(), null, "localStorage 清除后未登录");

// 以下为异步断言（401 拦截），完成后统一输出
(async () => {
  // 7. 同源 API 401 → 清会话并跳登录页（next 含查询串）
  location.pathname = "/forum";
  location.search = "?tag=公告";
  location.href = "";
  window.GalleryAuth.save({ user_id: "123", token: "abc:def" });
  const res = await window.fetch("/api/forum/posts");
  assertEq(res.status, 401, "401 响应原样返回");
  assertEq(location.href, "/login?next=" + encodeURIComponent("/forum?tag=公告"), "401 跳登录页带 next");
  assertEq(window.GalleryAuth.load(), null, "401 后清会话");

  // 8. /api/auth/login 的 401 是密钥错误，不拦截
  location.href = "";
  await window.fetch("/api/auth/login");
  assertEq(location.href, "", "登录 API 401 不跳转");

  // 9. 外域 URL 不拦截
  location.href = "";
  await window.fetch("https://qq.example/avatar");
  assertEq(location.href, "", "外域 401 不跳转");

  // 10. 登录页自身不拦截（防自跳循环）
  location.pathname = "/login";
  location.search = "";
  location.href = "";
  await window.fetch("/api/auth/me");
  assertEq(location.href, "", "登录页不拦截");

  console.log("ALL PASS");
})();

function assertEq(actual, expected, name) {
  if (actual !== expected) {
    console.error(`FAIL ${name}: got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`);
    process.exit(1);
  }
  console.log(`ok - ${name}`);
}
