/* 社区时间线（社区主页）：侧边栏导航 + 登录态 + 无限滚动 feed。 */
(function () {
  "use strict";

  const PAGE_SIZE = 50;
  const UNBOUND = "未绑定玩家";
  const feed = document.getElementById("feed");
  const sentinel = document.getElementById("sentinel");
  const statusEl = document.getElementById("tlStatus");

  let cursor = null; // 下一页 keyset 游标
  let loading = false;
  let ended = false;
  let hasFeed = false;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function setStatus(text) {
    statusEl.textContent = text || "";
  }

  function openLoginDialog() {
    const dlg = GalleryAuth.ensureLoginDialog();
    if (dlg && typeof dlg.showModal === "function") dlg.showModal();
  }
  window.openLoginDialog = openLoginDialog;

  /* —— 侧边栏：entries.json 功能导航（唯一入口维护点）—— */
  async function loadNav() {
    try {
      const res = await fetch("/entries.json");
      if (!res.ok) return;
      const entries = await res.json();
      const nav = document.getElementById("tlNav");
      nav.innerHTML = '<div class="tl-nav-muted">功能</div>';
      entries.forEach(function (entry) {
        if (entry.url) {
          const a = document.createElement("a");
          a.href = entry.url;
          a.className = "tl-nav-link";
          a.innerHTML =
            '<span class="tl-nav-name">' + esc(entry.name) + "</span>" +
            (entry.desc ? '<span class="tl-nav-desc">' + esc(entry.desc) + "</span>" : "");
          nav.appendChild(a);
        } else if (entry.links) {
          const group = document.createElement("div");
          group.className = "tl-nav-group";
          group.innerHTML = '<span class="tl-nav-name">' + esc(entry.name) + "</span>";
          entry.links.forEach(function (link) {
            const a = document.createElement("a");
            a.className = "tl-nav-sublink";
            if (link.url) {
              a.href = link.url;
              a.textContent = link.label;
            } else if (link.copy) {
              a.href = "#";
              a.textContent = link.label;
              a.addEventListener("click", function (e) {
                e.preventDefault();
                if (navigator.clipboard) navigator.clipboard.writeText(link.copy);
              });
            }
            group.appendChild(a);
          });
          nav.appendChild(group);
        }
      });
    } catch (err) {
      /* 导航加载失败不阻塞时间线 */
    }
  }

  /* —— 时间线渲染 —— */
  function fmtTime(ts) {
    const d = new Date(String(ts).replace(" ", "T"));
    if (isNaN(d.getTime())) return ts;
    const pad = function (n) { return String(n).padStart(2, "0"); };
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
      " " + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
  }

  function substitute(text, users) {
    return text.replace(/\{id:(\d+)\}/g, function (_, uid) {
      const u = users[uid];
      if (!u) return UNBOUND;
      return '<span class="tl-user">' + esc(u.name) + "</span>";
    });
  }

  function renderEvent(ev, users) {
    const item = document.createElement("article");
    item.className = "tl-item";

    const head = document.createElement("div");
    head.className = "tl-item-head";
    const img = document.createElement("img");
    img.className = "tl-avatar";
    img.src = ev.actor.avatar_url || "";
    img.alt = "";
    img.onerror = function () { img.style.display = "none"; };
    const name = document.createElement("strong");
    name.className = "tl-actor";
    name.textContent = ev.actor.display_name || UNBOUND;
    const time = document.createElement("time");
    time.className = "tl-time";
    time.textContent = fmtTime(ev.received_at);
    head.append(img, name, time);
    item.appendChild(head);

    const title = document.createElement("p");
    title.className = "tl-title";
    title.innerHTML = substitute(ev.title || "", users);
    item.appendChild(title);

    if (ev.description) {
      const desc = document.createElement("p");
      desc.className = "tl-desc";
      desc.innerHTML = substitute(ev.description, users);
      item.appendChild(desc);
    }

    if (ev.data && Array.isArray(ev.data.images) && ev.data.images.length) {
      const strip = document.createElement("div");
      strip.className = "tl-images";
      ev.data.images.forEach(function (src) {
        const s = String(src);
        const a = document.createElement("a");
        a.href = s.startsWith("/thumb/") ? s.replace("/thumb/", "/media/") : s;
        a.target = "_blank";
        a.rel = "noopener";
        const img = document.createElement("img");
        img.src = s;
        img.alt = "";
        img.loading = "lazy";
        a.appendChild(img);
        strip.appendChild(a);
      });
      item.appendChild(strip);
    }

    if (ev.target && ev.target.url) {
      const a = document.createElement("a");
      a.className = "tl-detail";
      a.href = ev.target.url;
      a.target = "_blank";
      a.rel = "noopener";
      a.textContent = "» 详情";
      item.appendChild(a);
    }
    return item;
  }

  function appendPage(payload) {
    const frag = document.createDocumentFragment();
    (payload.events || []).forEach(function (ev) {
      frag.appendChild(renderEvent(ev, payload.users || {}));
    });
    feed.appendChild(frag);
    if (!hasFeed && payload.events.length === 0) {
      document.getElementById("feedEmpty").classList.remove("hidden");
    }
    cursor = payload.next_cursor || null;
    ended = !cursor;
    hasFeed = true;
  }

  function resetFeed() {
    cursor = null;
    ended = false;
    hasFeed = false;
    feed.innerHTML = '<div class="tl-empty muted hidden" id="feedEmpty">还没有事件，去打个卡吧</div>';
    setStatus("");
  }

  async function loadPage() {
    if (loading || ended) return;
    loading = true;
    setStatus("加载中…");
    try {
      const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
      if (cursor) params.set("cursor", cursor);
      const res = await fetch("/api/timeline?" + params.toString(), {
        headers: GalleryAuth.headers(),
      });
      if (res.status === 401) {
        openLoginDialog();
        setStatus("请先登录");
        return;
      }
      if (!res.ok) throw new Error("加载失败 " + res.status);
      appendPage(await res.json());
      setStatus("");
      sentinel.textContent = ended ? "— 已经到底了 —" : "加载中…";
    } catch (err) {
      setStatus(err.message || "加载失败");
    } finally {
      loading = false;
    }
  }

  function initObserver() {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) loadPage();
    }, { rootMargin: "400px" });
    io.observe(sentinel);
  }

  /* —— 登录态 —— */
  function bindAuth() {
    GalleryAuth.renderAuth(document.getElementById("authArea"));
    // 包装 login：成功后重置并重新拉取时间线
    const origLogin = GalleryAuth.login.bind(GalleryAuth);
    GalleryAuth.login = async function (key) {
      const session = await origLogin(key);
      resetFeed();
      loadPage();
      return session;
    };
    if (GalleryAuth.isLoggedIn()) {
      loadPage();
    } else {
      setTimeout(openLoginDialog, 300);
    }
  }

  loadNav();
  bindAuth();
  initObserver();

  const dateEl = document.getElementById("mastheadDate");
  if (dateEl) {
    dateEl.textContent = new Date().toLocaleDateString("zh-CN", {
      year: "numeric", month: "long", day: "numeric", weekday: "long",
    });
  }
})();
