const ENTRIES_URL = "entries.json";
const POLL_MS = 60000;
const TIMEOUT_MS = 3000;

const entriesEl = document.getElementById("entries");

function statusClass(entry, ok) {
  if (ok === true) return "up";
  if (ok === false) return "down";
  return "unknown";
}

function cardHTML(entry) {
  const badge = entry.badge ? `<span class="badge">${escapeHTML(entry.badge)}</span>` : "";
  const span = entry.span ? ` span-${entry.span}` : "";
  const links = (entry.links || []).map((l) =>
    l.copy
      ? `<button type="button" class="card-link copy-btn" data-copy="${escapeHTML(l.copy)}">${escapeHTML(l.label)}</button>`
      : `<a class="card-link" href="${escapeHTML(l.url)}">${escapeHTML(l.label)}</a>`
  ).join("");
  const main = entry.url
    ? `<a class="card-main" href="${escapeHTML(entry.url)}">前往 →</a>`
    : "";
  return `
    <article class="card${span}" id="card-${cssId(entry.name)}">
      <div class="card-head">
        <span class="dot ${statusClass(entry, undefined)}" data-dot></span>
        <h2 class="card-title">${escapeHTML(entry.name)}</h2>
        ${badge}
      </div>
      <p class="card-desc">${escapeHTML(entry.desc)}</p>
      ${main}
      ${links}
    </article>
  `;
}

function escapeHTML(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function cssId(s) {
  return String(s).replace(/[^a-zA-Z0-9\u4e00-\u9fa5_-]/g, "-");
}

async function loadEntries() {
  const res = await fetch(ENTRIES_URL, { cache: "no-store" });
  if (!res.ok) throw new Error("entries.json 加载失败: " + res.status);
  return res.json();
}

function probeURL(entry) {
  if (entry.probe_url || entry.url) return entry.probe_url || entry.url;
  const first = (entry.links || []).find((l) => l.url);
  return first ? first.url : null;
}

function checkStatus(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), TIMEOUT_MS);
  return fetch(url, { mode: "no-cors", signal: ctrl.signal, cache: "no-store" })
    .then(() => { clearTimeout(timer); return true; })
    .catch(() => { clearTimeout(timer); return false; });
}

async function refreshStatus(entries) {
  for (const entry of entries) {
    const el = document.querySelector(`#card-${cssId(entry.name)} [data-dot]`);
    if (!el) continue;
    const url = probeURL(entry);
    el.className = "dot " + statusClass(entry, undefined);
    if (!url) continue;
    const ok = await checkStatus(url);
    el.className = "dot " + statusClass(entry, ok);
  }
}

function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  const ta = document.createElement("textarea");
  ta.value = text;
  ta.style.position = "fixed";
  ta.style.opacity = "0";
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand("copy");
    return Promise.resolve();
  } catch {
    return Promise.reject(new Error("复制失败"));
  } finally {
    ta.remove();
  }
}

function bindCopy(entriesEl) {
  entriesEl.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".copy-btn");
    if (!btn) return;
    const original = btn.textContent;
    copyText(btn.dataset.copy)
      .then(() => { btn.textContent = "已复制 ✓"; })
      .catch(() => { btn.textContent = "复制失败"; })
      .finally(() => setTimeout(() => { btn.textContent = original; }, 1500));
  });
}

async function loadQuotes() {
  try {
    const res = await fetch("quotes.json", { cache: "no-store" });
    if (!res.ok) return [];
    const arr = await res.json();
    return Array.isArray(arr) ? arr.filter((q) => String(q).trim()) : [];
  } catch {
    return [];
  }
}

function showRandomQuote(quotes) {
  const el = document.getElementById("quote");
  if (!el) return;
  if (quotes.length === 0) {
    el.textContent = "本栏暂无收录，词条整理中……";
    return;
  }
  el.textContent = "“" + quotes[Math.floor(Math.random() * quotes.length)] + "”";
}

async function loadNotices() {
  try {
    const res = await fetch("notices.json", { cache: "no-store" });
    if (!res.ok) return [];
    const arr = await res.json();
    return Array.isArray(arr) ? arr.filter((n) => String(n).trim()) : [];
  } catch {
    return [];
  }
}

function renderNotices(notices) {
  const el = document.getElementById("notices");
  if (!el) return;
  if (notices.length === 0) {
    el.innerHTML = "<li>暂无公告。</li>";
    return;
  }
  el.innerHTML = notices.map((n) => `<li>${escapeHTML(n)}</li>`).join("");
}

async function init() {
  document.getElementById("today").textContent = new Date().toLocaleDateString("zh-CN", {
    year: "numeric", month: "long", day: "numeric", weekday: "long",
  });
  showRandomQuote(await loadQuotes());
  renderNotices(await loadNotices());
  try {
    const entries = await loadEntries();
    entriesEl.innerHTML = entries.map(cardHTML).join("");
    bindCopy(entriesEl);
    await refreshStatus(entries);
    setInterval(() => refreshStatus(entries), POLL_MS);
  } catch (err) {
    entriesEl.innerHTML = `<p class="error">${escapeHTML(err.message)}</p>`;
  }
}

init();
