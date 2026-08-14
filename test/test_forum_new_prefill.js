// 最小 DOM stub 验证编辑模式预填：?id= 立即填充标题/tag/类型（不依赖 Tiptap CDN 加载）

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {}, dataset: {}, href: undefined,
    value: "", disabled: false, hidden: undefined, checked: false,
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener(type, fn) { (this._listeners = this._listeners || {})[type] = fn; },
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

function runScenario(postPayload) {
  const els = {};
  global.location = {
    hostname: "127.0.0.1", protocol: "http:", search: "?id=5",
    href: "http://127.0.0.1/forum/new?id=5",
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
  global.localStorage.setItem("botero_gallery_session",
    JSON.stringify({ user_id: "1057613133", token: "t", display_name: "测试" }));

  ["msg", "type", "body-section", "poll-section", "poll-options", "body_json", "compose",
   "title", "tags", "editor", "add-option", "deadline", "anonymous", "authArea",
   "pageTitle", "submitBtn"].forEach((id) => {
    els[id] = makeEl("div");
    els[id].id = id;
  });
  els.type.value = "post";
  els["add-option"].style.display = "";
  els["anonymous"].disabled = false;
  els["deadline"].value = "";

  global.fetch = async (url) => {
    const u = String(url);
    if (u.includes("/api/forum/posts/5")) return { ok: true, status: 200, json: async () => postPayload };
    return { ok: false, status: 404, json: async () => ({}) };
  };

  const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
  eval(authSrc);
  global.GalleryAuth = window.GalleryAuth;

  const newSrc = fs.readFileSync("webapp/static/forum_new.js", "utf8");
  eval(newSrc);
  return els;
}

(async () => {
  // 场景 1：长文帖子 —— 标题/tag/类型/按钮文本预填（Tiptap 在 stub 中加载失败，恰好证明预填不依赖 CDN）
  const post = {
    id: 5, type: "post", title: "原文标题", body_json:
      '{"type":"doc","content":[{"type":"paragraph","content":[{"type":"text","text":"原文正文"}]}]}',
    tags: ["开张", "讨论"], poll_options: [], poll_deadline: null, status: "open",
  };
  const els1 = runScenario(post);
  await new Promise((r) => setTimeout(r, 150));
  check("页面标题切换为「编辑帖子」", els1.pageTitle.textContent === "编辑帖子");
  check("提交按钮为「保存修改」", els1.submitBtn.textContent === "保存修改");
  check("标题预填原文", els1.title.value === "原文标题");
  check("tag 预填（逗号连接）", els1.tags.value === "开张, 讨论");
  check("类型锁定为 post 且 disabled", els1.type.value === "post" && els1.type.disabled === true);

  // 场景 2：投票帖 —— 选项只读、锁定截止/匿名、正文区隐藏
  const poll = {
    id: 6, type: "poll", title: "投票原文", body_json: "",
    tags: [], poll_options: [{ id: 1, text: "选项A", ord: 0 }, { id: 2, text: "选项B", ord: 1 }],
    poll_deadline: "2026-08-20 12:00:00", status: "open",
  };
  const els2 = runScenario(poll);
  await new Promise((r) => setTimeout(r, 150));
  check("投票帖类型锁定 poll", els2.type.value === "poll" && els2.type.disabled === true);
  check("投票帖正文区隐藏", els2["body-section"].style.display === "none");
  check("投票帖增加选项按钮隐藏", els2["add-option"].style.display === "none");
  check("投票帖匿名复选框锁定", els2["anonymous"].disabled === true);
  check("投票帖截止时间预填并锁定",
        els2["deadline"].value === "2026-08-20T12:00" && els2["deadline"].disabled === true);

  process.exit(fail ? 1 : 0);
})();
