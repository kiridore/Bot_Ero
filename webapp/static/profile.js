const profileMain = document.getElementById("profileMain");
const dayDialog = document.getElementById("dayDialog");
const dayDialogTitle = document.getElementById("dayDialogTitle");
const dayDialogGrid = document.getElementById("dayDialogGrid");
const dayDialogClose = document.getElementById("dayDialogClose");
const lightbox = document.getElementById("lightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxClose = document.getElementById("lightboxClose");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

let profileData = null;
let titleFilter = "all";
let activeTab = "titles";
let checkinState = { loaded: false, page: 0, hasMore: true, loading: false, lastMonth: "" };
let currentRecord = null;

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  loginDialog.showModal();
}

function requireAuth() {
  if (!GalleryAuth.isLoggedIn()) {
    profileMain.innerHTML = "<p class='empty-hint center'>请先登录</p>";
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

function openLightbox(record) {
  lightboxImg.src = record.image_url;
  currentRecord = record;
  const shareBtn = document.getElementById("lightboxShare");
  if (shareBtn) shareBtn.classList.toggle("hidden", record.id == null);
  lightbox.classList.remove("hidden");
}

function closeLightbox() {
  lightbox.classList.add("hidden");
  lightboxImg.src = "";
}

async function openDay(date) {
  dayDialogTitle.textContent = `${date} 打卡`;
  dayDialogGrid.innerHTML = "<p class='empty'>加载中…</p>";
  dayDialog.showModal();
  const res = await fetch(`/api/me/day?date=${encodeURIComponent(date)}`, {
    headers: GalleryAuth.headers(),
  });
  if (!res.ok) {
    dayDialogGrid.innerHTML = "<p class='empty'>加载失败</p>";
    return;
  }
  const data = await res.json();
  dayDialogGrid.innerHTML = "";
  if (!data.items.length) {
    dayDialogGrid.innerHTML = "<p class='empty'>该日无打卡图片</p>";
    return;
  }
  for (const item of data.items) {
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = item.thumbnail_url || item.image_url;
    img.alt = item.checkin_date;
    img.addEventListener("click", () => openLightbox(item));
    dayDialogGrid.appendChild(img);
  }
}

function renderHeatmap(cells) {
  const wrap = document.createElement("div");
  wrap.className = "heatmap-wrap";
  const grid = document.createElement("div");
  grid.className = "heatmap-grid";
  for (const cell of cells) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `heatmap-cell level-${cell.level}`;
    btn.title = `${cell.date}：${cell.is_remedy ? "补卡" : `${cell.count} 张`}`;
    btn.dataset.date = cell.date;
    btn.addEventListener("click", () => openDay(cell.date));
    grid.appendChild(btn);
  }
  wrap.appendChild(grid);
  const legend = document.createElement("div");
  legend.className = "heatmap-legend";
  legend.textContent = "少 ← 打卡热度 → 多 · 深色为补卡日 · 点击格子查看当日图片";
  wrap.appendChild(legend);
  return wrap;
}

function filteredTitles() {
  if (!profileData) return [];
  if (titleFilter === "all") return profileData.titles;
  return profileData.titles.filter((t) => t.unlock_type === titleFilter);
}

function renderTitles() {
  const list = document.createElement("div");
  list.className = "title-list";
  for (const t of filteredTitles()) {
    const card = document.createElement("article");
    card.className = `title-card${t.unlocked ? " unlocked" : ""}`;
    card.dataset.reveal = "";
    const pct = Math.round(t.progress * 100);
    card.innerHTML = `
      <div class="title-row">
        <strong>「${escapeHtml(t.name)}」</strong>
        <span class="rarity">${escapeHtml(t.rarity)}${t.equipped ? " · 已装备" : ""}</span>
      </div>
      <p class="desc">${escapeHtml(t.description)}</p>
      <div class="progress-bar"><span style="width:${pct}%"></span></div>
      <p class="progress-label">${
        t.unlocked
          ? "已解锁"
          : `${t.progress_hint} ${t.progress_current}/${t.progress_target} (${pct}%)`
      }</p>
    `;
    list.appendChild(card);
  }
  return list;
}

function switchTab(key) {
  if (key === activeTab) return;
  activeTab = key;
  document.querySelectorAll(".profile-tabs button").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === key);
  });
  document.getElementById("panelTitles").classList.toggle("hidden", key !== "titles");
  document.getElementById("panelCheckins").classList.toggle("hidden", key !== "checkins");
  if (key === "checkins" && !checkinState.loaded) {
    checkinState.loaded = true;
    loadCheckins();
  }
}

async function loadCheckins() {
  const more = document.getElementById("checkinMore");
  if (!more || checkinState.loading || !checkinState.hasMore) return;
  checkinState.loading = true;
  more.disabled = true;
  more.textContent = "加载中…";
  try {
    const res = await fetch(`/api/me/checkins?page=${checkinState.page + 1}`, {
      headers: GalleryAuth.headers(),
    });
    if (!res.ok) throw new Error("加载失败");
    const data = await res.json();
    checkinState.page = data.page;
    checkinState.hasMore = data.has_more;
    appendCheckinCards(data.items);
    more.textContent = checkinState.hasMore ? "加载更多" : "没有更多了";
    more.disabled = !checkinState.hasMore;
  } catch (err) {
    more.textContent = "加载失败，点击重试";
    more.disabled = false;
  }
  checkinState.loading = false;
}

function appendCheckinCards(items) {
  const grid = document.getElementById("checkinGrid");
  for (const it of items) {
    const month = it.checkin_date.slice(0, 7);
    if (month !== checkinState.lastMonth) {
      checkinState.lastMonth = month;
      const head = document.createElement("h4");
      head.className = "checkin-month";
      head.textContent = month;
      grid.appendChild(head);
    }
    const card = document.createElement("button");
    card.type = "button";
    card.className = "checkin-card";
    card.dataset.reveal = "";
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = it.thumbnail_url || it.image_url;
    img.alt = it.checkin_date;
    const label = document.createElement("span");
    label.className = "checkin-card-date";
    label.textContent = it.checkin_date.slice(0, 16);
    card.append(img, label);
    card.addEventListener("click", () => openLightbox(it));
    grid.appendChild(card);
  }
}

function renderTabShell() {
  const tabs = document.createElement("div");
  tabs.className = "profile-tabs";
  for (const [key, label] of [
    ["titles", "称号"],
    ["checkins", "打卡记录"],
  ]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.dataset.tab = key;
    btn.className = key === activeTab ? "active" : "";
    btn.addEventListener("click", () => switchTab(key));
    tabs.appendChild(btn);
  }
  return tabs;
}

function renderProfile(data) {
  profileData = data;
  profileMain.innerHTML = "";
  checkinState = { loaded: false, page: 0, hasMore: true, loading: false, lastMonth: "" };

  const header = document.createElement("section");
  header.className = "profile-header";
  const avatar = document.createElement("img");
  avatar.src = data.avatar_url || "";
  avatar.alt = data.display_name;
  avatar.onerror = () => { avatar.style.display = "none"; };
  const info = document.createElement("div");
  info.innerHTML = `
    <h2>${escapeHtml(data.display_name)}</h2>
    <p class="meta-line">QQ ${escapeHtml(data.user_id)}</p>
    <p class="meta-line">积分 ${data.points} · 称号 ${data.titles_unlocked}/${data.titles_total}</p>
  `;
  header.append(avatar, info);
  profileMain.appendChild(header);

  const stats = document.createElement("div");
  stats.className = "profile-stats";
  const s = data.streaks;
  stats.innerHTML = `
    <span>当前连续日打卡 <strong>${s.current_daily}</strong></span>
    <span>最长连续日 <strong>${s.longest_daily}</strong></span>
    <span>当前连续周 <strong>${s.current_weekly}</strong></span>
    <span>最长连续周 <strong>${s.longest_weekly}</strong></span>
  `;
  profileMain.appendChild(stats);

  const heatTitle = document.createElement("h3");
  heatTitle.className = "section-title";
  const yearSel = document.createElement("select");
  const selectedYear = data.year;
  const currentYear = new Date().getFullYear();
  for (let i = currentYear; i >= currentYear - 3; i--) {
    const opt = document.createElement("option");
    opt.value = String(i);
    opt.textContent = `${i} 年`;
    if (i === selectedYear) opt.selected = true;
    yearSel.appendChild(opt);
  }
  yearSel.addEventListener("change", () => loadProfile(parseInt(yearSel.value, 10)));
  heatTitle.innerHTML = "<span>打卡热力图</span>";
  heatTitle.appendChild(yearSel);
  profileMain.appendChild(heatTitle);
  profileMain.appendChild(renderHeatmap(data.heatmap));

  profileMain.appendChild(renderTabShell());

  const panelTitles = document.createElement("section");
  panelTitles.id = "panelTitles";
  panelTitles.className = "tab-panel" + (activeTab === "titles" ? "" : " hidden");

  const filters = document.createElement("div");
  filters.className = "title-filters";
  for (const [key, label] of [
    ["all", "全部"],
    ["condition", "条件"],
    ["lottery", "抽奖"],
  ]) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.className = key === titleFilter ? "active" : "";
    btn.addEventListener("click", () => {
      titleFilter = key;
      filters.querySelectorAll("button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      const old = panelTitles.querySelector(".title-list");
      if (old) old.replaceWith(renderTitles());
    });
    filters.appendChild(btn);
  }
  panelTitles.appendChild(filters);
  panelTitles.appendChild(renderTitles());

  const panelCheckins = document.createElement("section");
  panelCheckins.id = "panelCheckins";
  panelCheckins.className = "tab-panel" + (activeTab === "checkins" ? "" : " hidden");
  const grid = document.createElement("div");
  grid.id = "checkinGrid";
  grid.className = "checkin-grid";
  const moreBtn = document.createElement("button");
  moreBtn.type = "button";
  moreBtn.id = "checkinMore";
  moreBtn.className = "checkin-more";
  moreBtn.textContent = "加载更多";
  moreBtn.addEventListener("click", loadCheckins);
  panelCheckins.append(grid, moreBtn);

  profileMain.append(panelTitles, panelCheckins);
  if (activeTab === "checkins" && !checkinState.loaded) {
    checkinState.loaded = true;
    loadCheckins();
  }
}

async function loadProfile(year) {
  if (!requireAuth()) return;
  profileMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  const url = year ? `/api/me/profile?year=${year}` : "/api/me/profile";
  const res = await fetch(url, { headers: GalleryAuth.headers() });
  if (!res.ok) {
    GalleryAuth.clear();
    requireAuth();
    return;
  }
  renderProfile(await res.json());
}

dayDialogClose.addEventListener("click", () => dayDialog.close());
lightboxClose.addEventListener("click", closeLightbox);

const shareDialog = document.getElementById("shareDialog");
const shareDialogClose = document.getElementById("shareDialogClose");
const lightboxShareBtn = document.getElementById("lightboxShare");

const WEEKDAY_CN = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];

function formatCheckinDateCN(s) {
  const d = new Date(String(s).replace(" ", "T"));
  if (isNaN(d)) return s;
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${WEEKDAY_CN[d.getDay()]} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function buildShareCardNode(record) {
  const p = profileData || {};
  const name = p.display_name || "打卡用户";
  const card = document.createElement("div");
  card.className = "share-card";

  const header = document.createElement("div");
  header.className = "share-card-header";
  const avatar = document.createElement("img");
  avatar.className = "share-card-avatar";
  avatar.src = "/api/me/avatar.png";
  avatar.alt = name;
  const initial = document.createElement("div");
  initial.className = "share-card-initial";
  initial.textContent = name.trim().slice(0, 1) || "?";
  avatar.onerror = () => avatar.replaceWith(initial);
  const headText = document.createElement("div");
  const nameEl = document.createElement("div");
  nameEl.className = "share-card-name";
  nameEl.textContent = name;
  const dateEl = document.createElement("div");
  dateEl.className = "share-card-date";
  dateEl.textContent = formatCheckinDateCN(record.checkin_date);
  headText.append(nameEl, dateEl);
  header.append(avatar, headText);

  const photo = document.createElement("div");
  photo.className = "share-photo";
  const bg = document.createElement("div");
  bg.className = "share-photo-bg";
  bg.style.backgroundImage = `url("${record.image_url}")`;
  const img = document.createElement("img");
  img.src = record.image_url;
  img.alt = "打卡图片";
  img.addEventListener("load", fitShareCardHost);
  img.onerror = () => { photo.style.minHeight = "240px"; };
  photo.append(bg, img);

  const stats = document.createElement("div");
  stats.className = "share-card-stats";
  const streak = (p.streaks && p.streaks.current_daily) || 0;
  stats.textContent = `连续打卡 ${streak} 天 · 累计 ${p.total_checkin_images || 0} 张`;

  const footer = document.createElement("div");
  footer.className = "share-card-footer";
  footer.textContent = "Power by 小埃同学";

  card.append(header, photo, stats, footer);
  return card;
}

function fitShareCardHost() {
  const host = document.getElementById("shareCardHost");
  const node = host && host.querySelector(".share-card");
  if (!host || !node) return;
  const scale = host.clientWidth / 1080;
  node.style.transform = `scale(${scale})`;
  host.style.height = node.offsetHeight * scale + "px";
}

function openShareCard() {
  if (!currentRecord) return;
  shareDialog.showModal(); // 先开弹层，hidden 状态下 clientWidth 为 0
  const host = document.getElementById("shareCardHost");
  host.innerHTML = "";
  const node = buildShareCardNode(currentRecord);
  host.appendChild(node);
  fitShareCardHost();
}

async function downloadShareCard() {
  const node = document.querySelector("#shareCardHost .share-card");
  if (!node) return;
  if (typeof htmlToImage === "undefined") {
    alert("图片转换组件未加载，请刷新页面重试");
    return;
  }
  const btn = document.getElementById("shareDownload");
  btn.disabled = true;
  btn.textContent = "生成中…";
  try {
    const dataUrl = await htmlToImage.toPng(node, {
      width: 1080,
      height: node.offsetHeight,
      pixelRatio: 1,
      backgroundColor: "#f5f5f5",
      style: { transform: "none" },
    });
    const a = document.createElement("a");
    a.href = dataUrl;
    a.download = `checkin-${currentRecord.id}.png`;
    a.click();
  } catch (err) {
    alert(`生成分享卡失败：${(err && err.message) || err}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "下载图片";
  }
}

lightboxShareBtn.addEventListener("click", openShareCard);
document.getElementById("shareDownload").addEventListener("click", downloadShareCard);
shareDialogClose.addEventListener("click", () => shareDialog.close());
lightbox.addEventListener("click", (e) => {
  if (e.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeLightbox();
    dayDialog.close();
  }
});

loginCancel.addEventListener("click", () => loginDialog.close());
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  try {
    await GalleryAuth.login(loginKey.value);
    loginDialog.close();
    loginKey.value = "";
    renderAuthChip();
    loadProfile();
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(() => {
  renderAuthChip();
  if (requireAuth()) loadProfile();
});
