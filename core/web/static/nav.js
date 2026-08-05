/* 站点导航条：全子应用共享。点击跳转导航主页与各功能子域，当前域高亮。
   部署时修改 NAV_HOME_URL（导航主页地址）与 NAV_ITEMS 中的子域 host。 */
const NAV_HOME_URL = "https://nav.littlero.com";
const NAV_HOME_LABEL = "小埃中继站";
const NAV_ITEMS = [
  { label: "图库", host: "gallery.littlero.com" },
  { label: "个人中心", host: "profile.littlero.com" },
  { label: "跑团", host: "trpg.littlero.com" },
  { label: "留言簿", host: "guestbook.littlero.com" },
  { label: "闹钟", host: "alarms.littlero.com" },
  { label: "活动", host: "activities.littlero.com" },
];

(function () {
  const style = document.createElement("style");
  style.textContent = `
.site-nav {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.15rem 1.1rem;
  padding: 0.55rem max(1.25rem, calc((100vw - 880px) / 2));
  background: var(--paper-card, #fbf7ec);
  border-bottom: 1px solid var(--rule, #b8ad8e);
  font-family: Georgia, "Songti SC", "Noto Serif SC", "SimSun", serif;
  font-size: 0.85rem;
}
.site-nav-brand {
  font-weight: 700;
  letter-spacing: 0.18em;
  color: var(--ink, #2c2a24);
  text-decoration: none;
  white-space: nowrap;
}
.site-nav-brand:hover { color: var(--accent-ink, #3f5347); }
.site-nav-sep {
  flex-shrink: 0;
  border-left: 1px solid var(--rule, #b8ad8e);
  height: 1rem;
  align-self: center;
}
.site-nav a {
  color: var(--ink-soft, #6b6350);
  text-decoration: none;
  white-space: nowrap;
  padding-bottom: 0.1rem;
  border-bottom: 1px solid transparent;
}
.site-nav a:hover { color: var(--ink, #2c2a24); }
.site-nav a.active {
  color: var(--accent-ink, #3f5347);
  border-bottom-color: var(--accent, #5f7a68);
}
`;
  document.head.appendChild(style);

  const current = location.hostname;
  const links = NAV_ITEMS.map(
    (it) =>
      `<a href="https://${it.host}/"${it.host === current ? ' class="active"' : ""}>${it.label}</a>`
  ).join("");

  const nav = document.createElement("nav");
  nav.className = "site-nav";
  nav.setAttribute("aria-label", "站点导航");
  nav.innerHTML =
    `<a class="site-nav-brand" href="${NAV_HOME_URL}">${NAV_HOME_LABEL}</a>` +
    `<span class="site-nav-sep"></span>` +
    links;
  document.body.insertBefore(nav, document.body.firstChild);
})();
