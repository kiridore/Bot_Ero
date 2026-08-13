/* ============================================================
   全站动效助手（零依赖）
   - 注入 <html>.js-motion 后 CSS 揭示层才生效（JS 失败内容可见）
   - 暴露 window.Motion：
       reveal(root?)          扫描并观察 [data-reveal]
       stagger(root, step)    给未揭示元素按序分配交错延迟后观察
       enter(el)              新条目进入动画（entering 类，动画后自动移除）
       animateNumber(el,to,o) 数字滚动（easeOutCubic，duration/decimals 可配）
   - prefers-reduced-motion 下整体禁用
   ============================================================ */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (reduced) return;

  document.documentElement.classList.add("js-motion");

  var observer = "IntersectionObserver" in window
    ? new IntersectionObserver(onIntersect, {
        rootMargin: "0px 0px -6% 0px",
        threshold: 0.06
      })
    : null;

  function onIntersect(entries) {
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].isIntersecting) revealNow(entries[i].target);
    }
  }

  function revealNow(el) {
    el.classList.add("revealed");
    if (observer) observer.unobserve(el);
  }

  function applyDelay(el) {
    var d = el.getAttribute("data-reveal-delay");
    if (d) el.style.setProperty("--reveal-delay", d + "ms");
  }

  function reveal(root) {
    var els = (root || document).querySelectorAll("[data-reveal]:not(.revealed)");
    if (!observer) {
      for (var i = 0; i < els.length; i++) revealNow(els[i]);
      return;
    }
    for (var j = 0; j < els.length; j++) {
      applyDelay(els[j]);
      observer.observe(els[j]);
    }
  }

  function stagger(root, stepMs) {
    var els = (root || document).querySelectorAll("[data-reveal]:not(.revealed)");
    var step = stepMs || 70;
    for (var i = 0; i < els.length; i++) {
      els[i].style.setProperty("--reveal-delay", Math.min(i * step, 600) + "ms");
    }
    reveal(root);
  }

  function enter(el) {
    if (!el || reduced) return;
    el.classList.remove("entering");
    void el.offsetWidth; // 强制重排，允许同元素重复触发
    el.classList.add("entering");
    el.addEventListener(
      "animationend",
      function () { el.classList.remove("entering"); },
      { once: true }
    );
  }

  function animateNumber(el, to, opts) {
    if (!el) return;
    var opt = opts || {};
    var duration = opt.duration || 600;
    var decimals = opt.decimals || 0;
    var from = opt.from !== undefined
      ? opt.from
      : parseFloat(el.dataset.value !== undefined ? el.dataset.value : el.textContent);
    if (!isFinite(from)) from = 0;
    var start = null;
    function frame(now) {
      if (start === null) start = now;
      var p = Math.min(1, (now - start) / duration);
      var eased = 1 - Math.pow(1 - p, 3); // easeOutCubic
      var v = from + (to - from) * eased;
      el.textContent = v.toFixed(decimals);
      if (p < 1) {
        requestAnimationFrame(frame);
      } else {
        el.textContent = to.toFixed(decimals);
        el.dataset.value = String(to);
      }
    }
    requestAnimationFrame(frame);
  }

  // 动态插入的内容自动接管：同一批新增的 [data-reveal] 元素自动交错揭示
  if ("MutationObserver" in window) {
    var pending = false;
    var newEls = [];
    var mo = new MutationObserver(function (mutations) {
      for (var i = 0; i < mutations.length; i++) {
        var nodes = mutations[i].addedNodes;
        for (var j = 0; j < nodes.length; j++) {
          var node = nodes[j];
          if (node.nodeType !== 1) continue;
          if (node.hasAttribute("data-reveal") && !node.classList.contains("revealed")) {
            newEls.push(node);
          }
          var inner = node.querySelectorAll("[data-reveal]:not(.revealed)");
          for (var k = 0; k < inner.length; k++) newEls.push(inner[k]);
        }
      }
      if (pending) return;
      pending = true;
      requestAnimationFrame(function () {
        pending = false;
        var batch = newEls;
        newEls = [];
        for (var i = 0; i < batch.length; i++) {
          batch[i].style.setProperty("--reveal-delay", Math.min(i * 55, 600) + "ms");
          if (observer) observer.observe(batch[i]);
          else revealNow(batch[i]);
        }
      });
    });
    mo.observe(document.body, { childList: true, subtree: true });
  }

  reveal(document);

  window.Motion = {
    reveal: reveal,
    stagger: stagger,
    enter: enter,
    animateNumber: animateNumber,
    reduced: reduced
  };
})();
