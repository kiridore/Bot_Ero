// 用 Proxy 沙箱实际执行 trpg_coc.js 的 bind()，捕获「标识符未定义」这类运行时错误
// （node --check 只查语法，查不出 skillInput is not defined）

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(path.join(__dirname, "..", "webapp", "static", "trpg_coc.js"), "utf8");
const start = src.indexOf("function bind()");
const end = src.indexOf("\nasync function save(", start);
if (start < 0 || end < 0) {
  console.log("FAIL - 未找到 bind() 区块");
  process.exit(1);
}
const block = src.slice(start, end);

function element() {
  const el = {
    value: "", textContent: "", innerHTML: "", checked: false, disabled: false, title: "",
    style: {},
    classList: { toggle() {}, add() {}, remove() {} },
    addEventListener() {}, insertAdjacentHTML() {}, appendChild() {}, focus() {},
    querySelector: () => element(), querySelectorAll: () => [], matches: () => false,
    dataset: {},
  };
  return el;
}

const stubs = {
  document: {
    getElementById: () => element(),
    querySelector: () => element(),
    querySelectorAll: () => [],
    createElement: () => element(),
    addEventListener() {},
  },
  window: { location: { href: "", pathname: "/trpg/coc" } },
  options: { skill_base: { 侦察: 25 }, skill_categories: ["技艺"], skill_aliases: {}, occupation_skills: {}, occupations: [] },
  card: { skills: {}, weapons: [] },
  occChoices: {},
  main: element(),
  CHAR_ID: null,
  canonSkill: (n) => n,
  normalizeSkillName: (n) => n,
  currentOccupation: () => null,
  renderOccChoices: () => {},
  syncChosenSkills: () => {},
  rerenderDerived: () => {},
  showToast: () => {},
  pointsBudget: () => 0,
  poolHint: () => "",
  attr: () => 0,
  skillRow: () => "",
  weaponRow: () => "",
  ATTR_SCORE: { 力量: () => 0, 体质: () => 0, 体型: () => 0, 敏捷: () => 0, 外貌: () => 0, 智力: () => 0, 意志: () => 0, 教育: () => 0 },
};

// 未声明的标识符一律返回桩函数/桩对象，避免误报；已经声明的正常解析
const sandbox = new Proxy(stubs, {
  has: () => true,
  get: (target, key) => {
    if (key in target) return target[key];
    if (key === Symbol.unscopables) return undefined;
    return function stub() { return stub; };
  },
});

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fail++;
}

try {
  vm.runInNewContext(`${block}\nbind();`, sandbox, { timeout: 5000 });
  check("bind() 可执行且所有标识符已定义", true);
} catch (err) {
  check("bind() 可执行且所有标识符已定义", false, String(err && err.message).slice(0, 120));
}

console.log(fail === 0 ? "\n全部通过" : `\n${fail} 项失败`);
process.exit(fail === 0 ? 0 : 1);
