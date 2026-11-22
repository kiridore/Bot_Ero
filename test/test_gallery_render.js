// 最小 DOM stub 验证打卡图库前端（gallery.js）的图片位三态渲染：
// 非作者 show → <img>；blur → 模糊缩略图 URL；text/hidden（服务端下发空串）→
// .card-placeholder 占位（文案「图片仅作者可见」）且不打开灯箱。
const fs = require("fs");

function makeEl(tag) {
  const el = {
    tagName: tag, id: "", className: "", textContent: "",
    children: [], attributes: {}, style: {}, dataset: {},
    _classes: new Set(), _html: "", _listeners: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    querySelector(sel) {
      const m = /^\.day-section\[data-day="(.*)"\]$/.exec(sel);
      if (m) {
        return this.children.find((c) => c.className === "day-section" && c.dataset.day === m[1]) || null;
      }
      if (sel.startsWith(".")) {
        const cls = sel.slice(1).split("[")[0];
        return this.children.find((c) => c.className === cls) || null;
      }
      return this.children.find((c) => c.id === sel.replace("#", "")) || null;
    },
    querySelectorAll(sel) {
      const cls = sel.replace(/^\./, "");
      const out = [];
      const walk = (node) => node.children.forEach((c) => {
        if (c.className === cls) out.push(c);
        walk(c);
      });
      walk(this);
      return out;
    },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  el.classList = {
    add(c) { el._classes.add(c); },
    remove(...cs) { cs.forEach((c) => el._classes.delete(c)); },
    contains(c) { return el._classes.has(c); },
  };
  return el;
}

const els = {};
[
  "gallery", "sentinel", "userFilter", "yearFilter", "applyBtn", "stats",
  "lightbox", "lightboxImg", "lightboxCaption", "lightboxClose",
  "authArea", "loginDialog", "loginForm", "loginKey", "loginCancel", "loginError",
].forEach((id) => {
  els[id] = makeEl("div");
  els[id].id = id;
  if (id === "userFilter" || id === "yearFilter") els[id].value = "";
});
els.lightbox.classList.add("hidden");

global.window = { matchMedia: () => ({ matches: false }) };
global.document = {
  createElement: (t) => makeEl(t),
  getElementById: (id) => els[id] || null,
  addEventListener() {},
};
global.GalleryAuth = {
  load: () => null,
  login: async () => {},
  refreshMe: () => Promise.resolve(null),
};

const checkinsPayload = {
  items: [
    {
      id: 3, user_id: "123456", display_name: "小明", checkin_date: "2026-08-10 20:00:00",
      thumbnail_url: "/thumb/123456/a.png", image_url: "/media/123456/a.png", has_file: true,
    },
    {
      id: 2, user_id: "123456", display_name: "小明", checkin_date: "2026-08-10 19:00:00",
      thumbnail_url: "/thumb/123456/b.png?blur=1", image_url: "/thumb/123456/b.png?blur=1",
      has_file: true,
    },
    {
      // text / hidden 态：服务端下发空 URL，只保留卡片信息
      id: 1, user_id: "123456", display_name: "小明", checkin_date: "2026-08-10 18:00:00",
      thumbnail_url: "", image_url: "", has_file: true,
    },
  ],
  total: 3, page: 1, page_size: 40, has_more: false,
};

const fetched = [];
global.fetch = async (url) => {
  fetched.push(String(url));
  if (String(url).startsWith("/api/users")) return { json: async () => ({ users: [] }) };
  return { json: async () => checkinsPayload };
};

global.IntersectionObserver = class {
  constructor(cb) { this.cb = cb; }
  observe() {}
  unobserve() {}
  disconnect() {}
};

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fail += 1;
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  eval(fs.readFileSync("webapp/static/gallery.js", "utf8"));
  await wait(30);

  const section = els.gallery.children.find((c) => c.className === "day-section");
  check("图库渲染日分组", Boolean(section));
  const masonry = section && section.querySelector(".day-masonry");
  const cards = (masonry && masonry.children) || [];
  check("三条记录都出卡片（含图片不可见的两条）", cards.length === 3, String(cards.length));

  const [showCard, blurCard, hiddenCard] = cards;
  const imgOf = (card) => card.children.find((c) => c.tagName === "img");

  check("show 态渲染 <img>", Boolean(imgOf(showCard)));
  check("show 态用原缩略图", imgOf(showCard) && imgOf(showCard).src === "/thumb/123456/a.png");
  check("blur 态渲染 <img> 且是模糊图", imgOf(blurCard) && imgOf(blurCard).src === "/thumb/123456/b.png?blur=1");

  const placeholder = hiddenCard.children.find((c) => c.className === "card-placeholder");
  check("空 URL 渲染占位块", Boolean(placeholder));
  check("占位文案为「图片仅作者可见」", placeholder && placeholder.textContent === "图片仅作者可见");
  check("空 URL 不渲染 <img>", !imgOf(hiddenCard));
  check("空 URL 卡片信息仍在（昵称+时间）",
        hiddenCard.children.some((c) => c.className === "meta" && c.innerHTML.includes("小明")));
  check("空 URL 不绑定灯箱点击", !(hiddenCard._listeners.click || []).length);

  // 点击行为：占位卡不打开灯箱，show 卡打开灯箱并指向原图
  (hiddenCard._listeners.click || []).forEach((fn) => fn());
  check("点占位卡灯箱保持关闭", els.lightbox.classList.contains("hidden"));
  (showCard._listeners.click || []).forEach((fn) => fn());
  check("点 show 卡打开灯箱", !els.lightbox.classList.contains("hidden"));
  check("灯箱指向原图", els.lightboxImg.src === "/media/123456/a.png");

  // IntersectionObserver 兜底加载不应重复追加
  check("只请求一次列表", fetched.filter((u) => u.startsWith("/api/checkins")).length === 1,
        fetched.join(","));

  process.exit(fail ? 1 : 0);
})();
