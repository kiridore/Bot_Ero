const charViewMain = document.getElementById("charViewMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  if (!loginDialog.open) loginDialog.showModal();
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    charViewMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
    openLoginDialog();
    return false;
  }
  return true;
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
    openLoginDialog();
    throw new Error("未登录");
  }
  if (res.status === 403) {
    throw new Error("对方未公开角色卡");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "操作失败");
  return data;
}

function abilityMod(score) {
  return Math.floor((Number(score || 8) - 10) / 2);
}

function attrKey(name) {
  return { "力量": "str_score", "敏捷": "dex_score", "体质": "con_score",
           "智力": "int_score", "感知": "wis_score", "魅力": "cha_score" }[name] || "";
}

function fmtMod(v) {
  return `${v >= 0 ? "+" : ""}${v}`;
}

// COC 7th 角色卡：与建卡页同口径展示（属性 / 派生 / 技能 / 武器 / 资产 / 背景）
let cocSkillNotes = null;   // 技能说明缓存（/api/trpg/coc/skill-notes）

async function loadCocSkillNotes() {
  if (cocSkillNotes) return cocSkillNotes;
  try {
    const res = await fetch("/api/trpg/coc/skill-notes", { headers: GalleryAuth.headers() });
    const data = await res.json().catch(() => ({}));
    cocSkillNotes = (res.ok && data.notes) || {};
  } catch (err) {
    cocSkillNotes = {};
  }
  return cocSkillNotes;
}

function cocSkillNoteTitle(name) {
  const notes = cocSkillNotes || {};
  const key = String(name || "");
  const note = notes[key] || (key.includes(":") ? notes[key.split(":")[0]] : null);
  if (!note) return "";
  const meta = [note.base ? `基础值 ${note.base}` : "", note.special && note.special !== "——" ? note.special : ""]
    .filter(Boolean).join("｜");
  return [note.note || "", meta].filter(Boolean).join("\n\n");
}

const COC_ATTR_ROWS = [
  ["力量", "str_score"], ["敏捷", "dex_score"], ["意志", "pow_score"],
  ["体质", "con_score"], ["外貌", "app_score"], ["教育", "edu_score"],
  ["体型", "siz_score"], ["智力", "int_score"], ["幸运", "luck"],
];

const COC_BACKGROUND = [
  ["description", "个人描述"], ["ideology", "思想与信念"], ["significant_people", "重要之人"],
  ["meaningful_places", "意义非凡之地"], ["treasured_possessions", "宝贵之物"], ["traits", "特质"],
  ["scars", "伤口和疤痕"], ["phobias", "恐惧症和狂躁症"],
];

function damageWithDb(damage, db) {
  const text = String(damage || "").trim();
  if (!text || !text.includes("DB")) return text;
  return `${text}（DB=${db || 0}）`;
}

function cocSection(title, buildBody) {
  const sec = document.createElement("section");
  sec.className = "settings-section";
  sec.innerHTML = `<div class="section-head"><h2>${title}</h2></div>`;
  buildBody(sec);
  charViewMain.appendChild(sec);
  return sec;
}

function renderCocView(char) {
  charViewMain.innerHTML = "";
  const scores = char.scores || {};

  const head = document.createElement("div");
  head.className = "section-head";
  const title = `【${char.char_name || "无名调查员"}】${char.occupation || "无职业"}`;
  head.innerHTML = `<h2>${escapeHtml(title)}</h2>
    <span class="muted">${escapeHtml(char.display_name || "")} 的调查员卡</span>`;
  charViewMain.appendChild(head);

  const meta = document.createElement("p");
  meta.className = "muted";
  meta.textContent = [
    char.age ? `${char.age}岁` : "", char.sex, char.era, char.residence ? `住地 ${char.residence}` : "",
  ].filter(Boolean).join(" · ");
  if (meta.textContent) charViewMain.appendChild(meta);

  const vitals = document.createElement("p");
  vitals.className = "muted";
  vitals.textContent = [
    `HP ${char.current_hp}/${char.hp}`, `MP ${char.current_mp}/${char.mp}`,
    `SAN ${char.current_san}/${char.max_san}`,
    `MOV ${char.mov}`, `伤害加值 ${char.db}`, `体格 ${char.build}`, `闪避 ${char.dodge}`,
    `信用评级 ${char.credit_rating}`,
  ].join(" · ");
  charViewMain.appendChild(vitals);

  cocSection("属性", (sec) => {
    const grid = document.createElement("div");
    grid.className = "coc-grid coc-attrs";
    for (const [label, key] of COC_ATTR_ROWS) {
      const value = key === "luck" ? (char.luck || 0) : (scores[label] ?? 0);
      const cell = document.createElement("p");
      cell.className = "coc-note-cell";
      cell.innerHTML = `<strong>${label}</strong> ${value}`;
      grid.appendChild(cell);
    }
    sec.appendChild(grid);
  });

  const skills = Object.entries(char.skills || {});
  if (skills.length) {
    cocSection("技能", (sec) => {
      const table = document.createElement("table");
      table.className = "trpg-table";
      table.innerHTML = "<tr><th>技能</th><th>成长</th><th>职业</th><th>兴趣</th><th>成功率</th></tr>";
      for (const [name, entry] of skills) {
        const tr = document.createElement("tr");
        const check = entry.check ? " ✓" : "";
        const note = cocSkillNoteTitle(name);
        const icon = note
          ? `<span class="coc-info" role="img" tabindex="0" aria-label="技能说明" title="${escapeHtml(note)}">i</span>`
          : "";
        tr.innerHTML = `<th>${escapeHtml(name)}${check}${icon}</th>
          <td>${entry.growth || 0}</td><td>${entry.occupation || 0}</td>
          <td>${entry.interest || 0}</td><td>${entry.total || 0}%</td>`;
        table.appendChild(tr);
      }
      sec.appendChild(table);
    });
  }

  const weapons = char.weapons || [];
  if (weapons.length) {
    cocSection("武器", (sec) => {
      const table = document.createElement("table");
      table.className = "trpg-table";
      table.innerHTML = "<tr><th>武器</th><th>类型</th><th>使用技能</th><th>成功率</th>" +
        "<th>伤害</th><th>射程</th><th>次数</th><th>装弹量</th><th>故障值</th><th>贯穿</th></tr>";
      for (const weapon of weapons) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<th>${escapeHtml(weapon.name || "")}</th>
          <td>${escapeHtml(weapon.type || "")}</td>
          <td>${escapeHtml(weapon.skill || "")}</td>
          <td>${weapon.success || 0}</td>
          <td>${escapeHtml(damageWithDb(weapon.damage, char.db))}</td>
          <td>${escapeHtml(weapon.range || "")}</td>
          <td>${escapeHtml(weapon.attacks || "")}</td>
          <td>${escapeHtml(weapon.ammo || "")}</td>
          <td>${escapeHtml(String(weapon.malfunction || ""))}</td>
          <td>${escapeHtml(weapon.pierce || "")}</td>`;
        table.appendChild(tr);
      }
      sec.appendChild(table);
    });
  }

  const assets = char.assets || {};
  const assetLines = [
    ["币种", assets.currency], ["生活水平", assets.living_standard], ["现金", assets.cash],
    ["消费水平", assets.spending_level], ["其他资产", assets.other_assets],
    ["交通工具", assets.vehicle], ["住所", assets.residence], ["奢侈品", assets.luxury],
    ["股票/证券", assets.securities], ["其他", assets.other], ["剩余资产值", assets.remaining],
    ["克苏鲁神话", char.cthulhu_mythos],
  ].filter(([, v]) => v !== undefined && v !== null && String(v).trim() !== "");
  if (assetLines.length) {
    cocSection("资产", (sec) => {
      const p = document.createElement("p");
      p.className = "muted";
      p.textContent = assetLines.map(([k, v]) => `${k}：${v}`).join(" · ");
      sec.appendChild(p);
      const total = window.BoteroAssets ? window.BoteroAssets.total(assets) : 0;
      if (total) {
        const sum = document.createElement("p");
        sum.className = "muted";
        sum.textContent = `资产总和：${total}`;
        sec.appendChild(sum);
      }
    });
  }

  const bg = char.social_background || {};
  const bgLines = COC_BACKGROUND.filter(([key]) => String(bg[key] || "").trim());
  if (bgLines.length) {
    cocSection("背景", (sec) => {
      const box = document.createElement("div");
      box.style.whiteSpace = "pre-wrap";
      box.textContent = bgLines.map(([key, label]) => `【${label}】\n${bg[key]}`).join("\n\n");
      sec.appendChild(box);
    });
  }

  if (char.notes) {
    cocSection("调查员笔记", (sec) => {
      const p = document.createElement("p");
      p.style.whiteSpace = "pre-wrap";
      p.textContent = char.notes;
      sec.appendChild(p);
    });
  }
}

async function renderView(char, rules) {
  if ((char.rules || "dnd5e") === "coc7th") {
    await loadCocSkillNotes();
    renderCocView(char);
    return;
  }
  charViewMain.innerHTML = "";

  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = `<h2>【${escapeHtml(char.char_name)}】</h2>
    <span class="muted">${escapeHtml(char.display_name)} 的角色卡</span>`;
  charViewMain.appendChild(head);

  const meta = document.createElement("p");
  meta.className = "muted";
  meta.textContent = `Lv.${char.level} ${char.race} ${char.class_name} · HP ${char.hp} · AC ${char.ac}`;
  charViewMain.appendChild(meta);

  const meta2 = document.createElement("p");
  meta2.className = "muted";
  meta2.textContent = `熟练加值 +${char.prof_bonus} · 先攻 ${fmtMod(char.initiative)} · 被动感知 ${char.passive_perception} · 生命骰 ${char.hit_dice}`;
  charViewMain.appendChild(meta2);

  const attrSec = document.createElement("section");
  attrSec.className = "settings-section";
  attrSec.dataset.reveal = "";
  attrSec.innerHTML = `<div class="section-head"><h2>属性</h2></div>`;
  const attrTable = document.createElement("table");
  attrTable.className = "trpg-table";
  for (const attr of rules.attributes) {
    const key = attrKey(attr);
    const score = char.scores[key] ?? 8;
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${attr}</th><td>${score}</td><td class="muted">${fmtMod(abilityMod(score))}</td>`;
    attrTable.appendChild(tr);
  }
  attrSec.appendChild(attrTable);
  charViewMain.appendChild(attrSec);

  const skillSec = document.createElement("section");
  skillSec.className = "settings-section";
  skillSec.dataset.reveal = "";
  skillSec.innerHTML = `<div class="section-head"><h2>技能</h2></div>`;
  const skillTable = document.createElement("table");
  skillTable.className = "trpg-table";
  for (const [skill, attr] of Object.entries(rules.skills)) {
    const mod = char.skill_mods[skill];
    const proficient = (char.proficient_skills || []).includes(skill);
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${skill}</th><td class="muted">${attr}</td>
      <td>${proficient ? "熟练" : ""}</td><td>${mod !== undefined ? fmtMod(mod) : ""}</td>`;
    skillTable.appendChild(tr);
  }
  skillSec.appendChild(skillTable);
  charViewMain.appendChild(skillSec);

  const saveSec = document.createElement("section");
  saveSec.className = "settings-section";
  saveSec.dataset.reveal = "";
  saveSec.innerHTML = `<div class="section-head"><h2>豁免</h2></div>`;
  const saveTable = document.createElement("table");
  saveTable.className = "trpg-table";
  for (const attr of rules.attributes) {
    const mod = char.save_mods[attr];
    const prof = (char.saving_profs || []).includes(attr);
    const tr = document.createElement("tr");
    tr.innerHTML = `<th>${attr}</th><td>${prof ? "熟练" : ""}</td><td>${mod !== undefined ? fmtMod(mod) : ""}</td>`;
    saveTable.appendChild(tr);
  }
  saveSec.appendChild(saveTable);
  charViewMain.appendChild(saveSec);

  const combatSec = document.createElement("section");
  combatSec.className = "settings-section";
  combatSec.innerHTML = `<div class="section-head"><h2>战斗</h2></div>`;
  const combatTable = document.createElement("table");
  combatTable.className = "trpg-table";
  combatTable.innerHTML = `
    <tr><th>HP</th><td>${char.hp}</td><th>当前 HP</th><td>${char.current_hp || 0}</td>
        <th>临时 HP</th><td>${char.temp_hp || 0}</td></tr>
    <tr><th>AC</th><td>${char.ac}</td><th>速度</th><td>${char.speed || 30}</td>
        <th>激励</th><td>${char.inspiration ? "✓" : "—"}</td></tr>
    <tr><th>死亡豁免</th><td colspan="5">成功 ${char.death_saves_success || 0} / 失败 ${char.death_saves_fail || 0}</td></tr>`;
  combatSec.appendChild(combatTable);
  charViewMain.appendChild(combatSec);

  if ((char.equipment || []).length || char.other_proficiencies || (char.attacks || []).length || char.features) {
    const resSec = document.createElement("section");
    resSec.className = "settings-section";
    resSec.innerHTML = `<div class="section-head"><h2>资源</h2></div>`;
    const resList = document.createElement("div");
    resList.style.whiteSpace = "pre-wrap";
    const parts = [];
    if ((char.equipment || []).length) parts.push("【装备与钱币】\n" + char.equipment.join("\n"));
    if (char.other_proficiencies) parts.push("【其他熟练项和语言】\n" + char.other_proficiencies);
    if ((char.attacks || []).length) parts.push("【攻击与法术】\n" + char.attacks.join("\n"));
    if (char.features) parts.push("【特性与特质】\n" + char.features);
    resList.textContent = parts.join("\n\n");
    resSec.appendChild(resList);
    charViewMain.appendChild(resSec);
  }

  const bgFields = [
    ["个人特点", char.personality_traits], ["理想", char.ideals],
    ["牵绊", char.bonds], ["缺点", char.flaws],
  ].filter(([, v]) => v);
  if (bgFields.length) {
    const bgSec = document.createElement("section");
    bgSec.className = "settings-section";
    bgSec.innerHTML = `<div class="section-head"><h2>背景</h2></div>`;
    const bgDiv = document.createElement("div");
    bgDiv.style.whiteSpace = "pre-wrap";
    bgDiv.textContent = bgFields.map(([k, v]) => `【${k}】\n${v}`).join("\n\n");
    bgSec.appendChild(bgDiv);
    charViewMain.appendChild(bgSec);
  }

  if (char.notes) {
    const noteSec = document.createElement("section");
    noteSec.className = "settings-section";
    noteSec.innerHTML = `<div class="section-head"><h2>备注</h2></div>
      <p style="white-space:pre-wrap">${escapeHtml(char.notes)}</p>`;
    charViewMain.appendChild(noteSec);
  }
}

async function init() {
  if (!requireAuth()) return;
  const segs = window.location.pathname.split("/").filter(Boolean);
  const user_id = segs[segs.length - 2];
  const char_id = segs[segs.length - 1];
  const party = new URLSearchParams(window.location.search).get("party");
  const cardUrl = party
    ? `/api/trpg/party/${encodeURIComponent(party)}/card/${encodeURIComponent(user_id)}`
    : `/api/characters/${user_id}/${char_id}`;
  try {
    const [char, rules] = await Promise.all([
      apiFetch(cardUrl),
      apiFetch("/api/trpg/rules"),
    ]);
    await renderView(char, rules);
  } catch (err) {
    charViewMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

loginCancel.addEventListener("click", () => loginDialog.close());
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  try {
    await GalleryAuth.login(loginKey.value);
    loginDialog.close();
    loginKey.value = "";
    init();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

init();
GalleryAuth.renderAuth(document.getElementById("authArea"));
