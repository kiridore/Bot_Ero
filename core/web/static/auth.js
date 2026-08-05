const STORAGE_KEY = "botero_gallery_session";

const GalleryAuth = {
  load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      return null;
    }
  },

  save(session) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  },

  clear() {
    localStorage.removeItem(STORAGE_KEY);
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
