// 建卡页：保存后留在编辑页（新建即有卡号）+ 本页自己的 showToast
const fs = require("fs");

const src = fs.readFileSync("webapp/static/trpg_coc.js", "utf8");
const html = fs.readFileSync("webapp/static/trpg_coc.html", "utf8");
const css = fs.readFileSync("webapp/static/trpg.css", "utf8");

const checks = [];
function check(name, ok, extra) {
  console.log(`${ok ? "ok" : "FAIL"} - ${name}${extra ? " " + extra : ""}`);
  if (!ok) checks.push(name);
}

// 1) 保存后跳回编辑页并带 saved=1，而不是回列表
check("保存后留在编辑页", /window\.location\.href = savedId \? `\/trpg\/coc\/\$\{savedId\}\?saved=1` : "\/trpg"/.test(src),
  (src.match(/window\.location\.href = [^\n;]+/) || [""])[0]);
check("不再直接跳列表", !/window\.location\.href = "\/trpg";\n  \} catch/.test(src));

// 2) 保存回来的提示
check("识别 saved=1", /get\("saved"\) === "1"/.test(src));
check("提示可以应用年龄调整", /现在可以应用年龄调整/.test(src));
check("提示后清理地址栏", /history\.replaceState\(\{\}, "", location\.pathname\)/.test(src));

// 3) showToast 在本页确实有定义（之前 12 处调用全是 ReferenceError）
const start = src.indexOf("function showToast");
const end = src.indexOf("function attr(name)", start);
check("本页定义了 showToast", start > 0 && end > start);
const toastCalls = (src.match(/showToast\(/g) || []).length;
check("调用点仍然存在", toastCalls >= 10, String(toastCalls));

// 4) 页面与样式具备承载 toast 的元素
check("页面有 #toast 容器", /id="toast"/.test(html));
check("样式定义 .toast", /^\.toast \{/m.test(css) && /\.toast\[hidden\]/.test(css));

// 5) 真实执行 showToast：不抛错、写入文字、显示元素
const el = { textContent: "", className: "", hidden: true };
const document = { getElementById: (id) => (id === "toast" ? el : null) };
const factory = new Function("document", "clearTimeout", "setTimeout",
  `${src.slice(start, end)}\nreturn showToast;`);
const showToast = factory(document, () => {}, () => 1);
let threw = "";
try {
  showToast("已保存，现在可以应用年龄调整", false);
} catch (err) { threw = String(err); }
check("showToast 可执行", threw === "", threw);
check("showToast 写入文字并显示", el.textContent.includes("已保存") && el.hidden === false,
  `${el.textContent} / hidden=${el.hidden}`);
try { showToast("出错了", true); } catch (err) { threw = String(err); }
check("错误态带 error 类", el.className.includes("error"), el.className);

console.log(checks.length ? `\n${checks.length} 项失败` : "\n全部通过");
process.exit(checks.length ? 1 : 0);
