/* 议事厅列表页 */

(function () {
  "use strict";

  const list = document.getElementById("list");
  const sentinel = document.getElementById("sentinel");
  const filterBar = document.getElementById("filterBar");
  const tagNav = document.getElementById("tagNav");

  const TYPE_LABEL = { post: "长文", announce: "公告", poll: "投票" };

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function fmtTime(ts) {
    const d = new Date(String(ts).replace(" ", "T"));
    const pad = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate())
      + " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function getTag() {
    const u = new URL(location.href);
    return u.searchParams.get("tag");
  }
  function setTag(t) {
    const u = new URL(location.href);
    if (t) u.searchParams.set("tag", t); else u.searchParams.delete("tag");
    location.href = u.toString();
  }

  async function loadTags() {
    const res = await fetch("/api/forum/tags", { headers: GalleryAuth.headers() });
    if (!res.ok) return;
    const data = await res.json();
    tagNav.innerHTML = "";
    const all = document.createElement("a");
    all.href = "/forum";
    all.className = "forum-tag";
    all.textContent = "全部";
    tagNav.appendChild(all);
    (data.tags || []).forEach(function (t) {
      const a = document.createElement("a");
      a.href = "/forum?tag=" + encodeURIComponent(t.name);
      a.className = "forum-tag";
      a.textContent = `${t.name} (${t.post_count})`;
      tagNav.appendChild(a);
    });
  }

  async function loadList(cursor) {
    const tag = getTag();
    if (tag) {
      filterBar.textContent = `tag 过滤：${tag}（` +
        `<a class="forum-link" href="/forum">清除</a>）`;
    } else {
      filterBar.textContent = "";
    }
    const params = new URLSearchParams({ limit: "20" });
    if (tag) params.set("tag", tag);
    if (cursor) params.set("cursor", String(cursor));
    try {
      const res = await fetch("/api/forum/posts?" + params.toString(), { headers: GalleryAuth.headers() });
      if (!res.ok) { sentinel.textContent = "加载失败"; return; }
      const data = await res.json();
      if (!cursor) list.innerHTML = "";
      if (!data.items || data.items.length === 0) {
        if (!cursor) list.innerHTML = '<p class="forum-empty">还没有帖子，<a class="forum-link" href="/forum/new">发第一篇</a></p>';
        sentinel.textContent = data.next_cursor ? "加载更多…" : "— 已经到底了 —";
        return;
      }
      const frag = document.createDocumentFragment();
      data.items.forEach(function (it) {
        const div = document.createElement("div");
        div.className = "forum-item is-" + it.type;
        const typeLabel = TYPE_LABEL[it.type] || it.type;
        const title = document.createElement("a");
        title.className = "forum-title";
        title.href = "/forum/" + it.id;
        title.textContent = it.title;
        const head = document.createElement("div");
        head.className = "forum-item-head";
        const type = document.createElement("span");
        type.className = "forum-type";
        type.textContent = typeLabel;
        head.appendChild(type);
        head.appendChild(title);
        div.appendChild(head);
        const meta = document.createElement("div");
        meta.className = "forum-meta";
        if (it.author_avatar) {
          const av = document.createElement("img");
          av.className = "tl-avatar forum-avatar";
          av.src = it.author_avatar;
          av.alt = "";
          av.onerror = function () { av.style.display = "none"; };
          meta.appendChild(av);
        }
        const metaText = document.createElement("span");
        metaText.textContent = (it.author_name || it.author_user_id) + " · " + fmtTime(it.created_at) +
          (it.poll_deadline ? " · 截止 " + it.poll_deadline : "");
        meta.appendChild(metaText);
        div.appendChild(meta);
        frag.appendChild(div);
      });
      list.appendChild(frag);
      window.__nextCursor = data.next_cursor;
      sentinel.textContent = data.next_cursor ? "加载更多…" : "— 已经到底了 —";
    } catch (e) {
      sentinel.textContent = "加载失败：" + e.message;
    }
  }

  function initObserver() {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting && window.__nextCursor) {
        loadList(window.__nextCursor);
      }
    }, { rootMargin: "400px" });
    io.observe(sentinel);
  }

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadTags();
  loadList();
  initObserver();
})();
