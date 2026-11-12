// 资产总计：现金 + 其他资产表五类；以及信用评级 → 生活水平档位
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const start = src.indexOf("const LIVING_LEVELS");
const end = src.indexOf("const BACKGROUND_FIELDS");
const factory = new Function(`${src.slice(start, end)}\nreturn { levelForCredit, assetsTotal, LIVING_LEVELS, ASSET_ITEMS };`);
const api = factory();

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

check("六档生活水平", api.LIVING_LEVELS.length === 6 && api.LIVING_LEVELS[5] === "富豪");
check("其他资产五类", api.ASSET_ITEMS.length === 5);

const cases = [[0, "身无分文"], [1, "拮据"], [9, "拮据"], [10, "标准"], [49, "标准"],
               [50, "小康"], [89, "小康"], [90, "富裕"], [98, "富裕"], [99, "富豪"]];
check("信用评级分档", cases.every(([cr, lv]) => api.levelForCredit(cr) === lv),
  cases.map(([cr]) => `${cr}:${api.levelForCredit(cr)}`).join(" "));

check("总和=现金+五类", api.assetsTotal("120000", { vehicle: 300000, residence: "0", luxury: "", securities: 0, other: "0" }) === 420000);
check("现金带符号也能算", api.assetsTotal("¥12,000", {}) === 12000);
check("非数字按 0", api.assetsTotal("很多", { vehicle: "若干", luxury: 5 }) === 5);
check("空值安全", api.assetsTotal(undefined, undefined) === 0);

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
