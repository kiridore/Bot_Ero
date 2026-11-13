// 跑团记录列表页 DOM stub：行式条目的字段渲染
// （团名 / 状态 / 起止时间 / 玩家数 / 我的身份 / 规则 / 消息条数），以及「只看我参加的」查询参数。

const fs = require("fs");

function newEl(tag) {
  return {
    tagName: String(tag).toUpperCase(), innerHTML: "", textContent: "",
    children: [], className: "", checked: false,
    addEventListener() {},
    appendChild(c) { this.children.push(c); return c; },
  };
}

let fail = 0;
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra != null ? " " + extra : ""}`);
  if (!ok) fail++;
}

const els = { recordList: newEl("div"), mineOnly: newEl("input"), authArea: newEl("div") };

global.document = {
  getElementById: (id) => els[id] || null,
  createElement: (t) => newEl(t),
  documentElement: { scrollHeight: 0 },
  addEventListener() {},
};
global.window = {};
global.localStorage = { getItem: () => null, setItem() {}, removeItem() {} };

const RECORDS = [
  {
    group_id: "800001", group_name: "夜航团", start: "2026-11-10 20:00:00", end: "2026-11-10 23:10:00",
    start_dir: "2026-11-10_20-00-00", state: "ended", rules_name: "DND 5E", player_count: 3,
    message_count: 128, my_role: { role: "dm", char_name: "" }, is_mine: true,
  },
  {
    group_id: "800002", group_name: "深海团", start: "2026-11-12 21:00:00", end: null,
    start_dir: "2026-11-12_21-00-00", state: "recording", rules_name: "COC 7th", player_count: 2,
    message_count: 40, my_role: { role: "player", char_name: "艾拉" }, is_mine: true,
  },
];

const fetchCalls = [];
global.fetch = async (url) => {
  fetchCalls.push(url);
  return { ok: true, json: async () => ({ records: RECORDS }) };
};
global.GalleryAuth = {
  renderAuth() {},
  refreshMe: async () => ({ user_id: "12345601" }),
  headers: () => ({}),
};

eval(fs.readFileSync("webapp/static/trpg_records.js", "utf8"));

(async () => {
  await new Promise((r) => setImmediate(r));
  await new Promise((r) => setImmediate(r));
  const html = els.recordList.innerHTML;

  check("列表渲染出两行", (html.match(/class="trpg-row"/g) || []).length === 2);
  check("显示团名", html.includes("夜航团") && html.includes("深海团"));
  check("已结束显示起止时间", html.includes("2026-11-10 20:00:00 — 2026-11-10 23:10:00"));
  check("录制中显示进行中", html.includes("2026-11-12 21:00:00 — 进行中"));
  check("状态徽标", html.includes(">已结束<") && html.includes(">录制中<"));
  check("暂停状态徽标", stateBadge({ state: "paused" }).includes("已暂停"),
    stateBadge({ state: "paused" }));
  // 准备中的团：DM/超管才能看到清除按钮
  const partyDm = { group_id: "296470819", group_name: "夜航团", dm: "1", dm_name: "守密人",
    rules_name: "COC 7th", prepared_count: 2, member_count: 3, members: [], can_audit: true };
  const partyOther = { ...partyDm, can_audit: false };
  check("DM 可见清除按钮", partyCard(partyDm).includes('data-clear-party="296470819"'));
  check("非 DM 不显示清除按钮", !partyCard(partyOther).includes("data-clear-party"));
  check("清除按钮文案", partyCard(partyDm).includes("清除这条准备"));

  // DM 与观察者不挂角色卡名，玩家仍显示
  const partyMembers = { ...partyDm, members: [
    { user_id: "1", nickname: "守密人", role: "dm", char_name: "不该出现的角色名", char_id: 9 },
    { user_id: "2", nickname: "旁观者", role: "ob", char_name: "也不该出现", char_id: 10 },
    { user_id: "3", nickname: "玩家A", role: "", char_name: "艾拉", char_id: 11 },
  ] };
  const partyHtml = partyCard(partyMembers);
  check("DM 行不显示角色卡名", !partyHtml.includes("不该出现的角色名"), partyHtml);
  check("观察者行不显示角色卡名", !partyHtml.includes("也不该出现"), partyHtml);
  check("玩家行仍显示角色卡名", partyHtml.includes("艾拉"), partyHtml);
  check("DM/观察者仍显示群昵称",
    partyHtml.includes("守密人") && partyHtml.includes("旁观者"), partyHtml);

  // 群里所有人都在卡片里：没准备但有当前卡也能点开；没卡的人提示等待准备
  const mixed = { ...partyDm, members: [
    { user_id: "1", nickname: "守密人", role: "dm", char_name: "", char_id: 9, prepared: false },
    { user_id: "3", nickname: "玩家A", role: "", char_name: "艾拉", char_id: 11, prepared: true },
    { user_id: "4", nickname: "迟到的人", role: "", char_name: "青山 小夜", char_id: 14, prepared: false },
    { user_id: "5", nickname: "没建卡的人", role: "", char_name: "", char_id: null, prepared: false },
  ] };
  const mixedHtml = partyCard(mixed);
  check("所有人都列出来", ["守密人", "玩家A", "迟到的人", "没建卡的人"].every((n) => mixedHtml.includes(n)),
    mixedHtml);
  check("没准备但有卡也算链接", mixedHtml.includes('/trpg/char/4/14?party=296470819'), mixedHtml);
  check("没准备的人带未准备标记", mixedHtml.includes("trpg-party-pending"), mixedHtml);
  check("没卡的人不可点开", mixedHtml.includes("未设置角色卡")
    && !mixedHtml.includes("等待准备") && !mixedHtml.includes('/trpg/char/5/'), mixedHtml);
  check("DM/观察者行不显示角色卡也不可点", (() => {
    const staff = { ...partyDm, members: [
      { user_id: "1", nickname: "守密人", role: "dm", char_name: "", char_id: 9, prepared: false },
      { user_id: "2", nickname: "旁观者", role: "ob", char_name: "", char_id: 10, prepared: false },
    ] };
    const staffHtml = partyCard(staff);
    return !staffHtml.includes("/trpg/char/") && !staffHtml.includes("查看角色卡")
      && !staffHtml.includes("未设置角色卡") && !staffHtml.includes("等待准备")
      && !staffHtml.includes("未准备");
  })());

  check("暂停记录时间行写明已暂停",
    timeRange({ start: "2026-11-12 09:00:00", state: "paused" }).includes("已暂停"),
    timeRange({ start: "2026-11-12 09:00:00", state: "paused" }));
  check("玩家数只算玩家", html.includes("3 人") && html.includes("2 人"));
  check("我的身份 DM", html.includes("我的身份：DM"));
  check("我的身份带角色卡名", html.includes("我的身份：艾拉（玩家）"));
  check("规则展示", html.includes("DND 5E") && html.includes("COC 7th"));
  check("消息条数", html.includes("128 条消息"));

  check("默认查询全部", fetchCalls[0] === "/api/trpg/records", String(fetchCalls[0]));
  els.mineOnly.checked = true;
  await load();
  check("只看我参加的带 mine=1", String(fetchCalls[fetchCalls.length - 1]).includes("mine=1"));

  process.exitCode = fail ? 1 : 0;
})();
