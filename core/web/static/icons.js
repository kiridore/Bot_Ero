/* 共享内联 SVG 图标库（自托管，无外链 CDN）
 *
 * 图标来源: lucide-static v0.454.0 — https://lucide.dev/ （ISC License）
 * 版权: Copyright (c) for portions of Lucide are held by Cole Bemis 2013-2022
 *       as part of Feather (MIT). All other copyright (c) for Lucide are
 *       held by Lucide Contributors 2022. Licensed under the ISC License.
 * 每个图标保留原始 24x24 viewBox 与 path；stroke 继承 currentColor，
 * 颜色由各页面 CSS token 控制，禁止硬编码颜色。
 */
(function () {
  "use strict";

  var PATHS = {
    // 眼睛：点击次数/浏览量
    eye: '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    // 加号：添加
    plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    // 上下箭头：排序方向切换
    swap: '<path d="m3 16 4 4 4-4"/><path d="M7 20V4"/><path d="m21 8-4-4-4 4"/><path d="M17 4v16"/>',
    // 宫格：卡片视图
    grid: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="14" y="3" rx="1"/><rect width="7" height="7" x="14" y="14" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/>',
    // 列表：列表视图
    list: '<rect width="7" height="7" x="3" y="3" rx="1"/><rect width="7" height="7" x="3" y="14" rx="1"/><path d="M14 4h7"/><path d="M14 9h7"/><path d="M14 15h7"/><path d="M14 20h7"/>',
    // 垃圾桶：删除
    trash: '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/><line x1="10" x2="10" y1="11" y2="17"/><line x1="14" x2="14" y1="11" y2="17"/>',
    // 铅笔：编辑
    pencil: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
    // 叉号：清除
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  };

  function svgHTML(name, cls) {
    var path = PATHS[name] || "";
    return '<svg class="' + (cls || "g-icon") + '" viewBox="0 0 24 24" fill="none" ' +
      'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" ' +
      'aria-hidden="true">' + path + "</svg>";
  }

  function svgEl(name, cls) {
    var wrap = document.createElement("div");
    wrap.innerHTML = svgHTML(name, cls);
    return wrap.firstChild;
  }

  window.GalleryIcons = {
    svgHTML: svgHTML,
    svgEl: svgEl,
  };
})();
