// COC 建卡页技能名规范化的行为校验：官方名 / 别名 / 「类别:专攻」写法 / 无效名。
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
const start = src.indexOf("function canonSkill");
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
};

const factory = new Function("options", `${src.slice(start, end)}\nreturn { canonSkill, normalizeSkillName };`);
const { canonSkill, normalizeSkillName } = factory(options);

check("官方技能名原样通过", normalizeSkillName("侦察") === "侦察");
check("别名归一", canonSkill("侦查") === "侦察" && normalizeSkillName("侦查") === "侦察");
check("类别:专攻 保留", normalizeSkillName("科学:生物学") === "科学:生物学");
check("全角冒号转半角", normalizeSkillName("技艺：摄影") === "技艺:摄影");
check("漏写分隔符自动补", normalizeSkillName("科学生物学") === "科学:生物学");
check("空白裁掉", normalizeSkillName("  语言:拉丁语 ") === "语言:拉丁语");
check("纯类别拒绝", normalizeSkillName("科学") === null);
check("凭空造名拒绝", normalizeSkillName("飞天") === null);
check("空字符串拒绝", normalizeSkillName("") === null);

console.log(fail === 0 ? "\n全部通过" : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
