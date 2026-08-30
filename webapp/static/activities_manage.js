(function () {
  const STATUS_LABEL = { open: "报名中", running: "进行中", finished: "已结束", cancelled: "已取消" };
  const MEMBER_STATUS_ICON = { done: "✓", skipped: "跳过", missed: "未交", left: "退出", pending: "…" };
  const SUPER_USER_IDS = ["1057613133"];

  const id = location.pathname.split("/")[2];
  const msgEl = document.getElementById("msg");
  let actCache = null;

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function showMsg(text, ok) {
    msgEl.textContent = text;
    msgEl.className = "msg " + (ok ? "ok" : "err");
  }

  function toLocalTime(serverValue) {
    // "2099-01-01 20:00:00" → "2099-01-01T20:00"；空返回 ""
    return serverValue ? serverValue.slice(0, 16).replace(" ", "T") : "";
  }

  function toServerTime(localValue) {
    return localValue ? localValue.replace("T", " ") : "";
  }

  async function api(path, method, body) {
    const res = await fetch(path, {
      method: method,
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "操作失败");
    return data;
  }

  function isOwner(act) {
    const session = GalleryAuth.load();
    const uid = session && session.user_id;
    return String(act.created_by) === String(uid) || SUPER_USER_IDS.includes(String(uid));
  }

  function renderActions(act) {
    const row = document.getElementById("actionRow");
    row.innerHTML = "";
    const mk = function (text, cls, handler, hint) {
      const btn = document.createElement("button");
      btn.className = cls; btn.textContent = text;
      btn.addEventListener("click", handler);
      row.appendChild(btn);
      if (hint) {
        const p = document.createElement("p");
        p.className = "muted"; p.textContent = hint;
        row.appendChild(p);
      }
    };
    if (act.status === "open") {
      mk("开始活动", "btn-primary", function () {
        if (!confirm("开始后系统约 1 分钟内通知所有成员，确认开始？")) return;
        api("/api/activities/" + id + "/start", "POST").then(
          d => showMsg(d.note || "已请求开始", true), e => showMsg(e.message, false));
      }, "约 1 分钟内生效（等待机器人心跳）");
      mk("取消活动", "btn-danger", function () {
        if (!confirm("取消后无法恢复，确认取消？")) return;
        api("/api/activities/" + id + "/cancel", "POST").then(
          () => { showMsg("已取消", true); load(); }, e => showMsg(e.message, false));
      });
    } else if (act.status === "running") {
      mk("提前结束", "btn-danger", function () {
        if (!confirm("未提交成员将记为未交并归档，约 1 分钟生效，确认结束？")) return;
        api("/api/activities/" + id + "/finish", "POST").then(
          d => showMsg(d.note || "已请求结束", true), e => showMsg(e.message, false));
      }, "约 1 分钟内生效（等待机器人心跳）");
    }
  }

  function render(act) {
    actCache = act;
    const badge = document.getElementById("statusBadge");
    const cls = act.status === "open" ? "badge-open" : act.status === "running" ? "badge-running"
      : act.status === "finished" ? "badge-done" : "badge-cancelled";
    badge.innerHTML = '<span class="status-badge ' + cls + '">' + (STATUS_LABEL[act.status] || act.status) + "</span>";

    const editable = act.status === "open" || act.status === "running";
    ["mTitle", "mDesc", "mDeadline"].forEach(function (elId) {
      document.getElementById(elId).disabled = !editable;
    });
    document.getElementById("mHoursRow").style.display = act.type === "relay" ? "" : "none";
    document.getElementById("mSignupRow").style.display = act.status === "open" ? "" : "none";
    document.getElementById("mHours").disabled = act.status !== "open";
    document.getElementById("mSignup").disabled = act.status !== "open";
    document.getElementById("saveBtn").disabled = !editable;

    document.getElementById("mTitle").value = act.title || "";
    document.getElementById("mDesc").value = act.description || "";
    document.getElementById("mHours").value = act.hours_per_user || 48;
    document.getElementById("mSignup").value = toLocalTime(act.signup_deadline);
    document.getElementById("mDeadline").value = toLocalTime(act.deadline);

    document.getElementById("memberCount").textContent = act.members.length;
    document.getElementById("memberList").innerHTML = act.members.map(function (m) {
      return '<span class="member-chip">' + (m.seq || "·") + ". " + escapeHtml(m.nickname)
        + " " + (MEMBER_STATUS_ICON[m.status] || "") + "</span>";
    }).join("");

    document.getElementById("announceBlock").hidden = act.status !== "open";
    renderActions(act);
  }

  async function loadAnnounce() {
    try {
      const d = await api("/api/activities/" + id + "/announce", "GET");
      document.getElementById("announceBox").textContent = d.announce;
    } catch { /* 非创建人拿不到，隐藏块即可 */ }
  }

  async function load() {
    if (!GalleryAuth.isLoggedIn()) {
      document.getElementById("denyTitle").textContent = "请先登录";
      document.getElementById("denyCard").hidden = false;
      return;
    }
    try {
      const res = await fetch("/api/activities/" + id);
      if (!res.ok) {
        document.getElementById("denyTitle").textContent = "活动不存在";
        document.getElementById("denyCard").hidden = false;
        return;
      }
      const act = await res.json();
      if (!isOwner(act)) {
        document.getElementById("denyCard").hidden = false;
        return;
      }
      document.getElementById("manageCard").hidden = false;
      render(act);
      if (act.status === "open") await loadAnnounce();
    } catch {
      showMsg("加载失败", false);
    }
  }

  document.getElementById("saveBtn").addEventListener("click", async function () {
    const body = { title: document.getElementById("mTitle").value.trim() };
    if (!body.title) { showMsg("标题不能为空", false); return; }
    const desc = document.getElementById("mDesc").value.trim();
    if (desc) body.description = desc;
    const dl = toServerTime(document.getElementById("mDeadline").value);
    if (dl) body.deadline = dl;
    if (actCache && actCache.status === "open") {
      const su = toServerTime(document.getElementById("mSignup").value);
      if (su) body.signup_deadline = su;
      if (actCache.type === "relay") body.hours_per_user = Number(document.getElementById("mHours").value) || 48;
    }
    try {
      await api("/api/activities/" + id, "PATCH", body);
      showMsg("已保存", true);
      await load();
    } catch (e) { showMsg(e.message, false); }
  });

  document.getElementById("copyBtn").addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(document.getElementById("announceBox").textContent);
      showMsg("已复制", true);
    } catch { showMsg("复制失败，请手动选择文本", false); }
  });

  GalleryAuth.renderAuth(document.getElementById("authArea"));
  load();
  setInterval(load, 15000); // 开始终止动作后观察状态跳转（bot 心跳 ≤60s 生效）
})();
