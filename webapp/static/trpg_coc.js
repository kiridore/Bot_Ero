// COC 7th 建卡工具：属性/职业/技能点/派生值，对齐 docs/COC七版人物卡v1.6.1.xlsx 的建卡口径。
const main = document.getElementById("cocMain");
const PATH_PARTS = location.pathname.split("/").filter(Boolean); // trpg / coc / <id>
const CHAR_ID = PATH_PARTS[2] ? Number(PATH_PARTS[2]) : null;

const ATTRS = [
  ["str_score", "力量", "3d6"], ["con_score", "体质", "3d6"], ["siz_score", "体型", "2d6+6"],
  ["dex_score", "敏捷", "3d6"], ["app_score", "外貌", "3d6"], ["int_score", "智力", "2d6+6"],
  ["pow_score", "意志", "3d6"], ["edu_score", "教育", "2d6+6"],
];

const BACKGROUND_FIELDS = [
  ["description", "个人描述"], ["ideology", "思想与信念"], ["significant_people", "重要之人"],
  ["meaningful_places", "意义非凡之地"], ["treasured_possessions", "宝贵之物"], ["traits", "特质"],
  ["scars", "伤口和疤痕"], ["phobias", "恐惧症和狂躁症"],
];

let options = null;
let card = null;
let me = null;

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
  let occSpent = 0, intSpent = 0;
  document.querySelectorAll("[data-skill]").forEach((row) => {
    occSpent += Number(row.querySelector("[data-occ]").value || 0);
    intSpent += Number(row.querySelector("[data-int]").value || 0);
    const base = Number(row.querySelector("[data-base]").value || 0);
    const growth = Number(row.querySelector("[data-growth]").value || 0);
    const value = Math.min(base + growth + Number(row.querySelector("[data-occ]").value || 0) + Number(row.querySelector("[data-int]").value || 0), 199);
    row.querySelector("[data-total]").textContent = value;
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
  set("out-int-budget", interestBudget);
  set("out-int-spent", intSpent);
  const occNote = document.getElementById("occ-note");
  if (occNote) {
    occNote.textContent = occ
      ? `职业点 ${occ.formula}；信用评级 ${occ.credit_min}-${occ.credit_max}；本职技能：${occ.own_skills}`
      : "未选择职业";
  }
  const occWarn = document.getElementById("occ-warn");
  if (occWarn) {
    const over = [];
    if (occSpent > occBudget) over.push(`职业点超出 ${occSpent}/${occBudget}`);
    if (intSpent > interestBudget) over.push(`兴趣点超出 ${intSpent}/${interestBudget}`);
    occWarn.textContent = over.join("；");
  }
}

function skillRow(name, entry) {
  const base = entry.base != null ? entry.base : (options.skill_base[name] || 0);
  return `
    <tr data-skill data-name="${escapeHtml(name)}">
      <td>${escapeHtml(name)}</td>
      <td><input type="number" data-base value="${base}" min="0" max="99" class="coc-num" /></td>
      <td><input type="number" data-growth value="${entry.growth || 0}" min="0" max="199" class="coc-num" />${entry.check ? " ✓" : ""}</td>
      <td><input type="number" data-occ value="${entry.occupation || 0}" min="0" max="99" class="coc-num" /></td>
      <td><input type="number" data-int value="${entry.interest || 0}" min="0" max="99" class="coc-num" /></td>
      <td data-total class="coc-total">0</td>
      <td><button type="button" class="btn-sm" data-remove>删</button></td>
    </tr>`;
}

const WEAPON_FIELDS = [
  ["name", "武器", "text"],
  ["success", "成功率", "number"],
  ["damage", "伤害", "text"],
  ["range", "射程", "text"],
  ["attacks", "次数", "text"],
  ["ammo", "弹药", "text"],
  ["malfunction", "故障值", "text"],
  ["pierce", "贯穿", "text"],
];

function weaponRow(weapon) {
  const cells = WEAPON_FIELDS.map(([key, , type]) => {
    const value = weapon[key] != null ? weapon[key] : "";
    const cls = type === "number" ? "coc-num" : "";
    return `<td><input type="${type}" data-weapon="${key}" value="${escapeHtml(value)}" class="${cls}" /></td>`;
  }).join("");
  return `<tr data-weapon-row>${cells}<td><button type="button" class="btn-sm" data-remove-weapon>删</button></td></tr>`;
}

function render() {
  const bg = card.social_background || {};
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
      <p class="coc-note" id="occ-note"></p>
      <p class="coc-warn" id="occ-warn"></p>
    </section>

    <section class="coc-block">
      <h3>属性 <button type="button" class="btn-sm" id="rollAll">全部重掷</button></h3>
      <div class="coc-grid coc-attrs">
        ${ATTRS.map(([key, label, spec]) => `
          <label>${label}<input type="number" data-attr="${key}" value="${card[key] || 0}" min="0" max="99" class="coc-num" />
            <button type="button" class="btn-sm" data-roll="${key}" data-spec="${spec}">掷</button></label>`).join("")}
        <label>幸运<input type="number" id="luck" value="${card.luck || 0}" min="0" max="99" class="coc-num" />
          <button type="button" class="btn-sm" data-roll="luck" data-spec="3d6">掷</button></label>
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
      <h3>技能 <button type="button" class="btn-sm" id="addSkill">添加技能</button></h3>
      <div class="coc-table-wrap">
        <table class="coc-table">
          <thead><tr><th>技能</th><th>基础</th><th>成长</th><th>职业</th><th>兴趣</th><th>成功率</th><th></th></tr></thead>
          <tbody id="skillBody">${Object.entries(card.skills || {}).map(([n, e]) => skillRow(n, e)).join("")}</tbody>
        </table>
      </div>
    </section>

    <section class="coc-block">
      <h3>武器 <button type="button" class="btn-sm" id="addWeapon">添加武器</button></h3>
      <div class="coc-table-wrap">
        <table class="coc-table">
          <thead><tr>${WEAPON_FIELDS.map(([, label]) => `<th>${label}</th>`).join("")}<th></th></tr></thead>
          <tbody id="weaponBody">${(card.weapons || []).map(weaponRow).join("")}</tbody>
        </table>
      </div>
    </section>

    <section class="coc-block">
      <h3>资产</h3>
      <div class="coc-grid">
        <label>信用评级<input id="credit_rating" type="number" min="0" max="99" value="${card.credit_rating || 0}" class="coc-num" /></label>
        <label>现金<input id="cash" value="${escapeHtml((card.assets || {}).cash || "")}" /></label>
        <label>消费水平<input id="spending_level" value="${escapeHtml((card.assets || {}).spending_level || "")}" /></label>
        <label>生活水平<input id="living_standard" value="${escapeHtml((card.assets || {}).living_standard || "")}" /></label>
      </div>
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
    // 幸运与八项属性同属「属性」区，全部重掷必须一起掷
    const luck = document.getElementById("luck");
    if (luck) luck.value = rollDie("3d6");
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
  document.getElementById("occupation").addEventListener("change", () => {
    const occ = currentOccupation();
    if (occ) {
      const credit = document.getElementById("credit_rating");
      if (credit) credit.value = occ.credit_min;
    }
    rerenderDerived();
  });
  document.getElementById("addSkill").addEventListener("click", () => {
    const name = prompt("技能名（可用类别：技艺:xxx / 科学:xxx / 语言:xxx / 格斗:xxx / 射击:xxx）");
    if (!name) return;
    const tbody = document.getElementById("skillBody");
    tbody.insertAdjacentHTML("beforeend", skillRow(name.trim(), { base: options.skill_base[name.trim()] || 0 }));
    rerenderDerived();
  });
  document.getElementById("addWeapon").addEventListener("click", () => {
    document.getElementById("weaponBody").insertAdjacentHTML(
      "beforeend",
      weaponRow({ name: "", success: 0, damage: "", range: "", attacks: "", ammo: "", malfunction: "", pierce: "" })
    );
  });
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
function collect() {
  const skills = {};
  document.querySelectorAll("[data-skill]").forEach((row) => {
    const name = row.dataset.name;
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
    age: Number(document.getElementById("age").value || 0),
    sex: document.getElementById("sex").value.trim(),
    residence: document.getElementById("residence").value.trim(),
    birthplace: document.getElementById("birthplace").value.trim(),
    era: document.getElementById("era").value.trim(),
    luck: Number(document.getElementById("luck").value || 0),
    credit_rating: Number(document.getElementById("credit_rating").value || 0),
    cthulhu_mythos: Number(document.getElementById("cthulhu_mythos").value || 0),
    str_score: attr("str_score"), con_score: attr("con_score"), siz_score: attr("siz_score"),
    dex_score: attr("dex_score"), app_score: attr("app_score"), int_score: attr("int_score"),
    pow_score: attr("pow_score"), edu_score: attr("edu_score"),
    skills,
    assets: {
      cash: document.getElementById("cash").value.trim(),
      spending_level: document.getElementById("spending_level").value.trim(),
      living_standard: document.getElementById("living_standard").value.trim(),
    },
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
    } else {
      card = {
        age: 25,
        skills: { 侦查: { base: 25 }, 聆听: { base: 20 }, 图书馆: { base: 20 }, 闪避: { base: 0 } },
        weapons: [{ name: "徒手格斗", success: 25, damage: "1D3+DB", range: "—", attacks: "1", ammo: "—", malfunction: "—", pierce: "—" }],
      };
    }
    render();
  } catch (err) {
    main.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message || "加载失败")}</p>`;
  }
}

init();
