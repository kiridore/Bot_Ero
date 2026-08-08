const guestbookMain = document.getElementById("guestbookMain");
const authArea = document.getElementById("authArea");
const loginDialog = document.getElementById("loginDialog");
const loginForm = document.getElementById("loginForm");
const loginKey = document.getElementById("loginKey");
const loginError = document.getElementById("loginError");
const loginCancel = document.getElementById("loginCancel");

let page = 1;
let hasMore = false;
let loading = false;
let maxContentLen = 500;

function escapeHtml(s) {
  return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function showToast(msg, isError = false) {
  let toast = document.getElementById("guestbookToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "guestbookToast";
    toast.className = "settings-toast";
    guestbookMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function openLoginDialog() {
  loginError.classList.add("hidden");
  loginDialog.showModal();
}

function renderAuthArea() {
  authArea.innerHTML = "";
  const session = GalleryAuth.load();
  if (session && session.token) {
    const link = document.createElement("a");
    link.className = "user-chip";
    link.href = "/guestbook";
    const img = document.createElement("img");
    img.src = session.avatar_url || "";
    img.alt = session.display_name || session.user_id;
    img.onerror = () => { img.style.display = "none"; };
    const wrap = document.createElement("span");
    wrap.innerHTML = `<strong>${escapeHtml(session.display_name || session.user_id)}</strong><br><span class="uid">${session.user_id}</span>`;
    link.append(img, wrap);
    authArea.appendChild(link);
    return;
  }
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "btn-login";
  btn.textContent = "登录";
  btn.addEventListener("click", openLoginDialog);
  authArea.appendChild(btn);
}

function renderComposeBox() {
  const section = document.createElement("section");
  section.className = "guestbook-compose settings-section";
  if (!GalleryAuth.isLoggedIn()) {
    section.innerHTML = `
      <h2>写下留言</h2>
      <p class="preview-hint">登录后可匿名留言。夸夸小埃，或提提建议——想要的新功能、觉得不好用的地方，都可以说。</p>
      <button type="button" class="btn-sm primary" id="guestbookLoginBtn">登录后留言</button>
    `;
    section.querySelector("#guestbookLoginBtn").addEventListener("click", openLoginDialog);
    return section;
  }

  section.innerHTML = `
    <h2>写下留言</h2>
    <p class="preview-hint">完全匿名。欢迎夸夸小埃，或提建议：想要的功能、用着不顺手的地方，都可以写。</p>
    <textarea id="guestbookContent" class="guestbook-input" rows="4" maxlength="${maxContentLen}" placeholder="例如：小埃的打卡提醒超贴心！ / 希望商店能… / 网页打卡这里有点不好用…"></textarea>
    <div class="guestbook-compose-meta">
      <span id="guestbookCharCount">0 / ${maxContentLen}</span>
      <button type="button" class="btn-sm primary" id="guestbookPostBtn">发布留言</button>
    </div>
  `;

  const textarea = section.querySelector("#guestbookContent");
  const counter = section.querySelector("#guestbookCharCount");
  textarea.addEventListener("input", () => {
    counter.textContent = `${textarea.value.length} / ${maxContentLen}`;
  });
  section.querySelector("#guestbookPostBtn").addEventListener("click", postEntry);
  return section;
}

function renderEntry(item) {
  const card = document.createElement("article");
  card.className = "guestbook-item";
  card.dataset.id = String(item.id);

  const likedClass = item.liked ? " liked" : "";
  card.innerHTML = `
    <div class="guestbook-item-main">
      <p class="guestbook-author">匿名</p>
      <p class="guestbook-content">${escapeHtml(item.content)}</p>
      <p class="guestbook-meta">${escapeHtml(item.created_at)}</p>
    </div>
    <button type="button" class="guestbook-like-btn${likedClass}" data-id="${item.id}" ${item.liked ? "disabled" : ""}>
      <span class="like-icon">♥</span>
      <span class="like-count">${item.like_count}</span>
    </button>
  `;

  const btn = card.querySelector(".guestbook-like-btn");
  if (!item.liked) {
    btn.addEventListener("click", () => likeEntry(item.id, btn));
  }
  return card;
}

function renderListShell() {
  guestbookMain.innerHTML = "";
  guestbookMain.appendChild(renderComposeBox());

  const listSection = document.createElement("section");
  listSection.className = "settings-section guestbook-list-section";
  listSection.innerHTML = `
    <h2>全部留言</h2>
    <p class="preview-hint">按点赞数从高到低排列，点赞越多越靠前。</p>
    <div id="guestbookList" class="guestbook-list"></div>
    <p id="guestbookLoadMore" class="guestbook-load-more hidden"></p>
  `;
  guestbookMain.appendChild(listSection);
}

function appendEntries(items, replace = false) {
  const list = document.getElementById("guestbookList");
  if (!list) return;
  if (replace) list.innerHTML = "";
  if (replace && !items.length) {
    list.innerHTML = "<p class='empty-hint center'>还没有留言，来夸夸小埃或提提建议吧</p>";
    return;
  }
  for (const item of items) {
    list.appendChild(renderEntry(item));
  }
}

function updateLoadMore() {
  const el = document.getElementById("guestbookLoadMore");
  if (!el) return;
  if (hasMore) {
    el.classList.remove("hidden");
    el.innerHTML = `<button type="button" class="btn-sm" id="guestbookMoreBtn">加载更多</button>`;
    el.querySelector("#guestbookMoreBtn").addEventListener("click", () => loadEntries(false));
  } else {
    el.classList.add("hidden");
    el.innerHTML = "";
  }
}

async function loadEntries(reset = true) {
  if (loading) return;
  loading = true;
  if (reset) {
    page = 1;
    renderListShell();
  }

  const list = document.getElementById("guestbookList");
  if (reset && list) list.innerHTML = "<p class='loading-msg'>加载中…</p>";

  try {
    const params = new URLSearchParams({
      page: String(page),
      page_size: "30",
    });
    const res = await fetch(`/api/guestbook?${params}`, { headers: GalleryAuth.headers() });
    if (!res.ok) throw new Error("加载失败");
    const data = await res.json();
    maxContentLen = data.max_content_len || maxContentLen;
    hasMore = Boolean(data.has_more);
    appendEntries(data.items, reset);
    if (reset) {
      const compose = guestbookMain.querySelector(".guestbook-compose");
      if (compose) compose.replaceWith(renderComposeBox());
    }
    page += 1;
    updateLoadMore();
  } catch (err) {
    if (reset) {
      guestbookMain.innerHTML = "<p class='loading-msg error'>加载失败</p>";
    } else {
      showToast(err.message || "加载失败", true);
    }
  } finally {
    loading = false;
  }
}

async function postEntry() {
  if (!GalleryAuth.isLoggedIn()) {
    openLoginDialog();
    return;
  }
  const textarea = document.getElementById("guestbookContent");
  const btn = document.getElementById("guestbookPostBtn");
  const content = (textarea?.value || "").trim();
  if (!content) {
    showToast("请填写留言内容", true);
    return;
  }

  btn.disabled = true;
  btn.textContent = "发布中…";
  try {
    const res = await fetch("/api/guestbook", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ content }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "发布失败");
    showToast(data.message || "留言已发布");
    await loadEntries(true);
  } catch (err) {
    showToast(err.message || "发布失败", true);
  } finally {
    btn.disabled = false;
    btn.textContent = "发布留言";
  }
}

async function likeEntry(entryId, btn) {
  if (!GalleryAuth.isLoggedIn()) {
    openLoginDialog();
    return;
  }
  btn.disabled = true;
  try {
    const res = await fetch(`/api/guestbook/${entryId}/like`, {
      method: "POST",
      headers: GalleryAuth.headers(),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "点赞失败");
    btn.classList.add("liked");
    btn.querySelector(".like-count").textContent = String(data.like_count ?? "");
    showToast(data.message || "已点赞");
    await loadEntries(true);
  } catch (err) {
    showToast(err.message || "点赞失败", true);
    btn.disabled = false;
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
    await loadEntries(true);
  } catch (err) {
    loginError.textContent = err.message || "登录失败";
    loginError.classList.remove("hidden");
  }
});

GalleryAuth.refreshMe().finally(async () => {
  renderAuthArea();
  await loadEntries(true);
});
