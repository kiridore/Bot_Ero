// 最小 DOM stub 验证跑团记录详情页：气泡类名与位置、徽标、图片 + lightbox、
// 页签高亮、导航最长前缀匹配、暗骰默认隐藏与「显示暗骰」开关（AC08、AC10）。

const fs = require("fs");

const ME = "12345601";
const OTHER = "12345602";

// 桩工厂不能叫 makeEl：eval 页面脚本时其函数声明落进本模块作用域，同名会互相递归
function newEl(tag) {
  const el = {
    tagName: String(tag).toUpperCase(),
    id: "", className: "", textContent: "",
    children: [], attributes: {}, style: {}, dataset: {}, handlers: {},
    checked: false, loading: "", alt: "",
    setAttribute(k, v) { this.attributes[k] = v; },
    getAttribute(k) { return k in this.attributes ? this.attributes[k] : null; },
    addEventListener(type, fn) { this.handlers[type] = fn; },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { this.children.push(...cs); },
    closest(sel) {
      const hit = String(sel).split(",").map((s) => s.trim()).some(
        (part) => part.startsWith("img.")
          && this.tagName === "IMG"
          && this.className.split(/\s+/).includes(part.slice(4))
      );
      return hit ? this : null;
    },
    classList: {
      _set: new Set(),
      add(c) { this._set.add(c); },
      remove(c) { this._set.delete(c); },
      contains(c) { return this._set.has(c); },
      toggle(c, on) { if (on) this._set.add(c); else this._set.delete(c); },
    },
  };
  Object.defineProperty(el, "src", {
    get() { return el.attributes.src || ""; },
    set(v) { el.attributes.src = v; },
  });
  // 真实 DOM 中 innerHTML="" 会清空子节点；页面靠它重建消息列表
  let html = "";
  Object.defineProperty(el, "innerHTML", {
    get() { return html; },
    set(v) { html = v; if (v === "") el.children.length = 0; },
  });
  return el;
}

function childrenWithClass(node, cls) {
  return (node.children || []).filter((c) => c.className.split(/\s+/).includes(cls));
}

function findFirst(node, pred) {
  if (!node) return null;
  if (pred(node)) return node;
  for (const c of node.children || []) {
    const hit = findFirst(c, pred);
    if (hit) return hit;
  }
  return null;
}

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra != null ? " " + extra : ""}`);
  if (!ok) fail++;
}

// ── 环境 stub ──────────────────────────────────────────
const els = {};
const bodyChildren = [];
const docClickHandlers = [];
let headStyle = null;

global.location = {
  hostname: "127.0.0.1", protocol: "http:", search: "", href: "http://127.0.0.1/trpg/records",
  pathname: "/trpg/records/800001/2026-11-10_20-00-00",
};
global.window = {};
global.document = {
  createElement: (t) => newEl(t),
  getElementById: (id) => els[id] || null,
  body: {
    children: bodyChildren,
    appendChild(c) { bodyChildren.push(c); return c; },
    insertBefore(n) { bodyChildren.unshift(n); return n; },
    get firstChild() { return bodyChildren[0] || null; },
  },
  head: { appendChild(n) { headStyle = n; } },
  documentElement: { scrollHeight: 1200 },
  addEventListener(type, fn) { if (type === "click") docClickHandlers.push(fn); },
  cookie: "",
};
global.localStorage = (() => {
  let m = {};
  return {
    getItem: (k) => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v); },
    removeItem: (k) => { delete m[k]; },
  };
})();
global.requestAnimationFrame = (fn) => fn();
global.GalleryIcons = { svgHTML: (name) => `<svg data-icon="${name}"></svg>` };
const scrollCalls = [];
global.window.scrollTo = (opts) => { scrollCalls.push(opts); };

["messageList", "threadHint", "recordTitle", "recordMeta", "recordState", "revealToggle",
 "oocToggle", "sheetBox", "sheetList", "fabTop", "fabSecret", "fabOoc", "authArea"]
  .forEach((id) => {
    els[id] = newEl("div");
    els[id].id = id;
  });

// ── 顶部导航：跑团只有一个顶层入口，/trpg/records 点亮它 ─────────────
eval(fs.readFileSync("core/web/static/nav.js", "utf8"));
const nav = bodyChildren[0];
check("nav 已注入", nav && nav.tagName === "NAV" && nav.className === "site-nav");
check("顶层不再有跑团记录入口", nav && !nav.innerHTML.includes('href="/trpg/records"'));
check("nav 含跑团入口", nav && nav.innerHTML.includes('href="/trpg"') && nav.innerHTML.includes(">跑团<"));
const activeNav = (nav.innerHTML.match(/<a href="([^"]+)" class="active"/) || [])[1];
check("nav 高亮跑团入口", activeNav === "/trpg", String(activeNav));
check("nav 只有一个高亮项", (nav.innerHTML.match(/class="active"/g) || []).length === 1);
check("nav 已注入样式", headStyle && headStyle.tagName === "STYLE");

// ── 页签条：/trpg 与 /trpg/records 共用且各自高亮 ─────────
function activeTab(html) {
  const m = html.match(/<a class="trpg-tab is-active" href="([^"]+)"/);
  return m ? m[1] : null;
}
const trpgHtml = fs.readFileSync("webapp/static/trpg.html", "utf8");
const recordsHtml = fs.readFileSync("webapp/static/trpg_records.html", "utf8");
const recordHtml = fs.readFileSync("webapp/static/trpg_record.html", "utf8");
for (const [name, html, active] of [
  ["车卡页", trpgHtml, "/trpg"],
  ["记录列表页", recordsHtml, "/trpg/records"],
  ["记录详情页", recordHtml, "/trpg/records"],
]) {
  check(`${name}页签条含两个页签`,
    html.includes('class="trpg-tabs"') && html.includes('href="/trpg"') && html.includes('href="/trpg/records"'));
  check(`${name}当前页签高亮`, activeTab(html) === active, String(activeTab(html)));
}

// ── 详情页数据 stub ────────────────────────────────────
const participants = [
  { user_id: ME, nickname: "老张", display_name: "老张（实时）", avatar_url: "https://q1.qlogo.cn/g?b=qq&nk=1",
    char_name: "艾拉", role: "dm", char_id: 11,
    sheet_start: { rules: "dnd5e", level: 3, hp: 30, current_hp: 22, ac: 16, prof_bonus: 2,
      passive_perception: 13, race: "人类", class_name: "战士" } },
  { user_id: OTHER, nickname: "小王", display_name: "小王", avatar_url: "", char_name: "上枝景子",
    role: "ob", char_id: 12,
    sheet_start: { rules: "coc7th", occupation: "酒保", age: 27, hp: 11, current_hp: 9,
      san: 65, current_san: 60, mp: 13, current_mp: 13, max_san: 95, mov: 8, db: "0",
      build: 0, dodge: 27, skills: { 侦察: 45 } } },
];
const allMessages = [
  { time: 1762776000, sender_type: "user", user_id: ME, nickname: "老张", char_name: "艾拉",
    role: "dm", segments: [{ type: "text", text: "我推开酒馆的门" }] },
  { time: 1762776010, sender_type: "user", user_id: OTHER, nickname: "小王", char_name: "",
    role: "ob", segments: [{ type: "text", text: "我跟着进去" }] },
  { time: 1762776031, sender_type: "bot", user_id: "3915014383", nickname: "小埃", char_name: "",
    role: "", segments: [{ type: "text", text: "老张的感知检定: D20=13=13" }] },
  { time: 1762776050, sender_type: "user", user_id: OTHER, nickname: "小王", char_name: "",
    role: "", segments: [{ type: "image", local: "imgs/img_0001.jpg",
      url: "/trpg/media/800001/2026-11-10_20-00-00/img_0001.jpg" }] },
  { time: 1762776040, sender_type: "bot", user_id: "3915014383", nickname: "小埃", char_name: "",
    role: "", secret: true, segments: [{ type: "text", text: "暗骰：老张的D20=7=7" }] },
];
const detail = {
  group_id: "800001", group_name: "夜航团", start: "2026-11-10 20:00:00",
  end: "2026-11-10 23:10:00", state: "ended", participants, total: allMessages.length,
};

global.fetch = async (url) => {
  const u = String(url);
  if (u.startsWith("/api/auth/me")) {
    return { ok: true, status: 200, json: async () => ({ user_id: ME, display_name: "老张", avatar_url: "" }) };
  }
  if (u.startsWith("/api/trpg/records/800001/")) {
    const query = new URLSearchParams(u.split("?")[1] || "");
    const from = Number(query.get("from") || 0);
    const windowMsgs = allMessages.slice(from);
    const messages = query.get("reveal") === "1" ? windowMsgs : windowMsgs.filter((m) => !m.secret);
    return { ok: true, status: 200, json: async () => ({ ...detail, from, messages }) };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

localStorage.setItem("botero_gallery_session", JSON.stringify({ token: "test-token" }));
eval(fs.readFileSync("core/web/static/auth.js", "utf8"));
global.GalleryAuth = window.GalleryAuth;
eval(fs.readFileSync("core/web/static/lightbox.js", "utf8"));
eval(fs.readFileSync("webapp/static/trpg_record.js", "utf8"));

const msgList = els.messageList;
const settle = () => new Promise((r) => setTimeout(r, 50));

(async () => {
  await settle();

  // —— AC08 气泡渲染 ——
  check("标题显示团名", els.recordTitle.textContent === "夜航团", els.recordTitle.textContent);
  check("状态徽标为已结束", els.recordState.textContent === "已结束", els.recordState.textContent);
  check("头部消息条数取 total", els.recordMeta.textContent.includes("5 条消息"), els.recordMeta.textContent);
  check("默认渲染 4 条（暗骰不返回）", msgList.children.length === 4, String(msgList.children.length));

  const [selfNode, otherNode, botNode, imageNode] = msgList.children;
  check("自己的消息带 is-self 且无头像",
    selfNode.className.includes("is-self") && !childrenWithClass(selfNode, "trpg-avatar").length);
  check("他人消息不带 is-self 且带头像",
    !otherNode.className.includes("is-self")
    && Boolean(findFirst(otherNode, (n) => n.className === "trpg-avatar")));
  const selfHead = childrenWithClass(selfNode, "trpg-msg-body")[0].children[0];
  check("名字行显示角色名（实时名称）", selfHead.children[0].textContent === "艾拉（老张（实时））",
    selfHead.children[0].textContent);
  check("DM 徽标", childrenWithClass(selfHead, "role-dm")[0].textContent === "DM");
  const otherHead = childrenWithClass(otherNode, "trpg-msg-body")[0].children[0];
  check("观察者徽标", childrenWithClass(otherHead, "role-ob")[0].textContent === "观察者");
  check("无角色卡时名字只显示昵称", otherHead.children[0].textContent === "小王", otherHead.children[0].textContent);
  check("有头像的参与者用 QQ 头像图片", (() => {
    rebuildNickMap([{ user_id: "777", nickname: "旧名", display_name: "路人",
      avatar_url: "https://q1.qlogo.cn/g?b=qq&nk=777" }]);
    const node = renderMessage({ sender_type: "user", user_id: "777", nickname: "旧名",
      char_name: "", segments: [{ type: "text", text: "hi" }] });
    const avatars = childrenWithClass(node, "trpg-avatar");
    const head = childrenWithClass(node, "trpg-msg-body")[0].children[0];
    return avatars.length === 1 && avatars[0].tagName === "IMG"
      && avatars[0].src.includes("qlogo.cn") && head.children[0].textContent === "路人";
  })());
  check("没有头像时回落名字首字", (() => {
    const node = renderAvatar({ user_id: "999999", nickname: "无名", char_name: "" });
    return node.tagName === "DIV" && node.className === "trpg-avatar" && node.textContent === "无";
  })());
  check("机器人消息带 is-bot 且无头像",
    botNode.className.includes("is-bot") && !childrenWithClass(botNode, "trpg-avatar").length);
  check("每条消息显示时间", childrenWithClass(selfHead, "trpg-msg-time")[0].textContent === "20:00:00",
    childrenWithClass(selfHead, "trpg-msg-time")[0].textContent);
  check("消息默认不含暗骰", !msgList.children.some((n) => n.className.includes("is-secret")));

  // 图片段 + lightbox 点击
  const imgEl = findFirst(imageNode, (n) => n.tagName === "IMG");
  check("图片段渲染为 img.trpg-img", imgEl && imgEl.className === "trpg-img"
    && imgEl.src === "/trpg/media/800001/2026-11-10_20-00-00/img_0001.jpg", imgEl && imgEl.src);
  for (const handler of docClickHandlers) {
    handler({ target: imgEl, preventDefault() {} });
  }
  const overlay = bodyChildren.find((n) => n.className.startsWith("lightbox"));
  check("点击图片打开 lightbox", Boolean(overlay));
  const overlayImg = overlay && findFirst(overlay, (n) => n.tagName === "IMG");
  check("lightbox 显示同一张图片", overlayImg && overlayImg.src === imgEl.src);

  // —— AC10 显示暗骰开关 ——
  els.revealToggle.checked = true;
  els.revealToggle.handlers.change();
  await settle();
  check("打开开关后渲染 5 条", msgList.children.length === 5, String(msgList.children.length));
  const secretNode = msgList.children[4];
  check("暗骰消息带 is-secret", secretNode.className.includes("is-secret"));
  check("暗骰消息仍为机器人窄条", secretNode.className.includes("is-bot"));
  check("暗骰消息带暗骰徽标",
    childrenWithClass(secretNode, "trpg-msg-body")[0].children[0]
      .children.some((c) => c.className === "trpg-role role-secret"));
  check("暗骰消息内容完整",
    findFirst(secretNode, (n) => n.className === "trpg-text").textContent === "暗骰：老张的D20=7=7");

  els.revealToggle.checked = false;
  els.revealToggle.handlers.change();
  await settle();
  check("关闭开关后暗骰重新隐藏", msgList.children.length === 4
    && !msgList.children.some((n) => n.className.includes("is-secret")));

  // —— 场外发言（整条消息被括号包住）——
  const ooc = (text, extra = []) => isOoc({ segments: [{ type: "text", text }, ...extra] });
  check("全角括号包裹算场外", ooc("（我去倒杯水）"));
  check("半角括号包裹算场外", ooc("(等一下，我查下规则)"));
  check("括号前后有空格也算场外", ooc("  （笑）  "));
  check("括号只在开头不算场外", !ooc("（笑）他推门进来"));
  check("括号只在结尾不算场外", !ooc("他推门进来（笑）"));
  check("空括号不算场外", !ooc("（）"));
  check("带图片的消息不算场外", !ooc("（看图）", [{ type: "image", url: "/x.jpg" }]));
  check("普通发言不算场外", !ooc("我推开酒馆的门"));

  check("场外消息渲染带 is-ooc", renderMessage({ sender_type: "user", user_id: OTHER,
    nickname: "小王", char_name: "", segments: [{ type: "text", text: "（场外）" }] })
    .className.includes("is-ooc"));
  check("普通消息不带 is-ooc", !renderMessage({ sender_type: "user", user_id: OTHER,
    nickname: "小王", char_name: "", segments: [{ type: "text", text: "我推门" }] })
    .className.includes("is-ooc"));

  check("头部有隐藏场外开关", recordHtml.includes('id="oocToggle"')
    && recordHtml.includes("隐藏场外发言"));
  const css = fs.readFileSync("webapp/static/trpg.css", "utf8");
  check("CSS 按容器类隐藏场外", css.includes(".trpg-thread.hide-ooc .trpg-msg.is-ooc"));
  renderHeader({ group_name: "暂停团", start: "2026-11-12 09:00:00", state: "paused",
    rules_name: "DND 5E", total: 1 });
  check("暂停时状态徽标显示已暂停", els.recordState.textContent === "已暂停",
    els.recordState.textContent);
  check("暂停时时间行仍可用", els.recordMeta.textContent.includes("1 条消息"));
  check("已暂停徽标有样式", css.includes(".trpg-badge.is-paused"));

  // —— 角色卡详情入口（头像 + 参团角色卡条目）——
  check("悬停概要含职业与关键数值",
    cardSummary(participants[1]).includes("酒保") && cardSummary(participants[1]).includes("SAN 60/65"),
    cardSummary(participants[1]));
  check("DND 概要含等级与 AC",
    cardSummary(participants[0]).includes("Lv.3") && cardSummary(participants[0]).includes("AC 16"),
    cardSummary(participants[0]));
  check("无快照时概要说明", cardSummary({ user_id: "1", char_name: "阿铁" }).includes("没有角色卡快照"));
  check("角色卡地址按 user_id/char_id 拼", charUrl({ user_id: "777", char_id: 9 }) === "/trpg/char/777/9",
    charUrl({ user_id: "777", char_id: 9 }));
  check("无 char_id 时没有地址", charUrl({ user_id: "777" }) === "");
  check("无 char_id 的节点不被包链接",
    (() => {
      const node = newEl ? globalThis.document.createElement("div") : null;
      const out = linkToCard(node, { user_id: "777" });
      return out === node;
    })());

  const otherAvatarLink = findFirst(otherNode, (n) => n.className === "trpg-card-link");
  check("他人头像为角色卡链接",
    otherAvatarLink && otherAvatarLink.tagName === "A"
      && otherAvatarLink.href === `/trpg/char/${OTHER}/12`,
    otherAvatarLink && otherAvatarLink.href);
  check("头像链接带悬停概要", otherAvatarLink && String(otherAvatarLink.title).includes("酒保"));
  const sheetCards = els.sheetList.children;
  check("参团角色卡条目已展开", sheetCards.length === 2 && els.sheetBox.hidden === false,
    String(sheetCards.length));
  check("角色卡条目本身是链接",
    sheetCards.every((c) => c.tagName === "A" && /^\/trpg\/char\//.test(c.href)), String(sheetCards[0] && sheetCards[0].href));
  check("角色卡条目带「查看角色卡」提示",
    sheetCards[0].children.some((c) => c.className === "trpg-sheet-link"));
  check("角色卡条目带悬停概要", String(sheetCards[0].title).includes("HP"));

  els.oocToggle.checked = true;
  els.oocToggle.handlers.change();
  check("勾选后容器加 hide-ooc", msgList.classList.contains("hide-ooc"));
  check("勾选状态写入 localStorage", localStorage.getItem("botero_trpg_hide_ooc") === "1");
  els.oocToggle.checked = false;
  els.oocToggle.handlers.change();
  check("取消勾选移除 hide-ooc", !msgList.classList.contains("hide-ooc"));
  check("取消勾选写入 0", localStorage.getItem("botero_trpg_hide_ooc") === "0");

  // —— 底部悬浮按钮 ——
  check("页面有三个悬浮按钮", ["fabTop", "fabSecret", "fabOoc"].every((id) => recordHtml.includes(`id="${id}"`)),
    String(["fabTop", "fabSecret", "fabOoc"].map((id) => recordHtml.includes(`id="${id}"`))));
  check("悬浮按钮加载图标库", recordHtml.includes("/shared/icons.js"));
  check("回到顶部用向上箭头图标", els.fabTop.innerHTML.includes('data-icon="arrow-up"'), els.fabTop.innerHTML);
  check("隐藏暗骰用眼睛图标", els.fabSecret.innerHTML.includes('data-icon="eye-off"'), els.fabSecret.innerHTML);
  check("隐藏场外发言用气泡图标", els.fabOoc.innerHTML.includes('data-icon="message-off"'), els.fabOoc.innerHTML);
  check("按钮带可读标签",
    els.fabTop.getAttribute("aria-label") === "回到顶部"
      && els.fabSecret.getAttribute("aria-label") === "隐藏暗骰"
      && els.fabOoc.getAttribute("aria-label") === "隐藏场外发言");

  check("暗骰默认隐藏时按钮按下", els.fabSecret.getAttribute("aria-pressed") === "true"
    && els.revealToggle.checked === false);
  check("场外开关默认未按下", els.fabOoc.getAttribute("aria-pressed") === "false");
  check("CSS 有悬浮按钮样式", css.includes(".trpg-fab") && css.includes(".trpg-fab-btn.is-active"));

  check("顶部时回到顶部按钮隐藏", els.fabTop.classList.contains("is-hidden")
    && els.fabTop.tabIndex === -1);
  global.window.scrollY = 600;
  syncTopFab();
  check("下滚后回到顶部按钮出现", !els.fabTop.classList.contains("is-hidden")
    && els.fabTop.tabIndex === 0);
  check("CSS 有隐藏态样式", css.includes(".trpg-fab-btn.is-hidden"));

  // —— 气泡宽度按内容收缩（纯样式，只能断言规则存在；观感需浏览器确认）——
  const bodyRule = (css.match(/\.trpg-msg-body \{[^}]*\}/) || [""])[0];
  check("气泡容器改为列弹性布局", /\.trpg-msg-body \{[^}]*flex-direction:\s*column/.test(css)
    && /align-items:\s*flex-start/.test(bodyRule), bodyRule.slice(0, 120));
  check("自己的气泡右对齐", /\.trpg-msg\.is-self \.trpg-msg-body \{[^}]*flex-end/.test(css));
  check("机器人气泡居中", /\.trpg-msg\.is-bot \.trpg-msg-body \{[^}]*center/.test(css));
  check("气泡最大宽度不超过容器", /\.trpg-bubble \{[^}]*max-width:\s*100%/.test(css));

  els.fabTop.handlers.click();
  check("回到顶部滚动到 0", (() => {
    const last = scrollCalls[scrollCalls.length - 1];
    return last && last.top === 0;
  })(), JSON.stringify(scrollCalls[scrollCalls.length - 1]));

  els.fabSecret.handlers.click();
  await settle();
  check("点按钮显示暗骰", els.revealToggle.checked === true
    && els.fabSecret.getAttribute("aria-pressed") === "false"
    && msgList.children.length === 5, String(msgList.children.length));
  els.fabSecret.handlers.click();
  await settle();
  check("再点按钮隐藏暗骰", els.revealToggle.checked === false
    && els.fabSecret.getAttribute("aria-pressed") === "true"
    && msgList.children.length === 4, String(msgList.children.length));

  els.fabOoc.handlers.click();
  check("点按钮隐藏场外", els.fabOoc.getAttribute("aria-pressed") === "true"
    && msgList.classList.contains("hide-ooc") && els.oocToggle.checked === true);
  check("按钮状态写入 localStorage", localStorage.getItem("botero_trpg_hide_ooc") === "1");
  els.fabOoc.handlers.click();
  check("再点按钮显示场外", els.fabOoc.getAttribute("aria-pressed") === "false"
    && !msgList.classList.contains("hide-ooc") && els.oocToggle.checked === false);

  process.exit(fail ? 1 : 0);
})();
