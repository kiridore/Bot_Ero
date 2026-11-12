// 武器库按卡上「时代」筛选：只需一个纯函数即可覆盖
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const start = src.indexOf("function weaponEraMatches");
const end = src.indexOf("function libraryWeapons");
if (start < 0 || end < 0) throw new Error("找不到 weaponEraMatches");
const factory = new Function(`${src.slice(start, end)}\nreturn { weaponEraMatches };`);
const { weaponEraMatches } = factory();

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

// 卡上时代没填 / 写得笼统 → 不筛选
check("未填时代时全通过", weaponEraMatches("", "1920s") && weaponEraMatches("", "现代") && weaponEraMatches("", "罕见"));
check("其他时代不筛选", weaponEraMatches("未来", "1920s") && weaponEraMatches("未来", "现代"));

// 1920s 卡
check("1920s 卡只认 1920s 武器", weaponEraMatches("1920s", "1920s") && weaponEraMatches("1920年代", "1920s,现代"));
check("1920s 卡排除现代限定武器", !weaponEraMatches("1920s", "现代"));
check("1920s 卡排除罕见武器", !weaponEraMatches("1920s", "罕见"));

// 现代卡
check("现代卡认现代武器", weaponEraMatches("现代", "现代") && weaponEraMatches("2020年", "1920s,现代"));
check("现代卡排除只标 1920s 的武器", !weaponEraMatches("现代", "1920s"));

// 多标签与空标签
check("多标签武器按任一命中", weaponEraMatches("1920s", "1920s,现代") && weaponEraMatches("现代", "1920s,现代"));
check("武器未标时代时总是通过", weaponEraMatches("1920s", "") && weaponEraMatches("现代", ""));

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
