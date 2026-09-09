(function () {
  "use strict";

  // 共享富文本模块（议事厅与活动描述共用）：
  // - RichText.render(doc)：TipTap JSON -> HTML（白名单节点类型，全程转义，无 XSS）
  // - RichText.mount(container, opts)：挂载 Tiptap 编辑器（esm.sh 12s 超时降级；opts.upload 提供时才插入图片按钮）
  // 用法见 forum_new.js / activities_new.js / activities_manage.js。

  function escText(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function render(doc) {
    if (!doc || !doc.type) return "";
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
    const children = Array.isArray(doc.content) ? doc.content.map(render).join("") : "";
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

  function withTimeout(promise, label) {
    return Promise.race([
      promise,
      new Promise(function (_, reject) {
        setTimeout(function () { reject(new Error(label + " 加载超时（12s）")); }, 12000);
      }),
    ]);
  }

  // opts: { content: TipTap doc | null, upload: async(fileOption)->url | null, onReady(editor), onError(err) }
  async function mount(container, opts) {
    try {
      const { Editor } = await withTimeout(import("https://esm.sh/@tiptap/core@2.6.0"), "Tiptap core");
      const { default: StarterKit } = await withTimeout(import("https://esm.sh/@tiptap/starter-kit@2.6.0"), "StarterKit");
      const extensions = [StarterKit];
      if (opts.upload) {
        const { default: Image } = await withTimeout(import("https://esm.sh/@tiptap/extension-image@2.6.0"), "Image");
        extensions.push(Image);
      }
      const toolbar = document.createElement("div");
      toolbar.className = "richtext-toolbar";
      const content = document.createElement("div");
      content.className = "richtext-content";
      const wrap = document.createElement("div");
      wrap.className = "richtext-editor";
      const editor = new Editor({ element: content, extensions: extensions, content: opts.content || { type: "doc", content: [{ type: "paragraph" }] } });
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
      if (opts.upload) {
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
            const url = await opts.upload(f);
            editor.chain().focus().setImage({ src: url }).run();
          } catch (err) {
            if (opts.onError) opts.onError(err);
          } finally {
            uploading = false;
          }
        });
        toolbar.appendChild(imgBtn);
        toolbar.appendChild(fileInput);
      }
      wrap.appendChild(toolbar);
      wrap.appendChild(content);
      container.innerHTML = "";
      container.appendChild(wrap);
      if (opts.onReady) opts.onReady(editor);
      return editor;
    } catch (e) {
      if (opts.onError) opts.onError(e);
      return null;
    }
  }

  function docFrom(value) {
    // 历史纯文本（旧版描述）→ 最小 doc；合法 TipTap JSON 原样返回
    try {
      const d = JSON.parse(value);
      if (d && d.type) return d;
    } catch (e) { /* ignore */ }
    return {
      type: "doc",
      content: (value || "").split("\n").filter(function (s) { return s.trim(); })
        .map(function (p) { return { type: "paragraph", content: [{ type: "text", text: p }] }; }),
    };
  }

  function docText(node) {
    if (!node) return "";
    if (node.type === "text") return node.text || "";
    return (Array.isArray(node.content) ? node.content.map(docText).join(" ") : "").trim();
  }

  window.RichText = { render: render, mount: mount, docFrom: docFrom, docText: docText };
})();
