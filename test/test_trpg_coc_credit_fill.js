// 信用评级自动填充：选职业补下限、旧卡从资产区迁移、已有加点不覆盖
// （真实执行 trpg_coc.js 里的 fillCreditFloor / seedCreditFromAsset / syncCreditAssets）

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(path.join(__dirname, "..", "webapp", "static", "trpg_coc.js"), "utf8");
function slice(from, to) {
  const a = src.indexOf(from);
  const b = src.indexOf(to);
  if (a < 0 || b < 0) throw new Error(`找不到片段：${from} … ${to}`);
  return src.slice(a, b);
}
const baseBlock = slice("function skillBaseFor", "function poolHint");
const creditBlock = slice("function isCreditSkill", "function skillRow");
const occBlock = slice("function occAllowedNames", "function poolHint");

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fail++;
}

function makeRow(name) {
  const cells = {
    "[data-base]": { value: "0" },
    "[data-growth]": { value: "0" },
    "[data-occ]": { value: "0" },
    "[data-int]": { value: "0" },
    "[data-total]": { textContent: "0" },
  };
  return { dataset: { name }, querySelector: (sel) => cells[sel] || null, _cells: cells };
}

function harness() {
  const rows = [makeRow("信用评级")];
  const field = { value: "0", dataset: {} };
  const level = { value: "", dataset: { auto: "1" } };
  const card = { credit_rating: 0 };
  const state = { occ: null };
  const document = {
    getElementById: (id) => (id === "credit_rating" ? field
      : id === "life_level" ? level
        : id === "skillBody" ? { insertAdjacentHTML() {} } : null),
    querySelectorAll: (sel) => (sel === "[data-skill]" ? rows : []),
  };
  const sandbox = {
    document, card, options: {}, occChoices: {}, console,
    currentOccupation: () => state.occ,
    canonSkill: (name) => name,
    levelForCredit: () => "标准",
    skillRow: () => "",
  };
  const ctx = vm.createContext(sandbox);
  vm.runInContext(`${baseBlock}\n${creditBlock}`, ctx);
  const run = (code) => vm.runInContext(code, ctx);
  return { rows, row: rows[0], field, card, state, run, ctx };
}

// 1. 选职业补下限（职业点列）
{
  const h = harness();
  h.state.occ = { name: "药剂师", credit_min: 35, credit_max: 75 };
  h.run("fillCreditFloor(currentOccupation());");
  check("选职业把信用评级补到下限", h.row._cells["[data-occ]"].value === 35,
    String(h.row._cells["[data-occ]"].value));
  check("资产区同步为下限", h.field.value === "35", String(h.field.value));
  check("合计列同步", h.row._cells["[data-total]"].textContent === "35",
    String(h.row._cells["[data-total]"].textContent));
}

// 1b. 先填了兴趣点再选职业：合计不变，下限那部分换成职业点
{
  const h = harness();
  h.state.occ = { name: "药剂师", credit_min: 35, credit_max: 75 };
  h.row._cells["[data-int]"].value = "20";
  h.run("fillCreditFloor(currentOccupation());");
  check("先填兴趣点：下限挪进职业点", h.row._cells["[data-occ]"].value === 35,
    String(h.row._cells["[data-occ]"].value));
  check("先填兴趣点：合计仍按玩家填的 35（下限托底）", h.field.value === "35", String(h.field.value));
}
{
  const h = harness();
  h.state.occ = { name: "药剂师", credit_min: 35, credit_max: 75 };
  h.row._cells["[data-int]"].value = "50";
  h.run("fillCreditFloor(currentOccupation());");
  check("先填兴趣点超过下限：只移下限那部分",
    h.row._cells["[data-occ]"].value === 35 && h.row._cells["[data-int]"].value === 15,
    `${h.row._cells["[data-occ]"].value}/${h.row._cells["[data-int]"].value}`);
}

// 1c. 信用评级永远算本职技能（职业点可编辑），与服务端一致
{
  const h = harness();
  const allowed = vm.runInContext("occAllows({ exact: new Set(), wild: [] }, '信用评级');", h.ctx);
  check("信用评级允许加职业点", allowed === true, String(allowed));
  const other = vm.runInContext("occAllows({ exact: new Set(), wild: [] }, '攀爬');", h.ctx);
  check("其他非本职技能仍被拦", other === false, String(other));
  const struct = vm.runInContext(
    "occAllowedNames({ seq: '3' }, {}).exact.size", h.ctx);
  check("occAllowedNames 不因信用评级改动而变", struct === 0, String(struct));
}

// 2. 已有加点不覆盖
{
  const h = harness();
  h.row._cells["[data-occ]"].value = "40";
  h.row._cells["[data-int]"].value = "5";
  h.state.occ = { name: "古物学家", credit_min: 10, credit_max: 40 };
  h.run("fillCreditFloor(currentOccupation());");
  check("已有加点不被覆盖", h.row._cells["[data-occ]"].value === "40",
    String(h.row._cells["[data-occ]"].value));
}

// 3. 旧卡：资产区有值、技能行空 → 按下限拆成职业点 + 兴趣点
{
  const h = harness();
  h.card.credit_rating = 45;
  h.state.occ = { name: "药剂师", credit_min: 35, credit_max: 75 };
  h.run("seedCreditFromAsset();");
  check("旧卡迁移：下限部分记职业点", h.row._cells["[data-occ]"].value === 35,
    String(h.row._cells["[data-occ]"].value));
  check("旧卡迁移：超出部分记兴趣点", h.row._cells["[data-int]"].value === 10,
    String(h.row._cells["[data-int]"].value));
  check("旧卡迁移后资产区仍是 45", h.field.value === "45", String(h.field.value));
}

// 4. 没有职业时旧值全记兴趣点（职业点不该无职业乱加）
{
  const h = harness();
  h.card.credit_rating = 20;
  h.state.occ = null;
  h.run("seedCreditFromAsset();");
  check("无职业时旧值记兴趣点", h.row._cells["[data-occ]"].value === 0
    && h.row._cells["[data-int]"].value === 20,
    `${h.row._cells["[data-occ]"].value}/${h.row._cells["[data-int]"].value}`);
}

// 5. 技能行已有加点时不再迁移动产区的旧值
{
  const h = harness();
  h.card.credit_rating = 45;
  h.row._cells["[data-occ]"].value = "35";
  h.run("seedCreditFromAsset();");
  check("已有加点时不重复迁移", h.row._cells["[data-int]"].value === "0",
    String(h.row._cells["[data-int]"].value));
}

// 6. 接线守卫：职业变更先补下限（不受「职业没变」的早退影响），加载后也补一次
check("职业变更先补下限",
  /const creditFilled = fillCreditFloor\(occ\);[\s\S]{0,120}occ\.name === lastOccupation/.test(src));
check("职业没变但补了下限会刷新派生", /if \(creditFilled\) rerenderDerived\(\);/.test(src));
check("加载完成后迁移旧值并补下限",
  /render\(\);[\s\S]{0,200}seedCreditFromAsset\(\);\s*fillCreditFloor\(currentOccupation\(\)\);/.test(src));

process.exit(fail ? 1 : 0);
