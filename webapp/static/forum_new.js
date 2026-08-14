/* 议事厅发布页：Tiptap 富文本编辑器 + 表单提交。Tiptap 通过 esm.sh 加载。 */

(async function () {
  "use strict";

  // 编辑模式：/forum/new?id=<post_id>
  const editingId = (function () {
    const m = location.search.match(/[?&]id=(\d+)/);
    return m ? Number(m[1]) : null;
  })();

  const msg = document.getElementById("msg");
  const typeSelect = document.getElementById("type");
  const bodySection = document.getElementById("body-section");
  const pollSection = document.getElementById("poll-section");
  const pollOptions = document.getElementById("poll-options");
  const bodyHidden = document.getElementById("body_json");
  const form = document.getElementById("compose");

  // 回车误触防护：title/tags 是单行文本输入，Enter 会触发表单隐式提交
  ["title", "tags"].forEach(function (id) {
    document.getElementById(id).addEventListener("keydown", function (e) {
      if (e.key === "Enter") e.preventDefault();
    });
  });

  function showMsg(text, ok) {
    msg.innerHTML = "";
    const d = document.createElement("div");
    d.className = "forum-msg" + (ok ? "" : " is-error");
    d.textContent = text;
    msg.appendChild(d);
  }

  // 投票选项动态增减
  function addOption(value) {
    const row = document.createElement("div");
    row.className = "forum-poll-option";
    const input = document.createElement("input");
    input.type = "text";
    input.name = "poll_option";
    input.value = value || "";
    input.maxLength = 200;
    input.placeholder = "选项文本";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "forum-btn-secondary";
    btn.textContent = "×";
    btn.addEventListener("click", function () { row.remove(); });
    row.append(input, btn);
    pollOptions.appendChild(row);
  }
  addOption("选项A");
  addOption("选项B");
  document.getElementById("add-option").addEventListener("click", function () { addOption(""); });

  // 类型切换显示
  function updateSections() {
    const t = typeSelect.value;
    pollSection.style.display = t === "poll" ? "" : "none";
    bodySection.style.display = t === "poll" ? "none" : "";
  }
  typeSelect.addEventListener("change", updateSections);
  updateSections();

  // Tiptap 编辑器
  let editor = null;
  try {
    const { Editor } = await import("https://esm.sh/@tiptap/core@2.6.0");
    const { default: StarterKit } = await import("https://esm.sh/@tiptap/starter-kit@2.6.0");
    const { default: Image } = await import("https://esm.sh/@tiptap/extension-image@2.6.0");
    const toolbar = document.createElement("div");
    toolbar.className = "forum-editor-toolbar";
    const content = document.createElement("div");
    content.className = "forum-editor-content";
    const wrap = document.createElement("div");
    wrap.className = "forum-editor";
    const editorRoot = document.getElementById("editor");
    editorRoot.innerHTML = "";
    [
      ["B", "粗体", function () { return editor.chain().focus().toggleBold().run(); }],
      ["I", "斜体", function () { return editor.chain().focus().toggleItalic().run(); }],
      ["H2", "标题", function () { return editor.chain().focus().toggleHeading({ level: 2 }).run(); }],
      ["UL", "列表", function () { return editor.chain().focus().toggleBulletList().run(); }],
      ["OL", "有序", function () { return editor.chain().focus().toggleOrderedList().run(); }],
      ["\"", "引用", function () { return editor.chain().focus().toggleBlockquote().run(); }],
      ["<>", "代码", function () { return editor.chain().focus().toggleCode().run(); }],
    ].forEach(function (b) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = b[0];
      btn.title = b[1];
      btn.addEventListener("click", function (e) { e.preventDefault(); b[2](); });
      toolbar.appendChild(btn);
    });
    // 图片插入：上传本地文件到服务器后插入正文
    const imgBtn = document.createElement("button");
    imgBtn.type = "button";
    imgBtn.textContent = "IMG";
    imgBtn.title = "插入图片";
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.accept = "image/jpeg,image/png,image/webp,image/gif";
    fileInput.hidden = true;
    let uploading = false;
    imgBtn.addEventListener("click", function (e) { e.preventDefault(); fileInput.click(); });
    fileInput.addEventListener("change", async function () {
      const f = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (!f || uploading) return;
      uploading = true;
      try {
        const fd = new FormData();
        fd.append("file", f);
        const res = await fetch("/api/forum/images", {
          method: "POST",
          headers: GalleryAuth.headers(),
          body: fd,
        });
        if (res.status === 401) {
          const dlg = GalleryAuth.ensureLoginDialog();
          if (typeof dlg.showModal === "function") dlg.showModal();
          return;
        }
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          showMsg(data.detail || "图片上传失败", false);
          return;
        }
        const data = await res.json();
        editor.chain().focus().setImage({ src: data.url }).run();
      } catch (err) {
        showMsg("图片上传失败：" + err.message, false);
      } finally {
        uploading = false;
      }
    });
    toolbar.appendChild(imgBtn);
    toolbar.appendChild(fileInput);
    wrap.appendChild(toolbar);
    wrap.appendChild(content);
    editorRoot.appendChild(wrap);
    editor = new Editor({
      element: content,
      extensions: [StarterKit, Image],
      content: { type: "doc", content: [{ type: "paragraph" }] },
    });
    if (editingId) loadForEdit(editingId);
  } catch (e) {
    showMsg("Tiptap 加载失败（请检查网络或刷新重试）：" + e.message, false);
    if (editingId) loadForEdit(editingId);
  }

  GalleryAuth.renderAuth(document.getElementById("authArea"));

  // 编辑模式预填：?id= 加载帖子（类型/投票结构不可改，title/body/tags 可改）
  async function loadForEdit(id) {
    const res = await fetch(`/api/forum/posts/${id}`, { headers: GalleryAuth.headers() });
    if (!res.ok) {
      showMsg("加载帖子失败：" + res.status, false);
      return;
    }
    const post = await res.json();
    document.getElementById("pageTitle").textContent = "编辑帖子";
    document.getElementById("submitBtn").textContent = "保存修改";
    document.getElementById("title").value = post.title;
    document.getElementById("tags").value = (post.tags || []).join(", ");
    typeSelect.value = post.type;
    typeSelect.disabled = true; // 类型不可改
    updateSections();
    if (post.type === "poll") {
      // 选项只读展示，截止/匿名锁定
      pollOptions.innerHTML = "";
      (post.poll_options || []).forEach(function (o) { addOption(o.text); });
      pollOptions.querySelectorAll("input[name=poll_option]").forEach(function (i) { i.disabled = true; });
      document.getElementById("add-option").style.display = "none";
      document.getElementById("anonymous").disabled = true;
      const dl = document.getElementById("deadline");
      if (post.poll_deadline) {
        dl.value = post.poll_deadline.replace(" ", "T").slice(0, 16);
        dl.disabled = true;
      }
    }
    if (editor) {
      try {
        editor.commands.setContent(JSON.parse(post.body_json || "{}"));
      } catch (e) {
        editor.commands.setContent("");
      }
    } else if (post.type !== "poll") {
      showMsg("Tiptap 编辑器加载失败，无法编辑正文（请刷新重试）", false);
    }
  }

  // 提交
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    if (!GalleryAuth.isLoggedIn()) {
      const dlg = GalleryAuth.ensureLoginDialog();
      if (dlg && typeof dlg.showModal === "function") dlg.showModal();
      showMsg("请先登录", false);
      return;
    }
    const type = typeSelect.value;
    const title = document.getElementById("title").value.trim();
    if (!title) { showMsg("请输入标题", false); return; }
    const tags = document.getElementById("tags").value.split(/[,，]/).map(function (s) { return s.trim(); }).filter(Boolean);
    const body = editor ? JSON.stringify(editor.getJSON()) : "";
    if (editingId) {
      // 编辑模式：类型/投票结构不可改；投票帖不提交正文
      if (type !== "poll" && !editor) {
        showMsg("Tiptap 编辑器加载失败，无法编辑正文", false);
        return;
      }
      const payload = { title: title, tags: tags };
      if (type !== "poll") payload.body_json = body;
      showMsg("保存中…", true);
      try {
        const res = await fetch("/api/forum/posts/" + editingId, {
          method: "PATCH",
          headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
          body: JSON.stringify(payload),
        });
        if (!res.ok) {
          const err = await res.json().catch(function () { return {}; });
          showMsg("保存失败：" + (err.detail || res.status), false);
          return;
        }
        location.href = "/forum/" + editingId;
      } catch (e) {
        showMsg("保存失败：" + e.message, false);
      }
      return;
    }
    const payload = { type: type, title: title, body_json: body, tags: tags };
    if (type === "poll") {
      const opts = [];
      pollOptions.querySelectorAll("input[name=poll_option]").forEach(function (i) {
        const v = i.value.trim();
        if (v) opts.push({ text: v });
      });
      if (opts.length < 2) { showMsg("投票至少需要 2 个选项", false); return; }
      payload.polls = opts;
      payload.poll_anonymous = document.getElementById("anonymous").checked;
      const dl = document.getElementById("deadline").value;
      if (dl) {
        // datetime-local -> "YYYY-MM-DD HH:MM:SS"
        const d = new Date(dl);
        const pad = function (n) { return String(n).padStart(2, "0"); };
        payload.poll_deadline = d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
          " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":00";
      }
    }
    showMsg("发布中…", true);
    try {
      const res = await fetch("/api/forum/posts", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(function () { return {}; });
        showMsg("发布失败：" + (err.detail || res.status), false);
        return;
      }
      const data = await res.json();
      location.href = "/forum/" + data.id;
    } catch (e) {
      showMsg("发布失败：" + e.message, false);
    }
  });
})();
