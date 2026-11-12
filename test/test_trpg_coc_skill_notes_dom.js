// 技能说明图标：有说明的技能名后出现 ⓘ，title 含注释正文
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const start = src.indexOf("function skillNote(name)");
const end = src.indexOf("function skillRow");
const factory = new Function("options", "canonSkill", "normalizeSkillName", "escapeHtml",
  `${src.slice(start, end)}\nreturn { skillNote, skillNoteTitle };`);

const notes = {
  "会计": { base: "5%", special: "——", note: "· 理解会计工作的流程" },
  "技艺:表演": { base: "5%", special: "技艺的子项", note: "· 受过戏剧训练的演员" },
  "技艺": { base: "——", special: "专业化", note: "· 艺术与手艺的说明" },
  "手枪": { base: "20%", special: "——", note: "· 射击专攻" },
};
const options = { skill_notes: notes };
const api = factory(options, (n) => n, (n) => n, (s) => s);

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

check("精确命中会计", api.skillNote("会计").note.includes("会计工作"));
check("专攻命中子项说明", api.skillNote("技艺:表演").note.includes("戏剧"));
check("未列出的专攻回落类别说明", api.skillNote("技艺:烹饪").note.includes("艺术与手艺"));
check("去掉类别前缀也能命中", api.skillNote("射击:手枪").note.includes("射击专攻"));
check("没有说明返回 null", api.skillNote("飞天") === null);
check("title 含正文与基础值",
  api.skillNoteTitle(notes["会计"]).includes("会计工作") && api.skillNoteTitle(notes["会计"]).includes("基础值 5%"),
  JSON.stringify(api.skillNoteTitle(notes["会计"])));

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
