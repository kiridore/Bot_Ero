// 记录列表页的「准备中」区块：成员行、查看卡链接、DM 审核提示
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_records.js", "utf8");
const start = src.indexOf("const ROLE_LABEL");
const end = src.indexOf("function renderList");
const factory = new Function("escapeHtml", `${src.slice(start, end)}\nreturn { partyCard, partyMemberRow };`);
const escapeHtml = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const api = factory(escapeHtml);

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

const party = {
  group_id: "296470819", rules_name: "COC 7th", dm: "111",
  prepared_count: 1, member_count: 2, is_dm: true,
  members: [
    { user_id: "111", nickname: "111", role: "dm", char_id: null, char_name: "", prepared: false },
    { user_id: "222", nickname: "老张", role: "", char_id: 3, char_name: "田宫真莉", prepared: true },
  ],
};
const html = api.partyCard(party);
check("含群号与规则", html.includes("296470819") && html.includes("COC 7th"));
check("含准备计数", html.includes("已准备 1/2"));
check("DM 有审核提示", html.includes("你是本群 DM"));
check("已准备成员可点卡", html.includes("查看角色卡") && html.includes("/trpg/char/222/3?party=296470819"));
check("未准备成员提示等待", html.includes("等待准备"));
check("观察者/DM 徽标", html.includes("DM"));

const observer = { group_id: "1", rules_name: "DND 5E", dm: "111", prepared_count: 0, member_count: 1, is_dm: false,
  members: [{ user_id: "333", nickname: "围观", role: "ob", char_id: null, char_name: "", prepared: false }] };
const html2 = api.partyCard(observer);
check("非 DM 无审核提示", !html2.includes("你是本群 DM"));
check("观察者徽标", html2.includes("观察者"));
check("空角色名显示未选", html2.includes("未选角色卡"));

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
