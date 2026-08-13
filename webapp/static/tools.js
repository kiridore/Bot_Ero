/* 工具箱：链接卡片网格 + 关键字搜索 + 卡片/列表视图切换。 */

(function () {
  "use strict";

  const toolList = document.getElementById("toolList");
  const toolEmpty = document.getElementById("toolEmpty");
  const searchInput = document.getElementById("searchInput");
  const addBtn = document.getElementById("addBtn");
  const viewToggle = document.getElementById("viewToggle");
  const addDialog = document.getElementById("addDialog");
  const addForm = document.getElementById("addForm");
  const addMsg = document.getElementById("addMsg");
  const addTitle = document.getElementById("addTitle");
  const addDesc = document.getElementById("addDesc");
  const addUrl = document.getElementById("addUrl");
  const addCancel = document.getElementById("addCancel");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /* —— 侧边栏：entries.json 功能导航（唯一入口维护点）—— */
  async function loadNav() {
    try {
      const res = await fetch("/entries.json");
      if (!res.ok) return;
      const entries = await res.json();
      const nav = document.getElementById("tlNav");
      nav.innerHTML = '<div class="tl-nav-muted">功能</div>';
      entries.forEach(function (entry) {
        if (entry.url) {
          const a = document.createElement("a");
          a.href = entry.url;
          a.className = "tl-nav-link";
          a.innerHTML =
            '<span class="tl-nav-name">' + esc(entry.name) + "</span>" +
            (entry.desc ? '<span class="tl-nav-desc">' + esc(entry.desc) + "</span>" : "");
          nav.appendChild(a);
        } else if (entry.links) {
          const group = document.createElement("div");
          group.className = "tl-nav-group";
          group.innerHTML = '<span class="tl-nav-name">' + esc(entry.name) + "</span>";
          entry.links.forEach(function (link) {
            const a = document.createElement("a");
            a.className = "tl-nav-sublink";
            if (link.url) {
              a.href = link.url;
              a.textContent = link.label;
            } else if (link.copy) {
              a.href = "#";
              a.textContent = link.label;
              a.addEventListener("click", function (e) {
                e.preventDefault();
                if (navigator.clipboard) navigator.clipboard.writeText(link.copy);
              });
            }
            group.appendChild(a);
          });
          nav.appendChild(group);
        }
      });
    } catch (err) {
      /* 导航加载失败不阻塞页面 */
    }
  }

  /* —— 视图切换 —— */
  let viewMode = localStorage.getItem("tools_view_mode") || "card";

  function applyView() {
    toolList.className = viewMode === "list" ? "tools-grid is-list" : "tools-grid";
    viewToggle.textContent = viewMode === "card" ? "列表" : "卡片";
  }

  viewToggle.addEventListener("click", function () {
    viewMode = viewMode === "card" ? "list" : "card";
    localStorage.setItem("tools_view_mode", viewMode);
    applyView();
    loadTools();
  });

  /* —— 渲染 —— */
  function showEmpty(text) {
    toolEmpty.textContent = text;
    toolEmpty.classList.remove("hidden");
  }

  function renderIcon(item) {
    const img = document.createElement("img");
    img.className = "tools-icon";
    img.alt = "";
    img.src = "https://" + item.domain + "/favicon.ico";
    const first = item.title.trim().charAt(0).toUpperCase() || "?";
    img.onerror = function () {
      const fb = document.createElement("span");
      fb.className = "tools-icon tools-icon-fallback";
      fb.textContent = first;
      img.replaceWith(fb);
    };
    return img;
  }

  function renderItems(items) {
    toolList.innerHTML = "";
    toolEmpty.classList.add("hidden");
    if (!items.length) {
      showEmpty(searchInput.value.trim() ? "没有匹配的链接" : "还没有链接，点右上角「添加链接」提交第一个");
      return;
    }
    items.forEach(function (item) {
      const a = document.createElement("a");
      a.className = "tools-card";
      a.href = item.url;
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.appendChild(renderIcon(item));
      const name = document.createElement("span");
      name.className = "tools-name";
      name.textContent = item.title;
      a.appendChild(name);
      if (item.description) {
        const desc = document.createElement("span");
        desc.className = "tools-desc";
        desc.textContent = item.description;
        a.appendChild(desc);
      }
      const meta = document.createElement("span");
      meta.className = "tools-meta";
      const avatar = document.createElement("img");
      avatar.className = "tools-meta-avatar";
      avatar.alt = "";
      avatar.src = item.created_by_avatar || "";
      avatar.onerror = function () { avatar.style.display = "none"; };
      meta.appendChild(avatar);
      meta.appendChild(document.createTextNode("由 " + (item.created_by_name || item.created_by) + " 提交"));
      a.appendChild(meta);
      toolList.appendChild(a);
    });
  }

  /* —— 数据 —— */
  async function loadTools() {
    const q = searchInput.value.trim();
    try {
      const res = await fetch("/api/tools?q=" + encodeURIComponent(q), {
        headers: GalleryAuth.headers(),
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      renderItems(data.items || []);
    } catch (err) {
      toolList.innerHTML = "";
      showEmpty("加载失败");
    }
  }

  let searchTimer = null;
  searchInput.addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadTools, 300);
  });
  searchInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      clearTimeout(searchTimer);
      loadTools();
    }
  });

  /* —— 添加链接 —— */
  function openAddDialog() {
    addMsg.classList.add("hidden");
    if (typeof addDialog.showModal === "function") addDialog.showModal();
    addTitle.focus();
  }

  addBtn.addEventListener("click", function () {
    if (GalleryAuth.isLoggedIn()) {
      openAddDialog();
      return;
    }
    const dlg = GalleryAuth.ensureLoginDialog();
    if (typeof dlg.showModal === "function") dlg.showModal();
    // 登录成功后继续打开添加框；不依赖 dialog close 事件（部分浏览器/构建不触发），轮询兜底
    const timer = setInterval(function () {
      if (GalleryAuth.isLoggedIn()) {
        clearInterval(timer);
        openAddDialog();
      } else if (!dlg.open) {
        clearInterval(timer); // 用户取消登录
      }
    }, 250);
  });

  addCancel.addEventListener("click", function () {
    addDialog.close();
  });

  addForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    addMsg.classList.add("hidden");
    const payload = {
      title: addTitle.value.trim(),
      description: addDesc.value.trim(),
      url: addUrl.value.trim(),
    };
    try {
      const res = await fetch("/api/tools", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, GalleryAuth.headers()),
        body: JSON.stringify(payload),
      });
      if (res.status === 401) {
        addDialog.close();
        const dlg = GalleryAuth.ensureLoginDialog();
        if (typeof dlg.showModal === "function") dlg.showModal();
        return;
      }
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        const detail = data.detail;
        addMsg.textContent = Array.isArray(detail)
          ? detail.map(function (d) { return d.msg; }).join("; ")
          : (detail || "提交失败");
        addMsg.classList.remove("hidden");
        return;
      }
      addDialog.close();
      addForm.reset();
      loadTools();
    } catch (err) {
      addMsg.textContent = "网络错误，请重试";
      addMsg.classList.remove("hidden");
    }
  });

  /* —— 初始化 —— */
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadNav();
  applyView();
  loadTools();
})();
