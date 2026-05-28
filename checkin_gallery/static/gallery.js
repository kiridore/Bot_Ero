const gallery = document.getElementById("gallery");
const sentinel = document.getElementById("sentinel");
const userFilter = document.getElementById("userFilter");
const yearFilter = document.getElementById("yearFilter");
const applyBtn = document.getElementById("applyBtn");
const stats = document.getElementById("stats");
const lightbox = document.getElementById("lightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxCaption = document.getElementById("lightboxCaption");
const lightboxClose = document.getElementById("lightboxClose");

const WEEKDAYS = ["日", "一", "二", "三", "四", "五", "六"];

let page = 1;
let loading = false;
let hasMore = true;
let total = 0;

function queryParams() {
  const params = new URLSearchParams({ page: String(page), page_size: "40" });
  const uid = userFilter.value;
  const year = yearFilter.value.trim();
  if (uid) params.set("user_id", uid);
  if (year) params.set("year", year);
  return params;
}

async function loadUsers() {
  const res = await fetch("/api/users");
  const data = await res.json();
  for (const u of data.users) {
    const opt = document.createElement("option");
    opt.value = u.user_id;
    opt.textContent = u.display_name;
    userFilter.appendChild(opt);
  }
}

function userLabel(item) {
  return item.display_name || item.user_id;
}

/** 与 Bot 打卡结算一致：时间向前偏移 8 小时再取日期 */
function settlementDayKey(iso) {
  const d = new Date(iso.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) return iso.slice(0, 10);
  d.setHours(d.getHours() - 8);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

function formatDayHeader(dayKey) {
  const d = new Date(`${dayKey}T12:00:00`);
  const w = Number.isNaN(d.getTime()) ? "" : ` 星期${WEEKDAYS[d.getDay()]}`;
  return `${dayKey}${w}`;
}

function formatTime(iso) {
  const t = iso.includes(" ") ? iso.split(" ")[1] : iso;
  return t.slice(0, 8);
}

function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function countCards() {
  return gallery.querySelectorAll(".card").length;
}

function getOrCreateDaySection(dayKey) {
  let section = gallery.querySelector(`.day-section[data-day="${dayKey}"]`);
  if (section) return section.querySelector(".day-masonry");

  section = document.createElement("section");
  section.className = "day-section";
  section.dataset.day = dayKey;

  const header = document.createElement("header");
  header.className = "day-divider";
  const label = document.createElement("span");
  label.className = "day-divider-date";
  label.textContent = formatDayHeader(dayKey);
  header.appendChild(label);

  const masonry = document.createElement("div");
  masonry.className = "day-masonry";

  section.appendChild(header);
  section.appendChild(masonry);
  gallery.appendChild(section);
  return masonry;
}

function appendCard(item) {
  const dayKey = settlementDayKey(item.checkin_date);
  const dayMasonry = getOrCreateDaySection(dayKey);

  const card = document.createElement("article");
  card.className = "card";
  const img = document.createElement("img");
  img.loading = "lazy";
  img.alt = `${userLabel(item)} 打卡`;
  img.src = item.thumbnail_url || item.image_url;
  img.dataset.fullSrc = item.image_url;
  const meta = document.createElement("div");
  meta.className = "meta";
  meta.innerHTML = `<strong>${escapeHtml(userLabel(item))}</strong><br>${formatTime(item.checkin_date)}`;
  card.appendChild(img);
  card.appendChild(meta);
  card.addEventListener("click", () => openLightbox(item, dayKey));
  dayMasonry.appendChild(card);
}

function openLightbox(item, dayKey) {
  const dayLabel = dayKey ? formatDayHeader(dayKey) : settlementDayKey(item.checkin_date);
  lightboxCaption.textContent = `${userLabel(item)} · ${dayLabel} ${formatTime(item.checkin_date)}`;
  lightbox.classList.remove("hidden");
  lightbox.classList.add("is-loading");
  lightboxImg.alt = userLabel(item);
  lightboxImg.onload = () => lightbox.classList.remove("is-loading");
  lightboxImg.onerror = () => {
    lightbox.classList.remove("is-loading");
    lightboxCaption.textContent += "（原图加载失败）";
  };
  lightboxImg.src = item.image_url;
}

function closeLightbox() {
  lightbox.classList.add("hidden");
  lightboxImg.src = "";
}

async function loadPage(reset = false) {
  if (loading || (!hasMore && !reset)) return;
  loading = true;
  sentinel.textContent = "加载中…";

  if (reset) {
    page = 1;
    hasMore = true;
    gallery.innerHTML = "";
  }

  const res = await fetch(`/api/checkins?${queryParams()}`);
  const data = await res.json();
  total = data.total;
  hasMore = data.has_more;

  for (const item of data.items) {
    appendCard(item);
  }

  stats.textContent = `共 ${total} 张（已显示 ${countCards()}）`;
  sentinel.textContent = hasMore ? "向下滚动加载更多" : "已加载全部";
  if (hasMore) page += 1;
  loading = false;
}

function resetAndLoad() {
  loadPage(true);
}

applyBtn.addEventListener("click", resetAndLoad);
lightboxClose.addEventListener("click", closeLightbox);
lightbox.addEventListener("click", (e) => {
  if (e.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeLightbox();
});

const observer = new IntersectionObserver(
  (entries) => {
    if (entries[0].isIntersecting) loadPage(false);
  },
  { rootMargin: "200px" }
);
observer.observe(sentinel);

loadUsers().then(() => loadPage(true));

// —— 登录 / 用户入口 ——
const authArea = document.getElementById("authArea");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

function renderAuthArea() {
  const session = GalleryAuth.load();
  authArea.innerHTML = "";
  if (session && session.token) {
    const checkinLink = document.createElement("a");
    checkinLink.className = "btn-checkin";
    checkinLink.href = "/profile/checkin";
    checkinLink.textContent = "打卡";
    authArea.appendChild(checkinLink);

    const link = document.createElement("a");
    link.className = "user-chip";
    link.href = "/profile";
    const img = document.createElement("img");
    img.alt = session.display_name || session.user_id;
    img.src = session.avatar_url || "";
    img.onerror = () => {
      img.style.display = "none";
    };
    const textWrap = document.createElement("span");
    textWrap.innerHTML = `<strong>${escapeHtml(session.display_name || session.user_id)}</strong><br><span class="uid">${session.user_id}</span>`;
    link.appendChild(img);
    link.appendChild(textWrap);
    authArea.appendChild(link);
  } else {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-login";
    btn.textContent = "登录";
    btn.addEventListener("click", () => loginDialog.showModal());
    authArea.appendChild(btn);
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
    renderAuthArea();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(renderAuthArea);
