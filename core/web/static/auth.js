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
