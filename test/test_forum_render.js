// 最小 DOM stub 验证议事厅列表页：tag 过滤、条目渲染、空状态

const fs = require("fs");

function makeEl(tag) {
  return {
    tagName: tag, id: "", className: "", textContent: "", innerHTML: "",
    children: [], attributes: {}, style: {}, dataset: {}, href: undefined,
    setAttribute(k, v) { this.attributes[k] = v; if (k === "href") this.href = v; },
    addEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    querySelector() { return null; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    classList: { add() {}, remove() {}, contains() { return false; } },
  };
}

let bodyEl = makeEl("body");
const els = {};
global.location = { hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/forum" };
global.window = {};
global.document = {
  createElement: (t) => makeEl(t),
  createDocumentFragment: () => makeEl("fragment"),
  getElementById: (id) => els[id] || null,
  body: { appendChild(c) { bodyEl.children.push(c); els[c.id] = c; } },
  head: { appendChild() {} },
  cookie: "",
};
global.localStorage = (() => { let m = {}; return {
  getItem: (k) => (k in m ? m[k] : null),
  setItem: (k, v) => { m[k] = String(v); },
  removeItem: (k) => { delete m[k]; },
}; })();

["feed", "sentinel", "filterBar", "tagNav", "list", "tlNav", "authArea"].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
});

const tagsPayload = {
  tags: [
    { id: 1, name: "开张", post_count: 3 },
    { id: 2, name: "投票", post_count: 1 },
  ],
};
const listPayload = {
  items: [
    { id: 1, type: "announce", title: "欢迎来到议事厅", created_at: "2026-08-10 14:00:00", poll_deadline: null,
      author_user_id: 1057613133, author_name: "埃洛Erodis", author_avatar: "https://q.qlogo.cn/1.png" },
    { id: 2, type: "post", title: "议事厅首发", created_at: "2026-08-10 14:30:00", poll_deadline: null,
      author_user_id: 3915014383, author_name: "小埃同学", author_avatar: "" },
    { id: 3, type: "poll", title: "周末做什么", created_at: "2026-08-10 15:00:00", poll_deadline: "2099-01-01 00:00:00",
      author_user_id: 1171676207, author_name: "1171676207", author_avatar: "https://q.qlogo.cn/3.png" },
  ],
  next_cursor: null,
};

global.fetch = async (url) => {
  const u = String(url);
  if (u.startsWith("/api/forum/tags")) return { ok: true, status: 200, json: async () => tagsPayload };
  if (u.startsWith("/api/forum/posts")) return { ok: true, status: 200, json: async () => listPayload };
  return { ok: false, status: 404, json: async () => ({}) };
};

const authSrc = fs.readFileSync("core/web/static/auth.js", "utf8");
eval(authSrc);
global.GalleryAuth = window.GalleryAuth;

const forumSrc = fs.readFileSync("webapp/static/forum.js", "utf8");
eval(forumSrc);

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }
function findLink(el) {
  if (el && (el.tagName || "").toUpperCase() === "A") return el;
  if (!el || !el.children) return null;
  for (const c of el.children) {
    const f = findLink(c);
    if (f) return f;
  }
  return null;
}

(async () => {
  await new Promise((r) => setTimeout(r, 100));
  const tags = els.tagNav.children;
  check("tagNav 渲染：全部 + 2 个 tag（标签 + 帖子数）", tags.length === 3 && tags[1].textContent.includes("开张 (3)"));
  const items = els.list.children[0] ? els.list.children[0].children : [];
  check("列表渲染 3 个 item", Array.isArray(items) && items.length === 3);
  check("第一个 item 标记 is-announce", items[0] && items[0].className.includes("is-announce"));
  const link = findLink(items[0]);
  check("item 含标题链接到 /forum/1", link && link.href === "/forum/1");
  check("第三个 item 标记 is-poll", items[2] && items[2].className.includes("is-poll"));
  const meta0 = items[0] && items[0].children[1];
  check("meta 显示作者昵称（非裸 id）", meta0 && meta0.children[1].textContent.includes("埃洛Erodis"));
  check("meta 含作者头像 img", meta0 && meta0.children[0] && meta0.children[0].tagName.toUpperCase() === "IMG");
  const meta1 = items[1] && items[1].children[1];
  check("无头像时降级为昵称文本（无 img）", meta1 && meta1.children.length === 1 && meta1.children[0].textContent.includes("小埃同学"));
  const meta2 = items[2] && items[2].children[1];
  check("昵称缺失时降级回 id（含截止时间）", meta2 && meta2.children[1].textContent.includes("1171676207") && meta2.children[1].textContent.includes("截止"));
  check("sentinel 文案", els.sentinel.textContent.includes("已经到底"));
  process.exit(fail ? 1 : 0);
})();
