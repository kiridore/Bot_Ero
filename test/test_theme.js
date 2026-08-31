// theme.js 行为验证：<head> 同步加载时依 localStorage 设置 <html data-theme>；
// 非法值回退默认（无属性）；BoteroTheme.get/set 读写 localStorage。
const fs = require("fs");

function makeEnv(stored) {
  const store = { value: stored };
  const calls = { set: [], remove: 0 };
  const env = {
    documentElement: { dataset: {} },
  };
  global.localStorage = {
    getItem: (k) => (k === "botero_theme" ? store.value : null),
    setItem: (k, v) => { if (k === "botero_theme") { store.value = v; calls.set.push(v); } },
    removeItem: (k) => { if (k === "botero_theme") { store.value = null; calls.remove++; } },
  };
  global.document = { documentElement: env.documentElement };
  global.window = {};
  return { store, calls };
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

const src = fs.readFileSync("core/web/static/theme.js", "utf8");

// 1. 预存 dark → 首帧前已设置 data-theme
{
  const { store } = makeEnv("dark");
  eval(src);
  check("预存 dark → <html data-theme=dark>", global.document.documentElement.dataset.theme === "dark");
  check("get() 返回 dark", window.BoteroTheme.get() === "dark");
}

// 2. 无记录 / 非法值 → 无属性、get() 回退 ""
for (const v of [null, "neon"]) {
  makeEnv(v);
  eval(src);
  check(`预存 ${v} → 无 data-theme 属性`, !("theme" in global.document.documentElement.dataset));
  check(`预存 ${v} → get() 为 ""`, window.BoteroTheme.get() === "");
}

// 3. set("mono") → 属性 + localStorage 写入
{
  const { store, calls } = makeEnv(null);
  eval(src);
  window.BoteroTheme.set("mono");
  check("set(mono) → <html data-theme=mono>", global.document.documentElement.dataset.theme === "mono");
  check("set(mono) → localStorage=mono", store.value === "mono" && calls.set.length === 1);
}

// 4. set("") → 清属性 + removeItem
{
  const { store, calls } = makeEnv("dark");
  eval(src);
  window.BoteroTheme.set("");
  check("set(\"\") → 属性清除", !("theme" in global.document.documentElement.dataset));
  check("set(\"\") → removeItem 调用", calls.remove === 1 && store.value === null);
}

// 5. set 非法值 → 按默认处理且不写盘
{
  const { store } = makeEnv(null);
  eval(src);
  window.BoteroTheme.set("neon");
  check("set(neon) → 无属性", !("theme" in global.document.documentElement.dataset));
  check("set(neon) → 不写 localStorage", store.value === null);
}

process.exit(fail ? 1 : 0);
