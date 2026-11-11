const main = document.getElementById("levelupMain");
const ATTRS = [
  ["str_score", "力量", "力量"],
  ["dex_score", "敏捷", "敏捷"],
  ["con_score", "体质", "体质"],
  ["int_score", "智力", "智力"],
  ["wis_score", "感知", "感知"],
  ["cha_score", "魅力", "魅力"],
];
const ASI_LEVELS = [4, 8, 12, 16, 19];

let charId = null;
let card = null;
let rules = null;
let hpMode = "average";
let asiMode = "one";
let asiOne = "str_score";
let asiTwo = [];

function escapeHtml(s) {
  return String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showToast(msg, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => { toast.hidden = true; }, 2800);
}

async function apiFetch(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...GalleryAuth.headers(), ...(options.headers || {}) },
  });
  if (res.status === 401) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
    throw new Error("未登录");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || "操作失败");
  return data;
}

function raceBonus(attr) {
  return (rules.races[card.race] || {})[attr] || 0;
}

function finalScore(key, attr) {
  return Number(card[key] || 0) + raceBonus(attr);
}

function nextLevel() {
  return (card.level || 1) + 1;
}

function needsAsi() {
  return ASI_LEVELS.includes(nextLevel());
}

function hpAverage() {
  const die = (rules.classes[card.class_name] || {}).hp_die || 8;
  const conMod = Math.floor((finalScore("con_score", "体质") - 10) / 2);
  return Math.max(die / 2 + 1 + conMod, 1);
}

function profBonus(level) {
  return 2 + Math.floor((level - 1) / 4);
}

function asiPayload() {
  if (!needsAsi()) return {};
  if (asiMode === "one") return { [asiOne.replace("_score", "")]: 2 };
  const out = {};
  for (const key of asiTwo) out[key.replace("_score", "")] = 1;
  return out;
}

function render() {
  const level = card.level || 1;
  const threshold = (rules.xp_thresholds || [])[level];
  const xp = Number(card.xp || 0);

  if (level >= 20) {
    main.innerHTML = `<section class="settings-section"><h2>${escapeHtml(card.char_name)} 已是 20 级</h2>
      <p class="muted">DND 5E 等级上限为 20，无法继续升级。</p>
      <p><a class="btn-sm" href="/trpg">返回角色列表</a></p></section>`;
    return;
  }

  if (!card.can_level_up) {
    main.innerHTML = `<section class="settings-section">
      <h2>${escapeHtml(card.char_name)} · Lv.${level}</h2>
      <p>经验值 ${xp} / ${threshold}，还差 <b>${Math.max(threshold - xp, 0)}</b> XP 才能升到 ${level + 1} 级。</p>
      <p class="muted">经验值由 DM 或玩家在角色编辑里填写。</p>
      <p><a class="btn-sm" href="/trpg">返回角色列表</a></p>
    </section>`;
    return;
  }

  const die = (rules.classes[card.class_name] || {}).hp_die || 8;
  const gain = hpAverage();
  const asiBlock = needsAsi() ? `
    <section class="settings-section">
      <h2>第 2 步 · 属性值提升</h2>
      <p class="muted">${level + 1} 级获得属性值提升：单项 +2，或两项各 +1；含种族加值不能超过 20。</p>
      <div class="row-actions">
        <label><input type="radio" name="asiMode" value="one" ${asiMode === "one" ? "checked" : ""} /> 单项 +2</label>
        <label><input type="radio" name="asiMode" value="two" ${asiMode === "two" ? "checked" : ""} /> 两项各 +1</label>
      </div>
      <table class="trpg-table">
        ${ATTRS.map(([key, attr]) => {
          const current = finalScore(key, attr);
          const control = asiMode === "one"
            ? `<input type="radio" name="asiOne" value="${key}" ${asiOne === key ? "checked" : ""} />`
            : `<input type="checkbox" name="asiTwo" value="${key}" ${asiTwo.includes(key) ? "checked" : ""} />`;
          const after = asiMode === "one"
            ? (asiOne === key ? current + 2 : current)
            : (asiTwo.includes(key) ? current + 1 : current);
          const warn = after > 20 ? " <b>超出 20</b>" : "";
          return `<tr><th>${attr}</th><td>${current}</td><td>${control}</td><td>${after}${warn}</td></tr>`;
        }).join("")}
      </table>
    </section>` : "";

  main.innerHTML = `
    <section class="settings-section">
      <h2>${escapeHtml(card.char_name)} 升级 · Lv.${level} → Lv.${level + 1}</h2>
      <p class="muted">职业 ${escapeHtml(card.class_name)}（生命骰 d${die}）· 种族 ${escapeHtml(card.race)} · 经验 ${xp} / ${threshold}</p>
      <table class="trpg-table">
        <tr><th>等级</th><td>${level} → ${level + 1}</td>
            <th>熟练加值</th><td>+${profBonus(level)} → +${profBonus(level + 1)}</td></tr>
        <tr><th>生命骰</th><td>${level}d${die} → ${level + 1}d${die}</td>
            <th>HP 上限</th><td>${card.hp} → 待选</td></tr>
      </table>
    </section>

    <section class="settings-section">
      <h2>第 1 步 · 生命值</h2>
      <div class="row-actions">
        <label><input type="radio" name="hpMode" value="average" ${hpMode === "average" ? "checked" : ""} />
          取均值 +${gain}（含体质加值）</label>
        <label><input type="radio" name="hpMode" value="roll" ${hpMode === "roll" ? "checked" : ""} />
          掷骰 1d${die}（含体质加值，结果提交后由服务器掷出）</label>
      </div>
    </section>

    ${asiBlock}

    <section class="settings-section">
      <h2>第 ${needsAsi() ? 3 : 2} 步 · 本次获得的特性 / 法术（可选）</h2>
      <textarea id="featuresText" rows="3" placeholder="例：获得动作如潮；法术：治疗伤口"></textarea>
      <p class="muted">会追加到角色卡的「特性与特质」末尾。</p>
    </section>

    <div class="row-actions" style="justify-content:flex-end; padding:12px 0;">
      <a class="btn-sm" href="/trpg">取消</a>
      <button type="button" class="btn-sm" id="submitLevelUp">确认升级</button>
    </div>
  `;

  main.querySelectorAll('input[name="hpMode"]').forEach((el) => {
    el.addEventListener("change", () => { hpMode = el.value; });
  });
  main.querySelectorAll('input[name="asiMode"]').forEach((el) => {
    el.addEventListener("change", () => { asiMode = el.value; render(); });
  });
  main.querySelectorAll('input[name="asiOne"]').forEach((el) => {
    el.addEventListener("change", () => { asiOne = el.value; render(); });
  });
  main.querySelectorAll('input[name="asiTwo"]').forEach((el) => {
    el.addEventListener("change", () => {
      asiTwo = [...main.querySelectorAll('input[name="asiTwo"]:checked')].map((x) => x.value);
      render();
    });
  });
  document.getElementById("submitLevelUp").addEventListener("click", submit);
}

async function submit() {
  const btn = document.getElementById("submitLevelUp");
  btn.disabled = true;
  try {
    const body = {
      hp_mode: hpMode,
      asi: asiPayload(),
      features: document.getElementById("featuresText").value,
    };
    const result = await apiFetch(`/api/me/characters/${charId}/levelup`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    renderSuccess(result, body);
  } catch (err) {
    showToast(err.message, true);
    btn.disabled = false;
  }
}

function renderSuccess(result, body) {
  const level = result.level;
  const asiText = Object.entries(result.asi || {})
    .map(([key, amount]) => `${ATTRS.find(([k]) => k === `${key}_score`)?.[1] || key} +${amount}`)
    .join("、");
  main.innerHTML = `
    <section class="settings-section">
      <h2>${escapeHtml(result.char_name)} 升到 Lv.${level}</h2>
      <table class="trpg-table">
        <tr><th>HP 上限</th><td>${result.hp - result.hp_gain} → ${result.hp}</td>
            <th>本次增长</th><td>+${result.hp_gain}（${body.hp_mode === "roll" ? "掷骰" : "取均值"}）</td></tr>
        <tr><th>熟练加值</th><td>+${result.prof_bonus}</td>
            <th>生命骰</th><td>${result.hit_dice}</td></tr>
        ${asiText ? `<tr><th>属性提升</th><td colspan="3">${asiText}</td></tr>` : ""}
      </table>
      <p><a class="btn-sm" href="/trpg">返回角色列表</a>
         <a class="btn-sm" href="/trpg/char/${result.user_id}/${result.id}">查看角色卡</a>
         ${result.can_level_up ? `<a class="btn-sm" href="/trpg/levelup/${result.id}">继续升级</a>` : ""}</p>
    </section>`;
}

async function boot() {
  if (!GalleryAuth.isLoggedIn()) {
    window.location.href = `/login?next=${encodeURIComponent(location.pathname)}`;
    return;
  }
  charId = location.pathname.split("/").pop();
  try {
    [rules, card] = await Promise.all([
      apiFetch("/api/trpg/rules"),
      apiFetch(`/api/me/characters/${charId}`),
    ]);
    if ((card.rules || "dnd5e") !== "dnd5e") {
      main.innerHTML = "<section class='settings-section'><h2>升级向导只适用于 DND 5E 角色卡</h2><p><a class='btn-sm' href='/trpg'>返回</a></p></section>";
      return;
    }
    render();
  } catch (err) {
    main.innerHTML = `<p class="empty-hint center">${escapeHtml(err.message)}</p>`;
  }
}

boot();
