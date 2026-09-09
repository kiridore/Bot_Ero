// 最小 DOM stub 验证 activities_detail.js：
// 我的提交区块（文字+图+可更新徽章）、can_submit 表单态、not_my_turn 原因态、非成员隐藏。
const fs = require("fs");

const ALL_ELS = [];
function makeEl(tag) {
  const el = {
    tagName: tag, id: "", type: "", className: "", textContent: "", value: "",
    children: [], dataset: {}, style: {}, _html: "", _listeners: {},
    addEventListener(t, f) { (el._listeners[t] = el._listeners[t] || []).push(f); },
    appendChild(c) { el.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => el.children.push(c)); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    showModal() { this.open = true; },
    close() { this.open = false; },
    scrollIntoView() {},
    click() {},
    remove() { el._removed = true; },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    _s: new Set(),
    add(c) { this._s.add(c); },
    remove(...cs) { cs.forEach((c) => this._s.delete(c)); },
    toggle(c, on) { if (on) this._s.add(c); else this._s.delete(c); },
    contains(c) { return this._s.has(c); },
  };
  ALL_ELS.push(el);
  return el;
}

const mainEl = makeEl("main");
mainEl.id = "detailMain";
const authArea = makeEl("div");
authArea.id = "authArea";
const els = { detailMain: mainEl, authArea, submitForm: null };
global.document = {
  createElement: makeEl,
  body: makeEl("body"),
  getElementById(id) {
    if (els[id]) return els[id];
    for (const el of ALL_ELS) {
      if (el.id === id) return el;
      if (el._html && new RegExp(`id="${id}"`).test(el._html)) {
        const stub = makeEl("div");
        stub.id = id;
        els[id] = stub;
        return stub;
      }
    }
    return null;
  },
};

global.location = { pathname: "/activities/3", search: "" };
const myUid = "333";
let meData = {
  member: { status: "done", seq: 1, content: "我的文字作品", submitted_at: "2026-09-02 10:00:00",
            images: ["/archive/3/media/1-1.png"] },
  can_submit: true, block_reason: null, block_text: null,
};
let actData = {
  id: 3, type: "relay", title: "接龙三", status: "running", hours_per_user: 48,
  members: [
    { user_id: "333", nickname: "成员甲", seq: 1, status: "done", content: "我的文字作品",
      images: ["/archive/3/media/1-1.png"], submitted_at: "2026-09-02 10:00:00" },
    { user_id: "444", nickname: "成员乙", seq: 2, status: "pending", images: [], content: null },
  ],
};
const posts = [];
global.fetch = async (path, options = {}) => {
  if (path === "/api/activities/3") return { ok: true, status: 200, json: async () => actData };
  if (path === "/api/activities/3/me") return { ok: true, status: 200, json: async () => meData };
  if (path.endsWith("/submit")) { posts.push(options); return { ok: true, status: 200, json: async () => ({ ok: true, updated: true }) }; }
  return { ok: false, status: 404, json: async () => ({}) };
};
global.GalleryAuth = {
  isLoggedIn: () => true,
  load: () => ({ token: "t", user_id: myUid, display_name: "甲", avatar_url: "" }),
  headers: () => ({}),
  renderAuth() {},
};
global.window = { addEventListener() {} };
global.FormData = class { constructor() { this._d = {}; } append(k, v) { (this._d[k] = this._d[k] || []).push(v); } };
global.confirm = () => true;
global.alert = () => {};
global.URL = { createObjectURL: (f) => `blob:${f.name}`, revokeObjectURL() {} };
const pngCalls = [];
global.htmlToImage = {
  toPng: async (node, opts) => { pngCalls.push({ node, opts }); return "data:image/png;base64,AAA"; },
};

eval(fs.readFileSync("webapp/static/activities_detail.js", "utf8"));

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

(async () => {
  await wait(150);
  const html = mainEl._html;

  // 1. 我的提交区块：内容 + 图片卡片 + 可更新徽章
  check("含我的提交区块", html.includes("我的提交"));
  check("显示我的文字", html.includes("我的文字作品"));
  check("显示我的图片", html.includes("/archive/3/media/1-1.png"));
  check("图片为方形卡片", html.includes("img-grid") && html.includes("img-card"));
  check("可更新徽章", /已提交|可更新/.test(html));

  // 2. can_submit=true → 表单渲染（textarea + file + 已有图卡片删除键 + 预览容器 + 按钮）
  check("含提交表单", html.includes("提交作品") && /textarea|work-input/.test(html));
  check("已有图卡片含删除键", /id="savedImages"/.test(html) && /img-del/.test(html));
  check("预览容器存在", /id="previewImages"/.test(html));

  // 3. 图片交互：选图预览追加 → 删除已传图/新图 → 提交载荷增量
  const myFilesEl = els.myFiles;
  myFilesEl.files = [
    { name: "new1.png", type: "image/png" },
    { name: "new2.png", type: "image/png" },
  ];
  myFilesEl._listeners.change.forEach((f) => f({ target: myFilesEl }));
  check("预览追加两张卡片", els.previewImages._html.includes("blob:new1.png")
    && els.previewImages._html.includes("blob:new2.png"));
  const delCardFake = { dataset: { name: "1-1.png" }, parentElement: null };
  const delBtnFake = { closest: (sel) => (sel === ".img-del" ? delBtnFake : sel === ".img-card" ? delCardFake : null) };
  const savedGridFake = { id: "savedImages", removeChild: (c) => { savedGridFake.removed = c; } };
  delCardFake.parentElement = savedGridFake;
  els.savedImages._listeners.click[0]({ target: delBtnFake });
  check("删除已传图入队", pendingRemovals.has("1-1.png") && savedGridFake.removed === delCardFake);
  const prevCardFake = { dataset: { idx: "0" }, parentElement: { id: "previewImages" } };
  const prevBtnFake = { closest: (sel) => (sel === ".img-del" ? prevBtnFake : sel === ".img-card" ? prevCardFake : null) };
  els.previewImages._listeners.click[0]({ target: prevBtnFake });
  check("预览删除留一张", pendingImages.length === 1
    && !els.previewImages._html.includes("blob:new1.png") && els.previewImages._html.includes("blob:new2.png"));
  document.getElementById("myContent").value = "我的最终作品";
  posts.length = 0;
  await els.submitBtn._listeners.click[0]();
  await wait(50);
  const body = (posts[0] && posts[0].body && posts[0].body._d) || {};
  check("提交载荷含内容", body.content && body.content[0] === "我的最终作品");
  check("提交载荷追加新图", body.files && body.files.length === 1 && body.files[0].name === "new2.png");
  check("提交载荷带 removed", body.removed && body.removed[0] === "1-1.png");

  // 4. not_my_turn → 原因替代表单
  meData = { member: { status: "pending", seq: 2, content: null, submitted_at: null, images: [] },
             can_submit: false, block_reason: "not_my_turn", block_text: "还未轮到你提交" };
  actData.members[0].status = "done";
  loadDetail();
  await wait(100);
  const html2 = mainEl._html;
  check("原因提示替代表单", html2.includes("还未轮到你提交") && !/id="submitBtn"/.test(html2));

  // 4. not_member → 两块隐藏
  meData = { member: null, can_submit: false, block_reason: "not_member", block_text: null };
  loadDetail();
  await wait(100);
  const html3 = mainEl._html;
  check("非成员隐藏提交区", !html3.includes("我的提交") && !html3.includes("提交作品"));

  // 5. finished → 生成分享长图按钮 + 点击接线 + 离屏节点清理
  check("运行中无分享按钮", !html.includes("shareBtn"));
  actData.status = "finished";
  actData.finished_at = "2026-09-03 12:00:00";
  actData.members[1] = { user_id: "444", nickname: "成员乙", seq: 2, status: "done",
    content: "乙的作品", images: [], submitted_at: "2026-09-02 11:00:00" };
  loadDetail();
  await wait(100);
  const html4 = mainEl._html;
  check("结束显示分享按钮", html4.includes("生成分享长图") && /id="shareBtn"/.test(html4));
  check("含全部作品块", html4.includes("乙的作品"));
  const shareBtn = els.shareBtn;
  check("按钮接线", !!(shareBtn && shareBtn._listeners.click && shareBtn._listeners.click.length === 1));
  if (shareBtn && shareBtn._listeners.click) {
    await shareBtn._listeners.click[0]();
    check("调用 toPng", pngCalls.length === 1);
    check("背景色为报纸色", pngCalls[0] && pngCalls[0].opts && pngCalls[0].opts.backgroundColor === "#f5efe0");
    check("下载文件名", ALL_ELS.some((e) => e.tagName === "a" && e.download === "activity-3.png"));
    check("离屏节点已清理", pngCalls[0] && pngCalls[0].node && !!pngCalls[0].node._removed);
    check("按钮文案复位", shareBtn.textContent === "生成分享长图");
  }

  process.exit(fail ? 1 : 0);
})();
