// 最小 DOM stub 验证议事厅详情页：作者可见编辑/删除按钮，非作者隐藏

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {}, dataset: {}, href: undefined,
    value: "", disabled: false, hidden: undefined, parentNode: null, _ls: {},
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener(t, fn) { (this._ls[t] = this._ls[t] || []).push(fn); },
    fire(t, ev) { (this._ls[t] || []).forEach((f) => f(ev || { target: this, preventDefault() {} })); },
    remove() { this._removed = true; },
    replaceWith(el) { this._replacedBy = el; },
    closest() { return null; },
    focus() {},
    appendChild(c) { c.parentNode = this; this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => { c.parentNode = this; }); this.children.push(...cs); },
    insertBefore(c) { c.parentNode = this; this.children.push(c); return c; },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    classList: { add() {}, remove() {}, contains() { return false; } },
  };
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

// 每次场景重建全局 DOM 并 eval 真实脚本
function runScenario(sessionUid, authorUid, payloadOverride, commentsOverride) {
  const els = {};
  global.location = {
    hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/forum/1",
    pathname: "/forum/1",
  };
  global.window = {};
  global.document = {
    createElement: (t) => makeEl(t),
    createDocumentFragment: () => makeEl("fragment"),
    getElementById: (id) => els[id]
      || (els.commentForm ? els.commentForm.parentNode.children.find((c) => c.id === id) : null)
      || null,
    body: { appendChild(c) { els[c.id] = c; } },
    head: { appendChild() {} },
    cookie: "",
  };
  global.localStorage = (() => { let m = {}; return {
    getItem: (k) => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: (k) => { delete m[k]; },
  }; })();
  if (sessionUid) {
    global.localStorage.setItem("botero_gallery_session",
      JSON.stringify({ user_id: sessionUid, token: "t", display_name: "测试" }));
  }

  ["postTitle", "postMeta", "postBody", "pollSection", "pollOptions", "commentCount",
   "commentsList", "commentForm", "commentText", "msg", "sentinel",
   "postActions", "editPostBtn", "deletePostBtn", "authArea"].forEach((id) => {
    els[id] = makeEl("div");
    els[id].id = id;
  });
  els.commentForm.parentNode = makeEl("div");

  const postPayload = Object.assign({
    id: 1, type: "post", title: "测试帖", body_json: "", status: "open",
    author_user_id: authorUid, author_name: "作者", author_avatar: "",
    created_at: "2026-08-14 10:00:00", updated_at: "2026-08-14 10:00:00",
    tags: [], polls: [],
  }, payloadOverride || {});
  global.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/comments")) return {
      ok: true, status: 200,
      json: async () => commentsOverride || { items: [], next_cursor: null, total: 0 },
    };
    if (u.includes("/api/forum/posts/")) return { ok: true, status: 200, json: async () => postPayload };
    return { ok: false, status: 404, json: async () => ({}) };
  };

  const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
  eval(authSrc);
  global.GalleryAuth = window.GalleryAuth;

  const detailSrc = fs.readFileSync("webapp/static/forum_detail.js", "utf8");
  eval(detailSrc);
  return els;
}

(async () => {
  // 场景 1：本人查看 → 显示编辑/删除
  const els1 = runScenario("1057613133", "1057613133");
  await new Promise((r) => setTimeout(r, 120));
  check("作者查看：postActions 显示（按钮已接线）", els1.postActions.hidden === false);

  // 场景 2：他人查看 → 隐藏
  const els2 = runScenario("3915014383", "1057613133");
  await new Promise((r) => setTimeout(r, 120));
  check("他人查看：postActions 保持隐藏", els2.postActions.hidden !== false);

  // 场景 3：未登录 → 隐藏
  const els3 = runScenario(null, "1057613133");
  await new Promise((r) => setTimeout(r, 120));
  check("未登录：postActions 保持隐藏", els3.postActions.hidden !== false);

  // 场景 4：富文本渲染 — marks（加粗/斜体/删除线/行内代码）与结构节点
  const richBody = JSON.stringify({
    type: "doc", content: [
      { type: "paragraph", content: [{ type: "text", text: "加粗", marks: [{ type: "bold" }] }] },
      { type: "paragraph", content: [{ type: "text", text: "斜体", marks: [{ type: "italic" }] }] },
      { type: "paragraph", content: [{ type: "text", text: "划线", marks: [{ type: "strike" }] }] },
      { type: "paragraph", content: [{ type: "text", text: "行内代码", marks: [{ type: "code" }] }] },
      { type: "paragraph", content: [{ type: "text", text: "粗斜", marks: [{ type: "bold" }, { type: "italic" }] }] },
      { type: "heading", attrs: { level: 2 }, content: [{ type: "text", text: "小标题" }] },
      { type: "bulletList", content: [{ type: "listItem", content: [{ type: "paragraph", content: [{ type: "text", text: "列表项" }] }] }] },
      { type: "paragraph", content: [{ type: "text", text: "<b>原样</b>&" }] },
    ],
  });
  const els4 = runScenario("1057613133", "1057613133", { body_json: richBody });
  await new Promise((r) => setTimeout(r, 120));
  const html = els4.postBody.innerHTML;
  check("加粗渲染为 <strong>", html.includes("<strong>加粗</strong>"));
  check("斜体渲染为 <em>", html.includes("<em>斜体</em>"));
  check("删除线渲染为 <s>", html.includes("<s>划线</s>"));
  check("行内代码渲染为 <code>", html.includes("<code>行内代码</code>"));
  check("多重 marks 叠加", html.includes("<em><strong>粗斜</strong></em>"));
  check("标题渲染为 <h2>", html.includes("<h2>小标题</h2>"));
  check("列表渲染为 ul/li/p", html.includes("<ul><li><p>列表项</p></li></ul>"));
  check("正文 HTML 仍被转义（防 XSS）", html.includes("&lt;b&gt;原样&lt;/b&gt;&amp;"));

  // 场景 5：评论线程渲染 — 顶层 + 缩进回复串 + 占位 + 操作按钮显隐
  const A_UID = "1057613133", B_UID = "3915014383";
  const threadPayload = {
    items: [
      {
        id: 1, post_id: 1, author_user_id: A_UID, body_text: "顶层评论", status: "open",
        created_at: "2026-08-14 10:00:00", edited_at: null, parent_id: null, root_id: null,
        author_name: "作者", author_avatar: "",
        replies: [
          {
            id: 2, post_id: 1, author_user_id: B_UID, body_text: "直接回复", status: "open",
            created_at: "2026-08-14 10:01:00", edited_at: null, parent_id: 1, root_id: 1,
            author_name: "路人", author_avatar: "",
          },
          {
            id: 3, post_id: 1, author_user_id: A_UID, body_text: "回复的回复", status: "open",
            created_at: "2026-08-14 10:02:00", edited_at: "2026-08-14 10:03:00", parent_id: 2, root_id: 1,
            author_name: "作者", author_avatar: "", reply_to_user_id: B_UID, reply_to_name: "路人",
          },
          {
            id: 4, post_id: 1, author_user_id: B_UID, body_text: "", status: "deleted",
            created_at: "2026-08-14 10:04:00", edited_at: null, parent_id: 2, root_id: 1,
            author_name: "路人", author_avatar: "", reply_to_user_id: B_UID, reply_to_name: "路人",
          },
        ],
      },
    ],
    next_cursor: null, total: 3,
  };
  const els5 = runScenario(B_UID, A_UID, null, threadPayload);
  await new Promise((r) => setTimeout(r, 120));
  const top5 = els5.commentsList.children[0];
  const replies5 = els5.commentsList.children[1];
  check("顶层评论渲染", top5 && top5.dataset.commentId === 1 && top5.children[1].textContent === "顶层评论");
  check("回复串容器渲染", replies5 && replies5.className === "forum-comment-replies"
    && replies5.children.length === 3);
  const rr5 = replies5.children[1];
  const rrMetaText = rr5.children[0].children[0];
  check("回复的回复标注 @目标", rrMetaText.children.some((c) => c.className === "forum-reply-to" && c.textContent === " · 回复 @路人"));
  check("已编辑标记", rrMetaText.children.some((c) => c.className === "is-edited"));
  const delBody = replies5.children[2].children[1];
  check("软删占位文案", delBody.textContent === "该评论已删除");
  const topActions5 = top5.children[0].children.filter((c) => c.className === "forum-comment-actions")[0];
  check("非作者只见「回复」按钮", topActions5 && topActions5.children.length === 1 && topActions5.children[0].textContent === "回复");
  const ownActions5 = replies5.children[0].children[0].children.filter((c) => c.className === "forum-comment-actions")[0];
  check("本人评论可见回复/编辑/删除", ownActions5 && ownActions5.children.map((b) => b.textContent).join(",") === "回复,编辑,删除");
  check("total 评论计数", els5.commentCount.textContent === "(3)");

  // 场景 6：点「回复」→ 底部表单出现回复 chip
  topActions5.children[0].fire("click");
  const chip = els5.commentForm.parentNode.children.find((c) => c.id === "replyChip");
  check("回复 chip 出现并显示目标", chip && chip.children[0].textContent === "回复 @作者：");
  chip.children[1].fire("click");
  check("点 × 清除回复目标", chip._removed === true);

  // 场景 7：未登录 → 无任何评论操作按钮
  const els7 = runScenario(null, A_UID, null, threadPayload);
  await new Promise((r) => setTimeout(r, 120));
  const top7 = els7.commentsList.children[0];
  const acts7 = top7.children[0].children.filter((c) => c.className === "forum-comment-actions")[0];
  check("未登录无操作按钮", acts7 && acts7.children.length === 0);

  process.exit(fail ? 1 : 0);
})();
