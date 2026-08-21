/* 社区时间线（社区主页）：侧边栏导航 + 登录态 + 无限滚动 feed + 30s 新事件轮询
   （Twitter 式「查看 N 条新事件」pill）+ 逐卡未读高亮（渲染即上报已读回执，被看到后高亮渐变褪回）。 */
(function () {
  "use strict";

  const PAGE_SIZE = 20;
  const POLL_MS = 30000;
  const READ_BATCH = 100;
  const READ_DEBOUNCE_MS = 300;
  const UNREAD_FADE_DELAY_MS = 800; // 未读卡被看到后高亮停留时长
  const UNREAD_FADE_DURATION_MS = 1500; // 高亮渐变时长（须与 timeline.css tl-unread-fade 的 1.5s 一致）
  const UNBOUND = "未绑定玩家";
  const feed = document.getElementById("feed");
  const sentinel = document.getElementById("sentinel");
  const statusEl = document.getElementById("tlStatus");
  const pill = document.getElementById("tlNewEvents");

  let cursor = null; // 下一页 keyset 游标（received_at|id，仅旧页无限滚动）
  let loading = false;
  let ended = false;
  let hasFeed = false;
  let topCursor = null; // 当前渲染顶部事件的 seq（rowid），新事件轮询锚点
  let renderedIds = new Set(); // 已渲染事件 id 去重（防轮询与首屏/旧页重叠）
  let pollTimer = null;
  let pollInFlight = false;
  let fetchingNew = false; // pill 点击拉取中
  let newCount = 0; // pill 计数（会话内未插入新事件）

  let unreadObserver = null; // 未读卡视口观察器（与 sentinel 独立）
  let unreadPending = new Set(); // 已读待提交：event_id（渲染即入队，视觉渐变独立进行）
  let unreadFlushTimer = null;
  let unreadRequestInFlight = false;

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
    item.dataset.reveal = "";
    item.dataset.eventId = ev.id;

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

    if (ev.unread) {
      item.classList.add("tl-unread");
      queueRead(item); // 渲染（加载）即上报已读；高亮仅为视觉提示，与上报结果解耦
      ensureUnreadObserver();
      if (unreadObserver) {
        unreadObserver.observe(item); // 首次进入视口才触发渐变（屏下卡片被看到前保持高亮）
      } else {
        scheduleUnreadFade(item); // 无观察器兜底：渲染后即渐变
      }
    }
    return item;
  }

  function appendPage(payload) {
    const frag = document.createDocumentFragment();
    (payload.events || []).forEach(function (ev) {
      frag.appendChild(renderEvent(ev, payload.users || {}));
      renderedIds.add(ev.id);
    });
    feed.appendChild(frag);
    if (!hasFeed && payload.events.length > 0 && topCursor == null) {
      topCursor = payload.events[0].seq; // 首屏顶部事件（新事件轮询锚点）
    }
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
    topCursor = null;
    renderedIds.clear();
    newCount = 0;
    pill.classList.add("hidden");
    pill.disabled = false;
    stopPolling();
    if (unreadFlushTimer) { clearTimeout(unreadFlushTimer); unreadFlushTimer = null; }
    unreadPending.clear();
    unreadRequestInFlight = false;
    if (unreadObserver) {
      unreadObserver.disconnect();
      unreadObserver = null;
    }
    feed.innerHTML = '<div class="tl-empty muted hidden" id="feedEmpty">还没有事件，去打个卡吧</div>';
    setStatus("");
  }

  async function loadPage() {
    if (loading || ended) return true;
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
        return false;
      }
      if (!res.ok) throw new Error("加载失败 " + res.status);
      appendPage(await res.json());
      sentinel.textContent = ended ? "— 已经到底了 —" : "加载中…";
      return true;
    } catch (err) {
      setStatus(err.message || "加载失败");
      return false;
    } finally {
      loading = false;
    }
  }

  function initObserver() {
    if (!("IntersectionObserver" in window)) return;
    const io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) loadPage();
    }, { rootMargin: "600px" });
    io.observe(sentinel);
  }

  /* —— 逐卡未读/已读：渲染即 queueRead 上报回执；观察器仅作渐变的视觉触发器 —— */
  function ensureUnreadObserver() {
    if (unreadObserver || !("IntersectionObserver" in window)) return;
    unreadObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        const el = entry.target;
        if (el._tlRead) return; // 已调度渐变
        unreadObserver.unobserve(el); // one-shot：首次进入视口即触发
        scheduleUnreadFade(el);
      });
    }, { threshold: 0 });
  }

  /* 未读卡被看到后：先停留 UNREAD_FADE_DELAY_MS，再渐变 UNREAD_FADE_DURATION_MS 褪回正常并清理。
     纯视觉时序，独立于已读上报必定走完（reduced-motion 下动画禁用，由本定时器跳变清理）。 */
  function scheduleUnreadFade(el) {
    if (el._tlRead) return;
    el._tlRead = {};
    el._tlRead.fadeTimer = setTimeout(function () {
      el.classList.add("tl-fading");
      el._tlRead.cleanupTimer = setTimeout(function () {
        el.classList.remove("tl-unread", "tl-fading");
        delete el._tlRead;
      }, UNREAD_FADE_DURATION_MS);
    }, UNREAD_FADE_DELAY_MS);
  }

  function queueRead(el) {
    const id = el.dataset.eventId;
    if (!id || unreadPending.has(id)) return;
    unreadPending.add(id);
    scheduleReadFlush();
  }

  function scheduleReadFlush() {
    if (unreadFlushTimer) return;
    unreadFlushTimer = setTimeout(flushReadPending, READ_DEBOUNCE_MS);
  }

  async function flushReadPending() {
    unreadFlushTimer = null;
    if (unreadRequestInFlight || unreadPending.size === 0) return;
    const ids = [...unreadPending].slice(0, READ_BATCH);
    unreadRequestInFlight = true;
    try {
      const res = await fetch("/api/timeline/read", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, GalleryAuth.headers()),
        body: JSON.stringify({ event_ids: ids }),
      });
      if (res.status === 401) {
        stopPolling();
        openLoginDialog();
        setStatus("请先登录");
        return; // pending 保留，重新登录时 resetFeed 清空
      }
      if (!res.ok) throw new Error("已读提交失败 " + res.status);
      ids.forEach(function (id) { unreadPending.delete(id); });
      // 渐变动画独立于已读上报播放到结束，成功后不做任何 DOM/observer 清理
      // 成功后立即循环发送剩余批次，避免 >100 张新卡时剩余 id 滞留到 pagehide
      if (unreadPending.size > 0) scheduleReadFlush();
    } catch (err) {
      // 失败：保留高亮与待提交集合，下次离开/pagehide 再提交，不紧密重试
      setStatus(err.message || "已读提交失败");
    } finally {
      unreadRequestInFlight = false;
    }
  }

  window.addEventListener("pagehide", function () {
    if (unreadPending.size === 0) return;
    const ids = [...unreadPending].slice(0, READ_BATCH);
    try {
      fetch("/api/timeline/read", {
        method: "POST",
        headers: Object.assign({ "Content-Type": "application/json" }, GalleryAuth.headers()),
        body: JSON.stringify({ event_ids: ids }),
        keepalive: true,
      });
    } catch (err) { /* 尽力而为 */ }
  });

  /* —— 30s 轮询 + 「查看 N 条新事件」pill（会话内，不打断阅读）—— */
  function updatePill(n) {
    newCount = n;
    if (n > 0) {
      pill.textContent = "查看 " + n + " 条新事件";
      pill.classList.remove("hidden");
    } else {
      pill.classList.add("hidden");
    }
  }

  function startPolling() {
    if (pollTimer || !GalleryAuth.isLoggedIn()) return;
    pollTimer = setInterval(pollOnce, POLL_MS);
  }

  function stopPolling() {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
  }

  async function pollOnce() {
    if (pollInFlight || fetchingNew || !GalleryAuth.isLoggedIn()) return;
    pollInFlight = true;
    try {
      const params = new URLSearchParams();
      if (topCursor != null) params.set("after", String(topCursor));
      const res = await fetch("/api/timeline/poll?" + params.toString(), {
        headers: GalleryAuth.headers(),
      });
      if (res.status === 401) {
        stopPolling();
        openLoginDialog();
        setStatus("请先登录");
        return;
      }
      if (!res.ok) throw new Error("轮询失败 " + res.status);
      const data = await res.json();
      updatePill(data.count || 0);
    } catch (err) {
      // 非 401 失败保留现有 pill，等待下个周期
    } finally {
      pollInFlight = false;
    }
  }

  async function fetchNewEvents() {
    if (fetchingNew) return;
    fetchingNew = true;
    pill.disabled = true;
    let after = topCursor;
    let allEvents = [];
    let users = {};
    try {
      while (true) {
        const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
        if (after != null) params.set("after", String(after));
        const res = await fetch("/api/timeline/new?" + params.toString(), {
          headers: GalleryAuth.headers(),
        });
        if (res.status === 401) {
          openLoginDialog();
          setStatus("请先登录");
          return;
        }
        if (!res.ok) throw new Error("加载失败 " + res.status);
        const data = await res.json();
        Object.assign(users, data.users || {});
        allEvents = allEvents.concat(data.events || []);
        if (data.next_after == null) break;
        after = data.next_after;
      }
      // 按 id 去重（与首屏/旧页/批间重叠），再按 feed 展示序新→旧
      const seen = new Set(renderedIds);
      const fresh = [];
      allEvents.forEach(function (ev) {
        if (seen.has(ev.id)) return;
        seen.add(ev.id);
        fresh.push(ev);
      });
      if (fresh.length === 0) {
        updatePill(0);
        return;
      }
      fresh.sort(function (a, b) {
        if (a.received_at !== b.received_at) {
          return a.received_at < b.received_at ? 1 : -1;
        }
        return a.id < b.id ? 1 : (a.id > b.id ? -1 : 0);
      });
      const frag = document.createDocumentFragment();
      fresh.forEach(function (ev) {
        frag.appendChild(renderEvent(ev, users));
        renderedIds.add(ev.id);
      });
      const emptyEl = document.getElementById("feedEmpty");
      if (emptyEl) emptyEl.classList.add("hidden");
      feed.insertBefore(frag, feed.firstChild);
      topCursor = fresh[0].seq; // 最新插入事件
      hasFeed = true;
      updatePill(0);
      const firstCard = feed.firstElementChild;
      if (firstCard && typeof firstCard.scrollIntoView === "function") {
        firstCard.scrollIntoView({ block: "start", behavior: "auto" });
      }
    } catch (err) {
      // 失败不改 DOM/topCursor/pill count
      setStatus(err.message || "加载失败");
    } finally {
      fetchingNew = false;
      pill.disabled = false;
    }
  }

  /* —— 登录态 —— */
  function bindAuth() {
    GalleryAuth.renderAuth(document.getElementById("authArea"));
    // 包装 login：成功后重置、重拉首屏并启动轮询（首次成功加载后才建 timer）
    const origLogin = GalleryAuth.login.bind(GalleryAuth);
    GalleryAuth.login = async function (key) {
      const session = await origLogin(key);
      resetFeed();
      const ok = await loadPage();
      if (ok) startPolling();
      return session;
    };
    if (GalleryAuth.isLoggedIn()) {
      loadPage().then(function (ok) { if (ok) startPolling(); });
    } else {
      setTimeout(openLoginDialog, 300);
    }
  }

  pill.addEventListener("click", fetchNewEvents);

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
