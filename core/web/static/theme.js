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
