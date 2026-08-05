const STORAGE_KEY = "botero_gallery_session";
const COOKIE_KEY = "botero_key";
const COOKIE_MAX_AGE = 365 * 24 * 3600;

function cookieDomain() {
  const host = location.hostname;
  if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) return "";
  const parts = host.split(".");
  return parts.length >= 3 ? "." + parts.slice(-2).join(".") : "";
}

function readCookie(name) {
  const m = document.cookie.match(new RegExp("(?:^|;\\s*)" + name + "=([^;]*)"));
  return m ? decodeURIComponent(m[1]) : "";
}

function writeCookie(name, value) {
  const domain = cookieDomain();
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie =
    name + "=" + encodeURIComponent(value) +
    "; domain=" + domain + "; path=/; max-age=" + COOKIE_MAX_AGE +
    "; SameSite=Lax" + secure;
}

function clearCookie(name) {
  const domain = cookieDomain();
  document.cookie = name + "=; domain=" + domain + "; path=/; max-age=0; SameSite=Lax";
}

const GalleryAuth = {
  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) return JSON.parse(raw);
    } catch {
      /* fallthrough */
    }
    const key = readCookie(COOKIE_KEY);
    return key ? { token: key } : null;
  },

  save(session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    if (session && session.token) {
      writeCookie(COOKIE_KEY, session.token);
    }
  },

  clear() {
    localStorage.removeItem(STORAGE_KEY);
    clearCookie(COOKIE_KEY);
  },

  token() {
    const s = this.load();
    return s && s.token ? s.token : "";
  },

  headers() {
    const t = this.token();
    return t ? { Authorization: `Bearer ${t}` } : {};
  },

  isLoggedIn() {
    return Boolean(this.token());
  },

  _escape(s) {
    return String(s).replace(/[&<>"']/g, (c) => (
      { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
    ));
  },

  ensureLoginDialog() {
    let dlg = document.getElementById("loginDialog");
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.id = "loginDialog";
    dlg.className = "login-dialog";
    dlg.innerHTML =
      '<form method="dialog" id="loginForm">' +
      "<h2>登录</h2>" +
      '<p class="login-hint">请向机器人私聊发送 <code>/图库密钥</code> 获取密钥</p>' +
      '<input type="password" id="loginKey" placeholder="粘贴登录密钥" autocomplete="off" required />' +
      '<p class="login-error hidden" id="loginError"></p>' +
      '<div class="login-actions">' +
      '<button type="button" id="loginCancel">取消</button>' +
      '<button type="submit" class="primary">登录</button>' +
      "</div>" +
      "</form>";
    document.body.appendChild(dlg);
    const form = dlg.querySelector("#loginForm");
    const input = dlg.querySelector("#loginKey");
    const errEl = dlg.querySelector("#loginError");
    dlg.querySelector("#loginCancel").addEventListener("click", () => dlg.close());
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      errEl.classList.add("hidden");
      try {
        await this.login(input.value);
        dlg.close();
        input.value = "";
        this.renderAuth(document.getElementById("authArea"));
      } catch (err) {
        errEl.textContent = err.message || "登录失败";
        errEl.classList.remove("hidden");
      }
    });
    return dlg;
  },

  renderAuth(area) {
    const el = area || document.getElementById("authArea");
    if (!el) return;
    el.innerHTML = "";
    const session = this.load();
    if (!session || !session.token) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "btn-login";
      btn.textContent = "登录";
      btn.addEventListener("click", () => {
        if (typeof window.openLoginDialog === "function") {
          window.openLoginDialog();
          return;
        }
        const dlg = this.ensureLoginDialog();
        if (dlg && typeof dlg.showModal === "function") dlg.showModal();
      });
      el.appendChild(btn);
      return;
    }
    const link = document.createElement("a");
    link.className = "user-chip";
    link.href = "/";
    const img = document.createElement("img");
    img.src = session.avatar_url || "";
    img.alt = session.display_name || session.user_id;
    img.onerror = () => { img.style.display = "none"; };
    const wrap = document.createElement("span");
    wrap.innerHTML =
      `<strong>${this._escape(session.display_name || session.user_id)}</strong>` +
      `<br><span class="uid">${this._escape(session.user_id)}</span>`;
    link.append(img, wrap);
    el.appendChild(link);
  },

  async login(key) {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: key.trim() }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "登录失败");
    }
    const session = await res.json();
    session.token = key.trim();
    this.save(session);
    return session;
  },

  async refreshMe() {
    const res = await fetch("/api/auth/me", { headers: this.headers() });
    if (!res.ok) {
      this.clear();
      return null;
    }
    const me = await res.json();
    const prev = this.load() || {};
    this.save({ ...prev, ...me, token: prev.token });
    return this.load();
  },
};

window.GalleryAuth = GalleryAuth;
