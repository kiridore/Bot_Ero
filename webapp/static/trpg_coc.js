// COC 7th 建卡工具：属性/职业/技能点/派生值，对齐 docs/COC七版人物卡v1.6.1.xlsx 的建卡口径。
const main = document.getElementById("cocMain");
const PATH_PARTS = location.pathname.split("/").filter(Boolean); // trpg / coc / <id>
const CHAR_ID = PATH_PARTS[2] ? Number(PATH_PARTS[2]) : null;

const ATTRS = [
  ["str_score", "力量", "3d6"], ["dex_score", "敏捷", "3d6"], ["pow_score", "意志", "3d6"],
  ["con_score", "体质", "3d6"], ["app_score", "外貌", "3d6"], ["edu_score", "教育", "2d6+6"],
  ["siz_score", "体型", "2d6+6"], ["int_score", "智力", "2d6+6"], ["luck", "幸运", "3d6"],
];

// 「您的角色可能（只是可能！）」——人物卡 AJ3/AJ5/AJ7/AV3/AV5/AV7/BD3/BD5/BD7 的 IF 链，
// 每项为 [上限, 文案]，取第一个满足 值 <= 上限 的；值为 0 时不显示。
const ATTR_NOTE_TITLE = "您的角色可能（只是可能！）";
const ATTR_NOTES = {
  str_score: [[15, "虚弱，孱弱"], [40, "力量弱小"], [60, "有正常人的力量"], [80, "超乎常人的力量"], [99, "超乎超乎常人的力量"]],
  con_score: [[20, "常年患病在身"], [40, "体弱多病"], [60, "不会生什么大毛病"], [80, "健硕，浑身湿透也不会感冒"], [99, "身体素质极好，精神抖擞"]],
  siz_score: [[20, "孩童，身短体瘦"], [40, "乙女身材"], [60, "普遍身高155-175"], [80, "不是高就是胖"], [100, "大号的人"], [149, "听说你正在申请身高世界记录？"], [179, "你可能是一头牛"], [199, "你已经是历史上最重的人类了"], [999, "过分了喂！"]],
  dex_score: [[20, "很不灵活"], [40, "不是很灵活"], [60, "普通人水平"], [80, "是一位运动健将"], [99, "高速而灵活，可以达成超凡的技艺"]],
  app_score: [[20, "用脸就能恐惧敌人。。或队友"], [40, "有些难看"], [60, "人群之中谁也不会看你一眼之后就忘不掉你容颜"], [80, "五官端正，仪表堂堂"], [99, "沉鱼落雁，闭月羞花"]],
  int_score: [[20, "脑子是个好东西，可惜。。。"], [40, "理解知识要耗费比普通人更多的时间"], [60, "有着普通人的灵光一现"], [80, "可以自主进行发明创造"], [99, "天才级水准"]],
  pow_score: [[20, "尔不过玩物"], [40, "痴愚盲目"], [60, "如常人一般会有一定自制力"], [80, "我心如铁，心坚石穿"], [99, "泰山崩于面而色不变"], [139, "钢铁之心，还能看见鬼"], [999, "你怕是个假人吧"]],
  edu_score: [[20, "目不识丁"], [40, "小学毕业"], [60, "高中毕业"], [80, "是重点大学的学生，或是普通大学的研究生"], [99, "饱读诗书，满腹经纶"]],
  luck: [[20, "克夫克妻"], [40, "霉运连连"], [60, "命格平庸"], [80, "在马路边捡到100块"], [99, "被幸运女神所眷顾"]],
};

// 「您的角色可能」：按属性值落桶；0 或没填时不显示
function describeAttr(key, value) {
  const buckets = ATTR_NOTES[key] || [];
  const score = Number(value || 0);
  if (!score) return "";
  for (const [limit, text] of buckets) {
    if (score <= limit) return text;
  }
  return buckets.length ? buckets[buckets.length - 1][1] : "";
}

const LIVING_LEVELS = ["身无分文", "拮据", "标准", "小康", "富裕", "富豪"];
const ASSET_ITEMS = [
  ["vehicle", "交通工具"], ["residence", "住所"], ["luxury", "奢侈品"],
  ["securities", "股票/证券等"], ["other", "其他"],
];

// 信用评级 → 生活水平档位（0 / 1-9 / 10-49 / 50-89 / 90-98 / 99）
function levelForCredit(credit) {
  const score = Number(credit || 0);
  if (score <= 0) return "身无分文";
  if (score <= 9) return "拮据";
  if (score <= 49) return "标准";
  if (score <= 89) return "小康";
  if (score <= 98) return "富裕";
  return "富豪";
}

const BACKGROUND_FIELDS = [
  ["description", "个人描述"], ["ideology", "思想与信念"], ["significant_people", "重要之人"],
  ["meaningful_places", "意义非凡之地"], ["treasured_possessions", "宝贵之物"], ["traits", "特质"],
  ["scars", "伤口和疤痕"], ["phobias", "恐惧症和狂躁症"],
];

let options = null;
let card = null;
let me = null;
let occChoices = {};   // {池下标: [技能名…]}，与职业定义里的 choices 顺序对应
let autoAdded = new Set();  // 选职业时自动补进来的技能（换职业时若没填点数会撤掉）

// 规则默认技能：技能表全部标准技能的基础值，闪避按 DEX/2
function skillDefaults(skillBase, dexScore, names, dynamic) {
  const out = {};
  const pick = names && names.length ? names : Object.keys(skillBase || {});
  pick.forEach((name) => {
    out[name] = { base: Number((skillBase || {})[name] || 0) };
  });
  // 由属性派生的技能（闪避/母语）按当前属性覆盖
  const rules = dynamic || {};
  const readAttr = (key) => {
    if (key === "dex_score") return Number(dexScore || 0);
    const el = document.querySelector(`[data-attr="${key}"]`);
    return Number(el ? el.value : 0);
  };
  Object.entries(rules).forEach(([name, rule]) => {
    out[name] = { base: Math.floor(readAttr(rule.attr) / Number(rule.divisor || 1)) };
  });
  return out;
}

// 任意技能的基础值（标准技能 / 专攻 / 武器技能）——后端 skill_base_map 是唯一来源
function skillBaseFor(name) {
  const canon = canonSkill(normalizeSkillName(name) || name);
  const rule = (options.dynamic_bases || {})[canon];
  if (rule) {
    const el = document.querySelector(`[data-attr="${rule.attr}"]`);
    return Math.floor(Number(el ? el.value : 0) / Number(rule.divisor || 1));
  }
  const table = options.skill_base || {};
  if (table[canon] != null) return Number(table[canon]);
  const parts = canon.split(":");
  if (parts.length > 1 && table[parts[1]] != null) return Number(table[parts[1]]);
  return 0;
}

// 卡上已存的技能覆盖默认值（保留成长/职业/兴趣点）
function mergeSkillDefaults(card, dexScore) {
  const merged = skillDefaults(options.skill_base, dexScore, options.default_skills, options.dynamic_bases);
  Object.entries((card && card.skills) || {}).forEach(([name, entry]) => {
    const canon = normalizeSkillName(name) || name;
    merged[canon] = { ...(merged[canon] || {}), ...(entry || {}) };
  });
  return merged;
}

// 可加职业点的技能名集合：固定项（含 类别:* 通配）+ 已选中的池内技能
function occAllowedNames(occ, choices) {
  const out = { exact: new Set(), wild: [] };
  if (!occ) return out;
  const struct = (options.occupation_skills || {})[String(occ.seq)];
  if (!struct) return out;
  (struct.required || []).forEach((name) => {
    const fixed = canonSkill(name);
    if (fixed.endsWith(":*")) out.wild.push(fixed.slice(0, -1));
    else out.exact.add(fixed);
  });
  Object.values(choices || {}).forEach((list) => {
    (list || []).forEach((name) => {
      const fixed = normalizeSkillName(name);
      if (fixed) out.exact.add(canonSkill(fixed));
    });
  });
  return out;
}

function occAllows(allowed, name) {
  const fixed = canonSkill(name);
  return allowed.exact.has(fixed) || allowed.wild.some((prefix) => fixed.startsWith(prefix));
}

// 本职技能里的固定项（通配项如「技艺:*」要玩家自己填专攻，不自动补）
function requiredSkillNames(struct) {
  return (struct?.required || []).filter((name) => !canonSkill(name).endsWith(":*"));
}

// 技能名规范化：别名（侦查→侦察）→ 官方名 → 「类别:专攻」；无效返回 null
function canonSkill(name) {
  const raw = String(name || "").trim();
  return (options.skill_aliases || {})[raw] || raw;
}

function normalizeSkillName(name) {
  // 技能名不再限定官方表：认识的做别名/类别归一，不认识的当自定义技能
  const canon = canonSkill(name).replace(/\s+/g, " ").trim();
  if (!canon) return "";
  if (canon in (options.skill_base || {})) return canon;
  const cats = options.skill_categories || [];
  const cat = cats.find((c) => canon.startsWith(c));
  if (!cat) return canon;
  const rest = canon.slice(cat.length).replace(/^[:：\s]+/, "").trim();
  return rest ? `${cat}:${rest}` : cat;
}

// 有官方基础值的技能自动填，自定义技能从 0 开始（可手填）
function skillBaseOrZero(name) {
  const base = skillBaseFor(name);
  return Number.isFinite(base) ? base : 0;
}

function escapeHtml(s) {
  return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function attr(name) {
  const el = document.querySelector(`[data-attr="${name}"]`);
  return el ? Number(el.value || 0) : 0;
}
function rollDie(spec) {
  const m = String(spec).match(/^(\d+)d(\d+)(?:\+(\d+))?$/);
  if (!m) return 0;
  const count = Number(m[1]);
  const sides = Number(m[2]);
  const plus = Number(m[3] || 0);
  let total = plus;
  for (let i = 0; i < count; i += 1) total += 1 + Math.floor(Math.random() * sides);
  return total * 5;
}
function dbBuild(total) {
  if (total <= 64) return ["-2", -2];
  if (total <= 84) return ["-1", -1];
  if (total <= 124) return ["0", 0];
  if (total <= 164) return ["+1D4", 1];
  if (total <= 204) return ["+1D6", 2];
  const steps = Math.floor((total - 205) / 80);
  return [`+${steps + 2}D6`, steps + 3];
}
function baseMov(str, dex, siz) {
  if (str > siz && dex > siz) return 9;
  if (str < siz && dex < siz) return 7;
  return 8;
}
function agePenalty(age) {
  let p = 0;
  [[40, 1], [50, 2], [60, 3], [70, 4], [80, 5]].forEach(([limit, value]) => { if (age >= limit) p = value; });
  return p;
}
// 结构化本职技能的可选池说明：职业点只能加在固定项或这些池内
function poolHint(occ) {
  const struct = (options.occupation_skills || {})[String(occ.seq)];
  if (!struct || !(struct.choices || []).length) return "";
  const parts = struct.choices.map((c) => (c.from === "*"
    ? `任意 ${c.count} 项`
    : `${c.from.join("、")} 中选 ${c.count} 项`));
  const fixed = (struct.required || []).length;
  return `（固定 ${fixed} 项；可选：${parts.join("；")}）`;
}

// 可选池控件：具名池用多选，类别通配/自由池用文本输入
function renderOccChoices() {
  const box = document.getElementById("occ-choices");
  if (!box) return;
  box.innerHTML = "";
  const occ = currentOccupation();
  const struct = occ ? (options.occupation_skills || {})[String(occ.seq)] : null;
  if (!struct || !(struct.choices || []).length) return;

  struct.choices.forEach((choice, index) => {
    const wrap = document.createElement("div");
    wrap.className = "coc-choice";
    const picked = occChoices[String(index)] || [];
    const label = document.createElement("strong");
    const named = choice.from !== "*" && !choice.from.some((n) => n.endsWith(":*"));
    label.textContent = `可选 #${index + 1}（选 ${choice.count} 项）`;
    wrap.appendChild(label);

    if (named) {
      const list = document.createElement("div");
      list.className = "coc-choice-list";
      const single = choice.count === 1;
      choice.from.forEach((name) => {
        const item = document.createElement("label");
        item.className = "coc-choice-item";
        const input = document.createElement("input");
        // 选 1 项用单选，选多项才用多选
        input.type = single ? "radio" : "checkbox";
        if (single) input.name = `occ-pool-${index}`;
        input.value = name;
        input.checked = picked.includes(name);
        input.addEventListener("change", () => {
          if (single) {
            occChoices[String(index)] = [name];
          } else {
            const current = new Set(occChoices[String(index)] || []);
            if (input.checked) current.add(name); else current.delete(name);
            occChoices[String(index)] = [...current];
          }
          syncChosenSkills();
          rerenderDerived();
        });
        item.appendChild(input);
        item.appendChild(document.createTextNode(name));
        list.appendChild(item);
      });
      wrap.appendChild(list);
    } else {
      const hint = choice.from === "*"
        ? "任意技能，如：攀爬、技艺:烹饪"
        : `从 ${choice.from.join("、")} 里选，如：${choice.from[0]}`;
      const input = document.createElement("input");
      input.type = "text";
      input.placeholder = hint;
      input.value = picked.join("、");
      input.addEventListener("change", () => {
        occChoices[String(index)] = input.value
          .split(/[、,，;；]/).map((x) => x.trim()).filter(Boolean);
        syncChosenSkills();
        rerenderDerived();
      });
      wrap.appendChild(input);
    }
    box.appendChild(wrap);
  });
}

// 选了池内技能但技能表里还没有 → 自动补一行，保证能填职业点
// 选了职业后把固定本职技能补进技能表
function fillRequiredSkills(occ) {
  const struct = occ ? (options.occupation_skills || {})[String(occ.seq)] : null;
  const tbody = document.getElementById("skillBody");
  if (!struct || !tbody) return 0;
  const existing = new Set([...document.querySelectorAll("[data-skill]")].map((r) => canonSkill(r.dataset.name)));
  let added = 0;
  requiredSkillNames(struct).forEach((raw) => {
    const name = normalizeSkillName(raw);
    if (!name || existing.has(canonSkill(name))) return;
    existing.add(canonSkill(name));
    autoAdded.add(canonSkill(name));
    tbody.insertAdjacentHTML("beforeend", skillRow(name, { base: skillBaseFor(name) }));
    added += 1;
  });
  return added;
}

// 换职业时撤掉上一职业自动补的行——只撤没填过成长/职业/兴趣点点的
function pruneAutoAdded() {
  document.querySelectorAll("[data-skill]").forEach((row) => {
    if (!autoAdded.has(canonSkill(row.dataset.name))) return;
    const untouched = ["[data-growth]", "[data-occ]", "[data-int]"]
      .every((sel) => Number(row.querySelector(sel).value || 0) === 0);
    if (untouched) row.remove();
  });
  autoAdded = new Set();
}

function syncChosenSkills() {
  const tbody = document.getElementById("skillBody");
  if (!tbody) return;
  const existing = new Set([...document.querySelectorAll("[data-skill]")].map((r) => canonSkill(r.dataset.name)));
  Object.values(occChoices).flat().forEach((raw) => {
    const name = normalizeSkillName(raw);
    if (!name || existing.has(canonSkill(name))) return;
    existing.add(canonSkill(name));
    tbody.insertAdjacentHTML("beforeend", skillRow(name, { base: skillBaseFor(name) }));
  });
}

function currentOccupation() {
  const name = document.getElementById("occupation")?.value || "";
  return (options.occupations || []).find((o) => o.name === name) || null;
}
function pointsBudget(formula, get) {
  let total = 0;
  String(formula || "").replace(/＋/g, "+").split("+").forEach((term) => {
    term = term.trim();
    if (!term) return;
    let multiplier = 1;
    if (term.includes("×")) {
      const [head, tail] = term.split("×");
      term = head.trim();
      multiplier = Number(tail.trim() || 1);
    }
    const values = term.split("或").map((t) => get(t.trim())).filter((v) => v != null);
    if (values.length) total += Math.max(...values) * multiplier;
  });
  return total;
}
const ATTR_SCORE = {
  力量: () => attr("str_score"), 体质: () => attr("con_score"), 体型: () => attr("siz_score"),
  敏捷: () => attr("dex_score"), 外貌: () => attr("app_score"), 智力: () => attr("int_score"),
  意志: () => attr("pow_score"), 教育: () => attr("edu_score"),
};

function rerenderDerived() {
  const str = attr("str_score"), con = attr("con_score"), siz = attr("siz_score"), dex = attr("dex_score");
  const pow = attr("pow_score"), int = attr("int_score");
  const age = Number(document.getElementById("age")?.value || 0);
  const [db, build] = dbBuild(str + siz);
  const mov = Math.max(baseMov(str, dex, siz) - agePenalty(age), 0);
  const occ = currentOccupation();
  const occBudget = occ ? pointsBudget(occ.formula, (k) => (ATTR_SCORE[k] ? ATTR_SCORE[k]() : null)) : 0;
  const allowedOcc = occAllowedNames(occ, occChoices);
  const cleared = [];
  let occSpent = 0, intSpent = 0;
  document.querySelectorAll("[data-skill]").forEach((row) => {
    const occInput = row.querySelector("[data-occ]");
    const allowed = occAllows(allowedOcc, row.dataset.name);
    if (!allowed && Number(occInput.value || 0) > 0) {
      // 技能被移出可选池/换了职业：清掉它的职业点，避免留下一填就报错的死数据
      cleared.push(row.dataset.name);
      occInput.value = 0;
    }
    occInput.disabled = !allowed;
    occInput.title = allowed ? "" : "非本职技能，只能用兴趣点";
    row.classList.toggle("is-not-occ", !allowed);
    occSpent += Number(occInput.value || 0);
    intSpent += Number(row.querySelector("[data-int]").value || 0);
    const base = Number(row.querySelector("[data-base]").value || 0);
    const growth = Number(row.querySelector("[data-growth]").value || 0);
    const value = Math.min(base + growth + Number(row.querySelector("[data-occ]").value || 0) + Number(row.querySelector("[data-int]").value || 0), 199);
    row.querySelector("[data-total]").textContent = value;
  });
  // 由属性派生的技能（闪避=DEX/2、母语=EDU）基础值随属性刷新
  Object.keys(options.dynamic_bases || {}).forEach((skillName) => {
    const row = [...document.querySelectorAll("[data-skill]")]
      .find((item) => canonSkill(item.dataset.name) === canonSkill(skillName));
    const baseInput = row && row.querySelector("[data-base]");
    if (baseInput) baseInput.value = skillBaseFor(skillName);
  });
  // 资产：档位提示 + 合计
  const assetHint = document.getElementById("assetHint");
  if (assetHint) {
    const credit = Number(document.getElementById("credit_rating")?.value || 0);
    const level = levelForCredit(credit);
    const chosen = document.getElementById("living_standard")?.value || "";
    assetHint.textContent = chosen && chosen !== level
      ? `信用评级 ${credit} 通常对应「${level}」，当前选的是「${chosen}」`
      : `信用评级 ${credit} 对应「${level}」`;
  }
  const totalBox = document.getElementById("assetTotal");
  if (totalBox) {
    const items = {};
    document.querySelectorAll("[data-asset-item]").forEach((el) => { items[el.dataset.assetItem] = el.value; });
    totalBox.value = window.BoteroAssets
      ? window.BoteroAssets.total({ cash: document.getElementById("cash")?.value, ...items })
      : "";
  }
  // 武器伤害的 DB 标注：伤害原文 + 当前伤害加值
  document.querySelectorAll("[data-weapon-row]").forEach((row) => {
    const note = row.querySelector("[data-damage-note]");
    if (!note) return;
    const damage = String(row.querySelector('[data-weapon="damage"]')?.value || "");
    note.textContent = damage.includes("DB") ? `（DB=${db}）` : "";
  });
  document.querySelectorAll("[data-attr-note]").forEach((cell) => {
    const key = cell.dataset.attrNote;
    const input = document.querySelector(`[data-attr="${key}"]`);
    cell.textContent = describeAttr(key, input?.value);
  });
  const interestBudget = int * 2;
  const set = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };
  set("out-hp", Math.floor((con + siz) / 10));
  set("out-mp", Math.floor(pow / 5));
  set("out-san", pow);
  set("out-mov", mov);
  set("out-db", db);
  set("out-build", build);
  set("out-dodge", Math.floor(dex / 2));
  set("out-cur-hp", card.current_hp != null ? card.current_hp : Math.floor((con + siz) / 10));
  set("out-cur-san", card.current_san != null ? card.current_san : pow);
  set("out-cur-mp", card.current_mp != null ? card.current_mp : Math.floor(pow / 5));
  set("out-occ-budget", occBudget);
  set("out-occ-spent", occSpent);
  if (cleared.length && typeof showToast === "function") {
    showToast(`已清除职业点：${cleared.join("、")}（不是本职技能）`, true);
  }
  set("out-int-budget", interestBudget);
  set("out-int-spent", intSpent);
  const occNote = document.getElementById("occ-note");
  if (occNote) {
    occNote.textContent = occ
      ? `职业点 ${occ.formula}；信用评级 ${occ.credit_min}-${occ.credit_max}；本职技能：${occ.own_skills}${poolHint(occ)}`
      : "未选择职业";
  }
  const choiceWarn = document.getElementById("occ-choice-warn");
  if (choiceWarn) {
    const struct = occ ? (options.occupation_skills || {})[String(occ.seq)] : null;
    const notes = [];
    (struct?.choices || []).forEach((choice, index) => {
      const picked = (occChoices[String(index)] || []).length;
      if (picked < choice.count) notes.push(`可选 #${index + 1} 还差 ${choice.count - picked} 项`);
      else if (picked > choice.count) notes.push(`可选 #${index + 1} 多选了 ${picked - choice.count} 项`);
    });
    choiceWarn.textContent = notes.join("；");
    choiceWarn.classList.toggle("coc-choice-warn-on", notes.length > 0);
  }
  const occWarn = document.getElementById("occ-warn");
  if (occWarn) {
    const over = [];
    if (occSpent > occBudget) over.push(`职业点超出 ${occSpent}/${occBudget}`);
    if (intSpent > interestBudget) over.push(`兴趣点超出 ${intSpent}/${interestBudget}`);
    occWarn.textContent = over.join("；");
  }
}

// 技能说明：精确命中 → 去掉「类别:」再试 → 类别本身（技艺 用「艺术与手艺」的说明）
function skillNote(name) {
  const notes = options.skill_notes || {};
  const canon = canonSkill(normalizeSkillName(name) || name);
  if (notes[canon]) return notes[canon];
  const parts = canon.split(":");
  if (parts.length > 1) {
    const bare = parts.slice(1).join(":");
    if (notes[bare]) return notes[bare];
    if (notes[parts[0]]) return notes[parts[0]];
  }
  return null;
}

function skillNoteTitle(note) {
  const lines = [note.note || ""];
  const meta = [note.base ? `基础值 ${note.base}` : "", note.special && note.special !== "——" ? note.special : ""]
    .filter(Boolean).join("｜");
  if (meta) lines.push("", meta);
  return lines.join("\n");
}

function isCreditSkill(name) {
  return canonSkill(name) === "信用评级";
}

function creditRowEl() {
  return [...document.querySelectorAll("[data-skill]")].find((r) => isCreditSkill(r.dataset.name));
}

// 信用评级由技能行的职业点 + 兴趣点决定；资产区那一格只做同步显示
function creditFromSkillRow() {
  const row = creditRowEl();
  if (!row) return 0;
  const num = (sel) => Number(row.querySelector(sel).value || 0);
  return Math.min(num("[data-occ]") + num("[data-int]"), 99);
}

function syncCreditAssets() {
  const value = String(creditFromSkillRow());
  const field = document.getElementById("credit_rating");
  if (field) field.value = value;
  const level = document.getElementById("life_level");
  if (level && level.dataset.auto !== "0") level.value = levelForCredit(value);
  const row = creditRowEl();
  const total = row && row.querySelector("[data-total]");
  if (total) total.textContent = value;
}

function skillRow(name, entry) {
  const credit = isCreditSkill(name);
  const base = credit ? 0 : (entry.base != null ? entry.base : skillBaseFor(name));
  const fixed = credit ? "disabled" : "";
  return `
    <tr data-skill data-name="${escapeHtml(name)}">
      <td>${escapeHtml(name)}${(() => {
        const note = skillNote(name);
        if (!note) return "";
        return `<span class="coc-info" role="img" tabindex="0" aria-label="技能说明"
                      data-note="${escapeHtml(skillNoteTitle(note))}"
                      title="${escapeHtml(skillNoteTitle(note))}">i</span>`;
      })()}</td>
      <td><input type="number" data-base value="${base}" min="0" max="99" class="coc-num" ${fixed}
                 ${credit ? "title=\"信用评级没有基础值\"" : ""} /></td>
      <td><input type="number" data-growth value="${credit ? 0 : (entry.growth || 0)}" min="0" max="199" class="coc-num" ${fixed}
                 ${credit ? "title=\"信用评级不能获得成长标记\"" : ""} />${!credit && entry.check ? " ✓" : ""}</td>
      <td><input type="number" data-occ value="${credit ? (entry.occupation || 0) : (entry.occupation || 0)}" min="0" max="99" class="coc-num"
                 ${credit ? "title=\"先用职业点补到职业下限\"" : ""} /></td>
      <td><input type="number" data-int value="${credit ? (entry.interest || 0) : (entry.interest || 0)}" min="0" max="99" class="coc-num"
                 ${credit ? "title=\"到达下限之后才能用兴趣点加点\"" : ""} /></td>
      <td data-total class="coc-total">${credit ? Math.min((entry.occupation || 0) + (entry.interest || 0), 99) : 0}</td>
      <td><button type="button" class="btn-sm" data-remove>删</button></td>
    </tr>`;
}

const WEAPON_FIELDS = [
  ["name", "武器", "text"],
  ["type", "类型", "text"],
  ["skill", "使用技能", "text"],
  ["success", "成功率", "number"],
  ["damage", "伤害", "text"],
  ["range", "射程", "text"],
  ["attacks", "次数", "text"],
  ["ammo", "装弹量", "text"],
  ["malfunction", "故障值", "number"],
  ["pierce", "贯穿", "text"],
];

const WEAPON_LIMITS = {
  type: { maxlength: 10, placeholder: "常规武器" },
  skill: { maxlength: 20, placeholder: "斗殴 / 手枪" },
  success: { min: 0, max: 99, placeholder: "25" },
  damage: { placeholder: "1D8 / 1D3+DB" },
  range: { maxlength: 20, placeholder: "15m / 接触" },
  attacks: { maxlength: 12, placeholder: "1(3)" },
  ammo: { maxlength: 10, placeholder: "8" },
  malfunction: { min: 0, max: 100, placeholder: "98" },
  pierce: { maxlength: 10, placeholder: "—" },
};

// 卡上「时代」与武器库 era 字段的对应：1920s / 现代 / 罕见，空则不限
function weaponEraMatches(cardEra, weaponEra) {
  const era = String(cardEra || "");
  const tags = String(weaponEra || "").split(/[,，]/).map((x) => x.trim()).filter(Boolean);
  if (!tags.length) return true;
  if (/1920|1920s/i.test(era)) return tags.includes("1920s");
  if (/现代|2020|21世纪/i.test(era)) return tags.includes("现代");
  return true;   // 时代没填或写得笼统 → 不做筛选
}

function libraryWeapons() {
  return (options.weapon_library || []).filter((w) =>
    weaponEraMatches(document.getElementById("era")?.value, w.era));
}

function renderWeaponLibrary() {
  const select = document.getElementById("weaponLib");
  if (!select) return;
  const list = libraryWeapons();
  select.innerHTML = '<option value="">从武器库选择…</option>' +
    list.map((w, i) => {
      const mark = w.rare ? "（罕见）" : w.outdated ? "（不合时代）" : "";
      return `<option value="${i}">${escapeHtml(w.name)}${mark} · ${escapeHtml(w.type || "")}</option>`;
    }).join("");
}

// 技能表当前值：基础 + 成长 + 职业 + 兴趣（上限 199）
function currentSkillTotal(name) {
  const row = [...document.querySelectorAll("[data-skill]")]
    .find((r) => canonSkill(r.dataset.name) === canonSkill(name));
  if (!row) return skillBaseFor(name);
  const num = (sel) => Number(row.querySelector(sel).value || 0);
  return Math.min(num("[data-base]") + num("[data-growth]") + num("[data-occ]") + num("[data-int]"), 199);
}

function fillWeaponFromLibrary(weapon) {
  return {
    name: weapon.name,
    type: weapon.type || "",
    skill: weapon.skill || "",
    success: currentSkillTotal(weapon.skill || ""),
    damage: weapon.damage || "",
    range: weapon.range || "",
    attacks: weapon.attacks || "",
    ammo: weapon.capacity || "",
    malfunction: weapon.malfunction || "",
    pierce: weapon.pierce || "",
  };
}

function weaponRow(weapon) {
  const cells = WEAPON_FIELDS.map(([key, , type]) => {
    const value = weapon[key] != null ? weapon[key] : "";
    const cls = type === "number" ? "coc-num" : "";
    const limit = WEAPON_LIMITS[key] || {};
    const attrs = Object.entries(limit)
      .map(([name, v]) => `${name}="${escapeHtml(v)}"`)
      .join(" ");
    return `<td><input type="${type}" data-weapon="${key}" value="${escapeHtml(value)}" class="${cls}" ${attrs} /></td>`;
  }).join("");
  return `<tr data-weapon-row>${cells}<td class="coc-dmg-note" data-damage-note></td>` +
    `<td><button type="button" class="btn-sm" data-remove-weapon>删</button></td></tr>`;
}

function inventoryRow(item) {
  const statuses = options.inventory_statuses || ["装备", "携带", "背包"];
  const status = statuses.map((st) =>
    `<option value="${escapeHtml(st)}"${st === (item.status || "携带") ? " selected" : ""}>${escapeHtml(st)}</option>`).join("");
  return `
    <tr data-item-row>
      <td><select data-item="status">${status}</select></td>
      <td><input type="text" data-item="slot" maxlength="10" value="${escapeHtml(item.slot || "")}" placeholder="躯干 / 手 / 背" /></td>
      <td><input type="text" data-item="name" maxlength="30" value="${escapeHtml(item.name || "")}" placeholder="物品名称" /></td>
      <td><input type="number" data-item="slots" min="0" max="20" value="${item.slots != null ? escapeHtml(item.slots) : 1}" class="coc-num" /></td>
      <td><button type="button" class="btn-sm" data-remove-item>删</button></td>
    </tr>`;
}

function renderInventoryTotals() {
  const box = document.getElementById("inventoryTotals");
  if (!box) return;
  const groups = new Map();
  let total = 0;
  document.querySelectorAll("[data-item-row]").forEach((row) => {
    const status = row.querySelector('[data-item="status"]').value || "携带";
    const slots = Number(row.querySelector('[data-item="slots"]').value || 0);
    total += Number.isFinite(slots) ? slots : 0;
    groups.set(status, (groups.get(status) || 0) + 1);
  });
  const parts = [...groups.entries()].map(([status, count]) => `${status} ${count} 件`);
  box.textContent = parts.length ? `${parts.join(" · ")} · 合计 ${total} 格` : "";
}

function render() {
  const bg = card.social_background || {};
  const assets = card.assets || {};
  main.innerHTML = `
    <div class="section-head">
      <h2>${CHAR_ID ? "编辑调查员卡" : "新建 COC 7th 调查员卡"}</h2>
      <div>
        <button type="button" class="btn-sm" id="backBtn">返回</button>
        <button type="button" class="btn-sm primary" id="saveBtn">保存</button>
      </div>
    </div>

    <section class="coc-block">
      <h3>调查员信息</h3>
      <div class="coc-grid">
        <label>姓名<input id="char_name" value="${escapeHtml(card.char_name || "")}" /></label>
        <label>年龄<input id="age" type="number" min="15" max="90" value="${card.age || 25}" /></label>
        <label>性别<input id="sex" value="${escapeHtml(card.sex || "")}" /></label>
        <label>住地<input id="residence" value="${escapeHtml(card.residence || "")}" /></label>
        <label>故乡<input id="birthplace" value="${escapeHtml(card.birthplace || "")}" /></label>
        <label>时代<input id="era" value="${escapeHtml(card.era || "")}" /></label>
        <label class="coc-wide">职业
          <select id="occupation">
            <option value="">未选择</option>
            ${options.occupations.map((o) => `<option value="${escapeHtml(o.name)}"${o.name === card.occupation ? " selected" : ""}>${escapeHtml(o.name)}</option>`).join("")}
          </select>
        </label>
      </div>
      <div id="occ-choices" class="coc-choices"></div>
      <p class="coc-note" id="occ-choice-warn"></p>
      <p class="coc-note" id="occ-note"></p>
      <p class="coc-warn" id="occ-warn"></p>
    </section>

    <section class="coc-block">
      <h3>年龄调整</h3>
      <div id="ageAdjust" class="coc-age"></div>
    </section>

    <section class="coc-block">
      <h3>属性 <button type="button" class="btn-sm" id="rollAll">🎲 全部重掷</button></h3>
      <div class="coc-attr-wrap">
        <div class="coc-grid coc-attrs">
          ${ATTRS.map(([key, label, spec]) => `
            <label>${label}<span class="coc-attr-row">
              <input type="number" data-attr="${key}" id="${key === "luck" ? "luck" : ""}"
                     value="${card[key] || 0}" min="0" max="99" class="coc-num" />
              <button type="button" class="btn-sm coc-dice" data-roll="${key}" data-spec="${spec}"
                      title="重掷${label}" aria-label="重掷${label}">🎲</button>
            </span></label>`).join("")}
        </div>
        <div class="coc-attr-notes">
          <p class="coc-note">${ATTR_NOTE_TITLE}</p>
          <div class="coc-grid coc-notes">
            ${ATTRS.map(([key]) => `<p class="coc-note-cell" data-attr-note="${key}"></p>`).join("")}
          </div>
        </div>
      </div>
    </section>

    <section class="coc-block">
      <h3>派生值</h3>
      <p class="coc-derived">
        HP <b id="out-hp">0</b> · MP <b id="out-mp">0</b> · SAN <b id="out-san">0</b> ·
        MOV <b id="out-mov">0</b> · 伤害加值 <b id="out-db">0</b> · 体格 <b id="out-build">0</b> · 闪避 <b id="out-dodge">0</b>
      </p>
      <p class="coc-note">当前：HP <b id="out-cur-hp">0</b> / SAN <b id="out-cur-san">0</b> / MP <b id="out-cur-mp">0</b>（运行时数值，只能在群里用 .hp / .san 修改）</p>
      <p class="coc-note">职业点 <b id="out-occ-spent">0</b>/<b id="out-occ-budget">0</b> · 兴趣点 <b id="out-int-spent">0</b>/<b id="out-int-budget">0</b></p>
    </section>

    <section class="coc-block">
      <h3>技能</h3>
      <div class="coc-add-skill">
        <input type="text" id="skillName" placeholder="输入技能名，如 侦察 / 技艺:烹饪 / 自定技能" />
        <button type="button" class="btn-sm" id="addSkill">添加技能</button>
        <span class="coc-add-hint" id="skillAddHint"></span>
      </div>
      <div class="coc-table-wrap">
        <table class="coc-table">
          <thead><tr><th>技能</th><th>基础</th><th>成长</th><th>职业</th><th>兴趣</th><th>成功率</th><th></th></tr></thead>
          <tbody id="skillBody">${Object.entries(card.skills || {}).map(([n, e]) => skillRow(n, e)).join("")}</tbody>
        </table>
      </div>
    </section>

    <section class="coc-block">
      <h3>武器 <button type="button" class="btn-sm" id="addWeapon">添加武器</button></h3>
      <div class="coc-add-skill">
        <select id="weaponLib"></select>
        <span class="coc-add-hint" id="weaponLibHint"></span>
      </div>
      <div class="coc-table-wrap">
        <table class="coc-table">
          <thead><tr>${WEAPON_FIELDS.map(([, label]) => `<th>${label}</th>`).join("")}<th>实际伤害</th><th></th></tr></thead>
          <tbody id="weaponBody">${(card.weapons || []).map(weaponRow).join("")}</tbody>
        </table>
      </div>
    </section>

    <section class="coc-block">
      <h3>资产 <button type="button" class="btn-sm" id="fillAssets">按规则填入</button></h3>
      <div class="coc-grid">
        <label>信用评级<input id="credit_rating" type="number" min="0" max="99" value="${creditFromSkillRow()}" class="coc-num" readonly title="由技能表的信用评级决定（职业点补到下限后可用兴趣点）" /></label>
        <label>生活水平
          <select id="living_standard">
            <option value="">未选择</option>
            ${LIVING_LEVELS.map((lv) => `<option value="${lv}"${lv === (assets.living_standard || "") ? " selected" : ""}>${lv}</option>`).join("")}
          </select>
        </label>
        <label>币种
          <select id="currency">
            <option value="">未选择</option>
            ${(options.currencies || []).map((c) => `<option value="${escapeHtml(c.code)}"${c.code === (assets.currency || "JPY") ? " selected" : ""}>${escapeHtml(c.label)}</option>`).join("")}
          </select>
        </label>
        <label>现金<input id="cash" value="${escapeHtml(assets.cash || "")}" /></label>
        <label>消费水平<input id="spending_level" value="${escapeHtml(assets.spending_level || "")}" /></label>
        <label class="coc-wide">其他资产<input id="other_assets" value="${escapeHtml(assets.other_assets || "")}" placeholder="交通工具、房产、收藏品等" /></label>
      </div>
      <p class="coc-note" id="assetHint"></p>
      <div class="coc-grid coc-asset-items">
        ${ASSET_ITEMS.map(([key, label]) => `<label>${label}<input type="number" min="0" data-asset-item="${key}" value="${assets[key] != null ? escapeHtml(assets[key]) : ""}" class="coc-num" /></label>`).join("")}
        <label>资产总和<input id="assetTotal" value="" readonly class="coc-num" /></label>
        <label>剩余资产值<input id="assetRemaining" type="number" min="0" value="${assets.remaining != null ? escapeHtml(assets.remaining) : ""}" class="coc-num" /></label>
      </div>
    </section>

    <section class="coc-block">
      <h3>随身物品 <button type="button" class="btn-sm" id="addItem">添加物品</button></h3>
      <div class="coc-table-wrap">
        <table class="coc-table">
          <thead><tr><th>状态</th><th>部位</th><th>物品名称</th><th>背包格</th><th></th></tr></thead>
          <tbody id="itemBody">${(card.inventory || []).map(inventoryRow).join("")}</tbody>
        </table>
      </div>
      <p class="coc-note" id="inventoryTotals"></p>
    </section>

    <section class="coc-block">
      <h3>背景</h3>
      <div class="coc-grid coc-bg">
        ${BACKGROUND_FIELDS.map(([key, label]) => `<label>${label}<textarea rows="2" data-bg="${key}">${escapeHtml(bg[key] || "")}</textarea></label>`).join("")}
        <label>克苏鲁神话<input id="cthulhu_mythos" type="number" min="0" max="99" value="${card.cthulhu_mythos || 0}" class="coc-num" /></label>
        <label>古籍、咒文和魔法物品<textarea rows="2" data-bg="arcane_tomes">${escapeHtml(bg.arcane_tomes || "")}</textarea></label>
      </div>
      <label class="coc-wide">调查员笔记<textarea id="notes" rows="4">${escapeHtml(card.notes || "")}</textarea></label>
    </section>
  `;
  bind();
  renderOccChoices();
  renderWeaponLibrary();
  renderInventoryTotals();
  renderAgeAdjust();
  syncCreditAssets();   // 资产区的信用评级跟随技能行（整页刚渲染完才拿得到技能行）
  rerenderDerived();
}

function bind() {
  document.getElementById("backBtn").addEventListener("click", () => { window.location.href = "/trpg"; });
  document.getElementById("saveBtn").addEventListener("click", save);
  document.getElementById("rollAll").addEventListener("click", () => {
    ATTRS.forEach(([key, , spec]) => {
      const el = document.querySelector(`[data-attr="${key}"]`);
      if (el) el.value = rollDie(spec);
    });
    rerenderDerived();
  });
  main.querySelectorAll("[data-roll]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.dataset.roll;
      const spec = btn.dataset.spec;
      const value = rollDie(spec);
      const el = key === "luck" ? document.getElementById("luck") : document.querySelector(`[data-attr="${key}"]`);
      if (el) el.value = value;
      rerenderDerived();
    });
  });
  main.addEventListener("input", rerenderDerived);
  main.addEventListener("change", rerenderDerived);
  document.getElementById("age").addEventListener("change", renderAgeAdjust);
  document.getElementById("occupation").addEventListener("change", () => {
    occChoices = {};
    pruneAutoAdded();
    renderOccChoices();
    const occ = currentOccupation();
    if (occ && isCreditSkill("信用评级")) {
      const row = creditRowEl();
      if (row && creditFromSkillRow() === 0) {
        row.querySelector("[data-occ]").value = occ.credit_min;
        syncCreditAssets();
      }
    }
    const added = fillRequiredSkills(occ);
    rerenderDerived();
    if (added) showToast(`已补入本职技能 ${added} 项，可选池请逐项选择`, false);
  });
  const skillInput = document.getElementById("skillName");
  const skillHint = document.getElementById("skillAddHint");
  const setSkillHint = (text) => {
    if (!skillHint) return;
    skillHint.textContent = text || "";
    skillHint.classList.toggle("is-error", Boolean(text));
  };
  function addSkillFromInput() {
    const raw = (skillInput.value || "").trim();
    if (!raw) {
      setSkillHint("先输入技能名");
      skillInput.focus();
      return;
    }
    const name = normalizeSkillName(raw);
    if (!name) {
      setSkillHint("先输入技能名");
      return;
    }
    if (name.length > 30) {
      setSkillHint(`技能名太长（${name.length} 字），最多 30 字`);
      return;
    }
    const exists = [...document.querySelectorAll("[data-skill]")]
      .some((row) => canonSkill(row.dataset.name) === canonSkill(name));
    if (exists) {
      setSkillHint(`技能已存在：${name}`);
      return;
    }
    const tbody = document.getElementById("skillBody");
    const known = skillBaseFor(name) > 0;
    tbody.insertAdjacentHTML("beforeend", skillRow(name, { base: skillBaseOrZero(name) }));
    setSkillHint(known ? "" : `「${name}」不是官方技能，基础值可自行填写`);
    skillInput.value = "";
    setSkillHint("");
    rerenderDerived();
    skillInput.focus();
  }
  skillInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      addSkillFromInput();
    }
  });
  skillInput.addEventListener("input", () => setSkillHint(""));
  document.getElementById("addSkill").addEventListener("click", () => {
    addSkillFromInput();
  });
  document.getElementById("weaponLib").addEventListener("change", (event) => {
    const index = event.target.value;
    if (index === "") return;
    const weapon = libraryWeapons()[Number(index)];
    event.target.value = "";
    if (!weapon) return;
    const exists = [...document.querySelectorAll("[data-weapon-row]")]
      .some((row) => String(row.querySelector('[data-weapon="name"]').value || "").trim() === weapon.name);
    const hint = document.getElementById("weaponLibHint");
    if (exists) {
      if (hint) hint.textContent = `武器表里已有「${weapon.name}」`;
      return;
    }
    if (hint) hint.textContent = "";
    document.getElementById("weaponBody").insertAdjacentHTML("beforeend", weaponRow(fillWeaponFromLibrary(weapon)));
    rerenderDerived();
  });
  document.getElementById("era").addEventListener("change", renderWeaponLibrary);
  document.getElementById("fillAssets").addEventListener("click", async () => {
    const currency = document.getElementById("currency").value;
    const credit = document.getElementById("credit_rating").value;
    if (!currency) {
      showToast("先选择币种", true);
      return;
    }
    try {
      const params = new URLSearchParams({ currency, credit });
      const res = await fetch(`/api/trpg/coc/asset-reference?${params}`, { headers: GalleryAuth.headers() });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "查询失败");
      document.getElementById("living_standard").value = data.level || "";
      if (data.cash !== null && data.cash !== undefined) document.getElementById("cash").value = data.cash;
      if (data.spending !== null && data.spending !== undefined) {
        document.getElementById("spending_level").value = data.spending;
      }
      rerenderDerived();
      showToast(`已按「${data.level}」填入参考值`, false);
    } catch (err) {
      showToast(err.message || "查询失败", true);
    }
  });
  main.addEventListener("input", syncCreditAssets);
  main.addEventListener("change", syncCreditAssets);
  document.getElementById("credit_rating").addEventListener("change", () => {
    // 档位跟随信用评级（可手动改）
    const level = document.getElementById("living_standard");
    if (level) level.value = levelForCredit(document.getElementById("credit_rating").value);
    rerenderDerived();
  });
  document.getElementById("addWeapon").addEventListener("click", () => {
    document.getElementById("weaponBody").insertAdjacentHTML(
      "beforeend",
      weaponRow({ name: "", type: "", skill: "", success: 0, damage: "", range: "", attacks: "", ammo: "", malfunction: "", pierce: "" })
    );
  });
  document.getElementById("addItem").addEventListener("click", () => {
    document.getElementById("itemBody").insertAdjacentHTML("beforeend", inventoryRow({}));
    renderInventoryTotals();
  });
  document.getElementById("itemBody").addEventListener("click", (e) => {
    if (!e.target.matches("[data-remove-item]")) return;
    e.target.closest("tr").remove();
    renderInventoryTotals();
  });
  document.getElementById("itemBody").addEventListener("input", renderInventoryTotals);
  document.getElementById("itemBody").addEventListener("change", renderInventoryTotals);
  document.getElementById("weaponBody").addEventListener("click", (e) => {
    if (!e.target.matches("[data-remove-weapon]")) return;
    e.target.closest("tr").remove();
  });
  document.getElementById("skillBody").addEventListener("click", (e) => {
    if (!e.target.matches("[data-remove]")) return;
    e.target.closest("tr").remove();
    rerenderDerived();
  });
}
// ── 年龄调整 ─────────────────────────────────────
// 年龄段表由 /api/trpg/coc/options 下发（与 core/trpg/coc.py::AGE_BANDS 单一来源）；
// 体能合计扣减由玩家自己填，EDU 成长检定在服务端掷。
const AGE_LOCKED_KEYS = ["str_score", "con_score", "siz_score", "dex_score", "app_score", "edu_score"];

function ageBandFor(age) {
  const years = Number(age || 0);
  return (options.age_bands || []).find((band) => years >= band.min && years <= band.max) || null;
}

function lockAgeAttrs(record) {
  const band = record ? ageBandFor(record.age) : null;
  const locked = new Set();
  if (band) {
    band.phy.forEach((key) => locked.add({ str: "str_score", con: "con_score", siz: "siz_score", dex: "dex_score" }[key]));
    if (band.app) locked.add("app_score");
    if (band.edu_checks || band.edu_fixed) locked.add("edu_score");
  }
  AGE_LOCKED_KEYS.forEach((key) => {
    const input = document.querySelector(`[data-attr="${key}"]`);
    if (!input) return;
    input.readOnly = locked.has(key);
    input.classList.toggle("is-locked", locked.has(key));
    input.title = locked.has(key) ? "年龄调整已应用，如需修改请先撤销" : "";
  });
}

function renderAgeAdjust() {
  const box = document.getElementById("ageAdjust");
  if (!box) return;
  const age = Number(document.getElementById("age").value || 0);
  const band = ageBandFor(age);
  const record = card.age_adjust || null;
  if (!band) {
    const [low, high] = options.age_range || [15, 99];
    box.innerHTML = `<p class="coc-note">填写 ${low}-${high} 岁之间的年龄后可做年龄调整。</p>`;
    lockAgeAttrs(null);
    return;
  }
  if (record && record.kind === "applied") {
    lockAgeAttrs(record);
    const phy = (record.phy || {});
    // 用记录里的年龄段取体能项：年龄改到别的段时仍能正确显示已应用的内容
    const recBand = (options.age_bands || []).find((item) => item.band === record.band) || band;
    const phyText = recBand.phy.map((key, i) => `${recBand.phy_labels[i]} ${phy[key] || 0}`).join("、");
    const edu = record.edu || {};
    const rolls = (edu.rolls || []).map((r) => `${r.roll}${r.gain ? ` → +${r.gain}` : " → 无增长"}`).join("、");
    const stale = record.age !== age
      ? `<p class="coc-warn">年龄已改为 ${age}（应用时为 ${record.age}），请先撤销再重新应用。</p>` : "";
    box.innerHTML = `
      <p class="coc-note"><b>已应用</b>（${escapeHtml(record.band)} 岁）：体能 ${phyText || "无"}${record.app ? `；外貌 ${record.app}` : ""}${edu.before !== undefined ? `；教育 ${edu.before} → ${edu.after}` : ""}</p>
      ${rolls ? `<p class="coc-note">教育成长检定 ×${edu.checks || 0}：${rolls}</p>` : ""}
      ${stale}
      <button type="button" class="btn-sm" id="ageUndo">撤销年龄调整</button>`;
    document.getElementById("ageUndo").addEventListener("click", undoAgeAdjust);
    return;
  }
  lockAgeAttrs(null);
  const quota = band.phy_quota;
  const inputs = band.phy.map((key, i) => `
    <label>${band.phy_labels[i]}<input type="number" data-phy="${key}" class="coc-num" max="0" step="1" value="" placeholder="0" /></label>`).join("");
  const extras = [];
  if (band.app) extras.push(`外貌 -${band.app}`);
  if (band.edu_fixed) extras.push(`教育 ${band.edu_fixed}`);
  if (band.edu_checks) extras.push(`教育成长检定 ×${band.edu_checks}（服务端掷）`);
  if (band.luck_best) extras.push("幸运掷两次取高");
  const skipped = record && record.kind === "skipped"
    ? '<span class="coc-note">（已选过「不再提示」）</span>' : "";
  const summary = [
    quota ? `体能合计 -${quota}（扣在哪几项由你决定，填 0 或负数）` : "",
    ...extras,
  ].filter(Boolean).join("；");
  box.innerHTML = `
    <p class="coc-note">按 ${escapeHtml(band.band)} 岁：${summary}。${skipped}</p>
    ${inputs ? `<div class="coc-grid coc-age-phy">${inputs}</div>` : ""}
    ${band.luck_best ? '<button type="button" class="btn-sm" id="ageLuck">🎲 幸运掷两次取高</button>' : ""}
    <p class="coc-note" id="ageHint"></p>
    <button type="button" class="btn-sm primary" id="ageApply">应用年龄调整</button>
    <button type="button" class="btn-sm" id="ageSkip">不再提示</button>`;
  const hint = document.getElementById("ageHint");
  const applyBtn = document.getElementById("ageApply");
  const update = () => {
    let spent = 0;
    let bad = false;
    box.querySelectorAll("[data-phy]").forEach((el) => {
      const value = Number(el.value || 0);
      if (!Number.isInteger(value) || value > 0) bad = true;
      spent += -value;
    });
    const ok = !bad && spent === quota;
    applyBtn.disabled = !ok;
    hint.textContent = bad ? "只能填 0 或负数" : `体能合计 ${spent}/${quota}`;
    hint.classList.toggle("is-error", !ok);
  };
  box.querySelectorAll("[data-phy]").forEach((el) => el.addEventListener("input", update));
  update();
  applyBtn.addEventListener("click", applyAgeAdjust);
  document.getElementById("ageSkip").addEventListener("click", () => sendAgeAdjust({ action: "skip" }));
  const lucky = document.getElementById("ageLuck");
  if (lucky) {
    lucky.addEventListener("click", () => {
      const luck = document.getElementById("luck");
      luck.value = Math.max(rollDie("3d6"), rollDie("3d6"));
      rerenderDerived();
    });
  }
}

function afterAgeAdjust(data) {
  AGE_LOCKED_KEYS.forEach((key) => {
    const input = document.querySelector(`[data-attr="${key}"]`);
    if (input && data[key] !== undefined && data[key] !== null) input.value = data[key];
  });
  card.age_adjust = data.age_adjust;
  card.age = data.age;
  renderAgeAdjust();
  rerenderDerived();
}

async function sendAgeAdjust(payload) {
  if (!CHAR_ID) {
    showToast("先保存角色卡，再从编辑页应用年龄调整", true);
    return null;
  }
  try {
    const res = await fetch(`/api/me/characters/${CHAR_ID}/age-adjust`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "年龄调整失败");
    afterAgeAdjust(data);
    showToast(payload.action === "skip" ? "已记录：不再提示年龄调整" : "年龄调整已应用", false);
    return data;
  } catch (err) {
    showToast(err.message || "年龄调整失败", true);
    return null;
  }
}

function applyAgeAdjust() {
  const phy = {};
  document.querySelectorAll("[data-phy]").forEach((el) => { phy[el.dataset.phy] = Number(el.value || 0); });
  sendAgeAdjust({ action: "apply", phy });
}

async function undoAgeAdjust() {
  if (!CHAR_ID) return;
  try {
    const res = await fetch(`/api/me/characters/${CHAR_ID}/age-adjust`, {
      method: "DELETE",
      headers: GalleryAuth.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "撤销失败");
    afterAgeAdjust(data);
    showToast("已撤销年龄调整", false);
  } catch (err) {
    showToast(err.message || "撤销失败", true);
  }
}

function collect() {
  const skills = {};
  document.querySelectorAll("[data-skill]").forEach((row) => {
    const name = row.dataset.name;
    if (isCreditSkill(name)) {
      skills[name] = {
        base: 0,
        growth: 0,
        occupation: Number(row.querySelector("[data-occ]").value || 0),
        interest: Number(row.querySelector("[data-int]").value || 0),
      };
      return;
    }
    skills[name] = {
      base: Number(row.querySelector("[data-base]").value || 0),
      growth: Number(row.querySelector("[data-growth]").value || 0),
      occupation: Number(row.querySelector("[data-occ]").value || 0),
      interest: Number(row.querySelector("[data-int]").value || 0),
    };
  });
  const bg = {};
  main.querySelectorAll("[data-bg]").forEach((el) => { bg[el.dataset.bg] = el.value; });
  return {
    rules: "coc7th",
    char_name: document.getElementById("char_name").value.trim() || "无名调查员",
    occupation: document.getElementById("occupation").value,
    occupation_choices: occChoices,
    age: Number(document.getElementById("age").value || 0),
    sex: document.getElementById("sex").value.trim(),
    residence: document.getElementById("residence").value.trim(),
    birthplace: document.getElementById("birthplace").value.trim(),
    era: document.getElementById("era").value.trim(),
    luck: Number(document.getElementById("luck").value || 0),
    credit_rating: creditFromSkillRow(),
    cthulhu_mythos: Number(document.getElementById("cthulhu_mythos").value || 0),
    str_score: attr("str_score"), con_score: attr("con_score"), siz_score: attr("siz_score"),
    dex_score: attr("dex_score"), app_score: attr("app_score"), int_score: attr("int_score"),
    pow_score: attr("pow_score"), edu_score: attr("edu_score"),
    skills,
    assets: {
      cash: document.getElementById("cash").value.trim(),
      spending_level: document.getElementById("spending_level").value.trim(),
      living_standard: document.getElementById("living_standard").value,
      currency: document.getElementById("currency").value,
      other_assets: document.getElementById("other_assets").value.trim(),
      ...Object.fromEntries([...document.querySelectorAll("[data-asset-item]")]
        .map((el) => [el.dataset.assetItem, el.value.trim()])),
      remaining: document.getElementById("assetRemaining").value.trim(),
    },
    inventory: [...document.querySelectorAll("[data-item-row]")].map((row) => ({
      status: row.querySelector('[data-item="status"]').value,
      slot: row.querySelector('[data-item="slot"]').value.trim(),
      name: row.querySelector('[data-item="name"]').value.trim(),
      slots: row.querySelector('[data-item="slots"]').value.trim(),
    })).filter((item) => item.name),
    weapons: [...document.querySelectorAll("[data-weapon-row]")].map((row) => {
      const weapon = {};
      row.querySelectorAll("[data-weapon]").forEach((el) => {
        weapon[el.dataset.weapon] = el.type === "number" ? Number(el.value || 0) : el.value.trim();
      });
      return weapon;
    }).filter((weapon) => weapon.name),
    social_background: bg,
    notes: document.getElementById("notes").value,
  };
}

async function save() {
  const payload = collect();
  try {
    const url = CHAR_ID ? `/api/me/characters/${CHAR_ID}` : "/api/me/characters";
    const res = await fetch(url, {
      method: CHAR_ID ? "PUT" : "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "保存失败");
    window.location.href = "/trpg";
  } catch (err) {
    alert(err.message || "保存失败");
  }
}

async function init() {
  if (!(await GalleryAuth.refreshMe())) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
    return;
  }
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  try {
    const optRes = await fetch("/api/trpg/coc/options", { headers: GalleryAuth.headers() });
    options = await optRes.json();
    if (CHAR_ID) {
      const res = await fetch(`/api/me/characters/${CHAR_ID}`, { headers: GalleryAuth.headers() });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "读取角色卡失败");
      card = data;
      card.skills = mergeSkillDefaults(card, card.dex_score);
      occChoices = { ...(card.occupation_choices || {}) };
    } else {
      card = {
        age: 25,
        skills: skillDefaults(options.skill_base, 0, options.default_skills, options.dynamic_bases),
        weapons: [{ name: "徒手格斗", type: "常规武器", skill: "斗殴", success: 25, damage: "1D3+DB", range: "接触", attacks: "1", ammo: "", malfunction: "", pierce: "×" }],
      };
    }
    render();
  } catch (err) {
    main.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message || "加载失败")}</p>`;
  }
}

init();
