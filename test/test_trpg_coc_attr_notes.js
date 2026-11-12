// 「您的角色可能（只是可能！）」文案分档：边界值、0 值、超上限
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const start = src.indexOf("const ATTRS = [");
const end = src.indexOf("function describeAttr");
const fnEnd = src.indexOf("function poolHint");
if (start < 0 || end < 0) throw new Error("找不到属性描述数据");
const factory = new Function(
  `${src.slice(start, end)}${src.slice(end, fnEnd)}\nreturn { describeAttr, ATTR_NOTES, ATTR_NOTE_TITLE, ATTRS };`,
);
const api = factory();

const fails = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) fails.push(name);
}

check("标题照抄人物卡", api.ATTR_NOTE_TITLE === "您的角色可能（只是可能！）");
check("九项属性齐全", api.ATTRS.length === 9 && Object.keys(api.ATTR_NOTES).length === 9,
  `${api.ATTRS.length}/${Object.keys(api.ATTR_NOTES).length}`);

check("0 值不显示", api.describeAttr("str_score", 0) === "" && api.describeAttr("luck", "") === "");
check("力量分档边界", api.describeAttr("str_score", 15) === "虚弱，孱弱"
  && api.describeAttr("str_score", 16) === "力量弱小"
  && api.describeAttr("str_score", 60) === "有正常人的力量"
  && api.describeAttr("str_score", 99) === "超乎超乎常人的力量");
check("敏捷普通水平", api.describeAttr("dex_score", 50) === "普通人水平");
check("外貌高档", api.describeAttr("app_score", 90) === "沉鱼落雁，闭月羞花");
check("教育毕业线", api.describeAttr("edu_score", 40) === "小学毕业" && api.describeAttr("edu_score", 60) === "高中毕业");
check("智力天才", api.describeAttr("int_score", 85) === "天才级水准");
check("意志超上限档", api.describeAttr("pow_score", 100) === "钢铁之心，还能看见鬼"
  && api.describeAttr("pow_score", 150) === "你怕是个假人吧");
check("幸运最低档", api.describeAttr("luck", 10) === "克夫克妻" && api.describeAttr("luck", 99) === "被幸运女神所眷顾");
check("体型可超 99", api.describeAttr("siz_score", 120) === "听说你正在申请身高世界记录？"
  && api.describeAttr("siz_score", 300) === "过分了喂！");
check("未知属性返回空", api.describeAttr("nope", 50) === "");

console.log(fails.length ? `\n${fails.length} 项失败` : "\n全部通过");
process.exit(fails.length ? 1 : 0);
