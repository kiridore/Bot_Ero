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
    occChoices = {};
    renderOccChoices();
    const occ = currentOccupation();
    if (occ) {
      const credit = document.getElementById("credit_rating");
      if (credit) credit.value = occ.credit_min;
    }
    rerenderDerived();
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
      setSkillHint(`无法识别「${raw}」：用官方技能名，或「科学:生物学」这类「类别:专攻」写法`);
      return;
    }
    const exists = [...document.querySelectorAll("[data-skill]")]
      .some((row) => canonSkill(row.dataset.name) === canonSkill(name));
    if (exists) {
      setSkillHint(`技能已存在：${name}`);
      return;
    }
    const tbody = document.getElementById("skillBody");
    tbody.insertAdjacentHTML("beforeend", skillRow(name, { base: options.skill_base[name] || 0 }));
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
    occupation_choices: occChoices,
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
