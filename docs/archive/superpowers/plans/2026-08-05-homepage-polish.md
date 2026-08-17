# 导航主页现代化设计完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留现有"报纸风"框架（报头 + 语录栏 + 公告栏 + 服务卡片网格），通过设计 token 重构、装饰细节、微动效与响应式打磨，把导航页从"朴素报纸"升级为"有现代设计感的报纸"。

**Architecture:** 纯静态页面（`homepage/` 目录，Caddy 托管），零依赖、无构建。所有改动仅限 `homepage/` 下的 `index.html`、`style.css`、`app.js`（`entries.json` / `quotes.json` / `notices.json` 数据结构不变）。视觉升级以 CSS 为主，仅两处 JS 微调（语录引号移入 CSS、无其他逻辑变化）。无测试框架：每个任务用浏览器目测清单 + `node --check` 验证。

**Tech Stack:** HTML5 + 原生 CSS（CSS 变量 / 动画 / 伪元素 / grid）+ 原生 JS。

## Global Constraints

- 纯静态、零依赖、无构建系统（见 AGENTS.md：本项目无 pyproject/package.json）。
- 不使用外部字体、CDN、图标库——内网 + 国内网络环境，必须离线可用；字体只用系统字体栈。
- 少用 emoji；装饰用几何字符（`◆` `✦` `§` 等）与 CSS 绘制。
- `entries.json` / `quotes.json` / `notices.json` 的 JSON 数据结构不变（不破坏现有内容）。
- 现代浏览器（Chrome / Edge / Firefox 近两年版本），不兼容 IE。
- 提交消息：中文 Conventional Commits（.githooks 校验），如 `style(导航页): ...`。
- 每次改动后必须通过验证步骤才可提交。

---

### Task 0: 基线提交（当前工作版本入库）

**Files:**
- Commit: `homepage/`（新增目录，全部未跟踪）

**Interfaces:**
- Produces: git 历史基线，后续每个任务一个独立提交，便于 review。

- [ ] **Step 1: 确认当前文件状态**

Run: `git status --short homepage/`
Expected: `?? homepage/`（或未提交的修改）

- [ ] **Step 2: 提交基线**

```bash
git add homepage/
git commit -m "feat(导航页): 新增中继站导航主页（报纸风初版）"
```

---

### Task 1: 设计 token 与整体基调现代化

**Files:**
- Modify: `homepage/style.css`（`1-26` 行 `:root` 与 `body`）

**Interfaces:**
- Produces: 以下 CSS 变量，Task 2-6 全部引用：
  - 颜色：`--paper` `--paper-card` `--ink` `--ink-soft` `--line` `--rule`（保留现有值族）＋ 新增 `--accent`（苔绿 #5f7a68）、`--accent-soft`（#e4e9dd）、`--accent-ink`（#3f5347）、`--gold`（#b49a5e）
  - 阴影：`--shadow-sm` `--shadow-md` `--shadow-lg`（分层柔和阴影）
  - 圆角：`--radius-sm`（6px）`--radius-md`（12px）
  - 动效：`--motion-fast`（150ms）`--motion-base`（250ms）`--ease`（cubic-bezier(0.22, 1, 0.36, 1)）

- [ ] **Step 1: 重构 `:root` 与 `body`**

将 `style.css` 顶部替换为：

```css
:root {
  --paper: #f5efe0;
  --paper-card: #fbf7ec;
  --ink: #2c2a24;
  --ink-soft: #6b6350;
  --line: #8a7f63;
  --rule: #b8ad8e;
  --accent: #5f7a68;
  --accent-soft: #e4e9dd;
  --accent-ink: #3f5347;
  --gold: #b49a5e;
  --green: #4a7c4f;
  --red: #b0533f;
  --gray: #a8a294;
  --shadow-sm: 0 1px 2px rgba(44, 42, 36, 0.08), 0 2px 6px rgba(44, 42, 36, 0.05);
  --shadow-md: 0 2px 4px rgba(44, 42, 36, 0.08), 0 8px 20px rgba(44, 42, 36, 0.09);
  --shadow-lg: 0 4px 8px rgba(44, 42, 36, 0.1), 0 16px 32px rgba(44, 42, 36, 0.12);
  --radius-sm: 6px;
  --radius-md: 12px;
  --motion-fast: 150ms;
  --motion-base: 250ms;
  --ease: cubic-bezier(0.22, 1, 0.36, 1);
}

* { box-sizing: border-box; }

html { height: 100%; }

body {
  margin: 0;
  min-height: 100%;
  background-color: var(--paper);
  background-image:
    radial-gradient(rgba(44, 42, 36, 0.035) 1px, transparent 1px),
    linear-gradient(180deg, #f8f3e6 0%, var(--paper) 40%, #f1ead8 100%);
  background-size: 22px 22px, 100% 100%;
  color: var(--ink);
  font-family: Georgia, "Songti SC", "Noto Serif SC", "SimSun", serif;
  display: flex;
  flex-direction: column;
  align-items: center;
}
```

说明：噪点纹理用 `radial-gradient` 点阵纯 CSS 实现（纸张质感，无需图片）；背景加极浅纵向渐变避免单色沉闷。

- [ ] **Step 2: 验证**

```bash
python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/style.css; kill %1
```

Expected: `200`。浏览器打开 `http://127.0.0.1:8899/` 目测清单：
- [ ] 页面整体仍是纸张色，无刺眼变化
- [ ] 背景有隐约纸点质感与自上而下的极浅渐变
- [ ] 文字颜色、卡片底色与之前观感一致（只是层次更干净）

- [ ] **Step 3: 提交**

```bash
git add homepage/style.css
git commit -m "style(导航页): 重构设计 token 与整体色调"
```

---

### Task 2: 报头艺术化（装饰线 + 标题层级）

**Files:**
- Modify: `homepage/style.css`（`.masthead` 块，`28-57` 行）
- Modify: `homepage/index.html`（masthead 内新增一行副题）

**Interfaces:**
- Consumes: Task 1 的 `--accent` `--gold` `--motion-base` `--ease` 变量
- Produces: `.masthead::after` 渐变装饰线、`.masthead-title` 字距层级、`.masthead-sub` 副题行

- [ ] **Step 1: 改 index.html**

将 `<p class="masthead-date" id="today"></p>` 之前插入副题行：

```html
    <p class="masthead-sub">向群里大小消息说早安</p>
    <p class="masthead-date" id="today"></p>
```

- [ ] **Step 2: 替换 `.masthead` 样式块**

```css
/* —— 报头 —— */
.masthead {
  width: min(880px, 100% - 2rem);
  text-align: center;
  padding: 2.2rem 0 1.2rem;
  margin-top: 1.5rem;
  position: relative;
}

.masthead::after {
  content: "";
  position: absolute;
  left: 6%;
  right: 6%;
  bottom: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent) 30%, var(--gold) 50%, var(--accent) 70%, transparent);
}

.masthead::before {
  content: "✦";
  position: absolute;
  left: 50%;
  bottom: -0.62rem;
  transform: translateX(-50%);
  background: var(--paper);
  padding: 0 0.6rem;
  font-size: 0.8rem;
  color: var(--accent);
  line-height: 1;
}

.masthead-issue {
  margin: 0 0 0.4rem;
  font-size: 0.75rem;
  letter-spacing: 0.4em;
  text-transform: uppercase;
  color: var(--ink-soft);
}

.masthead-title {
  margin: 0;
  font-size: clamp(2.2rem, 6.5vw, 3.4rem);
  font-weight: 700;
  letter-spacing: 0.22em;
  text-indent: 0.22em;
  color: var(--ink);
}

.masthead-sub {
  margin: 0.45rem 0 0;
  font-size: 0.85rem;
  color: var(--ink-soft);
  letter-spacing: 0.3em;
  text-indent: 0.3em;
}

.masthead-date {
  margin: 0.4rem 0 0;
  font-size: 0.85rem;
  color: var(--ink-soft);
  letter-spacing: 0.15em;
}
```

- [ ] **Step 3: 验证**

```bash
python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/; kill %1
```

Expected: `200`。浏览器目测清单：
- [ ] 标题下方是中间发光两端渐隐的细线，线中央悬一枚 ✦
- [ ] 副题"向群里大小消息说早安"与日期两行不重叠、间距舒服
- [ ] 标题字距更大更庄重，整体仍报纸

- [ ] **Step 4: 提交**

```bash
git add homepage/index.html homepage/style.css
git commit -m "style(导航页): 报头增加渐变装饰线与副题"
```

---

### Task 3: 语录栏 / 公告栏升级（引号装饰 + 入场动画）

**Files:**
- Modify: `homepage/style.css`（`.quotes-bar` `.announce-bar` 块，`59-105` 行）
- Modify: `homepage/app.js`（`showRandomQuote`，`123-131` 行）

**Interfaces:**
- Consumes: Task 1 的 `--accent` `--accent-soft` `--radius-sm` `--motion-*` 变量
- Produces: 语录栏大引号由 CSS 渲染（JS 不再内嵌 `“”`），公告栏 `.announce-list li` hover 态，两栏入场淡入

- [ ] **Step 1: 改 app.js —— 语录去掉内嵌引号**

```js
function showRandomQuote(quotes) {
  const el = document.getElementById("quote");
  if (!el) return;
  if (quotes.length === 0) {
    el.textContent = "本栏暂无收录，词条整理中……";
    return;
  }
  el.textContent = quotes[Math.floor(Math.random() * quotes.length)];
}
```

- [ ] **Step 2: 替换两栏样式块**

```css
/* —— 语录栏 / 公告栏 —— */
.quotes-bar,
.announce-bar {
  width: min(880px, 100% - 2rem);
  border: 1px solid var(--rule);
  border-top: 3px double var(--line);
  background: var(--paper-card);
  box-shadow: var(--shadow-sm);
  border-radius: var(--radius-sm);
  padding: 0.8rem 1.2rem 0.8rem 1rem;
  display: flex;
  align-items: baseline;
  gap: 0.9rem;
  animation: bar-in var(--motion-base) var(--ease) both;
}

@keyframes bar-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.quotes-bar { margin-top: 1.4rem; }
.announce-bar { margin-top: 0.8rem; }

.quotes-bar::before {
  content: "“";
  align-self: flex-start;
  font-family: Georgia, serif;
  font-size: 2.4rem;
  line-height: 1;
  color: var(--accent);
  opacity: 0.7;
  flex-shrink: 0;
}

.quotes-title {
  margin: 0;
  flex-shrink: 0;
  font-size: 0.78rem;
  letter-spacing: 0.25em;
  background: var(--ink);
  color: var(--paper);
  border-radius: 3px;
  padding: 0.26rem 0.6rem;
}

.announce-bar .quotes-title { background: var(--accent-ink); }

.quotes-text {
  margin: 0;
  font-size: 0.95rem;
  line-height: 1.65;
  color: var(--ink);
}

.announce-list {
  margin: 0;
  padding: 0;
  list-style: none;
  font-size: 0.9rem;
  line-height: 1.7;
  color: var(--ink);
}

.announce-list li {
  padding: 0.15rem 0.3rem;
  border-radius: 3px;
  transition: background var(--motion-fast) ease;
}

.announce-list li:hover { background: var(--accent-soft); }

.announce-list li::before {
  content: "§ ";
  color: var(--accent);
}
```

- [ ] **Step 3: 验证**

```bash
node --check homepage/app.js && python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/; kill %1
```

Expected: `node --check` 无输出，curl `200`。浏览器目测清单：
- [ ] 语录栏左侧有一个浅绿色大引号"（不再有双重引号）
- [ ] 两栏顶部细圆角、柔和阴影，加载时轻微上浮淡入
- [ ] 公告栏栏题为墨绿色底（与语录栏的墨黑底区分）
- [ ] 鼠标划过公告条目出现浅绿底

- [ ] **Step 4: 提交**

```bash
git add homepage/style.css homepage/app.js
git commit -m "style(导航页): 语录与公告栏增加引号装饰、hover 与入场动画"
```

---

### Task 4: 卡片系统现代化（圆角层次 + 交错入场 + 印章角标）

**Files:**
- Modify: `homepage/style.css`（`.entries` `.card` 块与 `.badge`，`107-207` 行）
- Modify: `homepage/index.html`（卡片区上方加栏目标题）

**Interfaces:**
- Consumes: Task 1 的 `--shadow-md` `--shadow-lg` `--radius-md` `--accent*` `--motion-*` 变量
- Produces: `.card` hover 抬升 + 顶部强调线；`.badge` 印章化；卡片交错入场动画（纯 CSS，JS 零改动）；`.section-title` 栏题

- [ ] **Step 1: 改 index.html**

在 `<main id="entries" class="entries">` 前加栏题（放在 `<main>` 外、作为页面通栏）：

```html
  <h2 class="section-title">服务目录</h2>

  <main id="entries" class="entries" aria-live="polite"></main>
```

- [ ] **Step 2: 替换卡片区样式**

```css
/* —— 服务目录栏题 —— */
.section-title {
  width: min(880px, 100% - 2rem);
  margin: 1.8rem 0 0;
  font-size: 0.85rem;
  font-weight: 400;
  letter-spacing: 0.45em;
  text-indent: 0.45em;
  color: var(--accent-ink);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 0.5rem;
}

/* —— 卡片区 —— */
.entries {
  width: min(880px, 100% - 2rem);
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 1.3rem;
  padding: 1.3rem 0 2rem;
}

.card.span-2 { grid-column: span 2; }

.card {
  position: relative;
  background: var(--paper-card);
  border: 1px solid var(--rule);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  padding: 1.1rem 1.2rem 1.15rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
  transition: box-shadow var(--motion-base) var(--ease),
              transform var(--motion-base) var(--ease),
              border-color var(--motion-fast) ease;
  animation: card-in 0.55s var(--ease) both;
}

.card::before {
  content: "";
  position: absolute;
  top: 0;
  left: 1.2rem;
  right: 1.2rem;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--accent), transparent);
  opacity: 0;
  transition: opacity var(--motion-fast) ease;
}

.card:nth-child(2) { animation-delay: 60ms; }
.card:nth-child(3) { animation-delay: 120ms; }
.card:nth-child(4) { animation-delay: 180ms; }

@keyframes card-in {
  from { opacity: 0; transform: translateY(16px); }
  to { opacity: 1; transform: translateY(0); }
}

.card:hover {
  border-color: var(--accent);
  box-shadow: var(--shadow-md);
  transform: translateY(-3px);
}

.card:hover::before { opacity: 1; }

.card-head {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.card-title {
  margin: 0;
  font-size: 1.18rem;
  font-weight: 700;
  letter-spacing: 0.08em;
}

/* —— 角标：印章式 —— */
.badge {
  margin-left: auto;
  font-size: 0.66rem;
  letter-spacing: 0.18em;
  border: 1.5px solid var(--accent);
  border-radius: 999px;
  padding: 0.14rem 0.55rem;
  color: var(--accent-ink);
  background: var(--accent-soft);
  transform: rotate(-4deg);
  white-space: nowrap;
}

.card-desc {
  margin: 0;
  font-size: 0.88rem;
  line-height: 1.6;
  color: var(--ink-soft);
}

.card-main {
  margin-top: auto;
  font-size: 0.9rem;
  text-decoration: none;
  color: var(--ink);
  border-bottom: 1px solid var(--rule);
  padding-bottom: 0.15rem;
  align-self: flex-start;
  transition: color var(--motion-fast) ease, border-color var(--motion-fast) ease;
}

.card-main:hover { color: var(--accent-ink); border-bottom-color: var(--accent); }

.card-links {
  display: flex;
  flex-wrap: wrap;
  gap: 0.6rem;
  font-size: 0.85rem;
}

.card-link {
  color: var(--ink-soft);
  text-decoration: none;
  border-bottom: 1px dotted var(--rule);
  align-self: flex-start;
  padding: 0.05rem 0.2rem;
  border-radius: 3px;
  transition: color var(--motion-fast) ease, background var(--motion-fast) ease;
}

.card-link.copy-btn {
  background: none;
  border: none;
  border-bottom: 1px dotted var(--rule);
  border-radius: 3px;
  padding: 0.05rem 0.2rem;
  margin: 0;
  font: inherit;
  font-size: inherit;
  line-height: inherit;
  color: var(--ink-soft);
  cursor: pointer;
  white-space: nowrap;
  text-align: left;
}

.card-link:hover,
.card-link.copy-btn:hover {
  color: var(--accent-ink);
  background: var(--accent-soft);
}
```

注意：`.card-links` 目前未被 HTML 使用（链接直接平铺在卡片中），保留定义不影响渲染，无需删除。

- [ ] **Step 3: 验证**

```bash
python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/; kill %1
```

Expected: `200`。浏览器目测清单：
- [ ] "服务目录"栏题带下划线与宽字距，与报头风格统一
- [ ] 卡片圆角柔和、阴影有层次；加载时逐张错峰上浮（头条卡先入）
- [ ] 悬停：卡片上浮 3px，顶部浮现一条淡绿细线，边框变苔绿
- [ ] "本店招牌"角标呈微旋转的苔绿圆角印章
- [ ] 链接/复制按钮悬停出现浅绿底、深绿文字

- [ ] **Step 4: 提交**

```bash
git add homepage/index.html homepage/style.css
git commit -m "style(导航页): 卡片系统现代化与印章角标"
```

---

### Task 5: 状态点动效与页脚装饰

**Files:**
- Modify: `homepage/style.css`（`.dot` 块与 `.foot`，`208-234` 行）
- Modify: `homepage/index.html`（页脚加分隔线与版权行）

**Interfaces:**
- Consumes: Task 1 的 `--green` `--red` `--motion-*` 变量
- Produces: `.dot.up` 柔光脉冲、`.dot.down` 静止灰红、`.foot` 顶部渐变装饰线

- [ ] **Step 1: 改 index.html 页脚**

```html
  <footer class="foot">
    <p>点击卡片前往对应服务 · 绿点为在线，灰点为离线</p>
    <p class="foot-copy">小埃中继站 · 2026</p>
  </footer>
```

- [ ] **Step 2: 替换状态点与页脚样式**

```css
/* —— 状态点 —— */
.dot {
  width: 0.62rem;
  height: 0.62rem;
  border-radius: 50%;
  border: 1px solid var(--ink-soft);
  background: var(--gray);
  flex-shrink: 0;
}

.dot.up {
  background: var(--green);
  border-color: var(--green);
  animation: pulse-glow 2.4s var(--ease) infinite;
}

.dot.down {
  background: var(--red);
  border-color: var(--red);
  opacity: 0.75;
}

.dot.unknown { background: var(--gray); }

@keyframes pulse-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(74, 124, 79, 0.45); }
  50% { box-shadow: 0 0 0 5px rgba(74, 124, 79, 0); }
}

/* —— 页脚 —— */
.foot {
  margin-top: auto;
  padding: 1rem 0 1.4rem;
  font-size: 0.8rem;
  color: var(--ink-soft);
  letter-spacing: 0.12em;
  text-align: center;
  border-top: 1px solid var(--rule);
}

.foot-copy {
  margin: 0.5rem 0 0;
  font-size: 0.72rem;
  letter-spacing: 0.3em;
  color: var(--rule);
}
```

- [ ] **Step 3: 验证**

```bash
python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/; kill %1
```

Expected: `200`。浏览器目测清单：
- [ ] 在线卡片的状态灯有一圈缓慢呼吸的柔光；离线灯暗红不闪
- [ ] 页脚有顶部分隔线，"小埃中继站 · 2026"小字居下

- [ ] **Step 4: 提交**

```bash
git add homepage/index.html homepage/style.css
git commit -m "style(导航页): 状态灯脉冲动效与页脚装饰"
```

---

### Task 6: 响应式细化与可访问性收尾

**Files:**
- Modify: `homepage/style.css`（`@media` 块，`236-241` 行，追加内容）
- Modify: `homepage/index.html`（无需改动，仅验证）

**Interfaces:**
- Consumes: 前序所有类名
- Produces: 720px 断点、`:focus-visible` 样式、`prefers-reduced-motion` 全动效降级、移动端两栏排列修正

- [ ] **Step 1: 替换末尾 `@media` 块并追加新规则**

将文件末尾 `@media (max-width: 520px) { ... }` 替换为：

```css
/* —— 键盘焦点可见 —— */
a:focus-visible,
button:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 3px;
  border-radius: 3px;
}

/* —— 减弱动效偏好 —— */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  .card:hover { transform: none; }
}

@media (max-width: 720px) {
  .quotes-bar,
  .announce-bar {
    flex-direction: column;
    align-items: flex-start;
    gap: 0.4rem;
  }
  .quotes-bar::before { align-self: flex-start; }
}

@media (max-width: 520px) {
  .entries { grid-template-columns: 1fr; gap: 1rem; }
  .card.span-2 { grid-column: span 1; }
  .card { border-radius: var(--radius-sm); }
  .masthead { padding-top: 1.6rem; }
  .badge { transform: none; }
}
```

- [ ] **Step 2: 验证**

```bash
python3 -m http.server 8899 --directory homepage >/dev/null 2>&1 &
sleep 1; curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8899/; kill %1
```

Expected: `200`。浏览器目测清单（可用 DevTools 切换设备模拟）：
- [ ] 720px 以下：语录栏/公告栏栏题在上、内容在下，大引号不挤压文本
- [ ] 520px 以下：卡片单列，角标不再旋转
- [ ] 用 Tab 键遍历：链接/按钮有清晰的苔绿焦点环
- [ ] 系统开启"减弱动态效果"后：无任何动画，hover 不上浮

- [ ] **Step 3: 提交**

```bash
git add homepage/style.css
git commit -m "style(导航页): 响应式断点细化与可访问性完善"
```

---

## Self-Review 记录

**1. Spec 覆盖**（对照用户需求）：
- 保留报纸风框架 ✓（所有任务只改装饰/动效/响应式，不动 HTML 结构与 JSON 机制）
- 现代设计元素 ✓（Task 1 设计 token、Task 2 装饰线、Task 3 引号动画、Task 4 卡片层次、Task 5 脉冲、Task 6 可访问性）
- 用户已确认约束（少 emoji、柔和、JSON 配置、Caddy 静态托管）在 Global Constraints 中逐条落实 ✓

**2. Placeholder 扫描**：所有 CSS/HTML/JS 修改均给出完整代码，验证步骤含具体命令与目测清单，无 TBD/TODO。

**3. 类型/命名一致性**：所有 CSS 变量（`--accent` `--shadow-md` `--radius-md` 等）在 Task 1 定义、后续任务引用，命名一致；JS 仅 `showRandomQuote` 一处删除引号包裹，`cardHTML`/`refreshStatus` 等接口未变；`.badge`/`.card-link`/`.dot` 类名与现有 HTML 渲染输出一致。
