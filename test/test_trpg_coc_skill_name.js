// COC 建卡页技能名规范化的行为校验：官方名 / 别名 / 「类别:专攻」写法 / 自定义技能。
// 直接从 trpg_coc.js 里截取 canonSkill + normalizeSkillName 两个函数执行，避免复制规则。

const fs = require("fs");
const path = require("path");

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra != null ? " " + extra : ""}`);
  if (!ok) fail++;
}

const src = fs.readFileSync(
  path.join(__dirname, "..", "webapp", "static", "trpg_coc.js"),
  "utf8",
);
const start = src.indexOf("function occAllowedNames");
const end = src.indexOf("function escapeHtml");
if (start < 0 || end < 0 || end <= start) {
  console.log("FAIL - 未找到技能名规范化函数");
  process.exit(1);
}

const options = {
  // 与 coc_data 实际数据一致：类别名本身不在官方技能表里
  skill_base: { "侦察": 25, "图书馆使用": 20, "格斗": 25, "攀爬": 20 },
  skill_categories: ["技艺", "格斗", "射击", "语言", "母语", "驾驶", "科学", "生存", "罕见"],
  skill_aliases: { "侦查": "侦察", "图书馆": "图书馆使用", "外语": "语言" },
  occupation_skills: {
    "3": {"required": ["会计", "技艺:*", "科学:化学"], "choices": [{"count": 2, "from": "*"}]},
  },
};

const factory = new Function(
  "options",
  `${src.slice(start, end)}\nreturn { canonSkill, normalizeSkillName, occAllowedNames, occAllows, requiredSkillNames };`,
);
const { canonSkill, normalizeSkillName, occAllowedNames, occAllows, requiredSkillNames } = factory(options);

check("官方技能名原样通过", normalizeSkillName("侦察") === "侦察");
check("别名归一", canonSkill("侦查") === "侦察" && normalizeSkillName("侦查") === "侦察");
check("类别:专攻 保留", normalizeSkillName("科学:生物学") === "科学:生物学");
check("全角冒号转半角", normalizeSkillName("技艺：摄影") === "技艺:摄影");
check("漏写分隔符自动补", normalizeSkillName("科学生物学") === "科学:生物学");
check("空白裁掉", normalizeSkillName("  语言:拉丁语 ") === "语言:拉丁语");
check("纯类别保留为类别名", normalizeSkillName("科学") === "科学");
check("自定义技能放行", normalizeSkillName("飞天") === "飞天");
check("自定义技能去首尾空白", normalizeSkillName("  飞天  ") === "飞天");
check("自定义技能保留空格", normalizeSkillName("黑客 工具") === "黑客 工具");
check("空字符串拒绝", normalizeSkillName("") === "");

// 职业点允许集合：固定项 + 类别通配 + 已选池内技能
const occ = { seq: 3 };
const none = occAllowedNames(null, {});
check("无职业时为空", none.exact.size === 0 && none.wild.length === 0);
const base = occAllowedNames(occ, {});
check("固定项可加点", occAllows(base, "会计"));
check("类别通配可加点", occAllows(base, "技艺:烹饪") && occAllows(base, "技艺:摄影"));
check("未选中的自由技能不可加点", !occAllows(base, "攀爬"));
const withChoice = occAllowedNames(occ, { "0": ["攀爬", "技艺:伪造"] });
check("已选池内技能可加点", occAllows(withChoice, "攀爬") && occAllows(withChoice, "技艺:伪造"));
check("别名技能按规范名匹配", occAllows(occAllowedNames(occ, {}), "侦查") === false
  && occAllows(occAllowedNames({ seq: 3 }, { "0": ["侦察"] }), "侦查"));

// 选职业时自动补入的本职技能：只取固定项，通配项留给玩家填专攻
const required = requiredSkillNames(options.occupation_skills["3"]);
check("自动补入跳过通配项", required.includes("会计") && !required.some((n) => n.endsWith(":*")), String(required));
check("自动补入保留具体专攻", required.includes("科学:化学"));
check("无职业时为空", requiredSkillNames(null).length === 0);

console.log(fail === 0 ? "\n全部通过" : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
