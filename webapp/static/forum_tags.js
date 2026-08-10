/* 议事厅 tag 管理页 */

(function () {
  "use strict";

  const list = document.getElementById("tagList");
  const form = document.getElementById("tagForm");
  const nameInput = document.getElementById("tagName");
  const msg = document.getElementById("msg");

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function showMsg(text, ok) {
    msg.innerHTML = "";
    const d = document.createElement("div");
    d.className = "forum-msg" + (ok ? "" : " is-error");
    d.textContent = text;
    msg.appendChild(d);
  }

  async function loadList() {
    const res = await fetch("/api/forum/tags", { headers: GalleryAuth.headers() });
    if (!res.ok) { showMsg("加载失败", false); return; }
    const data = await res.json();
    list.innerHTML = "";
    if (!data.tags || data.tags.length === 0) {
      list.innerHTML = '<p class="forum-empty">还没有 tag</p>';
      return;
    }
    data.tags.forEach(function (t) {
      const div = document.createElement("div");
      div.className = "forum-item";
      const head = document.createElement("div");
      head.className = "forum-item-head";
      const name = document.createElement("a");
      name.className = "forum-title";
      name.href = "/forum?tag=" + encodeURIComponent(t.name);
      name.textContent = t.name;
      head.appendChild(name);
      div.appendChild(head);
      const meta = document.createElement("div");
      meta.className = "forum-meta";
      meta.textContent = `使用 ${t.post_count} 次 · 创建 ${t.created_at}`;
      div.appendChild(meta);
      list.appendChild(div);
    });
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const name = nameInput.value.trim();
    if (!name) return;
    const res = await fetch("/api/forum/tags", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ name: name }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      showMsg("创建失败：" + (err.detail || res.status), false);
      return;
    }
    nameInput.value = "";
    showMsg("已创建", true);
    loadList();
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadList();
})();
