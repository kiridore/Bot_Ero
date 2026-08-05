// 模拟浏览器环境验证 auth.js 的跨子域 cookie 逻辑
let fakeHost = "gallery.littlero.com";
let fakeProto = "https:";
let cookieStore = {};

global.location = {
  get hostname() { return fakeHost; },
  get protocol() { return fakeProto; },
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
eval(fs.readFileSync("core/web/static/auth.js", "utf8"));

// 1. cookieDomain: 生产子域 → .littlero.com
assertEq(cookieDomain(), ".littlero.com", "子域 domain");
// 2. cookieDomain: IP → 空
fakeHost = "192.168.1.5";
assertEq(cookieDomain(), "", "IP 无 domain");
// 3. cookieDomain: localhost → 空
fakeHost = "localhost";
assertEq(cookieDomain(), "", "localhost 无 domain");
// 4. 登录种 cookie
fakeHost = "gallery.littlero.com";
window.GalleryAuth.save({ user_id: "123", token: "abc:def" });
assertEq(readCookie("botero_key"), "abc:def", "cookie 写入");
// 5. 模拟另一子域（同 cookie store）→ load 从 cookie 恢复
localStorage.removeItem("botero_gallery_session");
fakeHost = "profile.littlero.com";
const s = window.GalleryAuth.load();
assertEq(s.token, "abc:def", "跨子域 cookie 恢复");
assertEq(window.GalleryAuth.isLoggedIn(), true, "跨子域已登录");
assertEq(window.GalleryAuth.headers().Authorization, "Bearer abc:def", "header 带 token");
// 6. clear 双清
window.GalleryAuth.clear();
assertEq(readCookie("botero_key"), "", "cookie 清除");
assertEq(window.GalleryAuth.load(), null, "localStorage 清除后未登录");
console.log("ALL PASS");

function assertEq(actual, expected, name) {
  if (actual !== expected) {
    console.error(`FAIL ${name}: got ${JSON.stringify(actual)}, want ${JSON.stringify(expected)}`);
    process.exit(1);
  }
  console.log(`ok - ${name}`);
}
