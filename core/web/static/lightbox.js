(function () {
  "use strict";

  // 共享灯箱：点击时间线事件图片 / 议事厅正文图片在当前页放大预览。
  // 复用 gallery.css 中既有的 .lightbox 报纸风样式。
  var overlay = null;

  function close() {
    if (!overlay) return;
    var el = overlay;
    overlay = null;
    el.classList.add("closing");
    setTimeout(function () {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, 200);
  }

  function open(url, caption) {
    if (!url) return;
    if (overlay) close();

    overlay = document.createElement("div");
    overlay.className = "lightbox is-loading hidden";
    overlay.setAttribute("role", "dialog");
    overlay.setAttribute("aria-modal", "true");

    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "lightbox-close";
    btn.setAttribute("aria-label", "关闭");
    btn.textContent = "×";

    var figure = document.createElement("figure");
    var img = document.createElement("img");
    img.alt = caption || "";
    img.addEventListener("load", function () {
      overlay && overlay.classList.remove("is-loading");
    });
    img.addEventListener("error", function () {
      overlay && overlay.classList.remove("is-loading");
    });
    figure.appendChild(img);
    if (caption) {
      var cap = document.createElement("figcaption");
      cap.textContent = caption;
      figure.appendChild(cap);
    }

    overlay.append(btn, figure);
    overlay.addEventListener("click", function (e) {
      if (e.target === overlay || e.target === btn) close();
    });
    document.body.appendChild(overlay);
    img.src = url;
    requestAnimationFrame(function () {
      overlay && overlay.classList.remove("hidden");
    });
  }

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && overlay) {
      e.preventDefault();
      close();
    }
  });

  document.addEventListener("click", function (e) {
    var el = e.target.closest(".tl-images a, img.forum-img");
    if (!el) return;
    var url = el.tagName === "A" ? el.getAttribute("href") : el.getAttribute("src");
    if (!url || url.startsWith("#")) return;
    e.preventDefault();
    var img = el.tagName === "A" ? el.querySelector("img") : el;
    open(url, img ? img.getAttribute("alt") : "");
  });

  window.GalleryLightbox = { open: open, close: close };
})();
