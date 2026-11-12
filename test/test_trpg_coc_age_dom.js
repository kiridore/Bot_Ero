// 建卡页「年龄调整」区块：按年龄段渲染、体能合计校验、已应用锁定、15-19 幸运取高
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const src = fs.readFileSync(path.join(__dirname, "..", "webapp", "static", "trpg_coc.js"), "utf8");
const start = src.indexOf("const AGE_LOCKED_KEYS");
const end = src.indexOf("function collect()", start);
if (start < 0 || end < 0) {
  console.log("FAIL - 未找到年龄调整区块");
  process.exit(1);
}

// ── 极简 DOM：innerHTML 里出现的 id / data-phy 自动注册成子节点 ──
class El {
  constructor(id, tag) {
    this.id = id || "";
    this.tag = tag || "div";
    this.value = "";
    this.textContent = "";
    this.disabled = false;
    this.readOnly = false;
    this.title = "";
    this.dataset = {};
    this.listeners = {};
    this.classList = { toggle() {}, add() {}, remove() {} };
    this.children = new Map();
    this._html = "";
  }
  set innerHTML(html) {
    this._html = html;
    this.children.clear();
    for (const m of html.matchAll(/id="([^"]+)"/g)) {
      const el = new El(m[1], "button");
      this.children.set(`#${m[1]}`, el);
    }
    for (const m of html.matchAll(/data-phy="([^"]+)"/g)) {
      const el = new El(`phy-${m[1]}`, "input");
      el.dataset.phy = m[1];
      this.children.set(`phy:${m[1]}`, el);
    }
  }
  get innerHTML() { return this._html; }
  addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); }
  fire(type) { (this.listeners[type] || []).forEach((fn) => fn({ target: this })); }
  querySelectorAll(sel) {
    if (sel === "[data-phy]") return [...this.children.values()].filter((el) => el.dataset.phy);
    return [];
  }
  querySelector() { return null; }
  appendChild() {}
}

function makeDocument() {
  const nodes = new Map();
  const get = (id) => {
    if (!nodes.has(id)) nodes.set(id, new El(id));
    return nodes.get(id);
  };
  const attrs = new Map();
  return {
    nodes,
    getElementById: get,
    createElement: (tag) => new El("", tag),
    addEventListener() {},
    querySelector: (sel) => {
      const m = /\[data-attr="([^"]+)"\]/.exec(sel);
      if (!m) return null;
      if (!attrs.has(m[1])) attrs.set(m[1], new El(m[1], "input"));
      return attrs.get(m[1]);
    },
    querySelectorAll: () => [],
    attrs,
  };
}

const documentStub = makeDocument();
const card = { age_adjust: null };
const options = {
  age_bands: [
    { band: "15-19", min: 15, max: 19, phy: ["str", "siz"], phy_labels: ["力量", "体型"], phy_quota: 5, app: 0, edu_checks: 0, edu_fixed: -5, luck_best: true },
    { band: "20-39", min: 20, max: 39, phy: [], phy_labels: [], phy_quota: 0, app: 0, edu_checks: 1, edu_fixed: 0, luck_best: false },
    { band: "40-49", min: 40, max: 49, phy: ["str", "con", "dex"], phy_labels: ["力量", "体质", "敏捷"], phy_quota: 5, app: 5, edu_checks: 2, edu_fixed: 0, luck_best: false },
    { band: "50-59", min: 50, max: 59, phy: ["str", "con", "dex"], phy_labels: ["力量", "体质", "敏捷"], phy_quota: 10, app: 10, edu_checks: 3, edu_fixed: 0, luck_best: false },
  ],
  age_range: [15, 99],
};
let luckRolls = [];
const stub = {
  // Proxy 的 has 恒为 true，内建全局必须显式给出，否则会被桩函数顶掉
  Set, Number, Object, Math, String, JSON, Array, Boolean, Promise, console,
  document: documentStub,
  options,
  card,
  CHAR_ID: 7,
  showToast: () => {},
  rerenderDerived: () => {},
  GalleryAuth: { headers: () => ({}) },
  fetch: async () => ({ ok: true, json: async () => ({}) }),
  rollDie: (spec) => { luckRolls.push(spec); return luckRolls.length === 1 ? 45 : 70; },
  escapeHtml: (s) => String(s == null ? "" : s),
};
const sandbox = new Proxy(stub, {
  has: () => true,
  get: (target, key) => {
    if (key in target) return target[key];
    if (key === Symbol.unscopables) return undefined;
    return function noop() { return noop; };
  },
});

const factory = new Function("sandbox", `
  with (sandbox) {
${src.slice(start, end)}
    return { renderAgeAdjust, ageBandFor, AGE_LOCKED_KEYS };
  }
`);

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fail++;
}

let api;
try {
  api = factory(sandbox);
} catch (err) {
  check("年龄调整区块可加载", false, String(err && err.message).slice(0, 120));
  process.exit(1);
}

const box = documentStub.getElementById("ageAdjust");
const ageInput = documentStub.getElementById("age");

// 1) 未填/超范围年龄
ageInput.value = "0";
api.renderAgeAdjust();
check("年龄无效时提示填写范围", /15-99 岁之间/.test(box.innerHTML), box.innerHTML.slice(0, 60));

ageInput.value = "100";
api.renderAgeAdjust();
check("年龄超范围也提示", /15-99 岁之间/.test(box.innerHTML));

// 2) 40-49：三个体能格 + 合计校验
ageInput.value = "45";
api.renderAgeAdjust();
check("40-49 渲染三个体能格", box.querySelectorAll("[data-phy]").length === 3,
  String(box.querySelectorAll("[data-phy]").length));
check("40-49 提示外貌与教育检定", /外貌 -5/.test(box.innerHTML) && /教育成长检定 ×2/.test(box.innerHTML),
  box.innerHTML.slice(0, 120));
const applyBtn = documentStub.getElementById("ageApply");
check("未分配时应用按钮禁用", applyBtn.disabled === true);
check("提示合计差额", /体能合计 0\/5/.test(documentStub.getElementById("ageHint").textContent),
  documentStub.getElementById("ageHint").textContent);

const phy = box.querySelectorAll("[data-phy]");
phy[0].value = "-3";
phy[0].fire("input");
phy[1].value = "-2";
phy[1].fire("input");
check("合计正确后按钮可用", applyBtn.disabled === false);
check("合计正确提示 5/5", /体能合计 5\/5/.test(documentStub.getElementById("ageHint").textContent));

phy[1].value = "2";
phy[1].fire("input");
check("正数分配被拦住", applyBtn.disabled === true
  && /只能填 0 或负数/.test(documentStub.getElementById("ageHint").textContent));

// 3) 已应用：属性只读 + 明细
card.age_adjust = {
  kind: "applied", age: 45, band: "40-49", phy: { str: -3, con: -2, dex: 0 }, app: -5,
  edu: { before: 60, after: 64, checks: 2, rolls: [{ roll: 71, gain: 4 }, { roll: 40, gain: 0 }] },
  before: { str: 63, con: 57, dex: 55, app: 55 },
};
api.renderAgeAdjust();
check("已应用显示明细", /已应用/.test(box.innerHTML) && /力量 -3/.test(box.innerHTML)
  && /71 → \+4/.test(box.innerHTML), box.innerHTML.slice(0, 160));
check("已应用显示撤销按钮", /id="ageUndo"/.test(box.innerHTML));
const strInput = documentStub.querySelector('[data-attr="str_score"]');
const sizInput = documentStub.querySelector('[data-attr="siz_score"]');
check("被调整的属性只读", strInput.readOnly === true);
check("未涉及的属性不锁（体型）", sizInput.readOnly === false);

// 4) 年龄与记录不一致
ageInput.value = "50";
api.renderAgeAdjust();
check("年龄改动后提示重新应用", /请先撤销再重新应用/.test(box.innerHTML), box.innerHTML.slice(0, 120));

// 5) 15-19：两个格 + 幸运取高
card.age_adjust = null;
ageInput.value = "17";
api.renderAgeAdjust();
check("15-19 渲染两个体能格", box.querySelectorAll("[data-phy]").length === 2);
check("15-19 显示幸运取高按钮", /id="ageLuck"/.test(box.innerHTML) && /幸运掷两次取高/.test(box.innerHTML));
check("15-19 提示教育定值 -5", /教育 -5/.test(box.innerHTML), box.innerHTML.slice(0, 140));
const luckBtn = documentStub.getElementById("ageLuck");
luckBtn.fire("click");
check("幸运取两次较高值", documentStub.getElementById("luck").value === 70,
  String(documentStub.getElementById("luck").value));

// 6) 20-39：无体能格、额度 0 时可直接应用
ageInput.value = "25";
api.renderAgeAdjust();
check("20-39 没有体能格", box.querySelectorAll("[data-phy]").length === 0);
check("20-39 应用按钮可用", documentStub.getElementById("ageApply").disabled === false);
check("20-39 提示一次教育检定", /教育成长检定 ×1/.test(box.innerHTML), box.innerHTML.slice(0, 120));

// 7) skipped 记录
card.age_adjust = { kind: "skipped", age: 25, band: "20-39" };
api.renderAgeAdjust();
check("skipped 仍可应用且标注不再提示", /已选过「不再提示」/.test(box.innerHTML)
  && /id="ageApply"/.test(box.innerHTML));

console.log(fail ? `\n${fail} 项失败` : "\n全部通过");
process.exit(fail ? 1 : 0);
