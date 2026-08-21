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

  // —— 评论线程渲染（顶层 + 缩进回复串，两级） ——

  let replyTarget = null; // {id, name} | null；非空时 #commentForm 以回复模式提交

  function currentSession() {
    try { return GalleryAuth.load(); } catch (e) { return null; }
  }

  function setReplyTarget(c) {
    replyTarget = c;
    let chip = document.getElementById("replyChip");
    if (!c) {
      if (chip) chip.remove();
      return;
    }
    if (!chip) {
      chip = document.createElement("div");
      chip.id = "replyChip";
      chip.className = "forum-reply-chip";
      commentForm.parentNode.insertBefore(chip, commentForm);
    }
    chip.innerHTML = "";
    const label = document.createElement("span");
    label.textContent = "回复 @" + c.name + "：";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "forum-reply-chip-cancel";
    cancel.setAttribute("aria-label", "取消回复");
    cancel.textContent = "×";
    cancel.addEventListener("click", function () { setReplyTarget(null); });
    chip.append(label, cancel);
  }

  function startInlineEdit(c, bodyEl) {
    bodyEl.innerHTML = "";
    const ta = document.createElement("textarea");
    ta.rows = 3;
    ta.maxLength = 2000;
    ta.value = c.body_text;
    const save = document.createElement("button");
    save.type = "button";
    save.className = "forum-btn";
    save.textContent = "保存";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "forum-btn forum-btn-secondary";
    cancel.textContent = "取消";
    const row = document.createElement("div");
    row.className = "forum-edit-row";
    row.append(save, cancel);
    bodyEl.append(ta, row);
    ta.focus();

    cancel.addEventListener("click", function () {
      renderCommentBody(c, bodyEl);
    });
    save.addEventListener("click", async function () {
      const text = ta.value.trim();
      if (!text) return;
      const res = await fetch(`/api/forum/comments/${c.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
        body: JSON.stringify({ body_text: text }),
      });
      if (!res.ok) {
        const err = await res.json().catch(function () { return {}; });
        showMsg("编辑失败：" + (err.detail || res.status), false);
        return;
      }
      const data = await res.json();
      c.body_text = data.comment.body_text;
      c.edited_at = data.comment.edited_at;
      const item = bodyEl.closest(".forum-comment-item");
      if (item) item.replaceWith(renderCommentItem(c, currentSession()));
    });
  }

  function editedMark() {
    const m = document.createElement("em");
    m.className = "is-edited";
    m.textContent = " · 已编辑";
    return m;
  }

  function renderCommentBody(c, bodyEl) {
    bodyEl.innerHTML = "";
    if (c.status === "deleted") {
      bodyEl.classList.add("is-deleted");
      bodyEl.textContent = "该评论已删除";
      return;
    }
    bodyEl.classList.remove("is-deleted");
    bodyEl.textContent = c.body_text;
  }

  function buildCommentActions(c, session) {
    const actions = document.createElement("span");
    actions.className = "forum-comment-actions";
    if (session) {
      const reply = document.createElement("button");
      reply.type = "button";
      reply.textContent = "回复";
      reply.addEventListener("click", function () {
        setReplyTarget({ id: c.id, name: c.author_name || String(c.author_user_id) });
        commentText.focus();
      });
      actions.appendChild(reply);
    }
    if (session && String(c.author_user_id) === String(session.user_id) && c.status !== "deleted") {
      const edit = document.createElement("button");
      edit.type = "button";
      edit.textContent = "编辑";
      edit.addEventListener("click", function () {
        const item = actions.closest(".forum-comment-item");
        const bodyEl = item && item.querySelector(".forum-comment-body");
        if (bodyEl) startInlineEdit(c, bodyEl);
      });
      const del = document.createElement("button");
      del.type = "button";
      del.textContent = "删除";
      del.addEventListener("click", async function () {
        if (!confirm("确定删除这条评论？有回复时将保留回复链。")) return;
        const res = await fetch(`/api/forum/comments/${c.id}`, {
          method: "DELETE",
          headers: GalleryAuth.headers(),
        });
        if (res.ok) { loadComments(); return; }
        if (res.status === 401) {
          const dlg = GalleryAuth.ensureLoginDialog();
          if (typeof dlg.showModal === "function") dlg.showModal();
          return;
        }
        const err = await res.json().catch(function () { return {}; });
        showMsg("删除失败：" + (err.detail || res.status), false);
      });
      actions.append(edit, del);
    }
    return actions;
  }

  function renderCommentItem(c, session) {
    const div = document.createElement("div");
    div.className = "forum-comment-item";
    div.dataset.reveal = "";
    div.dataset.commentId = c.id;
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
    if (c.reply_to_name) {
      const rt = document.createElement("span");
      rt.className = "forum-reply-to";
      rt.textContent = " · 回复 @" + c.reply_to_name;
      metaText.appendChild(rt);
    }
    if (c.edited_at) metaText.appendChild(editedMark());
    meta.appendChild(metaText);
    meta.appendChild(buildCommentActions(c, session));
    const body = document.createElement("div");
    body.className = "forum-comment-body";
    renderCommentBody(c, body);
    div.append(meta, body);
    return div;
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
    const session = currentSession();
    (data.items || []).forEach(function (c) {
      commentsList.appendChild(renderCommentItem(c, session));
      if (c.replies && c.replies.length) {
        const replies = document.createElement("div");
        replies.className = "forum-comment-replies";
        c.replies.forEach(function (r) {
          replies.appendChild(renderCommentItem(r, session));
        });
        commentsList.appendChild(replies);
      }
    });
    commentCount.textContent = `(${data.total != null ? data.total : 0})`;
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
      body: JSON.stringify({ body_text: text, parent_id: replyTarget ? replyTarget.id : null }),
    });
    if (!res.ok) {
      const err = await res.json().catch(function () { return {}; });
      showMsg("评论失败：" + (err.detail || res.status), false);
      return;
    }
    commentText.value = "";
    setReplyTarget(null);
    loadComments();
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  loadPost();
  loadComments();
  initObserver();
})();
