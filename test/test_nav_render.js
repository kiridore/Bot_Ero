// 最小 DOM stub 验证 nav.js 注入逻辑
const fs = require("fs");
let inserted = null;
let headStyle = null;

global.location = { hostname: "profile.littlero.tech" };
global.document = {
  createElement(tag) {
    return { tagName: tag, textContent: "", className: "", innerHTML: "", attributes: {}, setAttribute(k, v) { this.attributes[k] = v; } };
  },
  head: { appendChild(n) { headStyle = n; } },
  body: { insertBefore(n) { inserted = n; } },
};
eval(fs.readFileSync("core/web/static/nav.js", "utf8"));

const checks = [];
checks.push(["nav 已注入", inserted !== null && inserted.tagName === "nav"]);
checks.push(["nav 类名", inserted && inserted.className === "site-nav"]);
checks.push(["样式已注入", headStyle && headStyle.tagName === "style"]);
checks.push(["含主页入口", inserted && inserted.innerHTML.includes("littlero.tech")]);
checks.push(["当前域高亮", inserted && inserted.innerHTML.includes('class="active"') && inserted.innerHTML.includes("profile.littlero.tech")]);
checks.push(["含全部子域", inserted && ["gallery", "trpg", "guestbook", "alarms", "activities"].every((h) => inserted.innerHTML.includes(h + ".littlero.tech"))]);

let fail = 0;
for (const [name, ok] of checks) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}`);
  if (!ok) fail++;
}
process.exit(fail ? 1 : 0);
