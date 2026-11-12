// 规则默认技能：技能表全部标准技能 + 闪避按 DEX/2；卡上已存的值覆盖默认
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const start = src.indexOf("function skillDefaults");
const end = src.indexOf("// 可加职业点的技能名集合");
if (start < 0 || end < 0) throw new Error("找不到 skillDefaults");
global.document = { querySelector: () => null };   // 属性输入由测试按需替换
const factory = new Function(
  "options",
  "normalizeSkillName",
  `${src.slice(start, end)}\nreturn { skillDefaults, mergeSkillDefaults };`,
);

const options = {
  // 后端 skill_base_map：标准技能 + 专攻 + 武器技能；default_skills 只含标准技能
  skill_base: { 会计: 5, 侦察: 25, 急救: 30, 图书馆使用: 20, 闪避: 0, 母语: 0, "科学:化学": 1, 斗殴: 25 },
  default_skills: ["会计", "侦察", "急救", "图书馆使用", "闪避", "母语"],
  dynamic_bases: { 闪避: { attr: "dex_score", divisor: 2, label: "敏捷÷2" },
                   母语: { attr: "edu_score", divisor: 1, label: "教育" } },
};
const api = factory(options, (n) => n);

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

const defaults = api.skillDefaults(options.skill_base, 55, options.default_skills, options.dynamic_bases);
check("只铺标准技能（不含专攻与武器技能）",
  Object.keys(defaults).length === options.default_skills.length
  && !("科学:化学" in defaults) && !("斗殴" in defaults), String(Object.keys(defaults)));
check("母语基础值取教育输入", defaults["母语"].base === 0, String(defaults["母语"].base));
check("基础值取表值", defaults["会计"].base === 5 && defaults["急救"].base === 30);
check("闪避按 敏捷/2", defaults["闪避"].base === 27, String(defaults["闪避"].base));
check("敏捷缺省为 0",
  api.skillDefaults(options.skill_base, undefined, options.default_skills, options.dynamic_bases)["闪避"].base === 0);

// 属性输入存在时按输入计算（母语 = 教育，闪避 = 敏捷/2）
global.document.querySelector = (sel) => ({ value: sel.includes("edu_score") ? 70 : sel.includes("dex_score") ? 55 : 0 });
const withAttrs = api.skillDefaults(options.skill_base, 55, options.default_skills, options.dynamic_bases);
check("母语随教育", withAttrs["母语"].base === 70, String(withAttrs["母语"].base));
check("闪避随敏捷", withAttrs["闪避"].base === 27, String(withAttrs["闪避"].base));

const merged = api.mergeSkillDefaults(
  { skills: { 会计: { base: 5, occupation: 20 }, 射击游戏: { base: 9 } } },
  60,
);
check("已存技能保留点数", merged["会计"].occupation === 20);
check("已存技能覆盖基础值", merged["会计"].base === 5);
check("闪避按当前敏捷", merged["闪避"].base === 30, String(merged["闪避"].base));
check("表外技能也保留", merged["射击游戏"] && merged["射击游戏"].base === 9);
check("未存技能取默认", merged["急救"].base === 30);

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
