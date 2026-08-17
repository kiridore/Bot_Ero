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
    if (doc.type === "text") {
      // Tiptap 的加粗/斜体/删除线/行内代码是 text 节点上的 marks，需逐层包裹
      let t = escText(doc.text || "");
      (doc.marks || []).forEach(function (m) {
        if (!m || !m.type) return;
        switch (m.type) {
          case "bold": t = "<strong>" + t + "</strong>"; break;
          case "italic": t = "<em>" + t + "</em>"; break;
          case "strike": t = "<s>" + t + "</s>"; break;
          case "code": t = "<code>" + t + "</code>"; break;
        }
      });
      return t;
    }
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

  async function submitVote(pollId, optionIds) {
    const res = await fetch(`/api/forum/posts/${postId()}/vote`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ poll_id: pollId, option_ids: optionIds }),
    });
    if (res.ok) { location.reload(); return; }
    const err = await res.json().catch(function () { return {}; });
    showMsg("投票失败：" + (err.detail || res.status), false);
  }

  function renderPoll(post) {
    if (post.type !== "poll") return;
    pollSection.style.display = "";
    pollOptionsEl.innerHTML = "";
    const closed = post.status !== "open";
    (post.polls || []).forEach(function (poll) {
      const block = document.createElement("div");
      block.className = "forum-poll-block";
      block.dataset.reveal = "";

      // 子投票头：问题 + 单选/多选徽标
      const head = document.createElement("div");
      head.className = "forum-poll-block-head";
      const q = document.createElement("h4");
      q.className = "forum-poll-title";
      q.textContent = poll.title || "投票";
      const badge = document.createElement("span");
      badge.className = "forum-poll-mode-badge" + (poll.allow_multi ? " is-multi" : "");
      badge.textContent = poll.allow_multi ? "多选" : "单选";
      head.append(q, badge);
      block.appendChild(head);

      const total = (poll.options || []).reduce(function (s, o) { return s + (o.count || 0); }, 0);
      const mine = poll.my_vote || [];
      const hasVoted = mine.length > 0;
      const pctOf = function (n) { return total ? Math.round((n / total) * 100) : 0; };

      if (poll.allow_multi) {
        // 多选：复选框 + 提交按钮
        const optList = document.createElement("div");
        optList.className = "forum-poll-opts";
        (poll.options || []).forEach(function (o) {
          const row = document.createElement("label");
          row.className = "forum-poll-option forum-poll-check";
          const cb = document.createElement("input");
          cb.type = "checkbox";
          cb.value = String(o.id);
          cb.disabled = closed || hasVoted;
          if (mine.indexOf(o.id) !== -1) cb.checked = true;
          const label = document.createElement("span");
          label.className = "forum-poll-check-label";
          label.textContent = o.text;
          const cnt = document.createElement("span");
          cnt.className = "forum-poll-result" + (mine.indexOf(o.id) !== -1 ? " is-mine" : "");
          cnt.textContent = `${o.count} 票（${pctOf(o.count)}%）`;
          row.append(cb, label, cnt);
          optList.appendChild(row);
        });
        block.appendChild(optList);
        if (!closed && !hasVoted) {
          const submit = document.createElement("button");
          submit.type = "button";
          submit.className = "forum-btn";
          submit.textContent = "提交投票";
          submit.addEventListener("click", async function () {
            const selected = [];
            optList.querySelectorAll("input[type=checkbox]:checked").forEach(function (c) {
              selected.push(Number(c.value));
            });
            if (!selected.length) { showMsg("请至少选择一个选项", false); return; }
            await submitVote(poll.id, selected);
          });
          block.appendChild(submit);
        }
      } else {
        // 单选：点击即投
        (poll.options || []).forEach(function (o) {
          const row = document.createElement("div");
          row.className = "forum-poll-option";
          const btn = document.createElement("button");
          btn.type = "button";
          btn.className = "forum-btn" + (closed || hasVoted ? " forum-btn-secondary" : "");
          btn.textContent = (closed || hasVoted ? (mine.indexOf(o.id) !== -1 ? "✓ " : "") : "") + o.text;
          btn.disabled = closed || hasVoted;
          btn.style.flex = "1";
          btn.addEventListener("click", async function () {
            if (hasVoted) return;
            await submitVote(poll.id, [o.id]);
          });
          row.appendChild(btn);
          const cnt = document.createElement("span");
          cnt.className = "forum-poll-result" + (mine.indexOf(o.id) !== -1 ? " is-mine" : "");
          if (mine.indexOf(o.id) !== -1) cnt.classList.add("motion-pop");
          cnt.textContent = `${o.count} 票（${pctOf(o.count)}%）`;
          row.appendChild(cnt);
          block.appendChild(row);
        });
      }
      pollOptionsEl.appendChild(block);
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
