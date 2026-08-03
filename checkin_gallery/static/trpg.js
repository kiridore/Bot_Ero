const trpgMain = document.getElementById("trpgMain");

let rules = null;        // /api/trpg/rules 数据
let chars = [];          // 我的角色列表
let currentId = null;    // 当前角色 id
let editing = null;      // 正在编辑的角色数据（null = 新建）

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    window.location.href = "/";
    return false;
  }
  return true;
}

function renderAuthChip() {
  const session = GalleryAuth.load();
  const area = document.getElementById("authArea");
  if (!session) return;
  area.innerHTML = "";
  const link = document.createElement("a");
  link.className = "user-chip";
  link.href = "/profile";
  const img = document.createElement("img");
  img.src = session.avatar_url || "";
  img.alt = session.display_name;
  img.onerror = () => { img.style.display = "none"; };
  const wrap = document.createElement("span");
  wrap.innerHTML = `<strong>${escapeHtml(session.display_name)}</strong><br><span class="uid">${session.user_id}</span>`;
  link.append(img, wrap);
  area.appendChild(link);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...GalleryAuth.headers(),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) {
    GalleryAuth.clear();
    window.location.href = "/";
    throw new Error("未登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "操作失败");
  return data;
}

function showToast(msg, isError = false) {
  let toast = document.getElementById("trpgToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "trpgToast";
    toast.className = "settings-toast";
    trpgMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 2800);
}

// ── 计算（与后端 core/trpg/character.finalize 口径一致）──

function abilityMod(score) {
  return Math.floor((Number(score || 8) - 10) / 2);
}

function attrKey(name) {
  return { "力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
           "智力": "int_score", "感知": "wis_score", "魅力": "cha_score" }[name] || "";
}

function computeSheet(data) {
  const scores = {};
  for (const attr of rules.attributes) {
    const key = attrKey(attr);
    const base = Number(data[key] ?? 8) + (rules.races[data.race]?.[attr] || 0);
    scores[key] = base;
  }
  const conMod = abilityMod(scores.con_score);
  const dexMod = abilityMod(scores.dex_score);
  const hpDie = rules.classes[data.class_name]?.hp_die || 8;
  const skillMods = {};
  for (const [skill, attr] of Object.entries(rules.skills)) {
    let mod = abilityMod(scores[attrKey(attr)]);
    if ((data.proficient_skills || []).includes(skill)) mod += 2;
    skillMods[skill] = mod;
  }
  const profBonus = 2 + Math.floor((Number(data.level || 1) - 1) / 4);
  const savingProfs = data.saving_profs || [];
  const saveMods = {};
  for (const attr of rules.attributes) {
    let m = abilityMod(scores[attrKey(attr)]);
    if (savingProfs.includes(attr)) m += profBonus;
    saveMods[attr] = m;
  }
  const wisMod = abilityMod(scores.wis_score);
  const passivePerception = 10 + wisMod + ((data.proficient_skills || []).includes("察觉") ? 2 : 0);
  return {
    scores, skillMods, saveMods, profBonus,
    passivePerception,
    initiative: abilityMod(scores.dex_score),
    hitDice: `${data.level || 1}d${hpDie}`,
    hp: Number(data.hp) || hpDie + conMod,
    ac: Number(data.ac) || 10 + dexMod,
    hpDie,
  };
}

// ── 视图：列表 ──

function renderList() {
  trpgMain.innerHTML = "";
  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = `<h2>我的角色卡</h2>`;
  const newBtn = document.createElement("button");
  newBtn.type = "button";
  newBtn.className = "btn-sm primary";
  newBtn.textContent = "新建角色";
  newBtn.addEventListener("click", () => {
    editing = {
      char_name: "", race: "人类", class_name: "战士", level: 1, background: "",
      alignment: "绝对中立", xp: 0,
      str_score: 10, dex_score: 10, con_score: 10, int_score: 10, wis_score: 10, cha_score: 10,
      proficient_skills: [], saving_profs: [],
      hp: 0, ac: 0, current_hp: 0, temp_hp: 0, speed: 30,
      death_saves_success: 0, death_saves_fail: 0, inspiration: false,
      equipment: [], other_proficiencies: "", attacks: [], features: "",
      personality_traits: "", ideals: "", bonds: "", flaws: "",
      notes: "",
    };
    renderEditor();
  });
  head.appendChild(newBtn);
  trpgMain.appendChild(head);

  if (!chars.length) {
    const p = document.createElement("p");
    p.className = "empty-hint";
    p.textContent = "还没有角色卡，点击右上角「新建角色」开始车卡";
    trpgMain.appendChild(p);
    return;
  }

  for (const c of chars) {
    const row = document.createElement("article");
    row.className = "settings-title-row";
    const isCur = c.id === currentId;
    row.innerHTML = `
      <div class="row-main">
        <strong>[#${c.id}] ${escapeHtml(c.char_name)}${isCur ? " ◀ 当前" : ""}</strong>
        <span class="rarity">Lv.${c.level} ${escapeHtml(c.race)} ${escapeHtml(c.class_name)}</span>
        <p class="desc">HP ${c.hp} / AC ${c.ac}</p>
      </div>
    `;
    const actions = document.createElement("div");
    actions.className = "row-actions";
    const actBtn = document.createElement("button");
    actBtn.type = "button";
    actBtn.className = "btn-sm";
    actBtn.textContent = "查看";
    actBtn.addEventListener("click", () => { window.location.href = `/trpg/char/${c.user_id}/${c.id}`; });
    actions.appendChild(actBtn);
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn-sm";
    editBtn.textContent = "编辑";
    editBtn.addEventListener("click", async () => {
      try {
        editing = await apiFetch(`/api/me/characters/${c.id}`);
        renderEditor();
      } catch (err) { showToast(err.message, true); }
    });
    actions.appendChild(editBtn);
    if (!isCur) {
      const swBtn = document.createElement("button");
      swBtn.type = "button";
      swBtn.className = "btn-sm";
      swBtn.textContent = "设为当前";
      swBtn.addEventListener("click", async () => {
        try {
          await apiFetch(`/api/me/characters/${c.id}/activate`, { method: "POST" });
          await loadList();
          showToast("已设为当前角色");
        } catch (err) { showToast(err.message, true); }
      });
      actions.appendChild(swBtn);
    }
    const delBtn = document.createElement("button");
    delBtn.type = "button";
    delBtn.className = "btn-sm danger";
    delBtn.textContent = "删除";
    delBtn.addEventListener("click", async () => {
      if (!confirm(`确定删除角色「${c.char_name}」？`)) return;
      try {
        await apiFetch(`/api/me/characters/${c.id}`, { method: "DELETE" });
        await loadList();
        showToast("已删除角色");
      } catch (err) { showToast(err.message, true); }
    });
    actions.appendChild(delBtn);
    row.appendChild(actions);
    trpgMain.appendChild(row);
  }
}

// ── 视图：编辑器（单页分区表格）──

function renderEditor() {
  trpgMain.innerHTML = "";
  const back = document.createElement("button");
  back.type = "button";
  back.className = "btn-sm";
  back.textContent = "← 返回列表";
  back.addEventListener("click", () => renderList());
  trpgMain.appendChild(back);

  const form = document.createElement("div");
  form.className = "trpg-editor";
  let pointBuyMode = false;
  form.innerHTML = `
    <section class="settings-section">
      <div class="section-head"><h2>基本信息</h2></div>
      <table class="trpg-table">
        <tr><th>角色名</th><td><input type="text" data-f="char_name" maxlength="30"></td>
            <th>种族</th><td><select data-f="race"></select></td></tr>
        <tr><th>职业</th><td><select data-f="class_name"></select></td>
            <th>背景</th><td><input type="text" data-f="background"></td></tr>
        <tr><th>阵营</th><td>
            <select data-f="alignment_law">
              <option value="守序">守序</option><option value="中立">中立</option><option value="混乱">混乱</option>
            </select>
            <select data-f="alignment_moral">
              <option value="善良">善良</option><option value="中立">中立</option><option value="邪恶">邪恶</option>
            </select>
            <input type="text" data-f="alignment_custom" placeholder="自定义阵营（非九宫格）" style="display:none;">
          </td>
            <th>经验值</th><td><input type="number" data-f="xp" min="0"></td></tr>
        <tr><th>等级</th><td id="levelCell"></td>
            <th>熟练加值</th><td id="profBonusCell"></td></tr>
        <tr><th>备注</th><td colspan="3"><textarea data-f="notes" rows="3"></textarea></td></tr>
      </table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>属性生成</h2></div>
      <div class="row-actions">
        <button type="button" class="btn-sm" id="genPointBuy">购点法（27点）</button>
        <button type="button" class="btn-sm" id="genRoll">4d6k3 掷骰</button>
        <button type="button" class="btn-sm" id="genArray">标准数组</button>
        <span class="muted" id="pointBuyHint"></span>
      </div>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>属性 <span class="muted">（含种族加值）</span></h2></div>
      <table class="trpg-table" id="attrTable"></table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>技能熟练 <span class="muted">（每项 +2）</span></h2></div>
      <table class="trpg-table" id="skillTable"></table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>战斗 <span class="muted">（未填 HP/AC 时按规则自动计算）</span></h2></div>
      <table class="trpg-table">
        <tr><th>HP</th><td><input type="number" data-f="hp" min="0"></td>
            <th>AC</th><td><input type="number" data-f="ac" min="0"></td>
            <th>先攻</th><td id="initiativeCell"></td></tr>
        <tr><th>当前 HP</th><td><input type="number" data-f="current_hp" min="0"></td>
            <th>临时 HP</th><td><input type="number" data-f="temp_hp" min="0"></td>
            <th>速度</th><td><input type="number" data-f="speed" min="0"></td></tr>
        <tr><th>生命骰</th><td id="hitDiceCell"></td>
            <th>被动感知</th><td id="passiveCell"></td>
            <th>激励</th><td><input type="checkbox" data-f="inspiration" style="width:auto;height:auto;"></td></tr>
        <tr><th>死亡豁免成功</th><td><input type="number" data-f="death_saves_success" min="0" max="3"></td>
            <th>死亡豁免失败</th><td><input type="number" data-f="death_saves_fail" min="0" max="3"></td>
            <th colspan="2"></th></tr>
        <tr><th>建议 HP</th><td colspan="5" id="hpHint"></td></tr>
      </table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>资源 <span class="muted">（装备/攻击/特性，每行一条）</span></h2></div>
      <table class="trpg-table">
        <tr><th>装备与钱币</th><td colspan="3"><textarea data-f="equipment" rows="3" placeholder="每行一条，如：长剑、皮甲、50gp"></textarea></td></tr>
        <tr><th>其他熟练项和语言</th><td colspan="3"><textarea data-f="other_proficiencies" rows="2" placeholder="每行一条，如：通用语、精灵语、铁匠工具"></textarea></td></tr>
        <tr><th>攻击与法术</th><td colspan="3"><textarea data-f="attacks" rows="3" placeholder="格式：名称|攻击加值|伤害&#10;如：长剑|+5|1d8 挥砍"></textarea></td></tr>
        <tr><th>特性与特质</th><td colspan="3"><textarea data-f="features" rows="3"></textarea></td></tr>
      </table>
    </section>

    <section class="settings-section">
      <div class="section-head"><h2>背景 <span class="muted">（角色四要素）</span></h2></div>
      <table class="trpg-table">
        <tr><th>个人特点</th><td colspan="3"><textarea data-f="personality_traits" rows="2"></textarea></td></tr>
        <tr><th>理想</th><td colspan="3"><textarea data-f="ideals" rows="2"></textarea></td></tr>
        <tr><th>牵绊</th><td colspan="3"><textarea data-f="bonds" rows="2"></textarea></td></tr>
        <tr><th>缺点</th><td colspan="3"><textarea data-f="flaws" rows="2"></textarea></td></tr>
      </table>
    </section>

    <div class="row-actions" style="justify-content:flex-end; padding:12px 0;">
      <button type="button" class="btn-sm" id="saveBtn">保存</button>
    </div>
  `;
  trpgMain.appendChild(form);

  const raceSelect = form.querySelector('[data-f="race"]');
  for (const r of Object.keys(rules.races)) {
    const opt = document.createElement("option");
    opt.value = r;
    opt.textContent = r;
    raceSelect.appendChild(opt);
  }
  const classSelect = form.querySelector('[data-f="class_name"]');
  for (const c of Object.keys(rules.classes)) {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    classSelect.appendChild(opt);
  }
  // 旧角色自定义文本兼容：不在官方清单时追加临时选项
  for (const [sel, key] of [[raceSelect, "race"], [classSelect, "class_name"]]) {
    if (editing[key] && ![...sel.options].some((o) => o.value === editing[key])) {
      const opt = document.createElement("option");
      opt.value = editing[key];
      opt.textContent = `${editing[key]}（自定义）`;
      sel.appendChild(opt);
    }
  }

  form.querySelectorAll("[data-f]").forEach((el) => {
    const key = el.dataset.f;
    if (key === "inspiration" || key === "alignment_law" || key === "alignment_moral" || key === "alignment_custom") return;
    el.value = Array.isArray(editing[key]) ? editing[key].join("\n") : (editing[key] ?? "");
  });

  const lawSel = form.querySelector('[data-f="alignment_law"]');
  const moralSel = form.querySelector('[data-f="alignment_moral"]');
  const customSel = form.querySelector('[data-f="alignment_custom"]');
  const AL = ["守序善良", "守序中立", "守序邪恶", "中立善良", "绝对中立", "中立邪恶", "混乱善良", "混乱中立", "混乱邪恶"];
  if (AL.includes(editing.alignment)) {
    if (editing.alignment === "绝对中立") { lawSel.value = "中立"; moralSel.value = "中立"; }
    else {
      lawSel.value = editing.alignment.startsWith("守序") ? "守序" : editing.alignment.startsWith("混乱") ? "混乱" : "中立";
      moralSel.value = editing.alignment.endsWith("善良") ? "善良" : editing.alignment.endsWith("邪恶") ? "邪恶" : "中立";
    }
    customSel.style.display = "none";
  } else if (editing.alignment) {
    customSel.style.display = "";
    customSel.value = editing.alignment;
  }
  const inspEl = form.querySelector('[data-f="inspiration"]');
  if (inspEl) inspEl.checked = Boolean(editing.inspiration);

  const attrTable = document.getElementById("attrTable");
  const skillTable = document.getElementById("skillTable");
  const hpHint = document.getElementById("hpHint");

  function refresh() {
    const data = readForm();
    const calc = computeSheet(data);
    attrTable.innerHTML = "";
    for (const attr of rules.attributes) {
      const key = attrKey(attr);
      const tr = document.createElement("tr");
      tr.innerHTML = `<th>${attr}</th>`;
      const tdScore = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.min = pointBuyMode ? 8 : 1;
      input.max = pointBuyMode ? 15 : 30;
      input.value = data[key] ?? 8;
      input.dataset.attr = key;
      tdScore.appendChild(input);
      tr.appendChild(tdScore);
      const tdMod = document.createElement("td");
      tdMod.className = "muted";
      const bonus = (rules.races[data.race] || {})[attr] || 0;
      tdMod.textContent = `加值 ${abilityMod(calc.scores[key]) >= 0 ? "+" : ""}${abilityMod(calc.scores[key])}${bonus ? `（种族+${bonus}）` : ""}`;
      tr.appendChild(tdMod);
      const tdSave = document.createElement("td");
      const saveCb = document.createElement("input");
      saveCb.type = "checkbox";
      saveCb.checked = (data.saving_profs || []).includes(attr);
      saveCb.dataset.saveprof = attr;
      saveCb.title = "豁免熟练";
      tdSave.appendChild(saveCb);
      tr.appendChild(tdSave);
      const tdSaveMod = document.createElement("td");
      const saveMod = calc.saveMods[attr];
      tdSaveMod.textContent = `豁免 ${saveMod >= 0 ? "+" : ""}${saveMod}`;
      tdSaveMod.className = "muted";
      tr.appendChild(tdSaveMod);
      attrTable.appendChild(tr);
    }
    skillTable.innerHTML = "";
    for (const [skill, attr] of Object.entries(rules.skills)) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<th>${skill}</th><td class="muted">${attr}</td>`;
      const tdProf = document.createElement("td");
      const cb = document.createElement("input");
      cb.type = "checkbox";
      cb.checked = (data.proficient_skills || []).includes(skill);
      cb.dataset.skill = skill;
      tdProf.appendChild(cb);
      tr.appendChild(tdProf);
      const tdMod = document.createElement("td");
      const mod = calc.skillMods[skill];
      tdMod.textContent = `${mod >= 0 ? "+" : ""}${mod}`;
      tr.appendChild(tdMod);
      skillTable.appendChild(tr);
    }
    const suggestedHp = calc.hpDie + abilityMod(calc.scores.con_score);
    const suggestedAc = 10 + abilityMod(calc.scores.dex_score);
    hpHint.textContent = `职业 HP 骰 d${calc.hpDie} + 体质加值 = ${suggestedHp}；敏捷加值 AC = ${suggestedAc}（可在上方手动覆盖）`;
    document.getElementById("profBonusCell").textContent = `+${calc.profBonus}`;
    document.getElementById("initiativeCell").textContent = `${calc.initiative >= 0 ? "+" : ""}${calc.initiative}`;
    document.getElementById("hitDiceCell").textContent = calc.hitDice;
    document.getElementById("passiveCell").textContent = calc.passivePerception;
    const pointCost = {8:0,9:1,10:2,11:3,12:4,13:5,14:7,15:9};
    let spent = 0;
    form.querySelectorAll("[data-attr]").forEach((el) => {
      const v = Number(el.value) || 8;
      if (pointCost[v] !== undefined) spent += pointCost[v];
    });
    const hint = document.getElementById("pointBuyHint");
    hint.textContent = `购点已用 ${spent}/27`;
    const xpVal = Number(data.xp) || 0;
    const level = xpVal > 0 ? levelFromXp(xpVal, rules.xp_thresholds) : (data.level || 1);
    document.getElementById("levelCell").textContent = `Lv.${level}`;
  }

  function rollScores() {
    const scores = [];
    for (let i = 0; i < 6; i++) {
      const rolls = [];
      for (let j = 0; j < 4; j++) rolls.push(1 + Math.floor(Math.random() * 6));
      rolls.sort((a, b) => b - a);
      scores.push(rolls[0] + rolls[1] + rolls[2]);
    }
    return scores;
  }
  const arrayScores = [15, 14, 13, 12, 10, 8];

  form.querySelector("#genRoll").addEventListener("click", () => {
    const vals = rollScores();
    form.querySelectorAll("[data-attr]").forEach((el, i) => { el.value = vals[i]; });
    refresh();
  });
  form.querySelector("#genArray").addEventListener("click", () => {
    form.querySelectorAll("[data-attr]").forEach((el, i) => { el.value = arrayScores[i]; });
    refresh();
  });
  form.querySelector("#genPointBuy").addEventListener("click", () => {
    pointBuyMode = true;
    form.querySelectorAll("[data-attr]").forEach((el) => { el.min = 8; el.max = 15; });
    showToast("购点模式：属性值 8-15，总花费不超过 27 点");
    refresh();
  });

  function readForm() {
    const data = { ...editing };
    const NUM_KEYS = new Set(["hp", "ac", "xp", "current_hp", "temp_hp", "speed", "death_saves_success", "death_saves_fail"]);
    const LIST_KEYS = new Set(["equipment", "attacks"]);
    form.querySelectorAll("[data-f]").forEach((el) => {
      const key = el.dataset.f;
      if (key === "inspiration" || key === "alignment_law" || key === "alignment_moral" || key === "alignment_custom") return;
      if (NUM_KEYS.has(key)) data[key] = Number(el.value) || 0;
      else if (LIST_KEYS.has(key)) data[key] = el.value.split("\n").map((s) => s.trim()).filter(Boolean);
      else data[key] = el.value;
    });
    data.inspiration = Boolean(form.querySelector('[data-f="inspiration"]').checked);
    // 阵营：双下拉组合，或自定义文本
    const law = form.querySelector('[data-f="alignment_law"]').value;
    const moral = form.querySelector('[data-f="alignment_moral"]').value;
    const custom = form.querySelector('[data-f="alignment_custom"]').value.trim();
    if (custom) data.alignment = custom;
    else data.alignment = law === "中立" && moral === "中立" ? "绝对中立" : law + moral;
    // level 不手动编辑，但保留旧值提交——供后端做旧角色 xp 迁移（level>1 且 xp=0 → xp=阈值下限）
    data.level = editing.level ?? 1;
    form.querySelectorAll("[data-attr]").forEach((el) => {
      data[el.dataset.attr] = Number(el.value) || 8;
    });
    const saveCbs = form.querySelectorAll("[data-saveprof]");
    data.saving_profs = saveCbs.length
      ? [...form.querySelectorAll("[data-saveprof]:checked")].map((el) => el.dataset.saveprof)
      : (editing.saving_profs || []);
    const skillCbs = form.querySelectorAll("[data-skill]");
    data.proficient_skills = skillCbs.length
      ? [...form.querySelectorAll("[data-skill]:checked")].map((el) => el.dataset.skill)
      : (editing.proficient_skills || []);
    return data;
  }

  form.addEventListener("input", refresh);
  refresh();

  document.getElementById("saveBtn").addEventListener("click", async () => {
    const data = readForm();
    if (!data.char_name.trim()) {
      showToast("请填写角色名", true);
      return;
    }
    try {
      const isNew = !editing.id;
      const url = isNew ? "/api/me/characters" : `/api/me/characters/${editing.id}`;
      const method = isNew ? "POST" : "PUT";
      const saved = await apiFetch(url, { method, body: JSON.stringify(data) });
      showToast(isNew ? `角色创建成功 (#${saved.id})` : "已保存");
      await loadList();
    } catch (err) {
      showToast(err.message, true);
    }
  });
}

async function loadList() {
  trpgMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  try {
    const data = await apiFetch("/api/me/characters");
    chars = data.characters;
    currentId = data.current_id;
    renderList();
  } catch (err) {
    trpgMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

function levelFromXp(xp, thresholds) {
  let level = 1;
  thresholds.forEach((t, i) => { if (xp >= t) level = i + 1; });
  return level;
}

async function init() {
  if (!requireAuth()) return;
  try {
    rules = await apiFetch("/api/trpg/rules");
  } catch (err) {
    trpgMain.innerHTML = `<p class="loading-msg error">规则数据加载失败</p>`;
    return;
  }
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    loadList();
  });
}

init();
