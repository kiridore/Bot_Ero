/* 工具箱：链接卡片网格 + 关键字搜索 + 卡片/列表视图切换 + 双维度排序 + tag 徽标/筛选 + 点击统计。 */

(function () {
  "use strict";

  const toolList = document.getElementById("toolList");
  const toolEmpty = document.getElementById("toolEmpty");
  const searchInput = document.getElementById("searchInput");
  const tagFilterRow = document.getElementById("tagFilterRow");
  const tagFilterName = document.getElementById("tagFilterName");
  const tagFilterClear = document.getElementById("tagFilterClear");
  const tagCloud = document.getElementById("tagCloud");
  const addBtn = document.getElementById("addBtn");
  const sortSelect = document.getElementById("sortSelect");
  const orderToggle = document.getElementById("orderToggle");
  const viewToggle = document.getElementById("viewToggle");
  const addDialog = document.getElementById("addDialog");
  const addDialogTitle = document.getElementById("addDialogTitle");
  const addForm = document.getElementById("addForm");
  const addMsg = document.getElementById("addMsg");
  const addTitle = document.getElementById("addTitle");
  const addDesc = document.getElementById("addDesc");
  const addUrl = document.getElementById("addUrl");
  const addTags = document.getElementById("addTags");
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
    // 按钮图标 = 切换目标视图（惯例：显示点击后将切换到的视图）
    const target = viewMode === "card" ? "list" : "grid";
    viewToggle.innerHTML = GalleryIcons.svgHTML(target);
    viewToggle.title = viewMode === "card" ? "列表" : "卡片";
    viewToggle.setAttribute("aria-label", viewMode === "card" ? "切换到列表视图" : "切换到卡片视图");
  }

  viewToggle.addEventListener("click", function () {
    viewMode = viewMode === "card" ? "list" : "card";
    localStorage.setItem("tools_view_mode", viewMode);
    applyView();
    loadTools();
  });

  /* —— 排序（双维度 × 正/倒序，偏好持久化） —— */
  let sortDim = localStorage.getItem("tools_sort_dim") === "hot" ? "hot" : "time";
  let sortOrder = localStorage.getItem("tools_sort_order") === "asc" ? "asc" : "desc";

  function applySort() {
    sortSelect.value = sortDim;
    // 图标固定为上下箭头，title 提示切换目标方向（惯例：显示点击后将切换到的方向）
    orderToggle.title = sortOrder === "desc" ? "正序" : "倒序";
    orderToggle.setAttribute(
      "aria-label",
      "切换排序方向（当前" + (sortOrder === "desc" ? "倒序" : "正序") + "）"
    );
  }

  sortSelect.addEventListener("change", function () {
    sortDim = sortSelect.value;
    localStorage.setItem("tools_sort_dim", sortDim);
    loadTools();
  });

  orderToggle.addEventListener("click", function () {
    sortOrder = sortOrder === "desc" ? "asc" : "desc";
    localStorage.setItem("tools_sort_order", sortOrder);
    applySort();
    loadTools();
  });

  /* —— tag 筛选（会话内） —— */
  let activeTag = null;

  function renderTagFilter() {
    if (activeTag) {
      tagFilterName.textContent = activeTag;
      tagFilterRow.classList.remove("hidden");
    } else {
      tagFilterRow.classList.add("hidden");
    }
  }

  function toggleTag(name) {
    activeTag = activeTag === name ? null : name;
    renderTagFilter();
    loadTools();
    loadTagCloud(); // 同步 tag 云高亮
  }

  tagFilterClear.addEventListener("click", function () {
    activeTag = null;
    renderTagFilter();
    loadTools();
    loadTagCloud();
  });

  /* —— tag 云：全部 tag + 使用数量 —— */
  async function loadTagCloud() {
    try {
      const res = await fetch("/api/tools/tags");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      renderTagCloud(data.tags || []);
    } catch (err) {
      tagCloud.classList.add("hidden");
    }
  }

  function renderTagCloud(tags) {
    tagCloud.innerHTML = "";
    if (!tags.length) {
      tagCloud.classList.add("hidden");
      return;
    }
    tagCloud.classList.remove("hidden");
    tags.forEach(function (t) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "tools-tag" + (activeTag === t.name ? " is-active" : "");
      btn.title = t.name + "（" + t.count + " 个链接）";
      const nameEl = document.createElement("span");
      nameEl.textContent = t.name;
      const countEl = document.createElement("span");
      countEl.className = "tools-tag-count";
      countEl.textContent = t.count;
      btn.appendChild(nameEl);
      btn.appendChild(countEl);
      btn.addEventListener("click", function () {
        toggleTag(t.name);
      });
      tagCloud.appendChild(btn);
    });
  }

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
      let text;
      if (activeTag) {
        text = "没有匹配的链接";
      } else if (searchInput.value.trim()) {
        text = "没有匹配的链接";
      } else {
        text = "还没有链接，点右上角「添加链接」提交第一个";
      }
      showEmpty(text);
      return;
    }
    items.forEach(function (item) {
      const session = GalleryAuth.load();
      const wrap = document.createElement("div");
      wrap.className = "tools-card-wrap";
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
      if (item.tags && item.tags.length) {
        const tagRow = document.createElement("span");
        tagRow.className = "tools-tags-row";
        item.tags.forEach(function (tagName) {
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "tools-tag" + (activeTag === tagName ? " is-active" : "");
          btn.textContent = tagName;
          btn.addEventListener("click", function (e) {
            e.preventDefault();
            e.stopPropagation();
            toggleTag(tagName);
          });
          tagRow.appendChild(btn);
        });
        a.appendChild(tagRow);
      }
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
      meta.appendChild(document.createTextNode("由 " + (item.created_by_name || item.created_by) + " 提交 · "));
      const clicksEl = document.createElement("span");
      clicksEl.className = "tools-clicks";
      clicksEl.title = "点击次数";
      clicksEl.appendChild(GalleryIcons.svgEl("eye"));
      const clicksNum = document.createElement("span");
      clicksNum.className = "tools-clicks-num";
      clicksNum.textContent = item.click_count || 0;
      clicksEl.appendChild(clicksNum);
      meta.appendChild(clicksEl);
      a.appendChild(meta);
      // 点击计数：best-effort，不阻塞跳转
      a.addEventListener("click", function () {
        fetch("/api/tools/" + item.id + "/click", { method: "POST" })
          .then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            if (d && typeof d.clicks === "number") clicksNum.textContent = d.clicks;
          })
          .catch(function () {});
      });
      wrap.appendChild(a);
      if (session && String(item.created_by) === String(session.user_id)) {
        const edit = document.createElement("button");
        edit.type = "button";
        edit.className = "tools-edit";
        edit.title = "编辑";
        edit.setAttribute("aria-label", "编辑");
        edit.innerHTML = GalleryIcons.svgHTML("pencil");
        edit.addEventListener("click", function () {
          openAddDialog(item);
        });
        wrap.appendChild(edit);
        const del = document.createElement("button");
        del.type = "button";
        del.className = "tools-del";
        del.title = "删除";
        del.setAttribute("aria-label", "删除");
        del.innerHTML = GalleryIcons.svgHTML("trash");
        del.addEventListener("click", async function () {
          if (!confirm(`确定删除「${item.title}」？`)) return;
          try {
            const res = await fetch("/api/tools/" + item.id, {
              method: "DELETE",
              headers: GalleryAuth.headers(),
            });
            if (res.status === 401) {
              const dlg = GalleryAuth.ensureLoginDialog();
              if (typeof dlg.showModal === "function") dlg.showModal();
              return;
            }
            if (!res.ok) {
              const data = await res.json().catch(() => ({}));
              alert(data.detail || "删除失败");
              return;
            }
            loadTools();
            loadTagCloud();
          } catch (err) {
            alert("网络错误，请重试");
          }
        });
        wrap.appendChild(del);
      }
      toolList.appendChild(wrap);
    });
  }

  /* —— 数据 —— */
  async function loadTools() {
    const q = searchInput.value.trim();
    let url = "/api/tools?q=" + encodeURIComponent(q) +
      "&sort=" + encodeURIComponent(sortDim) +
      "&order=" + encodeURIComponent(sortOrder);
    if (activeTag) url += "&tag=" + encodeURIComponent(activeTag);
    try {
      const res = await fetch(url, {
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

  /* —— 添加/编辑链接 —— */
  let editingId = null;

  function openAddDialog(item) {
    editingId = item ? item.id : null;
    addDialogTitle.textContent = item ? "编辑链接" : "添加链接";
    addTitle.value = item ? item.title : "";
    addDesc.value = item ? (item.description || "") : "";
    addUrl.value = item ? item.url : "";
    addTags.value = item ? (item.tags || []).join(", ") : "";
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
        loadTools();
        loadTagCloud();
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
    const seen = {};
    const tags = [];
    addTags.value.split(/[,，]/).forEach(function (raw) {
      const name = raw.trim();
      if (name && !seen[name]) {
        seen[name] = true;
        tags.push(name);
      }
    });
    const payload = {
      title: addTitle.value.trim(),
      description: addDesc.value.trim(),
      url: addUrl.value.trim(),
      tags: tags,
    };
    const apiPath = editingId ? "/api/tools/" + editingId : "/api/tools";
    const method = editingId ? "PUT" : "POST";
    try {
      const res = await fetch(apiPath, {
        method: method,
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
      editingId = null;
      loadTools();
      loadTagCloud();
    } catch (err) {
      addMsg.textContent = "网络错误，请重试";
      addMsg.classList.remove("hidden");
    }
  });

  /* —— 初始化 —— */
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadNav();
  applyView();
  applySort();
  renderTagFilter();
  loadTools();
  loadTagCloud();
})();
