// 登录页：密钥登录 + 会话自愈（cookie 被清但 localStorage 仍有效时补写 cookie 直接跳回）
(function () {
  const params = new URLSearchParams(location.search);
  let next = params.get("next") || "/";
  if (!/^\/(?!\/)/.test(next)) next = "/"; // 仅接受站内相对路径，防开放重定向

  const form = document.getElementById("loginForm");
  const input = document.getElementById("loginKey");
  const errEl = document.getElementById("loginError");
  const submitBtn = document.getElementById("loginSubmit");

  function back() {
    location.replace(next);
  }

  // 会话自愈：已带有效会话进入登录页（如仅 cookie 丢失）→ 直接返回目标页
  if (window.GalleryAuth && GalleryAuth.isLoggedIn()) {
    GalleryAuth.refreshMe().then((me) => {
      if (me) back();
    });
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    errEl.classList.add("hidden");
    submitBtn.disabled = true;
    try {
      await GalleryAuth.login(input.value);
      back();
    } catch (err) {
      errEl.textContent = err.message || "登录失败";
      errEl.classList.remove("hidden");
      submitBtn.disabled = false;
    }
  });
})();
