const profileMain = document.getElementById("profileMain");
const dayDialog = document.getElementById("dayDialog");
const dayDialogTitle = document.getElementById("dayDialogTitle");
const dayDialogGrid = document.getElementById("dayDialogGrid");
const dayDialogClose = document.getElementById("dayDialogClose");
const lightbox = document.getElementById("lightbox");
const lightboxImg = document.getElementById("lightboxImg");
const lightboxClose = document.getElementById("lightboxClose");

let profileData = null;
let titleFilter = "all";

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

function openLightbox(url) {
  lightboxImg.src = url;
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
    img.addEventListener("click", () => openLightbox(item.image_url));
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

function renderProfile(data) {
  profileData = data;
  profileMain.innerHTML = "";

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

  const titleHead = document.createElement("h3");
  titleHead.className = "section-title";
  titleHead.textContent = "称号";
  profileMain.appendChild(titleHead);

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
      const old = profileMain.querySelector(".title-list");
      if (old) old.replaceWith(renderTitles());
    });
    filters.appendChild(btn);
  }
  profileMain.appendChild(filters);
  profileMain.appendChild(renderTitles());
}

async function loadProfile(year) {
  if (!requireAuth()) return;
  profileMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  const url = year ? `/api/me/profile?year=${year}` : "/api/me/profile";
  const res = await fetch(url, { headers: GalleryAuth.headers() });
  if (!res.ok) {
    GalleryAuth.clear();
    window.location.href = "/";
    return;
  }
  renderProfile(await res.json());
}

dayDialogClose.addEventListener("click", () => dayDialog.close());
lightboxClose.addEventListener("click", closeLightbox);
lightbox.addEventListener("click", (e) => {
  if (e.target === lightbox) closeLightbox();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeLightbox();
    dayDialog.close();
  }
});

if (requireAuth()) {
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    loadProfile();
  });
}
