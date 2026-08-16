const weekKey = (() => {
  const parts = location.pathname.split("/").filter(Boolean);
  return parts.length >= 2 ? parts[parts.length - 1] : "";
})();

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

function sectionTitle(kicker, title) {
  const head = el("header", "weekly-section-head");
  head.appendChild(el("p", "weekly-section-kicker", kicker));
  head.appendChild(el("h2", "weekly-section-title", title));
  return head;
}

function emptyOr(container, sectionEl, condition, msg) {
  if (condition) {
    container.appendChild(sectionEl);
  } else {
    const p = el("p", "weekly-empty muted", msg);
    container.appendChild(p);
  }
}

async function fetchList() {
  try {
    const res = await fetch("/api/weekly", { headers: GalleryAuth.headers() });
    if (res.status === 401) {
      document.getElementById("weeklyEmpty").textContent = "请先登录后查看周报";
      const dlg = GalleryAuth.ensureLoginDialog();
      if (dlg && typeof dlg.showModal === "function") dlg.showModal();
      return [];
    }
    if (!res.ok) throw new Error("列表加载失败 " + res.status);
    const data = await res.json();
    return data.items || [];
  } catch (err) {
    document.getElementById("weeklyEmpty").textContent = err.message;
    return [];
  }
}

async function fetchDetail() {
  try {
    const res = await fetch(`/api/weekly/${weekKey}`, { headers: GalleryAuth.headers() });
    if (res.status === 401) {
      document.getElementById("weeklyEmpty").textContent = "请先登录后查看周报";
      const dlg = GalleryAuth.ensureLoginDialog();
      if (dlg && typeof dlg.showModal === "function") dlg.showModal();
      return null;
    }
    if (!res.ok) throw new Error("周报加载失败 " + res.status);
    return await res.json();
  } catch (err) {
    document.getElementById("weeklyEmpty").textContent = err.message;
    return null;
  }
}

function renderNav(items) {
  const select = document.getElementById("issueSelect");
  const prev = document.getElementById("prevIssue");
  const next = document.getElementById("nextIssue");
  if (!items.length) {
    select.style.display = "none";
    prev.disabled = true;
    next.disabled = true;
    return;
  }
  select.innerHTML = "";
  items.forEach((it) => {
    const opt = document.createElement("option");
    opt.value = it.week_key;
    opt.textContent = `第 ${it.issue ?? "?"} 期 · ${it.start ?? ""}`;
    if (it.week_key === weekKey) opt.selected = true;
    select.appendChild(opt);
  });
  select.onchange = () => {
    if (select.value) location.href = `/weekly/${select.value}`;
  };
  const idx = items.findIndex((it) => it.week_key === weekKey);
  if (idx <= 0) prev.disabled = true; else {
    prev.disabled = false;
    prev.onclick = () => (location.href = `/weekly/${items[idx - 1].week_key}`);
  }
  if (idx < 0 || idx >= items.length - 1) next.disabled = true; else {
    next.disabled = false;
    next.onclick = () => (location.href = `/weekly/${items[idx + 1].week_key}`);
  }
}

function renderHeader(d) {
  const p = d.period || {};
  document.getElementById("weeklyDateRange").textContent =
    `${p.start || "?"} — ${p.end || "?"}`;

  const paper = document.getElementById("weeklyPaper");
  paper.innerHTML = "";

  const mast = el("header", "weekly-paper-header");
  mast.appendChild(el("p", "weekly-paper-kicker", `第 ${p.issue ?? "?"} 期`));
  mast.appendChild(el("h2", "weekly-paper-title", "小埃周报"));
  mast.appendChild(el("p", "weekly-paper-subtitle", (d.headline && d.headline.title) || ""));
  const big = el("div", "weekly-big-numbers");
  big.appendChild(numberCard("本周消息", p.total_messages ?? 0));
  big.appendChild(numberCard("总字数", p.total_chars ?? 0));
  mast.appendChild(big);
  paper.appendChild(mast);
}

function numberCard(label, value) {
  const card = el("div", "weekly-big-num");
  card.appendChild(el("span", "weekly-big-num-label", label));
  card.appendChild(el("span", "weekly-big-num-value", String(value)));
  return card;
}

function renderHeadline(d) {
  const h = d.headline || {};
  const sec = el("section", "weekly-section");
  sec.appendChild(sectionTitle("头版 · 本周头条", h.title || "平淡的一周"));
  sec.appendChild(el("p", "weekly-headline-body", h.body || ""));
  const stats = el("div", "weekly-headline-stats");
  (h.stats || []).forEach((s) => {
    const card = el("div", "weekly-headline-stat");
    card.appendChild(el("span", "weekly-headline-stat-label", s.label));
    card.appendChild(el("span", "weekly-headline-stat-value", String(s.value)));
    stats.appendChild(card);
  });
  sec.appendChild(stats);
  document.getElementById("weeklyPaper").appendChild(sec);
}

function renderCheckin(c) {
  const sec = el("section", "weekly-section");
  sec.appendChild(sectionTitle("二版 · 打卡战报", "打卡与抽奖"));
  const grid = el("div", "weekly-two-col");

  const left = el("div", "weekly-col");
  left.appendChild(el("h3", "weekly-col-title", "打卡战报"));
  const kpis = el("div", "weekly-kpis");
  kpis.appendChild(kpi("总打卡次数", c.total));
  kpis.appendChild(kpi("参与人数", c.users));
  kpis.appendChild(kpi("日均", c.daily_avg));
  kpis.appendChild(kpi("补卡次数", c.remedy));
  left.appendChild(kpis);
  if (c.full_week && c.full_week.length) {
    left.appendChild(el("h4", "weekly-mini-title", "全勤榜（7/7）"));
    const ul = el("ul", "weekly-list");
    c.full_week.forEach((u) => ul.appendChild(el("li", "", u.name)));
    left.appendChild(ul);
  } else {
    left.appendChild(el("p", "weekly-empty muted", "本周无人全勤"));
  }
  if (c.images && c.images.length) {
    left.appendChild(el("h4", "weekly-mini-title", "打卡群像墙"));
    const wall = el("div", "weekly-image-wall");
    c.images.forEach((img) => {
      const card = el("figure", "weekly-image-card");
      const im = document.createElement("img");
      im.src = img.url;
      im.alt = img.name;
      im.loading = "lazy";
      const cap = el("figcaption", "weekly-image-caption", img.name);
      card.append(im, cap);
      wall.appendChild(card);
    });
    left.appendChild(wall);
  }
  grid.appendChild(left);

  const right = el("div", "weekly-col");
  right.appendChild(el("h3", "weekly-col-title", "抽奖战报"));
  const l = d.lottery || {};
  const kpis2 = el("div", "weekly-kpis");
  kpis2.appendChild(kpi("总抽数", l.total_draws));
  kpis2.appendChild(kpi("人均抽数", l.per_user));
  right.appendChild(kpis2);
  if (l.top) {
    right.appendChild(el("p", "", `抽卡之王：${l.top.name}（${l.top.count} 抽）`));
  }
  (l.lucky || []).forEach((x) => {
    right.appendChild(el("p", "", `欧皇：${x.name}（${x.hit === "points_10" ? "单抽 10 积分" : "传说称号"}）`));
  });
  if (l.unlucky) {
    right.appendChild(el("p", "", `非酋：${l.unlucky.name}（最长 ${l.unlucky.zero_streak} 连零）`));
  }
  if (l.immortal) {
    right.appendChild(el("p", "", `仙人彩：开奖 ${l.immortal.digits} / 奖池 ${l.immortal.pool} / 中奖 ${l.immortal.winners} 注`));
  }
  grid.appendChild(right);
  sec.appendChild(grid);
  document.getElementById("weeklyPaper").appendChild(sec);
}

function kpi(label, value) {
  const node = el("div", "weekly-kpi");
  node.appendChild(el("span", "weekly-kpi-label", label));
  node.appendChild(el("span", "weekly-kpi-value", String(value)));
  return node;
}

function renderVoices(v) {
  const sec = el("section", "weekly-section");
  sec.appendChild(sectionTitle("三版 · 群友言论", "语录 · 热梗 · 热词"));

  const quotes = el("div", "weekly-quotes");
  (v.quotes || []).forEach((q) => {
    const block = el("blockquote", "weekly-quote");
    block.appendChild(el("p", "", q.text));
    const footer = el("footer", "weekly-quote-footer", `— ${q.name} · ${q.at}`);
    block.appendChild(footer);
    quotes.appendChild(block);
  });
  sec.appendChild(quotes);

  if (v.memes && v.memes.length) {
    sec.appendChild(el("h4", "weekly-mini-title", "复读热梗 TOP3"));
    const ul = el("ul", "weekly-list");
    v.memes.forEach((m) => ul.appendChild(el("li", "", `${m.text}（${m.count} 次 / ${m.users} 人）`)));
    sec.appendChild(ul);
  }
  if (v.meme_king) {
    sec.appendChild(el("p", "", `复读王：${v.meme_king.name}（${v.meme_king.count} 次）`));
  }

  if (v.words && v.words.length) {
    sec.appendChild(el("h4", "weekly-mini-title", "本周热词"));
    const cloud = el("div", "weekly-word-cloud");
    const max = Math.max(...v.words.map((w) => w.c), 1);
    v.words.forEach((w, i) => {
      const span = el("span", `weekly-word tier-${Math.ceil((w.c / max) * 4)}${i < 3 ? " top" : ""}`);
      span.textContent = w.w;
      const badge = el("sup", "weekly-word-count", `[${w.c}]`);
      span.appendChild(badge);
      cloud.appendChild(span);
      cloud.appendChild(el("span", "weekly-word-sep", "·"));
    });
    sec.appendChild(cloud);
  }
  document.getElementById("weeklyPaper").appendChild(sec);
}

function renderActivity(a) {
  const sec = el("section", "weekly-section");
  sec.appendChild(sectionTitle("四版 · 群像观察", "活跃柱状图与榜单"));

  const chart = el("div", "weekly-chart");
  chart.appendChild(svgChart(a.daily || []));
  sec.appendChild(chart);

  if (a.peak) {
    sec.appendChild(el("p", "", `峰值时段：周${a.peak.day + 1} ${a.peak.hour} 点最活跃，一小时 ${a.peak.count} 条`));
  }
  if (a.talkers && a.talkers.length) {
    sec.appendChild(el("h4", "weekly-mini-title", "话痨榜 TOP5"));
    const ul = el("ul", "weekly-list");
    a.talkers.forEach((t) => ul.appendChild(el("li", "", `${t.name}：${t.count} 条（${Math.round(t.ratio * 100)}%）`)));
    sec.appendChild(ul);
  }
  if (a.night_owl) sec.appendChild(el("p", "", `深夜党：${a.night_owl.name}（${a.night_owl.count} 条）`));
  if (a.early_bird) sec.appendChild(el("p", "", `早起鸟：${a.early_bird.name}（${a.early_bird.count} 条）`));
  sec.appendChild(el("p", "", `周常全清：${a.quest_clears ?? 0} 人 · 卧底局数：${a.spy_games ?? 0} 局`));
  document.getElementById("weeklyPaper").appendChild(sec);
}

function svgChart(daily) {
  const NS = "http://www.w3.org/2000/svg";
  const width = 700, height = 260, pad = 30;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "weekly-svg");
  const max = Math.max(...daily, 1);
  const labels = ["一", "二", "三", "四", "五", "六", "日"];
  const barW = Math.floor((width - pad * 2) / 7) * 0.6;
  const gap = (width - pad * 2) / 7;
  daily.forEach((v, i) => {
    const h = Math.max(v > 0 ? 8 : 2, (v / max) * (height - pad * 2 - 20));
    const x = pad + i * gap + (gap - barW) / 2;
    const y = height - pad - h;
    const rect = document.createElementNS(NS, "rect");
    rect.setAttribute("x", String(x));
    rect.setAttribute("y", String(y));
    rect.setAttribute("width", String(barW));
    rect.setAttribute("height", String(h));
    rect.setAttribute("class", v === max && v > 0 ? "weekly-bar peak" : "weekly-bar");
    svg.appendChild(rect);

    const text = document.createElementNS(NS, "text");
    text.setAttribute("x", String(x + barW / 2));
    text.setAttribute("y", String(y - 8));
    text.setAttribute("class", "weekly-bar-num");
    text.textContent = String(v);
    svg.appendChild(text);

    const label = document.createElementNS(NS, "text");
    label.setAttribute("x", String(x + barW / 2));
    label.setAttribute("y", String(height - pad + 18));
    label.setAttribute("class", "weekly-bar-label");
    label.textContent = labels[i];
    svg.appendChild(label);
  });
  return svg;
}

function renderTrivia(t) {
  const sec = el("section", "weekly-section");
  sec.appendChild(sectionTitle("五版 · 花絮", "蝉联 · 涨幅 · 冷知识"));
  if (t.streaks && t.streaks.length) {
    t.streaks.forEach((s) => sec.appendChild(el("p", "", `蝉联榜：${s.name} 连续 ${s.weeks} 周蝉联${s.title || ""}`)));
  }
  if (t.gains && t.gains.length) {
    t.gains.forEach((g) => sec.appendChild(el("p", "", `涨幅榜：${g.name} 较上周 +${g.delta} 条`)));
  }
  (t.records || []).forEach((r) => {
    sec.appendChild(el("p", "", `${r.label}：${r.detail}${r.name ? "（" + r.name + "）" : ""}`));
  });
  const footer = el("p", "weekly-colophon", "本期完 · 下期周一 08:00 自动出版");
  sec.appendChild(footer);
  document.getElementById("weeklyPaper").appendChild(sec);
}

async function render() {
  const items = await fetchList();
  renderNav(items);
  const data = await fetchDetail();
  if (!data) return;
  renderHeader(data);
  renderHeadline(data);
  renderCheckin(data);
  renderVoices(data.voices || {});
  renderActivity(data.activity || {});
  renderTrivia(data.trivia || {});
}

document.addEventListener("DOMContentLoaded", () => {
  GalleryAuth.renderAuth(document.getElementById("authArea"));
  render();
});
