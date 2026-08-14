/* 议事厅详情页：Tiptap 渲染正文 + 评论列表 + 投票 UI */

(async function () {
  "use strict";

  const titleEl = document.getElementById("postTitle");
  const metaEl = document.getElementById("postMeta");
  const bodyEl = document.getElementById("postBody");
  const pollSection = document.getElementById("pollSection");
  const pollOptionsEl = document.getElementById("pollOptions");
  const commentCount = document.getElementById("commentCount");
  const commentsList = document.getElementById("commentsList");
  const commentForm = document.getElementById("commentForm");
  const commentText = document.getElementById("commentText");
  const msg = document.getElementById("msg");
  const sentinel = document.getElementById("sentinel");

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

  function showMsg(text, ok) {
    msg.innerHTML = "";
    const d = document.createElement("div");
    d.className = "forum-msg" + (ok ? "" : " is-error");
    d.textContent = text;
    msg.appendChild(d);
  }

  function postId() {
    const m = location.pathname.match(/\/forum\/(\d+)/);
    return m ? Number(m[1]) : null;
  }

  // 渲染 Tiptap JSON -> HTML（仅长文/公告用）
  function renderTiptap(doc) {
    if (!doc || !doc.type) return "";
    const escText = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    }); };
    if (doc.type === "text") return escText(doc.text || "");
    const children = Array.isArray(doc.content) ? doc.content.map(renderTiptap).join("") : "";
    switch (doc.type) {
      case "doc": return children;
      case "paragraph": return "<p>" + children + "</p>";
      case "heading": return "<h2>" + children + "</h2>";
      case "bulletList": return "<ul>" + children + "</ul>";
      case "orderedList": return "<ol>" + children + "</ol>";
      case "listItem": return "<li>" + children + "</li>";
      case "blockquote": return "<blockquote>" + children + "</blockquote>";
      case "codeBlock": return "<pre><code>" + children + "</code></pre>";
      case "hardBreak": return "<br/>";
      case "image": {
        const src = escText((doc.attrs && doc.attrs.src) || "");
        const alt = escText((doc.attrs && doc.attrs.alt) || "");
        return '<img class="forum-img" src="' + src + '" alt="' + alt + '">';
      }
      default: return children;
    }
  }

  async function loadComments(cursor) {
    const params = new URLSearchParams({ limit: "30" });
    if (cursor) params.set("cursor", String(cursor));
    const res = await fetch(`/api/forum/posts/${postId()}/comments?` + params.toString(), {
      headers: GalleryAuth.headers(),
    });
    if (!res.ok) return;
    const data = await res.json();
    if (!cursor) commentsList.innerHTML = "";
    (data.items || []).forEach(function (c) {
      const div = document.createElement("div");
      div.className = "forum-comment-item";
      div.dataset.reveal = "";
      const meta = document.createElement("div");
      meta.className = "forum-comment-meta";
      if (c.author_avatar) {
        const av = document.createElement("img");
        av.className = "tl-avatar forum-avatar";
        av.src = c.author_avatar;
        av.alt = "";
        av.onerror = function () { av.style.display = "none"; };
        meta.appendChild(av);
      }
      const metaText = document.createElement("span");
      metaText.textContent = (c.author_name || c.author_user_id) + " · " + fmtTime(c.created_at);
      meta.appendChild(metaText);
      const body = document.createElement("div");
      body.className = "forum-comment-body";
      body.textContent = c.body_text;
      div.appendChild(meta);
      div.appendChild(body);
      commentsList.appendChild(div);
    });
    commentCount.textContent = `(${data.items ? data.items.length : 0})`;
    window.__nextCommentCursor = data.next_cursor;
    sentinel.textContent = data.next_cursor ? "加载更多评论…" : "";
  }

  function initObserver() {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting && window.__nextCommentCursor) {
        loadComments(window.__nextCommentCursor);
      }
    }, { rootMargin: "400px" });
    io.observe(sentinel);
  }

  function renderPoll(post) {
    if (post.type !== "poll") return;
    pollSection.style.display = "";
    pollOptionsEl.innerHTML = "";
    const counts = post.vote_counts || [];
    const total = counts.reduce(function (s, r) { return s + (r.count || 0); }, 0);
    const mine = post.my_vote;
    const closed = post.status !== "open";
    counts.forEach(function (r) {
      const row = document.createElement("div");
      row.className = "forum-poll-option";
      row.dataset.reveal = "";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "forum-btn" + (closed || mine ? " forum-btn-secondary" : "");
      btn.textContent = (closed || mine ? (mine === r.id ? "✓ " : "") : "") + r.text;
      btn.disabled = closed || !!mine;
      btn.style.flex = "1";
      btn.addEventListener("click", async function () {
        if (mine) return;
        const r2 = await fetch(`/api/forum/posts/${post.id}/vote`, {
          method: "POST",
          headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
          body: JSON.stringify({ option_id: r.id }),
        });
        if (r2.ok) location.reload();
        else {
          const err = await r2.json().catch(function () { return {}; });
          showMsg("投票失败：" + (err.detail || r2.status), false);
        }
      });
      row.appendChild(btn);
      const cnt = document.createElement("span");
      cnt.className = "forum-poll-result" + (mine === r.id ? " is-mine" : "");
      if (mine === r.id) cnt.classList.add("motion-pop");
      const pct = total ? Math.round((r.count / total) * 100) : 0;
      cnt.textContent = `${r.count} 票（${pct}%）` + (closed ? " · 已结束" : "");
      row.appendChild(cnt);
      pollOptionsEl.appendChild(row);
    });
    if (post.poll_deadline && !closed) {
      const dl = document.createElement("div");
      dl.className = "forum-meta-bar";
      dl.textContent = "截止时间：" + post.poll_deadline;
      pollOptionsEl.appendChild(dl);
    }
  }

  async function loadPost() {
    const res = await fetch(`/api/forum/posts/${postId()}`, { headers: GalleryAuth.headers() });
    if (!res.ok) { showMsg("加载失败：" + (await res.text()), false); return; }
    const post = await res.json();
    titleEl.textContent = post.title;
    const avHtml = post.author_avatar
      ? `<img class="tl-avatar forum-avatar" src="${esc(post.author_avatar)}" alt="" onerror="this.style.display='none'"> `
      : "";
    metaEl.innerHTML = `${esc(post.type)} · ${avHtml}${esc(post.author_name || post.author_user_id)} · ${fmtTime(post.created_at)}` +
      (post.tags && post.tags.length ? ` · ${post.tags.map(function (t) { return `<a class="forum-link" href="/forum?tag=${encodeURIComponent(t)}">${esc(t)}</a>`; }).join(" · ")}` : "");
    // 正文：Tiptap JSON 渲染（仅 post/announce）
    if (post.body_json && post.body_json.trim()) {
      try {
        const doc = JSON.parse(post.body_json);
        bodyEl.innerHTML = renderTiptap(doc);
      } catch (e) {
        bodyEl.textContent = post.body_json;
      }
    } else {
      bodyEl.innerHTML = "<p class=\"muted\">（无正文）</p>";
    }
    renderPoll(post);
    // 作者专属操作：编辑/删除（仅本人可见）
    const session = GalleryAuth.load();
    const mine = session && String(post.author_user_id) === String(session.user_id);
    const actions = document.getElementById("postActions");
    if (actions && mine) {
      actions.hidden = false;
      document.getElementById("editPostBtn").addEventListener("click", function () {
        location.href = "/forum/new?id=" + post.id;
      });
      document.getElementById("deletePostBtn").addEventListener("click", async function () {
        if (!confirm(`确定删除「${post.title}」？帖子与全部评论将一并删除，不可恢复。`)) return;
        const res = await fetch(`/api/forum/posts/${post.id}`, {
          method: "DELETE",
          headers: GalleryAuth.headers(),
        });
        if (res.ok) { location.href = "/forum"; return; }
        if (res.status === 401) {
          const dlg = GalleryAuth.ensureLoginDialog();
          if (typeof dlg.showModal === "function") dlg.showModal();
          return;
        }
        const err = await res.json().catch(function () { return {}; });
        showMsg("删除失败：" + (err.detail || res.status), false);
      });
    }
  }

  commentForm.addEventListener("submit", async function (e) {
    e.preventDefault();
    const text = commentText.value.trim();
    if (!text) return;
    const res = await fetch(`/api/forum/posts/${postId()}/comments`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ body_text: text }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      showMsg("评论失败：" + (err.detail || res.status), false);
      return;
    }
    commentText.value = "";
    loadComments();
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadPost();
  loadComments();
  initObserver();
})();
