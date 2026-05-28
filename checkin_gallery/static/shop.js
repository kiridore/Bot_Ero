const shopMain = document.getElementById("shopMain");

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

function showToast(msg, isError = false) {
  let toast = document.getElementById("shopToast");
  if (!toast) {
    toast = document.createElement("p");
    toast.id = "shopToast";
    toast.className = "settings-toast";
    shopMain.prepend(toast);
  }
  toast.textContent = msg;
  toast.classList.toggle("error", isError);
  toast.classList.remove("hidden");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add("hidden"), 3500);
}

function renderShop(data) {
  shopMain.innerHTML = "";

  const header = document.createElement("section");
  header.className = "shop-header settings-section";
  header.innerHTML = `
    <h2>小埃商店</h2>
    <p class="shop-points">当前积分：<strong id="shopPoints">${data.points}</strong></p>
    <p class="preview-hint">${escapeHtml(data.refresh_hint)}</p>
  `;
  shopMain.appendChild(header);

  if (!data.items.length) {
    const empty = document.createElement("p");
    empty.className = "empty-hint center";
    empty.textContent = "本周暂无上架商品";
    shopMain.appendChild(empty);
    return;
  }

  const list = document.createElement("div");
  list.className = "shop-list";
  list.id = "shopList";

  for (const item of data.items) {
    const card = document.createElement("article");
    card.className = "shop-item";
    if (item.owned) card.classList.add("owned");

    let status = "";
    if (item.owned) {
      status = "已拥有";
    } else if (item.stock === 0) {
      status = "已售罄";
    } else if (!item.affordable) {
      status = "积分不足";
    }

    card.innerHTML = `
      <div class="shop-item-main">
        <code class="shop-id">${escapeHtml(item.id)}</code>
        <p class="shop-desc">${escapeHtml(item.description)}</p>
        <p class="shop-meta">售价 ${item.cost} 积分 · 剩余 ${escapeHtml(item.stock_label)}</p>
        ${status ? `<p class="shop-status">${escapeHtml(status)}</p>` : ""}
      </div>
    `;

    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn-sm primary";
    btn.textContent = "兑换";
    btn.disabled = !item.can_buy;
    btn.addEventListener("click", () => redeemItem(item.id, btn));
    card.appendChild(btn);
    list.appendChild(card);
  }

  shopMain.appendChild(list);
}

async function loadShop() {
  shopMain.innerHTML = "<p class='loading-msg'>加载中…</p>";
  const res = await fetch("/api/me/shop", { headers: GalleryAuth.headers() });
  if (res.status === 401) {
    GalleryAuth.clear();
    window.location.href = "/";
    return;
  }
  if (!res.ok) {
    shopMain.innerHTML = "<p class='loading-msg error'>加载失败</p>";
    return;
  }
  renderShop(await res.json());
}

async function redeemItem(productId, btn) {
  if (!confirm(`确定兑换「${productId}」？积分将立刻扣除。`)) return;
  btn.disabled = true;
  btn.textContent = "兑换中…";
  try {
    const res = await fetch("/api/me/shop/redeem", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ product_id: productId }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "兑换失败");
    showToast(data.message || "兑换成功");
    await loadShop();
  } catch (err) {
    showToast(err.message || "兑换失败", true);
    btn.disabled = false;
    btn.textContent = "兑换";
  }
}

if (requireAuth()) {
  GalleryAuth.refreshMe().finally(() => {
    renderAuthChip();
    loadShop();
  });
}
