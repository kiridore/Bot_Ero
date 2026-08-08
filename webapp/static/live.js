// 小埃直播间：SRS HTTP-FLV 播放（mpegts.js，SRS 官方播放器同款）+ 状态轮询 + 观众在场
const LIVE_URL = "https://live.littlero.tech/live/livestream.flv";
const POLL_MS = 10000;
const HEARTBEAT_MS = 25000;
const VIEWERS_MS = 15000;
const CLIENT_ID_KEY = "botero_live_client_id";

const video = document.getElementById("liveVideo");
const overlay = document.getElementById("liveOverlay");
const statusText = document.getElementById("liveStatusText");
const playBtn = document.getElementById("livePlayBtn");
const viewerCountEl = document.getElementById("viewerCount");
const viewerListEl = document.getElementById("viewerList");

let player = null;
let playing = false;
let online = false;

function clientId() {
  let id = sessionStorage.getItem(CLIENT_ID_KEY);
  if (!id) {
    id = window.crypto && crypto.randomUUID
      ? crypto.randomUUID()
      : "c" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    sessionStorage.setItem(CLIENT_ID_KEY, id);
  }
  return id;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function destroyPlayer() {
  if (player) {
    try { player.destroy(); } catch (e) { /* ignore */ }
    player = null;
  }
  video.pause();
  video.removeAttribute("src");
  video.load();
}

function startPlayer() {
  if (!online) return;
  if (!window.mpegts || !mpegts.isSupported()) {
    statusText.textContent = "当前浏览器不支持直播播放，建议使用 Chrome / Edge";
    return;
  }
  destroyPlayer();
  player = mpegts.createPlayer(
    {
      type: "flv",
      url: LIVE_URL,
      isLive: true,
      hasAudio: true,
    },
    { enableStashBuffer: false, enableWorker: true } // 低延迟直播
  );
  player.on(mpegts.Events.ERROR, (errType, detail) => {
    console.warn("直播流错误:", errType, detail);
    playing = false;
    destroyPlayer();
    refresh(); // 状态轮询驱动重连 UI
  });
  player.attachMediaElement(video);
  player.load();
  player
    .play()
    .then(() => {
      playing = true;
      overlay.classList.add("hidden");
    })
    .catch(() => {
      playing = false;
      refresh();
    });
}

async function refresh() {
  try {
    const res = await fetch("/api/live/status", { cache: "no-store" });
    online = !!(await res.json()).online;
  } catch (e) {
    online = false;
  }
  if (!playing) {
    overlay.classList.remove("hidden");
    if (online) {
      statusText.textContent = "直播中";
      playBtn.classList.remove("hidden");
    } else {
      statusText.textContent = "未开播";
      playBtn.classList.add("hidden");
    }
  }
}

// —— 观众在场 ——
async function sendHeartbeat() {
  try {
    await fetch("/api/live/heartbeat", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...GalleryAuth.headers() },
      body: JSON.stringify({ client_id: clientId() }),
    });
  } catch (e) { /* 网络异常静默，下轮重试 */ }
}

async function refreshViewers() {
  try {
    const res = await fetch("/api/live/viewers", { cache: "no-store" });
    const data = await res.json();
    const items = data.viewers || [];
    viewerCountEl.textContent = String(items.length);
    viewerListEl.innerHTML = items.length
      ? items
          .map(
            (v) =>
              `<li>${escapeHtml(v.name)}${v.member ? ' <span class="viewer-tag">成员</span>' : ""}</li>`
          )
          .join("")
      : '<li class="muted">暂无观众</li>';
  } catch (e) { /* 忽略 */ }
}

playBtn.addEventListener("click", startPlayer);

GalleryAuth.refreshMe().finally(() => {
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  sendHeartbeat();
  refreshViewers();
  setInterval(sendHeartbeat, HEARTBEAT_MS);
  setInterval(refreshViewers, VIEWERS_MS);
});
refresh();
setInterval(refresh, POLL_MS);
