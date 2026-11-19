// 本职属性选择器与预算：真实执行建卡页里的 formulaOptions / pointsBudget / occBudgetFor / renderOccAttr
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
function slice(from, to) {
  const a = src.indexOf(from);
  const b = src.indexOf(to);
  if (a < 0 || b < 0) throw new Error(`找不到片段：${from} … ${to}`);
  return src.slice(a, b);
}
const pure = slice("const ATTR_ORDER", "const ATTR_SCORE");
const picker = slice("function renderOccAttr", "function renderOccChoices");

const checks = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) checks.push(name);
}

// ── 属性值桩：STR45 CON50 SIZ55 DEX70 APP40 INT60 POW65 EDU80 ──
const scores = { 力量: 45, 体质: 50, 体型: 55, 敏捷: 70, 外貌: 40, 智力: 60, 意志: 65, 教育: 80 };
const ATTR_SCORE = new Proxy({}, { get: (_t, key) => () => scores[key] });

// ── DOM stub ───────────────────────────────────
let box = null;
function makeInputs() {
  const list = [];
  return {
    list,
    querySelectorAll() { return list; },
  };
}
const occupationEl = { value: "" };
const document = {
  getElementById(id) {
    if (id === "occupation") return occupationEl;
    if (id === "occ-attr") return box;
    return null;
  },
};
const OCCUPATIONS = [
  { name: "猎人", formula: "教育×2＋力量或敏捷×2" },
  { name: "自定义职业", formula: "教育×4" },
  { name: "会计师", formula: "教育×4" },
];
function currentOccupation() {
  const name = occupationEl.value.trim();
  return OCCUPATIONS.find((o) => o.name === name) || null;
}
let rerendered = 0;
function rerenderDerived() { rerendered += 1; }

const factory = new Function(
  "document", "ATTR_SCORE", "currentOccupation", "rerenderDerived",
  `let occAttr = "";\n${pure}\n${picker}\n` +
  `return { formulaOptions, pointsBudget, occBudgetFor, renderOccAttr,` +
  ` get occAttr() { return occAttr; }, set occAttr(v) { occAttr = v; } };`,
);
const api = factory(document, ATTR_SCORE, currentOccupation, rerenderDerived);

function newBox() {
  const inputs = [];
  const el = {
    hidden: null,
    html: "",
    set innerHTML(v) {
      this.html = v;
      inputs.length = 0;
      const re = /<input[^>]*name="occAttr"[^>]*value="([^"]*)"[^>]*>/g;
      let m;
      while ((m = re.exec(v))) {
        const handlers = [];
        inputs.push({ value: m[1], handlers, addEventListener: (_e, fn) => handlers.push(fn) });
      }
    },
    get innerHTML() { return this.html; },
    querySelectorAll() { return inputs; },
    inputs,
  };
  return el;
}

// ── formulaOptions / 预算 ──────────────────
check("公式候选项", JSON.stringify(api.formulaOptions("教育×2＋力量或敏捷×2")) === '["力量","敏捷"]');
check("无或时无候选项", api.formulaOptions("教育×4").length === 0);
const hunter = OCCUPATIONS[0];
check("默认取高", api.occBudgetFor(hunter, "") === 300, String(api.occBudgetFor(hunter, "")));
check("按力量", api.occBudgetFor(hunter, "力量") === 250, String(api.occBudgetFor(hunter, "力量")));
check("按敏捷", api.occBudgetFor(hunter, "敏捷") === 300);
const custom = OCCUPATIONS[1];
check("自定义留空=教育×4", api.occBudgetFor(custom, "") === 320);
check("自定义第二属性", api.occBudgetFor(custom, "意志") === 160 + 130, String(api.occBudgetFor(custom, "意志")));

// ── 选择器渲染 ─────────────────────────────
box = newBox();
occupationEl.value = "猎人";
api.renderOccAttr();
check("猎人显示选择器", box.hidden === false);
check("猎人有三个单选项（置空+力量+敏捷）", box.inputs.length === 3, String(box.inputs.length));
check("候选项覆盖两个属性",
  box.inputs.some((i) => i.value === "力量") && box.inputs.some((i) => i.value === "敏捷"));
check("默认选中取高",
  (box.inputs.find((i) => i.value === "") || {}).value === "" && box.html.includes("不指定（取高）"));

occupationEl.value = "自定义职业";
box = newBox();
api.renderOccAttr();
check("自定义职业九个单选项", box.inputs.length === 9, String(box.inputs.length));
check("自定义职业带留空说明", box.html.includes("留空（视为教育）"));
check("自定义职业列出八属性", ["力量", "体质", "体型", "敏捷", "外貌", "智力", "意志", "教育"]
  .every((a) => box.inputs.some((i) => i.value === a)));

occupationEl.value = "会计师";
box = newBox();
api.renderOccAttr();
check("无「或」的职业不显示选择器", box.hidden === true && box.html === "");

occupationEl.value = "猎人";
api.occAttr = "意志";     // 卡上残留的非法选择
box = newBox();
api.renderOccAttr();
check("非法选择被清空", api.occAttr === "");

// ── 选择后重算 ─────────────────────────────
box.inputs.find((i) => i.value === "力量").handlers.forEach((fn) => fn());
check("选中力量后 occAttr=力量", api.occAttr === "力量");
check("选中力量触发重算", rerendered > 0);
check("选中后预算按力量", api.occBudgetFor(hunter, api.occAttr) === 250);

const css = fs.readFileSync("webapp/static/trpg.css", "utf8");
check("样式里定义了 #occ-attr", css.includes("#occ-attr {"));

console.log(checks.length ? `\n${checks.length} 项失败` : "\n全部通过");
process.exit(checks.length ? 1 : 0);
