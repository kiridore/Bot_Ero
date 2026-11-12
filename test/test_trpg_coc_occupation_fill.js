// 选职业后自动补入本职技能（固定项）与换职业时的清理：真实执行建卡页里的两个函数
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
function slice(from, to) {
  const a = src.indexOf(from);
  const b = src.indexOf(to);
  if (a < 0 || b < 0) throw new Error(`找不到片段：${from} … ${to}`);
  return src.slice(a, b);
}
const helpers = slice("function requiredSkillNames", "function escapeHtml");
const fillers = slice("function fillRequiredSkills", "function syncChosenSkills");

const checks = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) checks.push(name);
}

const options = {
  skill_base: { 会计: 5, 急救: 30, 侦察: 25 },
  skill_aliases: { 侦查: "侦察" },
  skill_categories: ["科学", "技艺"],
  occupation_skills: {
    "3": { required: ["会计", "技艺:*", "科学:化学", "急救"], choices: [] },
    "9": { required: ["侦察", "技艺:*"], choices: [] },
  },
};

// ── 最小 DOM stub：只保留技能表相关行为 ──────────────
const rows = [];
function makeRow(name) {
  const cells = { "[data-growth]": 0, "[data-occ]": 0, "[data-int]": 0 };
  return {
    dataset: { name },
    removed: false,
    cells,
    querySelector(sel) {
      return { value: cells[sel] ?? 0 };
    },
    remove() { this.removed = true; },
  };
}
const skillBody = {
  insertAdjacentHTML(_pos, html) {
    const name = (html.match(/data-name="([^"]+)"/) || [])[1];
    rows.push(makeRow(name));
  },
};
global.document = {
  getElementById: (id) => (id === "skillBody" ? skillBody : null),
  querySelectorAll: (sel) => (sel === "[data-skill]" ? rows.filter((r) => !r.removed) : []),
};
global.autoAdded = new Set();

const factory = new Function(
  "options",
  "document",
  "skillRow",
  `${helpers}\n${fillers}\nreturn { requiredSkillNames, fillRequiredSkills, pruneAutoAdded, get autoAdded() { return autoAdded; } };`,
);
const api = factory(
  options,
  global.document,
  (name) => `<tr data-skill data-name="${name}"></tr>`,
);
global.autoAdded = api.autoAdded;

// ── 补入固定项 ─────────────────────────────────
const added = api.fillRequiredSkills({ seq: 3 });
// 固定项共 4 条，其中「技艺:*」是通配 → 补 会计 / 科学:化学 / 急救 三行
check("补入三条固定本职技能", added === 3, `added=${added}`);
check("技能表出现会计与急救", rows.some((r) => r.dataset.name === "会计") && rows.some((r) => r.dataset.name === "急救"));
check("通配项不自动补", !rows.some((r) => r.dataset.name.includes(":*")));
check("具体专攻照常补入", rows.some((r) => r.dataset.name === "科学:化学"));
check("重复调用不重复添加", api.fillRequiredSkills({ seq: 3 }) === 0);

// ── 换职业：撤掉没填点数的自动行 ────────────────
const accounting = rows.find((r) => r.dataset.name === "会计");
accounting.cells["[data-int]"] = 10;   // 玩家已经填了兴趣点
api.pruneAutoAdded();
check("已填点数的行保留", !accounting.removed);
check("未填点数的自动行撤掉", rows.filter((r) => r.removed).length === 2, `removed=${rows.filter((r) => r.removed).length}`);

// ── 换到另一个职业 ──────────────────────────────
const added2 = api.fillRequiredSkills({ seq: 9 });
check("新职业补入其本职技能", added2 === 1 && rows.some((r) => r.dataset.name === "侦察" && !r.removed));
check("无职业时不补", api.fillRequiredSkills(null) === 0);

console.log(checks.length ? `\n${checks.length} 项失败` : "\n全部通过");
process.exit(checks.length ? 1 : 0);
