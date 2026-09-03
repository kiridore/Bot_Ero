const scheduleMain = document.getElementById("scheduleMain");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");
const alarmDialog = document.getElementById("alarmDialog");
const dayDialog = document.getElementById("dayDialog");

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
  { value: 1, label: "一" }, { value: 2, label: "二" }, { value: 3, label: "三" },
  { value: 4, label: "四" }, { value: 5, label: "五" }, { value: 6, label: "六" },
  { value: 7, label: "日" },
];

var formState = { scheduleType: "daily", weekday: 1, minLeadMinutes: 5, scope: "private", editingId: null, seeds: null };
var filters = { hideRecurring: true, hideOthers: false, hideGroup: false }; // 日历过滤（仅日历，底部列表不受影响）
var calState = { year: 0, month: 0, data: { month: "", days: {} }, selectedDate: null };
var listItems = [];
// ponytail: 上面三个用 var 而非 const/let——浏览器 classic script 顶层行为一致，
// 且 node DOM stub 测试（eval 本文件）才能在 eval 外访问 formState 做断言

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
function pad2(n) { return String(n).padStart(2, "0"); }
function fmtKey(y, m, d) { return `${y}-${pad2(m)}-${pad2(d)}`; }
function todayKey() { const t = new Date(); return fmtKey(t.getFullYear(), t.getMonth() + 1, t.getDate()); }

// —— 认证 / 提示（与旧闹钟页一致）——
function openLoginDialog() {
  loginError.classList.add("hidden");
  if (!loginDialog.open) loginDialog.showModal();
}
function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    scheduleMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
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
  link.href = "/profile/schedule";
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
  let toast = document.getElementById("scheduleToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "scheduleToast";
    toast.className = "settings-toast";
    scheduleMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

// —— 表单（自 alarms.js 移植 + 范围开关 + 编辑模式）——
function defaultTimeValue() {
  const now = new Date();
  now.setMinutes(now.getMinutes() + 30);
  return `${pad2(now.getHours())}:${pad2(now.getMinutes())}`;
}
function defaultDateValue() {
  const now = new Date();
  return fmtKey(now.getFullYear(), now.getMonth() + 1, now.getDate());
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
function makeTimeInput(id, value) {
  const input = document.createElement("input");
  input.type = "time";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value || defaultTimeValue();
  return input;
}
function makeDateInput(id, value) {
  const input = document.createElement("input");
  input.type = "date";
  input.id = id;
  input.className = "alarm-input alarm-input-sm";
  input.value = value || defaultDateValue();
  return input;
}
function renderScheduleFields(container) {
  container.innerHTML = "";
  const grid = document.createElement("div");
  grid.className = "alarm-fields-grid";
  const type = formState.scheduleType;
  const seeds = formState.seeds || {};

  if (type === "once_date") {
    grid.append(fieldRow("日期", makeDateInput("alarmDate", seeds.date)), fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
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
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "daily" || type === "monthly" || type === "yearly") {
    if (type === "monthly") {
      const day = makeNumberInput("alarmDay", "15", 1, 31);
      day.value = String(seeds.day || 1);
      grid.append(fieldRow("每月第几天", day));
    }
    if (type === "yearly") {
      const month = makeNumberInput("alarmMonth", "6", 1, 12);
      month.value = String(seeds.month || 1);
      const day = makeNumberInput("alarmDay", "1", 1, 31);
      day.value = String(seeds.day || 1);
      grid.append(fieldRow("月", month), fieldRow("日", day));
    }
    grid.append(fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  } else if (type === "interval_days") {
    const interval = makeNumberInput("alarmInterval", "3", 1);
    interval.value = String(seeds.interval || 3);
    grid.append(fieldRow("间隔天数", interval), fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
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
    grid.append(wrap, fieldRow("时刻", makeTimeInput("alarmTime", seeds.time)));
  }
  container.appendChild(grid);
}
function setScheduleType(type) {
  formState.scheduleType = type;
  document.querySelectorAll(".alarm-type-btn[data-type]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.type === type);
  });
  const fields = document.getElementById("alarmFields");
  if (fields) renderScheduleFields(fields);
}
function setScope(scope) {
  formState.scope = scope;
  document.querySelectorAll(".alarm-type-btn[data-scope]").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.scope === scope);
  });
}
function updateFormModeUi() {
  const title = document.getElementById("alarmFormTitle");
  const submit = document.getElementById("alarmSubmitBtn");
  const abort = document.getElementById("alarmAbortBtn");
  if (!title) return;
  if (formState.editingId) {
    title.textContent = `编辑闹钟 #${formState.editingId}`;
    submit.textContent = "保存修改";
    abort.classList.remove("hidden");
  } else {
    title.textContent = "新建闹钟";
    submit.textContent = "创建闹钟";
    abort.classList.add("hidden");
  }
}
function renderCreateForm() {
  const section = document.createElement("section");
  section.className = "alarm-form settings-section";
  section.innerHTML = `
    <h2 id="alarmFormTitle">新建闹钟</h2>
    <p class="preview-hint">触发时刻须距当前至少 ${formState.minLeadMinutes} 分钟；「群内公开」的闹钟会在群里提醒所有人。</p>
    <label class="alarm-field alarm-field-block">
      <span class="alarm-field-label">提醒内容</span>
      <input type="text" id="alarmContent" class="alarm-input" maxlength="200" placeholder="例如：起床、交报告" />
    </label>
    <div class="alarm-field alarm-field-block">
      <span class="alarm-field-label">触发方式</span>
      <div class="alarm-type-grid" id="alarmTypeGrid"></div>
    </div>
    <div id="alarmFields" class="alarm-fields"></div>
    <div class="alarm-field alarm-field-block">
      <span class="alarm-field-label">提醒范围</span>
      <div class="alarm-type-grid" id="alarmScopeGrid"></div>
    </div>
    <div class="alarm-actions">
      <button type="button" class="btn-sm hidden" id="alarmAbortBtn">放弃编辑</button>
      <button type="button" class="btn-sm primary" id="alarmSubmitBtn">创建闹钟</button>
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
    btn.addEventListener("click", () => { formState.seeds = null; setScheduleType(item.id); });
    grid.appendChild(btn);
  }
  const scopeGrid = section.querySelector("#alarmScopeGrid");
  for (const opt of [{ id: "private", label: "仅我" }, { id: "group", label: "群内公开" }]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "alarm-type-btn";
    btn.dataset.scope = opt.id;
    btn.textContent = opt.label;
    if (opt.id === formState.scope) btn.classList.add("active");
    btn.addEventListener("click", () => setScope(opt.id));
    scopeGrid.appendChild(btn);
  }
  renderScheduleFields(section.querySelector("#alarmFields"));
  section.querySelector("#alarmSubmitBtn").addEventListener("click", submitAlarm);
  section.querySelector("#alarmAbortBtn").addEventListener("click", resetCreateForm);
  return section;
}
function readFormPayload() {
  const content = (document.getElementById("alarmContent")?.value || "").trim();
  const payload = { content, schedule_type: formState.scheduleType, scope: formState.scope };
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
    if (type === "yearly") payload.month = Number(document.getElementById("alarmMonth")?.value || 0);
  }
  return payload;
}
function resetCreateForm() {
  formState.editingId = null;
  formState.seeds = null;
  formState.scope = "private";
  const content = document.getElementById("alarmContent");
  if (content) content.value = "";
  setScheduleType("daily");
  setScope("private");
  updateFormModeUi();
}
function ruleFromItem(item) {
  // 编辑预填：服务端结构化 recur 字段 → 表单类型与种子值
  if (!item.is_recurring) return { type: "once_date", seeds: { date: item.date, time: item.time } };
  const k = item.recur_kind, a = item.recur_a || 0, b = item.recur_b || 0;
  if (k === 1) return a === 1
    ? { type: "daily", seeds: { time: item.time } }
    : { type: "interval_days", seeds: { interval: a, time: item.time } };
  if (k === 2) return { type: "weekly", seeds: { weekday: a, time: item.time } };
  if (k === 3) return { type: "yearly", seeds: { month: a, day: b, time: item.time } };
  if (k === 4) return { type: "monthly", seeds: { day: a, time: item.time } };
  return { type: "once_date", seeds: { date: item.date, time: item.time } };
}
function enterEdit(item) {
  formState.editingId = item.id;
  formState.seeds = null;
  const { type, seeds } = ruleFromItem(item);
  if (seeds.weekday) formState.weekday = seeds.weekday;
  const content = document.getElementById("alarmContent");
  if (content) content.value = item.content;
  setScheduleType(type);
  formState.seeds = seeds;
  renderScheduleFields(document.getElementById("alarmFields"));
  formState.seeds = null;
  setScope(item.scope === "group" ? "group" : "private");
  updateFormModeUi();
  document.getElementById("alarmFormTitle")?.scrollIntoView({ behavior: "smooth", block: "start" });
}
async function submitAlarm() {
  const btn = document.getElementById("alarmSubmitBtn");
  const payload = readFormPayload();
  if (!payload.content) { showToast("请填写提醒内容", true); return; }
  btn.disabled = true;
  const oldText = btn.textContent;
  btn.textContent = "提交中…";
  try {
    const url = formState.editingId ? `/api/me/alarms/${formState.editingId}` : "/api/me/alarms";
    const res = await fetch(url, {
      method: formState.editingId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "提交失败");
    resetCreateForm();
    showToast(data.message || "已保存");
    await loadAll();
  } catch (err) {
    showToast(err.message || "提交失败", true);
  } finally {
    btn.disabled = false;
    btn.textContent = oldText;
    updateFormModeUi();
  }
}

// —— 日历 ——
function shiftMonth(delta) {
  const d = new Date(calState.year, calState.month - 1 + delta, 1);
  calState.year = d.getFullYear();
  calState.month = d.getMonth() + 1;
  calState.selectedDate = null;
  loadCalendar();
}
function goToday() {
  const t = new Date();
  calState.year = t.getFullYear();
  calState.month = t.getMonth() + 1;
  calState.selectedDate = null;
  loadCalendar();
}
async function loadCalendar() {
  const key = `${calState.year}-${pad2(calState.month)}`;
  const res = await fetch(`/api/me/calendar?month=${key}`, { headers: GalleryAuth.headers() });
  if (res.status === 401) { GalleryAuth.clear(); requireAuth(); return; }
  if (!res.ok) { showToast("日历加载失败", true); return; }
  calState.data = await res.json();
  renderCalendar();
}
function renderCalendar() {
  let host = document.getElementById("calendarSection");
  if (!host) {
    host = document.createElement("section");
    host.className = "settings-section";
    host.id = "calendarSection";
  }
  host.innerHTML = "";
  const y = calState.year, m = calState.month;

  const toolbar = document.createElement("div");
  toolbar.className = "cal-toolbar";
  const prev = document.createElement("button");
  prev.type = "button"; prev.className = "cal-nav-btn"; prev.textContent = "‹";
  prev.addEventListener("click", () => shiftMonth(-1));
  const next = document.createElement("button");
  next.type = "button"; next.className = "cal-nav-btn"; next.textContent = "›";
  next.addEventListener("click", () => shiftMonth(1));
  const title = document.createElement("h2");
  title.textContent = `${y} 年 ${m} 月`;
  const todayBtn = document.createElement("button");
  todayBtn.type = "button"; todayBtn.className = "cal-nav-btn"; todayBtn.textContent = "今天";
  todayBtn.addEventListener("click", goToday);
  toolbar.append(prev, title, next, todayBtn);
  host.appendChild(toolbar);

  const filterRow = document.createElement("div");
  filterRow.className = "cal-filters";
  for (const opt of [
    { key: "hideRecurring", label: "隐藏循环闹钟" },
    { key: "hideOthers", label: "隐藏非我创建" },
    { key: "hideGroup", label: "隐藏群聊闹钟" },
  ]) {
    const lab = document.createElement("label");
    lab.className = "cal-filter";
    const box = document.createElement("input");
    box.type = "checkbox";
    box.checked = filters[opt.key];
    box.addEventListener("change", (e) => {
      filters[opt.key] = e.target.checked;
      renderCalendar();
    });
    const txt = document.createElement("span");
    txt.textContent = opt.label;
    lab.append(box, txt);
    filterRow.appendChild(lab);
  }
  host.appendChild(filterRow);

  const weekRow = document.createElement("div");
  weekRow.className = "cal-week-row";
  for (const wd of ["一", "二", "三", "四", "五", "六", "日"]) {
    const cell = document.createElement("span");
    cell.textContent = wd;
    weekRow.appendChild(cell);
  }
  host.appendChild(weekRow);

  const grid = document.createElement("div");
  grid.className = "cal-grid";
  const first = new Date(y, m - 1, 1);
  const offset = (first.getDay() + 6) % 7; // 周一起始
  const tk = todayKey();
  for (let i = 0; i < 42; i++) {
    const d = new Date(y, m - 1, 1 - offset + i);
    const key = fmtKey(d.getFullYear(), d.getMonth() + 1, d.getDate());
    const cell = document.createElement("div");
    cell.className = "cal-cell";
    cell.dataset.date = key;
    if (d.getMonth() !== m - 1) cell.classList.add("dim");
    if (key < tk) cell.classList.add("past");
    if (key === tk) cell.classList.add("today");
    if (key === calState.selectedDate) cell.classList.add("selected");

    const num = document.createElement("span");
    num.className = "cal-cell-num";
    num.textContent = String(d.getDate());
    cell.appendChild(num);

    const items = (calState.data.days[key] || []).filter(visibleCalItem);
    const shown = items.slice(0, 3);
    for (const item of shown) cell.appendChild(makeChip(item));
    if (items.length > 3) {
      const more = document.createElement("span");
      more.className = "cal-chip more";
      more.textContent = `+${items.length - 3} 更多`;
      more.addEventListener("click", (e) => { e.stopPropagation(); openDayDialog(key); });
      cell.appendChild(more);
    }
    cell.addEventListener("click", () => selectDay(key));
    grid.appendChild(cell);
  }
  host.appendChild(grid);
  return host;
}
function makeChip(item) {
  const chip = document.createElement("span");
  chip.className = "cal-chip " + (item.is_mine ? "mine" : "other");
  chip.textContent = `${item.time} ${item.content}`;
  chip.title = `${item.time} ${item.content}（${item.creator_name}）`;
  chip.addEventListener("click", (e) => { e.stopPropagation(); openAlarmDialog(item); });
  return chip;
}
function selectDay(key) {
  calState.selectedDate = key;
  renderCalendar();
  // 从日期格新建时清空残留：编辑态遗留的旧内容与范围不带入新闹钟
  formState.editingId = null;
  formState.seeds = null;
  const contentEl = document.getElementById("alarmContent");
  if (contentEl) contentEl.value = "";
  setScope("private");
  updateFormModeUi();
  setScheduleType("once_date");
  const dateEl = document.getElementById("alarmDate");
  if (dateEl) dateEl.value = key;
  document.getElementById("alarmFormTitle")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// —— 悬浮窗 ——
function scopeBadge(scope) {
  return scope === "group" ? "群内公开" : "仅我";
}
function openAlarmDialog(item) {
  alarmDialog._item = item;
  const rule = item.is_recurring
    ? `${item.recur_desc} · ${item.time}`
    : `${item.date} ${item.time}`;
  const body = document.getElementById("alarmDlgBody");
  body.innerHTML = `
    <p><strong>${escapeHtml(item.content)}</strong></p>
    <p>创建人：${escapeHtml(item.creator_name)}${item.is_mine ? "（我）" : ""}</p>
    <p>触发：${escapeHtml(rule)}</p>
    <p><span class="alarm-dlg-badge">${scopeBadge(item.scope)}</span>
       ${item.is_recurring ? `<span class="alarm-dlg-badge">${escapeHtml(item.recur_desc)}</span>` : ""}</p>
  `;
  document.getElementById("alarmDlgActions").classList.toggle("hidden", !item.is_mine);
  if (!alarmDialog.open) alarmDialog.showModal();
}
function visibleCalItem(item) {
  if (filters.hideRecurring && item.is_recurring) return false;
  if (filters.hideOthers && !item.is_mine) return false;
  if (filters.hideGroup && item.scope === "group") return false;
  return true;
}
function openDayDialog(key) {
  const items = (calState.data.days[key] || []).filter(visibleCalItem);
  const list = document.getElementById("dayDlgList");
  list.innerHTML = "";
  for (const item of items) {
    const row = document.createElement("button");
    row.type = "button";
    row.className = "day-row-btn";
    row.innerHTML = `<span class="cal-chip ${item.is_mine ? "mine" : "other"}" style="display:inline-block;">${escapeHtml(item.time)}</span>
      ${escapeHtml(item.content)} <span style="color:var(--ink-soft);font-size:0.78rem;">${escapeHtml(item.creator_name)}</span>`;
    row.addEventListener("click", () => { dayDialog.close(); openAlarmDialog(item); });
    list.appendChild(row);
  }
  document.getElementById("dayDlgTitle").textContent = `当日闹钟（${items.length}）`;
  if (!dayDialog.open) dayDialog.showModal();
}
document.getElementById("alarmDlgClose").addEventListener("click", () => alarmDialog.close());
document.getElementById("dayDlgClose").addEventListener("click", () => dayDialog.close());
document.getElementById("alarmDlgEdit").addEventListener("click", () => {
  const item = alarmDialog._item;
  alarmDialog.close();
  if (item) enterEdit(item);
});
document.getElementById("alarmDlgCancel").addEventListener("click", async () => {
  const item = alarmDialog._item;
  alarmDialog.close();
  if (!item) return;
  if (!confirm(`确定取消闹钟 #${item.id}？`)) return;
  try {
    const res = await fetch(`/api/me/alarms/${item.id}`, { method: "DELETE", headers: GalleryAuth.headers() });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "取消失败");
    showToast(data.message || "已取消");
    await loadAll();
  } catch (err) {
    showToast(err.message || "取消失败", true);
  }
});

// —— 列表（旧页列表迁移：行点击进详情）——
function renderAlarmList() {
  const section = document.createElement("section");
  section.className = "settings-section";
  section.innerHTML = "<h2>待触发闹钟</h2>";
  if (!listItems.length) {
    const empty = document.createElement("p");
    empty.className = "empty-hint center";
    empty.textContent = "你还没有待触发的闹钟";
    section.appendChild(empty);
    return section;
  }
  const list = document.createElement("div");
  list.className = "alarm-list";
  for (const item of listItems) {
    const card = document.createElement("article");
    card.className = "alarm-item";
    card.dataset.reveal = "";
    const metaParts = [`#${item.id}`, item.is_private ? "仅我" : "群内公开"];
    if (item.recur_desc) metaParts.push(item.recur_desc);
    metaParts.push(item.fire_at);
    card.innerHTML = `
      <div class="alarm-item-main">
        <p class="alarm-meta">${escapeHtml(metaParts.join(" · "))}</p>
        <p class="alarm-content">${escapeHtml(item.content)}</p>
      </div>
    `;
    card.addEventListener("click", () => openAlarmDialog({
      ...item,
      // 列表 API 的 scope 是展示字符串（“私聊”/“群 N”），换成枚举供悬浮窗/编辑用
      scope: item.is_private ? "private" : "group",
      date: String(item.fire_at).slice(0, 10),
      time: String(item.fire_at).slice(11, 16),
      is_mine: true,
    }));
    list.appendChild(card);
  }
  section.appendChild(list);
  return section;
}

// —— 组装与启动 ——
function renderAll() {
  scheduleMain.innerHTML = "";
  scheduleMain.appendChild(renderCalendar());
  scheduleMain.appendChild(renderCreateForm());
  scheduleMain.appendChild(renderAlarmList());
  updateFormModeUi();
}
async function loadAll() {
  const [calRes, listRes] = await Promise.all([
    fetch(`/api/me/calendar?month=${calState.year}-${pad2(calState.month)}`, { headers: GalleryAuth.headers() }),
    fetch("/api/me/alarms", { headers: GalleryAuth.headers() }),
  ]);
  if (calRes.status === 401 || listRes.status === 401) { GalleryAuth.clear(); requireAuth(); return; }
  calState.data = await calRes.json();
  const listData = await listRes.json();
  listItems = listData.items || [];
  formState.minLeadMinutes = listData.min_lead_minutes || 5;
  renderAll();
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
    loadAll();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

(function boot() {
  const t = new Date();
  calState.year = t.getFullYear();
  calState.month = t.getMonth() + 1;
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    if (requireAuth()) loadAll();
  });
})();
