// 最小 DOM stub 验证周报前端（weekly.js）：
// 五个板块（头版/二版打卡+抽奖/三版群友言论/四版群像观察/五版花絮）全部渲染、
// 打卡与抽奖 KPI 取的是各自子对象字段（回归：renderCheckin 曾引用未定义变量 d
// 导致 ReferenceError，渲染在头版后中断、后续板块全部缺失）、期号下拉导航
const fs = require("fs");

function makeEl(tag) {
  const el = {
    tagName: tag, id: "", className: "", textContent: "",
    children: [], attributes: {}, style: {}, dataset: {},
    _listeners: {},
    setAttribute(k, v) { this.attributes[k] = v; },
    addEventListener(type, fn) { (this._listeners[type] = this._listeners[type] || []).push(fn); },
    appendChild(c) { this.children.push(c); return c; },
    append(...cs) { cs.forEach((c) => this.children.push(c)); },
  };
  Object.defineProperty(el, "innerHTML", {
    get() { return el._html || ""; },
    set(v) { el._html = v; el.children.length = 0; },
  });
  return el;
}

const els = {};
global.location = { pathname: "/weekly/2026-08-17", hostname: "127.0.0.1", protocol: "http:" };
let domContentLoaded = null;
global.document = {
  createElement: (t) => makeEl(t),
  createElementNS: (_ns, t) => makeEl(t),
  getElementById: (id) => els[id] || null,
  addEventListener: (type, fn) => { if (type === "DOMContentLoaded") domContentLoaded = fn; },
};
global.GalleryAuth = {
  headers: () => ({ Authorization: "Bearer test" }),
  renderAuth() {},
  ensureLoginDialog: () => null,
};

["weeklyEmpty", "issueSelect", "prevIssue", "nextIssue", "weeklyDateRange", "weeklyPaper", "authArea"]
  .forEach((id) => { els[id] = makeEl("div"); els[id].id = id; });

const detailPayload = {
  period: { issue: 1, start: "2026-08-17", end: "2026-08-24", total_messages: 15103, total_chars: 116654 },
  headline: { kind: "immortal_jackpot", title: "仙人彩大奖落定", body: "本期开奖号码 6573，仙人大帝（6573） 命中大奖！", stats: [{ label: "开奖号码", value: "6573" }, { label: "大奖得主", value: "仙人大帝（6573）" }, { label: "奖池", value: 7 }] },
  checkin: {
    total: 21, users: 3, daily_avg: 3.0, remedy: 1,
    full_week: [{ user_id: 1, name: "全勤侠" }],
    images: [{ user_id: 1, name: "打卡侠", url: "/thumb/1/abc.image" }],
  },
  lottery: {
    total_draws: 100, per_user: 10,
    top: { user_id: 2, name: "抽卡之王", count: 40 },
    lucky: [{ user_id: 3, name: "欧皇", hit: "points_10" }],
    unlucky: { user_id: 4, name: "非酋", zero_streak: 23 },
    immortal: {
      digits: "6573", pool: 7,
      winners: [
        { user_id: 99, name: "仙人大帝", tier: "一等奖(4A)", digits: "6573" },
        { user_id: 98, name: "半仙", tier: "三等奖(2A)", digits: "6500" },
      ],
    },
  },
  voices: {
    quotes: [{ user_id: 5, name: "语录侠", text: "这是一条足够长的语录内容。", at: "2026-08-18 12:00" }],
    memes: [{ text: "热梗", count: 5, users: 3 }],
    meme_king: { user_id: 6, name: "复读王", count: 3 },
    words: [{ w: "热词", c: 9 }],
  },
  activity: {
    daily: [10, 20, 30, 40, 50, 60, 70],
    peak: { day: 6, hour: 21, count: 70 },
    talkers: [{ user_id: 7, name: "话痨", count: 999, ratio: 0.5 }],
    night_owl: { user_id: 8, name: "夜猫子", count: 12 },
    early_bird: { user_id: 9, name: "早起鸟", count: 8 },
    quest_clears: 2, new_titles: [], activities: [], spy_games: 1,
  },
  trivia: {
    streaks: [],
    gains: [{ user_id: 10, name: "进步侠", delta: 50 }],
    records: [{ label: "单日最多消息", detail: "2026-08-20 · 3000 条" }],
  },
};

global.fetch = async (url) => {
  if (url === "/api/weekly") {
    return { ok: true, status: 200, json: async () => ({ items: [{ week_key: "2026-08-17", issue: 1, start: "2026-08-17" }] }) };
  }
  if (url === "/api/weekly/2026-08-17") {
    return { ok: true, status: 200, json: async () => detailPayload };
  }
  return { ok: false, status: 404, json: async () => ({}) };
};

eval(fs.readFileSync("webapp/static/weekly.js", "utf8"));

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

function findAll(node, cls, out = []) {
  if (node.className === cls) out.push(node);
  (node.children || []).forEach((c) => findAll(c, cls, out));
  return out;
}
function countClass(node, cls) {
  let n = 0;
  if (String(node.className || "").split(/\s+/).includes(cls)) n++;
  (node.children || []).forEach((c) => { n += countClass(c, cls); });
  return n;
}
function allText(node) {
  return node.textContent + (node.children || []).map(allText).join("");
}

(async () => {
  domContentLoaded();
  await wait(100);

  // 1. 期号导航
  check("期号下拉 1 项且含期号", els.issueSelect.children.length === 1
        && els.issueSelect.children[0].textContent.includes("第 1 期"));
  check("唯一一期时翻期按钮禁用", els.prevIssue.disabled === true && els.nextIssue.disabled === true);
  check("日期区间渲染", els.weeklyDateRange.textContent === "2026-08-17 — 2026-08-24");

  // 2. 五个板块全部渲染（回归核心：旧 bug 只有报头+头版）
  const paper = els.weeklyPaper;
  const sections = paper.children.filter((c) => c.className === "weekly-section");
  check("渲染 5 个板块", sections.length === 5, `实际 ${sections.length}`);
  const titles = sections.map((s) => s.children[0].children[1].textContent);
  check("头版标题", titles[0] === "仙人彩大奖落定");
  check("头版大奖得主卡片", allText(sections[0]).includes("大奖得主")
        && allText(sections[0]).includes("仙人大帝"));
  check("二版标题（打卡与抽奖）", titles[1] === "打卡与抽奖");
  check("三版标题（语录热梗热词）", titles[2] === "语录 · 热梗 · 热词");
  check("四版标题（群像观察）", titles[3] === "活跃柱状图与榜单");
  check("五版标题（花絮）", titles[4] === "蝉联 · 涨幅 · 冷知识");

  // 3. 打卡/抽奖 KPI 取自各自子对象（回归：旧实现读 data.checkin 前 c.total 为 undefined）
  const kpiValues = findAll(sections[1], "weekly-kpi-value").map((n) => n.textContent);
  check("打卡 KPI（总次数/人数/日均/补卡）", kpiValues.slice(0, 4).join(",") === "21,3,3,1",
        `实际 ${kpiValues.slice(0, 4).join(",")}`);
  check("抽奖 KPI（总抽数/人均）", kpiValues.slice(4, 6).join(",") === "100,10",
        `实际 ${kpiValues.slice(4, 6).join(",")}`);
  check("全勤榜渲染", allText(sections[1]).includes("全勤侠"));
  check("抽卡之王渲染", allText(sections[1]).includes("抽卡之王"));
  check("仙人彩结算渲染", allText(sections[1]).includes("仙人彩"));
  check("仙人彩中奖明细渲染", allText(sections[1]).includes("仙人大帝 一等奖(4A) 6573")
        && allText(sections[1]).includes("半仙 三等奖(2A) 6500"));
  check("打卡群像墙图片", findAll(sections[1], "weekly-image-card").length === 1);

  // 4. 三版：语录/热梗/热词
  check("语录渲染", findAll(sections[2], "weekly-quote").length === 1
        && allText(sections[2]).includes("语录侠"));
  check("热词云渲染", countClass(sections[2], "weekly-word") === 1);

  // 5. 四版：柱状图（7 根柱）+ 榜单
  const svg = findAll(sections[3], "weekly-chart")[0].children[0];
  const bars = (svg.children || []).filter((c) => c.tagName === "rect");
  check("活跃柱状图 7 根柱", bars.length === 7, `实际 ${bars.length}`);
  check("峰值时段渲染", allText(sections[3]).includes("峰值时段"));
  check("话痨榜渲染", allText(sections[3]).includes("话痨"));
  check("周常/卧底统计渲染", allText(sections[3]).includes("周常全清：2 人"));

  // 6. 五版：花絮与落款
  check("涨幅榜渲染", allText(sections[4]).includes("进步侠"));
  check("冷知识渲染", allText(sections[4]).includes("单日最多消息"));
  check("落款渲染", allText(sections[4]).includes("本期完"));

  // 7. 全页不应出现 undefined 文本
  check("无 undefined 文本", !allText(paper).includes("undefined"));

  // 8. 旧版周报归档兼容：immortal.winners 为数字（1.21.x 及之前格式）
  detailPayload.lottery.immortal.winners = 2;
  domContentLoaded();
  await wait(100);
  const sections2 = els.weeklyPaper.children.filter((c) => c.className === "weekly-section");
  check("重渲染替换而非叠加", sections2.length === 5, `实际 ${sections2.length}`);
  check("旧版 winners 数字兼容（中奖 N 注）", allText(sections2[1]).includes("中奖 2 注"));

  process.exit(fail ? 1 : 0);
})();
