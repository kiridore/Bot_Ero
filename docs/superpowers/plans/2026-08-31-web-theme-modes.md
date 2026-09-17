# 网页配色主题（上班摸鱼 / 夜间模式）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 设置页新增「网页配色」分区，全站 22 个页面可在 报纸风（默认）/ 上班摸鱼 / 夜间模式 三套配色间切换，选择存浏览器 localStorage。

**Architecture:** `base.css` 已是全站唯一主题 token 来源（`:root` CSS 变量）。本方案先收编残留硬编码色为 token 派生（`color-mix`），再以 `:root[data-theme="dark|mono"]` 两个 token 覆盖块实现换肤；新建共享 `theme.js` 在每页 `<head>` 同步加载，首帧前依 localStorage 设置 `<html data-theme>`，防夜间用户闪白。设置页调 `window.BoteroTheme.set()`，零后端改动。

**Tech Stack:** 纯 CSS custom properties + `color-mix()`（Baseline 2023，站点已用 backdrop-filter / View Transitions 同级特性）+ 原生 localStorage。无新依赖。

**Spec:** 需求经对话头脑风暴定稿，决策记录见下节（无独立 spec 文件）。

## 需求决策记录（头脑风暴定稿，执行时不可偏离）

1. **摸鱼模式 = 低调素雅**：低饱和灰白 token 覆盖 + `img { filter: grayscale(1) }`（彩图最显眼，灰掉才叫低调）；**不**伪装办公系统。
2. **存储 = localStorage**（键 `botero_theme`）：摸鱼/夜间都是"绑这台设备"的偏好，换设备不跟随是特性；**禁止**接入服务端 `user_settings` / `/api/me/settings`。
3. **夜间模式图片原样不动**：只换 UI 底色与文字色。
4. **不做老板键**、不做跟随系统 `prefers-color-scheme`（以后要加是一条 `@media` 的事）。
5. 默认主题 = 现行报纸风，`data-theme` 属性缺省即默认。

## Global Constraints

- bot 进程禁止 `async`/`await`（本计划不涉及 bot 代码）。
- 模块 CSS 禁止新增硬编码颜色；派生淡染色一律 `var(--tint…)` 或模块内 `color-mix()` 套 `:root` token。
- 测试统一入口 `pytest`（根目录）；`test/test_*.js` 由 `test/test_dom_render_suites.py` 自动发现（node 子进程，cwd=项目根），新增无需登记。
- Commit 消息 MUST 中文 + Conventional Commits；用户可见变更同 commit 更新 `CHANGELOG.md` 并 bump `core/config.py::BOTERO_VERSION`（新功能 minor）。
- 共享静态唯一目录 `core/web/static/`，经 `/shared` 挂载，新文件自动可服务，无需登记。

## 文件结构总览

| 文件 | 动作 | 职责 |
|------|------|------|
| `core/web/static/base.css` | 修改 | token 收编 + 两个主题覆盖块 + 摸鱼 img 灰化 |
| `core/web/static/profile.css` | 修改 | 淡染色/热力图色阶 token 化 |
| `webapp/static/{guestbook,weekly,timeline,alarms}.css` | 修改 | 残留硬编码色 token 化 |
| `core/web/static/theme.js` | 新建 | 读 localStorage → 设 `<html data-theme>`；导出 `window.BoteroTheme` |
| `webapp/static/*.html`（22 个） | 修改 | `<head>` 注入 theme.js 同步引用（base.css 之前） |
| `webapp/static/settings.js` | 修改 | 新增「网页配色」分区 |
| `test/test_theme.js` | 新建 | theme.js 行为用例 |
| `test/test_settings_render.js` | 修改 | 扩展配色分区断言 |
| `specs/web-gallery.md`、`CHANGELOG.md`、`core/config.py` | 修改 | spec 约束 + 版本记录 |

**提交策略（2 个 commit）：**
- Commit A（Task 1 后）：CSS token 收编纯重构 + CHANGELOG `[未发布]` 一行，不 bump 版本。
- Commit B（Task 6 后）：主题功能全部文件（theme.js + 22 页注入 + 主题块 + 设置页 + 测试 + specs + CHANGELOG `[1.31.0]` + 版本 bump）——一个逻辑变更一个 commit。

---

### Task 1: CSS token 收编（纯重构，渲染结果基本不变）

**Files:**
- Modify: `core/web/static/base.css`（:root 增 token + 9 处硬编码改引用）
- Modify: `core/web/static/profile.css`（12 处）
- Modify: `webapp/static/guestbook.css`（3 处）、`webapp/static/weekly.css`（4 处）、`webapp/static/timeline.css`（3 处）、`webapp/static/alarms.css`（1 处）
- Modify: `CHANGELOG.md`（`[未发布]` 节加一行）

**Interfaces:**
- Produces（后续 Task 4 主题块覆盖这些键，名字必须一字不差）：
  新增 `:root` token：`--paper-top` `--paper-bottom` `--paper-dots` `--toolbar-bg` `--tooltip-bg` `--overlay-shadow` `--tint` `--tint-strong` `--red-tint` `--red-tint-strong` `--heat-0` `--heat-1` `--heat-2` `--heat-3` `--heat-4` `--heat-neg`

- [ ] **Step 1: base.css `:root` 追加 token（插在 `--gray: #a8a294;` 行之后、`--shadow-sm` 之前）**

```css
  --paper-top: #f8f3e6;
  --paper-bottom: #f1ead8;
  --paper-dots: rgba(44, 42, 36, 0.035);
  --toolbar-bg: rgba(251, 247, 236, 0.94);
  --tooltip-bg: rgba(10, 12, 16, 0.88);
  --overlay-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
  /* 派生淡染色：color-mix 基于 token，主题换色自动跟随 */
  --tint: color-mix(in srgb, var(--ink) 6%, transparent);
  --tint-strong: color-mix(in srgb, var(--ink) 45%, transparent);
  --red-tint: color-mix(in srgb, var(--red) 8%, transparent);
  --red-tint-strong: color-mix(in srgb, var(--red) 12%, transparent);
  /* 打卡热力图色阶（level-0..4 及补卡 level--1） */
  --heat-0: #e2d9ba;
  --heat-1: #c0d8b2;
  --heat-2: #97ba89;
  --heat-3: #6b9670;
  --heat-4: #3a6646;
  --heat-neg: #bd9457;
```

- [ ] **Step 2: base.css 逐处替换（行号为当前值，先 grep 确认再改）**

| 位置 | 现值 | 改为 |
|------|------|------|
| L38 body 纹理点 | `radial-gradient(rgba(44, 42, 36, 0.035) 1px, …)` | `radial-gradient(var(--paper-dots) 1px, …)` |
| L39 body 渐变 | `linear-gradient(180deg, #f8f3e6 0%, var(--paper) 40%, #f1ead8 100%)` | `linear-gradient(180deg, var(--paper-top) 0%, var(--paper) 40%, var(--paper-bottom) 100%)` |
| L90 toolbar | `background: rgba(251, 247, 236, 0.94);` | `background: var(--toolbar-bg);` |
| L208 | `background: rgba(44, 42, 36, 0.06);` | `background: var(--tint);` |
| L230 | `background: rgba(176, 83, 63, 0.08);` | `background: var(--red-tint);` |
| L245 scrim | `background: rgba(44, 42, 36, 0.45);` | `background: var(--tint-strong);` |
| L364 | `box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);` | `box-shadow: var(--overlay-shadow);` |
| L371 | `background: rgba(44, 42, 36, 0.06);` | `background: var(--tint);` |
| L400 | `background: rgba(10, 12, 16, 0.88);` | `background: var(--tooltip-bg);` |

- [ ] **Step 3: profile.css 逐处替换**

| 位置 | 现值 | 改为 |
|------|------|------|
| L64 | `rgba(44, 42, 36, 0.06)` | `var(--tint)` |
| L134 | `.heatmap-cell.level-0 { background: #e2d9ba; }` | `var(--heat-0)` |
| L135 | `#c0d8b2` | `var(--heat-1)` |
| L136 | `#97ba89` | `var(--heat-2)` |
| L137 | `#6b9670` | `var(--heat-3)` |
| L138 | `#3a6646` | `var(--heat-4)` |
| L139 | `.level--1 { background: #bd9457; }` | `var(--heat-neg)` |
| L240 | `rgba(44, 42, 36, 0.45)` | `var(--tint-strong)` |
| L277 | `rgba(44, 42, 36, 0.06)` | `var(--tint)` |
| L456 | `rgba(176, 83, 63, 0.12)` | `var(--red-tint-strong)` |
| L535 | `rgba(44, 42, 36, 0.06)` | `var(--tint)` |
| L678 | `rgba(44, 42, 36, 0.45)` | `var(--tint-strong)` |

- [ ] **Step 4: 模块 CSS 逐处替换**

| 文件:行 | 现值 | 改为 |
|---------|------|------|
| guestbook.css:93 | `border-color: rgba(176, 83, 63, 0.55);` | `border-color: color-mix(in srgb, var(--red) 55%, transparent);` |
| guestbook.css:98 | `border-color: rgba(176, 83, 63, 0.65);` | `border-color: color-mix(in srgb, var(--red) 65%, transparent);` |
| guestbook.css:99 | `background: rgba(176, 83, 63, 0.12);` | `background: var(--red-tint-strong);` |
| weekly.css:80 | `box-shadow: 4px 4px 0 rgba(0, 0, 0, 0.08);` | `box-shadow: 4px 4px 0 color-mix(in srgb, var(--ink) 8%, transparent);` |
| weekly.css:218 | `background: #eee;` | `background: var(--tint);` |
| weekly.css:260 | `color: #a67c00;` | `color: var(--gold);`（装饰性微调，可接受） |
| weekly.css:281 | `fill: #a67c00;` | `fill: var(--gold);` |
| timeline.css:355 | `background: rgba(228, 233, 221, 0.95);` | `background: color-mix(in srgb, var(--accent-soft) 95%, transparent);` |
| timeline.css:396 | `rgba(44, 42, 36, 0.06)` | `var(--tint)` |
| timeline.css:451 | `rgba(44, 42, 36, 0.06)` | `var(--tint)` |
| alarms.css:63 | `rgba(95, 122, 104, 0.22)` | `color-mix(in srgb, var(--accent) 22%, transparent)` |

- [ ] **Step 5: 验证——全站 CSS 除 `:root` 定义行外无残留硬编码色**

Run: `grep -n "#[0-9a-fA-F]\{3,8\}\b\|rgba\?(" core/web/static/*.css webapp/static/*.css | grep -v "var(--" | grep -v "color-mix"`
Expected: 仅剩 `:root` 内的 token 定义行（`--xxx: #…;`）。

- [ ] **Step 6: 回归 + CHANGELOG `[未发布]` 记一行 + Commit A**

Run: `pytest`（DOM 套件不加载 CSS，此步防意外破坏）

`CHANGELOG.md` `[未发布]` 节新增：
```markdown
- **CSS token 收编**：全站样式残留的硬编码颜色统一改为 `:root` token / `color-mix` 派生（内部重构，渲染不变，为主题机制铺路）
```

```bash
git add core/web/static/base.css core/web/static/profile.css webapp/static/guestbook.css webapp/static/weekly.css webapp/static/timeline.css webapp/static/alarms.css CHANGELOG.md
git commit -m "refactor(网页): 收编全站 CSS 残留硬编码色为主题 token 派生"
```

---

### Task 2: theme.js（TDD）

**Files:**
- Test: `test/test_theme.js`（新建）
- Create: `core/web/static/theme.js`

**Interfaces:**
- Produces: `window.BoteroTheme = { get(): ""|"mono"|"dark", set(v: string): void }`；localStorage 键 `botero_theme`；副作用 `<html data-theme="mono|dark">`（默认无属性）。Task 5 的 settings.js 依赖此接口。

- [ ] **Step 1: 写失败测试 `test/test_theme.js`**

```js
// theme.js 行为验证：<head> 同步加载时依 localStorage 设置 <html data-theme>；
// 非法值回退默认（无属性）；BoteroTheme.get/set 读写 localStorage。
const fs = require("fs");

function makeEnv(stored) {
  const store = { value: stored };
  const calls = { set: [], remove: 0 };
  const env = {
    documentElement: { dataset: {} },
  };
  global.localStorage = {
    getItem: (k) => (k === "botero_theme" ? store.value : null),
    setItem: (k, v) => { if (k === "botero_theme") { store.value = v; calls.set.push(v); } },
    removeItem: (k) => { if (k === "botero_theme") { store.value = null; calls.remove++; } },
  };
  global.document = { documentElement: env.documentElement };
  global.window = {};
  return { store, calls };
}

let fail = 0;
function check(name, ok) { console.log(`${ok ? "ok" : "FAIL"} - ${name}`); if (!ok) fail++; }

const src = fs.readFileSync("core/web/static/theme.js", "utf8");

// 1. 预存 dark → 首帧前已设置 data-theme
{
  const { store } = makeEnv("dark");
  eval(src);
  check("预存 dark → <html data-theme=dark>", global.document.documentElement.dataset.theme === "dark");
  check("get() 返回 dark", window.BoteroTheme.get() === "dark");
}

// 2. 无记录 / 非法值 → 无属性、get() 回退 ""
for (const v of [null, "neon"]) {
  makeEnv(v);
  eval(src);
  check(`预存 ${v} → 无 data-theme 属性`, !("theme" in global.document.documentElement.dataset));
  check(`预存 ${v} → get() 为 ""`, window.BoteroTheme.get() === "");
}

// 3. set("mono") → 属性 + localStorage 写入
{
  const { store, calls } = makeEnv(null);
  eval(src);
  window.BoteroTheme.set("mono");
  check("set(mono) → <html data-theme=mono>", global.document.documentElement.dataset.theme === "mono");
  check("set(mono) → localStorage=mono", store.value === "mono" && calls.set.length === 1);
}

// 4. set("") → 清属性 + removeItem
{
  const { store, calls } = makeEnv("dark");
  eval(src);
  window.BoteroTheme.set("");
  check("set(\"\") → 属性清除", !("theme" in global.document.documentElement.dataset));
  check("set(\"\") → removeItem 调用", calls.remove === 1 && store.value === null);
}

// 5. set 非法值 → 按默认处理且不写盘
{
  const { store } = makeEnv(null);
  eval(src);
  window.BoteroTheme.set("neon");
  check("set(neon) → 无属性", !("theme" in global.document.documentElement.dataset));
  check("set(neon) → 不写 localStorage", store.value === null);
}

process.exit(fail ? 1 : 0);
```

- [ ] **Step 2: 运行确认失败**

Run: `node test/test_theme.js`
Expected: FAIL（`core/web/static/theme.js` 不存在，readFileSync 抛 ENOENT，非零退出）。

- [ ] **Step 3: 实现 `core/web/static/theme.js`**

```js
// 全站配色主题（缺省报纸风 / mono 上班摸鱼 / dark 夜间）：
// 选择存本浏览器 localStorage（键 botero_theme），<head> 内同步加载并在
// 首帧前设置 <html data-theme>，避免夜间用户加载闪白。设置页经
// window.BoteroTheme 读写；主题为浏览器本地偏好，不入服务端个人设置。
(function () {
  const KEY = "botero_theme";
  const VALID = ["", "mono", "dark"];

  function get() {
    const v = localStorage.getItem(KEY);
    return VALID.includes(v) ? v : "";
  }

  function apply(v) {
    if (!VALID.includes(v)) v = "";
    if (v) document.documentElement.dataset.theme = v;
    else delete document.documentElement.dataset.theme;
  }

  apply(get());

  window.BoteroTheme = {
    get,
    set(v) {
      v = VALID.includes(v) ? v : "";
      apply(v);
      if (v) localStorage.setItem(KEY, v);
      else localStorage.removeItem(KEY);
    },
  };
})();
```

- [ ] **Step 4: 运行确认通过（并纳入 pytest 自动发现）**

Run: `node test/test_theme.js`
Expected: 全部 `ok`，退出码 0。

Run: `pytest test/test_dom_render_suites.py -k theme -v`
Expected: PASS（`test_dom_render_suite[test_theme.js]`）。

---

### Task 3: 22 页 `<head>` 注入 theme.js

**Files:**
- Modify: `webapp/static/*.html`（全部 22 个，均在 `  <link rel="stylesheet" href="/shared/base.css" />` 一行之前插入）

**Interfaces:**
- Consumes: `/shared/theme.js`（Task 2 产物，`core/web/static/` 挂载自动可服务）。

- [ ] **Step 1: sed 批量插入**

```bash
sed -i 's|<link rel="stylesheet" href="/shared/base.css" />|<script src="/shared/theme.js"></script>\n  <link rel="stylesheet" href="/shared/base.css" />|' webapp/static/*.html
```

- [ ] **Step 2: 验证 22 页全部注入且顺序正确（theme.js 在 base.css 之前）**

Run: `grep -c 'src="/shared/theme.js"' webapp/static/*.html | grep -v ':1$' ; echo "exit=$?"`
Expected: 无输出且 `exit=1`（即所有文件恰好 1 处）。

Run: `for f in webapp/static/*.html; do grep -A1 'theme.js' "$f" | grep -q base.css || echo "BAD: $f"; done`
Expected: 无 `BAD` 输出。

- [ ] **Step 3: 回归（HTML 变更不破坏 DOM 套件）**

Run: `pytest test/test_dom_render_suites.py -v`
Expected: 全 PASS。

---

### Task 4: base.css 主题覆盖块（dark + mono 调色板）

**Files:**
- Modify: `core/web/static/base.css`（文件末尾追加；并更新首行头注释）

**Interfaces:**
- Consumes: Task 1 的全部 token 键名（覆盖块只重定义颜色类 token；`--tint*`/`--red-tint*` 为 `color-mix` 派生自动跟随，不重定义）。

- [ ] **Step 1: 更新 base.css 首行头注释**

现值：
```css
/* 全站基础样式 base.css：报纸风主题 token（全站唯一来源）+ 共享组件与全站滚动条；子应用样式一律引用，禁止硬编码颜色 */
```
改为：
```css
/* 全站基础样式 base.css：报纸风主题 token（全站唯一来源）+ 主题覆盖（:root[data-theme="dark"] 夜间 / "mono" 上班摸鱼，theme.js 按 localStorage 切换）+ 共享组件与全站滚动条；子应用样式一律引用，禁止硬编码颜色 */
```

- [ ] **Step 2: 文件末尾追加主题覆盖块（逐字使用）**

```css
/* ============ 主题覆盖：夜间模式（暖暗色调，图片保持原样） ============ */
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #211e19;
  --paper-card: #2b2721;
  --ink: #e6ddc9;
  --ink-soft: #a89d85;
  --line: #6b6350;
  --rule: #4d463a;
  --accent: #8fae97;
  --accent-soft: #2f362d;
  --accent-ink: #bad1c0;
  --gold: #cfb87c;
  --green: #86b38b;
  --red: #d08770;
  --gray: #7d7668;
  --paper-top: #26211a;
  --paper-bottom: #1b1813;
  --paper-dots: rgba(230, 221, 201, 0.045);
  --toolbar-bg: rgba(43, 39, 33, 0.94);
  --tooltip-bg: rgba(8, 10, 14, 0.92);
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3), 0 2px 6px rgba(0, 0, 0, 0.25);
  --shadow-md: 0 2px 4px rgba(0, 0, 0, 0.3), 0 8px 20px rgba(0, 0, 0, 0.35);
  --shadow-lg: 0 4px 8px rgba(0, 0, 0, 0.35), 0 16px 32px rgba(0, 0, 0, 0.4);
  --heat-0: #332e26;
  --heat-1: #3c5a41;
  --heat-2: #4d7a52;
  --heat-3: #69996e;
  --heat-4: #8cc291;
  --heat-neg: #8a6a3a;
}

/* ============ 主题覆盖：上班摸鱼（低饱和灰白，灰化图片降低显眼度） ============ */
:root[data-theme="mono"] {
  --paper: #f1f1ef;
  --paper-card: #fafaf8;
  --ink: #3b3b3b;
  --ink-soft: #787878;
  --line: #9c9c9a;
  --rule: #c6c6c4;
  --accent: #8a8a86;
  --accent-soft: #e9e9e7;
  --accent-ink: #575755;
  --gold: #9c9c98;
  --green: #8f8f8b;
  --red: #a4a4a1;
  --gray: #b1b1ad;
  --paper-top: #f5f5f3;
  --paper-bottom: #ececea;
  --paper-dots: rgba(59, 59, 59, 0.03);
  --toolbar-bg: rgba(250, 250, 248, 0.94);
  --heat-0: #e7e7e5;
  --heat-1: #cfcfcd;
  --heat-2: #b1b1af;
  --heat-3: #8b8b89;
  --heat-4: #60605e;
  --heat-neg: #cacac6;
}

:root[data-theme="mono"] img {
  filter: grayscale(1);
}
```

- [ ] **Step 3: 浏览器手动验证（视觉验收，自动化覆盖不了）**

Run: `python -m webapp`，浏览器开 `http://127.0.0.1:8765/login`（登录页在门控白名单，最省事）与登录后的 `/`（时间线）、`/profile/settings`。DevTools Console 执行：

```js
document.documentElement.dataset.theme = "dark"   // 夜间：暖暗底、无闪白、图片原样
document.documentElement.dataset.theme = "mono"   // 摸鱼：灰白 + 图片全灰
delete document.documentElement.dataset.theme     // 回默认报纸风
localStorage.setItem("botero_theme", "dark"); location.reload()  // 刷新后仍夜间、不闪白
```

Expected: 三态切换即时生效；刷新保持；重点看时间线报头、工具栏、热力图（`/profile`）、留言簿红框、周报 top 词无漏色。

---

### Task 5: 设置页「网页配色」分区（TDD）

**Files:**
- Test: `test/test_settings_render.js`（扩展）
- Modify: `webapp/static/settings.js`

**Interfaces:**
- Consumes: `window.BoteroTheme.get()/set(v)`（Task 2）。
- Produces: radio 组 `name="siteTheme"`，取值 `""` / `mono` / `dark`；切换**不调**任何 API。

- [ ] **Step 1: 扩展测试（先失败）。在 `test_settings_render.js` 做三处修改**

① 在 `global.window = { addEventListener() {} };` 之后加 stub（浏览器内 `window.BoteroTheme` 即全局 `BoteroTheme`，node 里两边都要挂）：

```js
let themeNow = "";
const themeSets = [];
const fakeTheme = { get: () => themeNow, set: (v) => { themeSets.push(v); themeNow = v; } };
global.window.BoteroTheme = fakeTheme;
global.BoteroTheme = fakeTheme;
```

② 用例 1 末尾（`check("角色卡开关默认勾选…")` 之后）加：

```js
  // 0. 网页配色：3 个 radio，默认选中"报纸风"
  const themeRadios = radiosOf("siteTheme");
  check("配色组渲染 3 个 radio", themeRadios.length === 3);
  check("配色组默认选中报纸风", checkedOf("siteTheme") === "");
```

③ 文件末尾主流程内（用例 3 之后、`process.exit` 之前）加用例 4：

```js
  // 4. 触发配色 mono radio：走本地 BoteroTheme.set，不 PUT 任何 API
  const putsBefore = puts.length;
  const monoRadio = radiosOf("siteTheme").filter((e) => e.value === "mono")[0];
  if (monoRadio && (monoRadio._listeners.change || []).length) {
    monoRadio.checked = true;
    radiosOf("siteTheme").forEach((e) => { if (e !== monoRadio) e.checked = false; });
    await monoRadio._listeners.change.shift()({ target: monoRadio });
    await wait(50);
  }
  check("配色切换调用 BoteroTheme.set(mono)", themeSets.length === 1 && themeSets[0] === "mono");
  check("配色切换不触发 API PUT", puts.length === putsBefore);
```

- [ ] **Step 2: 运行确认失败**

Run: `node test/test_settings_render.js`
Expected: FAIL —— `配色组渲染 3 个 radio` 等 2 项失败（settings.js 尚无该分区）。

- [ ] **Step 3: 实现 settings.js（两处修改）**

① 在 `CHECKIN_DISPLAY_OPTIONS` 定义之后追加：

```js
// 网页配色（本浏览器 localStorage，经 theme.js 的 window.BoteroTheme 读写，不走服务端 API）
const THEME_OPTIONS = [
  { value: "", label: "报纸风（默认）" },
  { value: "mono", label: "上班摸鱼" },
  { value: "dark", label: "夜间模式" },
];

function renderThemeSection() {
  const sec = document.createElement("section");
  sec.className = "settings-section";
  const head = document.createElement("div");
  head.className = "section-head";
  head.innerHTML = "<h2>网页配色</h2>";
  sec.appendChild(head);

  const row = document.createElement("div");
  row.className = "privacy-row privacy-row-options";
  const label = document.createElement("span");
  label.textContent = "全站配色";
  row.appendChild(label);

  const current = (window.BoteroTheme && BoteroTheme.get()) || "";
  THEME_OPTIONS.forEach((opt) => {
    const radioLabel = document.createElement("label");
    radioLabel.className = "radio-option";
    const input = document.createElement("input");
    input.type = "radio";
    input.name = "siteTheme";
    input.value = opt.value;
    input.checked = current === opt.value;
    input.addEventListener("change", (e) => {
      if (!e.target.checked || !window.BoteroTheme) return;
      BoteroTheme.set(opt.value);
      showToast(`配色已切换：${opt.label}`);
    });
    radioLabel.appendChild(input);
    const optText = document.createElement("span");
    optText.textContent = opt.label;
    radioLabel.appendChild(optText);
    row.appendChild(radioLabel);
  });
  sec.appendChild(row);

  const hint = document.createElement("p");
  hint.className = "preview-hint";
  hint.textContent =
    "配色保存在当前浏览器（更换设备需重新选择）：「上班摸鱼」为低饱和灰白风并灰化图片；" +
    "「夜间模式」为暗色底，图片均保持原样。";
  sec.appendChild(hint);
  return sec;
}
```

② 在 `renderPage()` 内 `privacySec.appendChild(checkinHint);` 之后追加一行：

```js
  settingsMain.appendChild(renderThemeSection());
```

- [ ] **Step 4: 运行确认通过 + 浏览器手动验收**

Run: `node test/test_settings_render.js`
Expected: 全部 `ok`，退出码 0。

Run: `pytest test/test_dom_render_suites.py -v`（全套防波及）
Expected: 全 PASS。

手动：`python -m webapp` → `/profile/settings` → 点「上班摸鱼」→ 全站即时变灰白（含当前设置页），刷新保持；点「报纸风」恢复且 localStorage 清键。

---

### Task 6: 文档 + 版本 + 汇总提交（Commit B）

**Files:**
- Modify: `specs/web-gallery.md`、`CHANGELOG.md`、`core/config.py`

**Interfaces:**
- Consumes: 前五个 Task 的全部产物。

- [ ] **Step 1: specs/web-gallery.md 两处更新**

① 「Constraint: 共享层（`core/`）」表格中 `core/web/static/` 行的静态清单加入 `theme.js`：
```
| `core/web/static/` | 共享静态（auth.js / nav.js / theme.js / base.css / profile.css / motion.css / motion.js / lightbox.js / icons.js），各子应用以 `/shared` 挂载同一目录，**MUST NOT** 复制 |
```

② 该表格下方现有 token 约束 bullet 之后追加两条：

```markdown
- Constraint: 全站配色主题：`base.css` 内 `:root[data-theme="dark"]`（夜间，暖暗色）与 `:root[data-theme="mono"]`（上班摸鱼，低饱和灰白 + `img { filter: grayscale(1) }` 灰化图片）覆盖 token；`theme.js` 由每个页面 `<head>` 在 `/shared/base.css` 之前以同步 `<script>` 引用，首帧前依 localStorage 键 `botero_theme`（取值 `""`/`mono`/`dark`，非法回退默认）设置 `<html data-theme>` 防闪白；设置页经 `window.BoteroTheme.get()/set(v)` 读写。主题为浏览器本地偏好，**MUST NOT** 写入服务端个人设置。
- Constraint: 派生淡染色（悬浮底、遮罩、红 tint、热力图色阶）MUST 经 `--tint`/`--tint-strong`/`--red-tint`/`--red-tint-strong`/`--heat-*` token 或模块内 `color-mix()` 套 `:root` token 表达（主题切换自动跟随）；模块 CSS **MUST NOT** 引入新的硬编码颜色或独立色阶。
```

- [ ] **Step 2: CHANGELOG 新版本节 + 版本 bump**

`CHANGELOG.md` 顶部 `[未发布]` 节之后新增：

```markdown
## [1.31.0] - 2026-08-31

### 新增

- **网页配色主题**：设置页新增「网页配色」分区，全站可在 报纸风（默认）/ 上班摸鱼 / 夜间模式 间切换——「上班摸鱼」为低饱和灰白风并灰化图片，「夜间模式」为暖暗色调底、图片原样；选择保存在当前浏览器，更换设备不跟随，切换即时生效且刷新不闪白
```

`core/config.py`：`BOTERO_VERSION = "1.30.0"` → `"1.31.0"`。

- [ ] **Step 3: 全量回归**

Run: `pytest`
Expected: 全 PASS（含 `test_dom_render_suite[test_theme.js]`、`test_dom_render_suite[test_settings_render.js]`）。

- [ ] **Step 4: Commit B（一个逻辑变更一个 commit，配套文件齐上）**

```bash
git add core/web/static/theme.js core/web/static/base.css webapp/static/*.html webapp/static/settings.js test/test_theme.js test/test_settings_render.js specs/web-gallery.md CHANGELOG.md core/config.py
git commit -m "feat(网页): 新增全站配色主题（上班摸鱼/夜间模式）"
```

---

## Self-Review 记录

- **Spec 覆盖**：决策 1（摸鱼=灰白+灰图）→ Task 4；决策 2（localStorage、禁后端）→ Task 2/5（测试断言不 PUT）；决策 3（夜间图片原样）→ Task 4（dark 块无 img 规则）；决策 4/5（无老板键、默认报纸风）→ 无对应代码即满足。22 页接线 → Task 3；设置页入口 → Task 5；文档/版本 → Task 6。
- **占位符**：无 TBD；全部编辑给出逐字内容。
- **类型/命名一致性**：token 键名（Task 1 定义 = Task 4 覆盖）；`window.BoteroTheme.get/set`（Task 2 定义 = Task 5 调用）；radio 组名 `siteTheme`（Task 5 测试 = 实现）；localStorage 键 `botero_theme`（Task 2 = specs 文案）。
