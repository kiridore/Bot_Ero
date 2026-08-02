const charViewMain = document.getElementById("charViewMain");

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

function renderView(char, rules) {
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

  const attrSec = document.createElement("section");
  attrSec.className = "settings-section";
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
  try {
    const [char, rules] = await Promise.all([
      apiFetch(`/api/characters/${user_id}/${char_id}`),
      apiFetch("/api/trpg/rules"),
    ]);
    renderView(char, rules);
  } catch (err) {
    charViewMain.innerHTML = `<p class="loading-msg error">${escapeHtml(err.message)}</p>`;
  }
}

init();
