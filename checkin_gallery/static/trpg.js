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
  return {
    scores, skillMods,
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
      str_score: 10, dex_score: 10, con_score: 10, int_score: 10, wis_score: 10, cha_score: 10,
      proficient_skills: [], hp: 0, ac: 0, equipment: [], notes: "",
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
  form.innerHTML = `
    <section class="settings-section">
      <div class="section-head"><h2>基本信息</h2></div>
      <table class="trpg-table">
        <tr><th>角色名</th><td><input type="text" data-f="char_name" maxlength="30"></td>
            <th>种族</th><td><input type="text" data-f="race" list="raceList"></td></tr>
        <tr><th>职业</th><td><input type="text" data-f="class_name" list="classList"></td>
            <th>等级</th><td><input type="number" data-f="level" min="1" max="20"></td></tr>
        <tr><th>背景</th><td colspan="3"><input type="text" data-f="background"></td></tr>
        <tr><th>备注</th><td colspan="3"><textarea data-f="notes" rows="3"></textarea></td></tr>
      </table>
      <datalist id="raceList"></datalist>
      <datalist id="classList"></datalist>
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
      <div class="section-head"><h2>战斗 <span class="muted">（未填时按规则自动计算）</span></h2></div>
      <table class="trpg-table">
        <tr><th>HP</th><td><input type="number" data-f="hp" min="0"></td>
            <th>AC</th><td><input type="number" data-f="ac" min="0"></td></tr>
        <tr><th>建议 HP</th><td colspan="3" id="hpHint"></td></tr>
      </table>
    </section>

    <div class="row-actions" style="justify-content:flex-end; padding:12px 0;">
      <button type="button" class="btn-sm" id="saveBtn">保存</button>
    </div>
  `;
  trpgMain.appendChild(form);

  const raceList = document.getElementById("raceList");
  for (const r of Object.keys(rules.races)) {
    const opt = document.createElement("option");
    opt.value = r;
    raceList.appendChild(opt);
  }
  const classList = document.getElementById("classList");
  for (const c of Object.keys(rules.classes)) {
    const opt = document.createElement("option");
    opt.value = c;
    classList.appendChild(opt);
  }

  form.querySelectorAll("[data-f]").forEach((el) => {
    el.value = editing[el.dataset.f] ?? "";
  });

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
      input.min = 1;
      input.max = 30;
      input.value = data[key] ?? 8;
      input.dataset.attr = key;
      tdScore.appendChild(input);
      tr.appendChild(tdScore);
      const tdMod = document.createElement("td");
      tdMod.className = "muted";
      const bonus = (rules.races[data.race] || {})[attr] || 0;
      tdMod.textContent = `加值 ${abilityMod(calc.scores[key]) >= 0 ? "+" : ""}${abilityMod(calc.scores[key])}${bonus ? `（种族+${bonus}）` : ""}`;
      tr.appendChild(tdMod);
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
  }

  function readForm() {
    const data = { ...editing };
    form.querySelectorAll("[data-f]").forEach((el) => {
      const key = el.dataset.f;
      if (key === "level" || key === "hp" || key === "ac") data[key] = Number(el.value) || 0;
      else data[key] = el.value;
    });
    form.querySelectorAll("[data-attr]").forEach((el) => {
      data[el.dataset.attr] = Number(el.value) || 8;
    });
    data.proficient_skills = [...form.querySelectorAll("[data-skill]:checked")].map((el) => el.dataset.skill);
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
