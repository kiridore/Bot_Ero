// 小埃直播间：SRS HTTP-FLV 播放（flv.js）+ 状态轮询（/api/live/status，方案 A 数据流探测）
const LIVE_URL = "https://live.littlero.tech/live/livestream.flv";
const POLL_MS = 10000;

const video = document.getElementById("liveVideo");
const overlay = document.getElementById("liveOverlay");
const statusText = document.getElementById("liveStatusText");
const playBtn = document.getElementById("livePlayBtn");

let player = null;
let playing = false;
let online = false;

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
  if (!window.flvjs || !flvjs.isSupported()) {
    statusText.textContent = "当前浏览器不支持直播播放，建议使用 Chrome / Edge";
    return;
  }
  destroyPlayer();
  player = flvjs.createPlayer({
    type: "flv",
    url: LIVE_URL,
    isLive: true,
    hasAudio: true,
    cors: true,
  });
  player.on(flvjs.Events.ERROR, (errType, detail) => {
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

playBtn.addEventListener("click", startPlayer);

GalleryAuth.renderAuth(document.getElementById("authArea"));
refresh();
setInterval(refresh, POLL_MS);
