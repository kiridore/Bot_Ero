(function () {
  const msgEl = document.getElementById("msg");
  const formSection = document.getElementById("createForm");
  const okSection = document.getElementById("createOk");

  function showMsg(text, ok) {
    msgEl.textContent = text;
    msgEl.className = "msg " + (ok ? "ok" : "err");
  }

  // 匹配必填截止、限时仅接龙显示
  document.querySelectorAll("input[name=actType]").forEach(function (r) {
    r.addEventListener("change", function () {
      const type = document.querySelector("input[name=actType]:checked").value;
      const needDeadline = type === "match" || type === "collect";
      document.getElementById("deadlineMust").hidden = !needDeadline;
      document.getElementById("hoursRow").style.display = type === "relay" ? "" : "none";
    });
  });

  function toServerTime(localValue) {
    // datetime-local "2026-08-30T20:00" → "2026-08-30 20:00"；空值原样返回
    return localValue ? localValue.replace("T", " ") : "";
  }

  // 富文本描述（共享 Tiptap 编辑器）
  let descEditor = null;
  RichText.mount(document.getElementById("description"), {
    content: RichText.docFrom(""),
    onReady: function (ed) { descEditor = ed; },
    onError: function (e) { showMsg("富文本编辑器加载失败：" + e.message, false); },
  });

  document.getElementById("submitBtn").addEventListener("click", async function () {
    if (!GalleryAuth.isLoggedIn()) { showMsg("请先登录", false); return; }
    const type = document.querySelector("input[name=actType]:checked").value;
    const title = document.getElementById("title").value.trim();
    if (!title) { showMsg("请填写标题", false); return; }
    const deadline = toServerTime(document.getElementById("deadline").value);
    if ((type === "match" || type === "collect") && !deadline) { showMsg("匹配与征集活动必须设定截止时间", false); return; }
    const body = { type: type, title: title, deadline: deadline || null };
    const descDoc = descEditor ? descEditor.getJSON() : null;
    if (descDoc && RichText.docText(descDoc)) body.description = JSON.stringify(descDoc);
    const signup = toServerTime(document.getElementById("signupDeadline").value);
    if (signup) body.signup_deadline = signup;
    if (type === "relay") body.hours_per_user = Number(document.getElementById("hours").value) || 48;
    this.disabled = true;
    showMsg("提交中…", true);
    try {
      const res = await fetch("/api/activities", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) { showMsg(data.detail || "创建失败", false); return; }
      document.getElementById("announceBox").textContent = data.announce;
      document.getElementById("manageLink").href = "/activities/" + data.id + "/manage";
      formSection.hidden = true;
      okSection.hidden = false;
    } catch {
      showMsg("网络错误，请重试", false);
    } finally {
      this.disabled = false;
    }
  });

  document.getElementById("copyBtn").addEventListener("click", async function () {
    const text = document.getElementById("announceBox").textContent;
    const copyMsg = document.getElementById("copyMsg");
    try {
      await navigator.clipboard.writeText(text);
      copyMsg.textContent = "已复制";
      copyMsg.className = "msg ok";
    } catch {
      copyMsg.textContent = "复制失败，请手动选择文本复制";
      copyMsg.className = "msg err";
    }
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
})();
