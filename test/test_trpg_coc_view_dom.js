// COC 角色卡查看页：确认建卡页新增的字段都能渲染出来（历史问题是整页按 DND 渲染）
const fs = require("fs");

const src = fs.readFileSync("webapp/static/char_view.js", "utf8");
const start = src.indexOf("function abilityMod");
const end = src.indexOf("async function init");
if (start < 0 || end < 0) throw new Error("找不到 COC 渲染代码");
const factory = new Function(
  "document",
  "charViewMain",
  "escapeHtml",
  `${src.slice(start, end)}\nreturn { renderCocView, renderView, damageWithDb };`,
);

// 查看页与建卡页共用 core/web/static/trpg_assets.js
global.window = {};
eval(fs.readFileSync("core/web/static/trpg_assets.js", "utf8"));

function makeEl(tag) {
  return {
    tagName: tag, className: "", innerHTML: "", textContent: "", style: {}, dataset: {}, children: [],
    appendChild(child) { this.children.push(child); },
  };
}
const main = makeEl("main");
const api = factory({ createElement: makeEl }, main, (s) => String(s));

function collect(node) {
  if (!node) return "";
  return [node.innerHTML || "", node.textContent || "", ...(node.children || []).map(collect)].join("\n");
}

const card = {
  rules: "coc7th", char_name: "田宫真莉", display_name: "老张",
  occupation: "药剂师", age: 28, sex: "女", era: "1920s", residence: "东京",
  credit_rating: 40, luck: 50,
  scores: { 力量: 60, 体质: 55, 体型: 45, 敏捷: 55, 外貌: 60, 智力: 85, 意志: 65, 教育: 45 },
  hp: 10, current_hp: 8, mp: 13, current_mp: 13, san: 65, max_san: 99, current_san: 40,
  mov: 9, db: "+1D4", build: 1, dodge: 27, cthulhu_mythos: 3,
  skills: { "科学:制药": { base: 1, growth: 0, occupation: 20, interest: 0, total: 21, check: true } },
  weapons: [{ name: "短管霰弹枪", type: "步枪", skill: "步枪/霰弹枪", success: 30,
              damage: "2D6+DB", range: "10/20/50", attacks: "1 or 2", ammo: "2",
              malfunction: "100", pierce: "×" }],
  assets: { currency: "JPY", cash: "120000", spending_level: "25000", living_standard: "小康",
            other_assets: "都市公寓", vehicle: "300000", residence: "0" },
  social_background: { traits: "冷静" },
  notes: "记一笔",
};

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

api.renderCocView(card);
const html = collect(main);

check("头部含姓名与职业", html.includes("田宫真莉") && html.includes("药剂师"));
check("调查员信息（年龄/性别/时代/住地）", html.includes("28岁") && html.includes("1920s") && html.includes("东京"));
check("派生数值完整", ["HP 8/10", "SAN 40/99", "MOV 9", "+1D4", "闪避 27", "信用评级 40"].every((x) => html.includes(x)), html.slice(0, 200));
check("八项属性 + 幸运全部出现", ["力量", "敏捷", "意志", "体质", "外貌", "教育", "体型", "智力", "幸运"].every((x) => html.includes(x)));
check("属性值渲染", html.includes(">60<") || html.includes("60"), "");
check("技能表带成功率与成长标记", html.includes("科学:制药") && html.includes("21%") && html.includes("✓"));
check("武器新字段（类型/使用技能/装弹量/贯穿）", ["短管霰弹枪", "步枪", "步枪/霰弹枪", "2", "×"].every((x) => html.includes(x)));
check("武器伤害带 DB 标注", html.includes("2D6+DB（DB=+1D4）"), "");
check("资产与背景", html.includes("现金：120000") && html.includes("币种：JPY")
  && html.includes("其他资产：都市公寓") && html.includes("资产总和：420000") && html.includes("冷静"), "");
check("笔记", html.includes("记一笔"));

// DND 卡仍走原渲染分支（不应命中 COC 渲染）
const main2 = makeEl("main");
const api2 = factory({ createElement: makeEl }, main2, (s) => String(s));
api2.renderView({ rules: "dnd5e", char_name: "艾伦", level: 1, race: "人类", class_name: "战士",
                  hp: 10, ac: 12, scores: {}, skills: {}, skill_mods: {}, save_mods: {} },
                { attributes: ["力量"], skills: {} });
check("DND 卡走原分支", collect(main2).includes("Lv.1") && !collect(main2).includes("调查员笔记"));

check("damageWithDb 只标注含 DB 的伤害",
  api.damageWithDb("2D6", "+1D4") === "2D6" && api.damageWithDb("1D3+半DB", "0") === "1D3+半DB（DB=0）");

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
