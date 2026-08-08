const alarmsMain = document.getElementById("alarmsMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

const SCHEDULE_TYPES = [
  { id: "once_date", label: "指定日期" },
  { id: "once_relative", label: "相对时间" },
  { id: "once_today", label: "今天" },
  { id: "daily", label: "每天" },
  { id: "interval_days", label: "每 N 天" },
  { id: "weekly", label: "每周" },
  { id: "monthly", label: "每月" },
  { id: "yearly", label: "每年" },
];

const WEEKDAYS = [
  { value: 1, label: "一" },
  { value: 2, label: "二" },
  { value: 3, label: "三" },
  { value: 4, label: "四" },
  { value: 5, label: "五" },
  { value: 6, label: "六" },
  { value: 7, label: "日" },
];

let formState = {
  scheduleType: "daily",
  weekday: 1,
  minLeadMinutes: 5,
};

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  if (!loginDialog.open) loginDialog.showModal();
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    alarmsMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
    openLoginDialog();
    return false;
  }
  return true;
}

function renderAuthChip() {
  const area = document.getElementById("authArea");
  if (!area) return;
  area.innerHTML = "";
  const session = GalleryAuth.load();
  if (!session || !session.token) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-login";
    btn.textContent = "登录";
    btn.addEventListener("click", openLoginDialog);
    area.appendChild(btn);
    return;
  }
  const link = document.createElement("a");
  link.className = "user-chip";
  link.href = "/alarms";
  const img = document.createElement("img");
  img.src = session.avatar_url || "";
  img.alt = session.display_name;
  img.onerror = () => { img.style.display = "none"; };
  const wrap = document.createElement("span");
  wrap.innerHTML = `<strong>${escapeHtml(session.display_name)}</strong><br><span class="uid">${session.user_id}</span>`;
  link.append(img, wrap);
  area.appendChild(link);
}

function showToast(msg, isError = false) {
  let toast = document.getElementById("alarmsToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "alarmsToast";
    toast.className = "settings-toast";
    alarmsMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function defaultTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 30);
  return `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`;
}

function defaultDateValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

function fieldRow(label, inputEl) {
  const row = document.createElement("label");
  row.className = "alarm-field";
  const span = document.createElement("span");
  span.className = "alarm-field-label";
  span.textContent = label;
  row.append(span, inputEl);
  return row;
}

function makeNumberInput(id, placeholder, min = 0, max = null) {
  const input = document.createElement("input");
  input.type = "number";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.placeholder = placeholder;
  input.min = String(min);
  if (max != null) input.max = String(max);
  input.value = "0";
  return input;
}

function makeTimeInput(id, value = defaultTimeValue()) {
  const input = document.createElement("input");
  input.type = "time";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value;
  return input;
}

function makeDateInput(id, value = defaultDateValue()) {
  const input = document.createElement("input");
  input.type = "date";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value;
  return input;
}

function renderScheduleFields(container) {
  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "alarm-fields-grid";
  const type = formState.scheduleType;

  if (type === "once_date") {
    grid.append(
      fieldRow("日期", makeDateInput("alarmDate")),
      fieldRow("时刻", makeTimeInput("alarmTime"))
    );
  } else if (type === "once_relative") {
    grid.append(
      fieldRow("年", makeNumberInput("alarmYears", "0")),
      fieldRow("月", makeNumberInput("alarmMonths", "0")),
      fieldRow("日", makeNumberInput("alarmDays", "0")),
      fieldRow("小时", makeNumberInput("alarmHours", "0")),
      fieldRow("分钟", makeNumberInput("alarmMinutes", "30"))
    );
    const hint = document.createElement("p");
    hint.className = "preview-hint alarm-field-hint";
    hint.textContent = "至少填写一项；合计须距当前至少 5 分钟。";
    container.append(grid, hint);
    return;
  } else if (type === "once_today") {
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime")));
  } else if (type === "daily" || type === "monthly" || type === "yearly") {
    if (type === "monthly") {
      const day = makeNumberInput("alarmDay", "15", 1, 31);
      day.value = "1";
      grid.append(fieldRow("每月第几天", day));
    }
    if (type === "yearly") {
      const month = makeNumberInput("alarmMonth", "6", 1, 12);
      month.value = "1";
      const day = makeNumberInput("alarmDay", "1", 1, 31);
      day.value = "1";
      grid.append(fieldRow("月", month), fieldRow("日", day));
    }
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime")));
  } else if (type === "interval_days") {
    const interval = makeNumberInput("alarmInterval", "3", 1);
    interval.value = "3";
    grid.append(
      fieldRow("间隔天数", interval),
      fieldRow("时刻", makeTimeInput("alarmTime"))
    );
  } else if (type === "weekly") {
    const group = document.createElement("div");
    group.className = "weekday-group";
    group.id = "alarmWeekdayGroup";
    for (const wd of WEEKDAYS) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "weekday-btn";
      btn.textContent = wd.label;
      btn.dataset.value = String(wd.value);
      if (wd.value === formState.weekday) btn.classList.add("active");
      btn.addEventListener("click", () => {
        formState.weekday = wd.value;
        group.querySelectorAll(".weekday-btn").forEach((el) => {
          el.classList.toggle("active", Number(el.dataset.value) === wd.value);
        });
      });
      group.appendChild(btn);
    }
    const wrap = document.createElement("div");
    wrap.className = "alarm-field alarm-field-block";
    const label = document.createElement("span");
    label.className = "alarm-field-label";
    label.textContent = "星期";
    wrap.append(label, group);
    grid.append(wrap, fieldRow("时刻", makeTimeInput("alarmTime")));
  }

  container.appendChild(grid);
}

function setScheduleType(type) {
  formState.scheduleType = type;
  document.querySelectorAll(".alarm-type-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.type === type);
  });
  const fields = document.getElementById("alarmFields");
  if (fields) renderScheduleFields(fields);
}

function renderCreateForm(minLeadMinutes) {
  formState.minLeadMinutes = minLeadMinutes || 5;
  const section = document.createElement("section");
  section.className = "alarm-form settings-section";
  section.innerHTML = `
    <h2>新建闹钟</h2>
    <p class="preview-hint">网页创建的闹钟为私聊提醒，触发时刻须距当前至少 ${formState.minLeadMinutes} 分钟。</p>
    <label class="alarm-field alarm-field-block">
      <span class="alarm-field-label">提醒内容</span>
      <input type="text" id="alarmContent" class="alarm-input" maxlength="200" placeholder="例如：起床、交报告" />
    </label>
    <div class="alarm-field alarm-field-block">
      <span class="alarm-field-label">触发方式</span>
      <div class="alarm-type-grid" id="alarmTypeGrid"></div>
    </div>
    <div id="alarmFields" class="alarm-fields"></div>
    <div class="alarm-actions">
      <button type="button" class="btn-sm primary" id="alarmCreateBtn">创建闹钟</button>
    </div>
  `;

  const grid = section.querySelector("#alarmTypeGrid");
  for (const item of SCHEDULE_TYPES) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "alarm-type-btn";
    btn.dataset.type = item.id;
    btn.textContent = item.label;
    if (item.id === formState.scheduleType) btn.classList.add("active");
    btn.addEventListener("click", () => setScheduleType(item.id));
    grid.appendChild(btn);
  }

  renderScheduleFields(section.querySelector("#alarmFields"));
  section.querySelector("#alarmCreateBtn").addEventListener("click", createAlarm);
  return section;
}

function readFormPayload() {
  const content = (document.getElementById("alarmContent")?.value || "").trim();
  const payload = {
    content,
    schedule_type: formState.scheduleType,
  };

  const timeEl = document.getElementById("alarmTime");
  if (timeEl) payload.time = timeEl.value;

  const type = formState.scheduleType;
  if (type === "once_date") {
    payload.date = document.getElementById("alarmDate")?.value || "";
  } else if (type === "once_relative") {
    payload.years = Number(document.getElementById("alarmYears")?.value || 0);
    payload.months = Number(document.getElementById("alarmMonths")?.value || 0);
    payload.days = Number(document.getElementById("alarmDays")?.value || 0);
    payload.hours = Number(document.getElementById("alarmHours")?.value || 0);
    payload.minutes = Number(document.getElementById("alarmMinutes")?.value || 0);
  } else if (type === "interval_days") {
    payload.interval_days = Number(document.getElementById("alarmInterval")?.value || 0);
  } else if (type === "weekly") {
    payload.weekday = formState.weekday;
  } else if (type === "monthly" || type === "yearly") {
    payload.day = Number(document.getElementById("alarmDay")?.value || 0);
    if (type === "yearly") {
      payload.month = Number(document.getElementById("alarmMonth")?.value || 0);
    }
  }

  return payload;
}

function resetCreateForm() {
  const content = document.getElementById("alarmContent");
  if (content) content.value = "";
  setScheduleType("daily");
}

function renderAlarmList(items) {
  const section = document.createElement("section");
  section.className = "settings-section";
  section.innerHTML = "<h2>待触发闹钟</h2>";

  if (!items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-hint center";
    empty.textContent = "你还没有待触发的闹钟";
    section.appendChild(empty);
    return section;
  }

  const list = document.createElement("div");
  list.className = "alarm-list";

  for (const item of items) {
    const card = document.createElement("article");
    card.className = "alarm-item";

    const metaParts = [`#${item.id}`, item.scope];
    if (item.recur_desc) metaParts.push(item.recur_desc);
    metaParts.push(item.fire_at);

    card.innerHTML = `
      <div class="alarm-item-main">
        <p class="alarm-meta">${escapeHtml(metaParts.join(" · "))}</p>
        <p class="alarm-content">${escapeHtml(item.content)}</p>
      </div>
    `;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-sm";
    btn.textContent = "取消";
    btn.addEventListener("click", () => cancelAlarm(item.id, btn));
    card.appendChild(btn);
    list.appendChild(card);
  }

  section.appendChild(list);
  return section;
}

function renderAlarms(data) {
  alarmsMain.innerHTML = "";
  alarmsMain.appendChild(renderCreateForm(data.min_lead_minutes));
  alarmsMain.appendChild(renderAlarmList(data.items));
}

async function loadAlarms() {
  alarmsMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  const res = await fetch("/api/me/alarms", { headers: GalleryAuth.headers() });
  if (res.status === 401) {
    GalleryAuth.clear();
    requireAuth();
    return;
  }
  if (!res.ok) {
    alarmsMain.innerHTML = "<p class='loading-msg error'>加载失败</p>";
    return;
  }
  renderAlarms(await res.json());
}

async function createAlarm() {
  const btn = document.getElementById("alarmCreateBtn");
  const payload = readFormPayload();
  if (!payload.content) {
    showToast("请填写提醒内容", true);
    return;
  }

  btn.disabled = true;
  btn.textContent = "创建中…";
  try {
    const res = await fetch("/api/me/alarms", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "创建失败");
    resetCreateForm();
    showToast(data.message || "创建成功");
    await loadAlarms();
  } catch (err) {
    showToast(err.message || "创建失败", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "创建闹钟";
  }
}

async function cancelAlarm(alarmId, btn) {
  if (!confirm(`确定取消闹钟 #${alarmId}？`)) return;
  btn.disabled = true;
  btn.textContent = "取消中…";
  try {
    const res = await fetch(`/api/me/alarms/${alarmId}`, {
      method: "DELETE",
      headers: GalleryAuth.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "取消失败");
    showToast(data.message || "已取消");
    await loadAlarms();
  } catch (err) {
    showToast(err.message || "取消失败", true);
    btn.disabled = false;
    btn.textContent = "取消";
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
    renderAuthChip();
    loadAlarms();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(() => {
  renderAuthChip();
  if (requireAuth()) loadAlarms();
});
