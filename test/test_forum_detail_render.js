// 最小 DOM stub 验证议事厅详情页：作者可见编辑/删除按钮，非作者隐藏

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {}, dataset: {}, href: undefined,
    value: "", disabled: false, hidden: undefined,
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
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
function runScenario(sessionUid, authorUid) {
  const els = {};
  global.location = {
    hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/forum/1",
    pathname: "/forum/1",
  };
  global.window = {};
  global.document = {
    createElement: (t) => makeEl(t),
    createDocumentFragment: () => makeEl("fragment"),
    getElementById: (id) => els[id] || null,
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

  const postPayload = {
    id: 1, type: "post", title: "测试帖", body_json: "", status: "open",
    author_user_id: authorUid, author_name: "作者", author_avatar: "",
    created_at: "2026-08-14 10:00:00", updated_at: "2026-08-14 10:00:00",
    tags: [], poll_options: [], my_vote: null,
  };
  global.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/comments")) return { ok: true, status: 200, json: async () => ({ items: [], next_cursor: null }) };
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

  process.exit(fail ? 1 : 0);
})();
