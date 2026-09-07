"""bot 内置 web 监控面板：插件启停 + 配置编辑（仅超管，图库密钥鉴权）。

stdlib http.server（每请求一线程，契合纯同步多线程模型）；main.py 以守护线程拉起。
配置 config.yaml panel 节（host/port，默认 0.0.0.0:8790，局域网访问）。
"""

import json
import os
import shutil
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from core import config
from core import context as runtime_context
from core.auth import verify_login_key

_PAGE = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BotEro 监控面板</title>
<style>
 body{font-family:system-ui,sans-serif;margin:0;background:#f6f4ee;color:#333;line-height:1.5}
 main{max-width:760px;margin:0 auto;padding:1rem}
 h1{font-size:1.3rem} h2{font-size:1.05rem;border-bottom:2px solid #5f7a68;padding-bottom:.3rem}
 section{background:#fff;border:1px solid #d8d2c2;border-radius:10px;padding:1rem;margin:1rem 0}
 .row{display:flex;align-items:center;gap:.6rem;padding:.4rem 0;border-bottom:1px solid #eee}
 .key{flex:1;font-size:.9rem}.desc{font-size:.75rem;color:#888}.badge{font-size:.75rem;color:#666}
 button{border:1px solid #5f7a68;background:#e4e9dd;color:#3f5347;border-radius:999px;
   padding:.2rem 1rem;font-size:.82rem;cursor:pointer}
 button.off{background:transparent;color:#888}
 button:disabled{opacity:.5;cursor:default}
 textarea{width:100%;box-sizing:border-box;min-height:22rem;font-family:Consolas,monospace;
   font-size:.82rem;padding:.6rem;border:1px solid #d8d2c2;border-radius:8px;white-space:pre}
 .hint{font-size:.78rem;color:#888}.err{font-size:.8rem;color:#b3402f;white-space:pre-wrap}
 input{padding:.45rem;border:1px solid #d8d2c2;border-radius:8px;font:inherit}
</style></head><body><main>
<h1>BotEro 监控面板</h1>
<div id="login" hidden><section><h2>登录</h2>
 <p class="hint">请输入超级用户的图库密钥（向机器人私聊发送 /图库密钥 获取）</p>
 <input type="password" id="keyInput" placeholder="粘贴密钥"> <button id="keyBtn">进入</button>
 <p class="err" id="loginErr"></p></section></div>
<div id="app" hidden>
 <section><h2>插件管理</h2>
  <p class="hint">改动即时生效；私聊=仅私聊消息生效的插件范围。</p>
  <label>作用范围 <select id="scope"></select></label>
  <div id="plugins"></div></section>
 <section><h2>配置文件</h2>
  <p class="hint">保存后需重启 bot 进程生效（webapp 若共用配置项也需重启）；自动备份 config.yaml.bak（保留一代）。</p>
  <textarea id="cfg" spellcheck="false"></textarea>
  <p><button id="save">保存配置</button> <span class="hint" id="hint"></span></p>
  <p class="err" id="err" hidden></p></section>
</div></main>
<script>
const $=id=>document.getElementById(id);
const api=async(p,o={})=>{const r=await fetch(p,{...o,headers:{Authorization:"Bearer "+localStorage.panelKey,...(o.headers||{})}});
 if(r.status===401){localStorage.removeItem("panelKey");throw new Error("密钥无效");}
 const d=await r.json().catch(()=>({}));
 if(!r.ok)throw new Error(typeof d.detail==="string"?d.detail:"请求失败");return d;};
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}
async function boot(){if(!localStorage.panelKey){$("login").hidden=false;return;}
 try{await loadScopes();await loadCfg();$("app").hidden=false;}
 catch(e){if(e.message==="密钥无效")$("login").hidden=false;else alert(e.message);}}
$("keyBtn").onclick=async()=>{localStorage.panelKey=$("keyInput").value.trim();location.reload();};
async function loadScopes(){const d=await api("/api/scopes");const s=$("scope");s.innerHTML="";
 d.scopes.forEach(x=>{const o=document.createElement("option");o.value=x.group_id;
  o.textContent=x.label+(x.is_default?"（默认）":"");s.appendChild(o);});
 if(d.scopes.length)await loadPlugins(+s.value);
 s.onchange=()=>loadPlugins(+s.value);}
async function loadPlugins(gid){const d=await api("/api/plugins?group_id="+gid);const h=$("plugins");
 h.innerHTML="";const sys=[],norm=[];
 d.plugins.forEach(p=>p.system?sys.push(p):norm.push(p));
 const mk=p=>{const r=document.createElement("div");r.className="row";
  const k=document.createElement("span");k.className="key";
  k.innerHTML=esc(p.key)+(p.description?`<div class="desc">${esc(p.description)}</div>`:"");
  const b=document.createElement("span");b.className="badge";b.textContent=p.enabled?"✅":"❌";
  const btn=document.createElement("button");btn.textContent=p.enabled?"禁用":"启用";
  btn.className=p.enabled?"":"off";
  btn.onclick=async()=>{btn.disabled=true;try{
    await api("/api/plugins",{method:"PUT",headers:{"Content-Type":"application/json"},
     body:JSON.stringify({group_id:gid,plugin_key:p.key,enabled:!p.enabled})});
    await loadPlugins(gid);}catch(e){alert(e.message);btn.disabled=false;}};
  r.append(k,b,btn);return r;};
 norm.forEach(p=>h.appendChild(mk(p)));
 const tip=document.createElement("p");tip.className="hint";
 tip.textContent="🔒 系统插件（恒启用，不可修改）";h.appendChild(tip);
 sys.forEach(p=>{const r=mk(p);r.querySelector("button").disabled=true;h.appendChild(r);});}
async function loadCfg(){const d=await api("/api/config");$("cfg").value=d.yaml;}
$("save").onclick=async()=>{const b=$("save");b.disabled=true;$("err").hidden=true;
 try{await api("/api/config",{method:"PUT",headers:{"Content-Type":"application/json"},
   body:JSON.stringify({yaml:$("cfg").value})});
  $("hint").textContent="已保存（重启进程后生效）";await loadCfg();}
 catch(e){$("err").textContent=e.message;$("err").hidden=false;}
 finally{b.disabled=false;}};
boot();
</script></body></html>"""


def _scope_label(gid: int) -> str:
    return "私聊" if gid == 0 else f"群 {gid}"


def _enabled_set(gid: int) -> set[str]:
    conn = sqlite3.connect(str(config.DB_PATH))
    rows = conn.execute(
        "SELECT plugin_name FROM group_plugin_config WHERE group_id = ?", (int(gid),)
    ).fetchall()
    conn.close()
    return {r[0] for r in rows}


def _plugin_entries() -> list[dict]:
    out = []
    for cls in runtime_context.plugin_registry:
        key = runtime_context.plugin_key(cls)
        out.append({
            "key": key,
            "description": getattr(cls, "description", "") or "",
            "system": key in runtime_context.SYSTEM_PLUGINS,
        })
    out.sort(key=lambda x: x["key"])
    return out


def _validate_config(text: str) -> str | None:
    """返回错误说明；None=通过。"""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return f"YAML 解析失败：{exc}"
    if not isinstance(data, dict):
        return "配置顶层必须是键值映射"
    for dotted in config._REQUIRED:
        section, _, key = dotted.partition(".")
        sec = data.get(section)
        value = sec.get(key) if isinstance(sec, dict) else None
        if value is None or value == "" or value == []:
            return f"缺少必填配置项 {dotted}"
    return None


class PanelHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # 静音默认访问日志
        pass

    # —— 鉴权 ——
    def _auth(self) -> tuple[int, str] | None:
        """通过返回 None；失败返回 (status, detail)。"""
        auth = self.headers.get("Authorization", "")
        token = auth[7:].strip() if auth.startswith("Bearer ") else ""
        if not token:
            return 401, "未登录"
        uid = verify_login_key(token)
        if uid is None:
            return 401, "密钥无效"
        if int(uid) not in config.SUPER_USER:
            return 403, "仅超级用户"
        return None

    def _json(self, status: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode())
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            page = _PAGE.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            self.end_headers()
            self.wfile.write(page)
            return
        denied = self._auth()
        if denied:
            self._json(denied[0], {"detail": denied[1]})
            return
        if u.path == "/api/scopes":
            conn = sqlite3.connect(str(config.DB_PATH))
            gids = [r[0] for r in conn.execute(
                "SELECT DISTINCT group_id FROM group_plugin_config").fetchall()]
            conn.close()
            seen = {0, config.DEFAULT_GROUP_ID, *gids}
            self._json(200, {"scopes": [
                {"group_id": g, "label": _scope_label(g),
                 "is_default": g == config.DEFAULT_GROUP_ID}
                for g in sorted(seen)
            ]})
            return
        if u.path == "/api/plugins":
            qs = parse_qs(u.query)
            try:
                gid = int((qs.get("group_id") or ["0"])[0])
            except ValueError:
                self._json(400, {"detail": "group_id 须为整数"})
                return
            enabled = _enabled_set(gid)
            self._json(200, {
                "group_id": gid, "label": _scope_label(gid),
                "is_default": gid == config.DEFAULT_GROUP_ID,
                "plugins": [{**p, "enabled": p["key"] in enabled} for p in _plugin_entries()],
            })
            return
        if u.path == "/api/config":
            try:
                text = config.CONFIG_PATH.read_text(encoding="utf-8")
            except OSError as exc:
                self._json(500, {"detail": f"读取失败：{exc}"})
                return
            self._json(200, {"yaml": text, "path": config.CONFIG_PATH.name})
            return
        self._json(404, {"detail": "不存在"})

    def do_PUT(self):
        u = urlparse(self.path)
        denied = self._auth()
        if denied:
            self._json(denied[0], {"detail": denied[1]})
            return
        body = self._body()
        if u.path == "/api/plugins":
            gid = body.get("group_id")
            key = str(body.get("plugin_key") or "")
            enabled = body.get("enabled")
            if not isinstance(gid, int) or gid < 0 or not key or not isinstance(enabled, bool):
                self._json(400, {"detail": "参数不合法（group_id/plugin_key/enabled）"})
                return
            if key in runtime_context.SYSTEM_PLUGINS:
                self._json(400, {"detail": "系统插件不可禁用"})
                return
            if key not in {p["key"] for p in _plugin_entries()}:
                self._json(400, {"detail": f"插件不存在：{key}"})
                return
            conn = sqlite3.connect(str(config.DB_PATH))
            if enabled:
                conn.execute(
                    "INSERT OR IGNORE INTO group_plugin_config (group_id, plugin_name) VALUES (?, ?)",
                    (gid, key),
                )
            else:
                conn.execute(
                    "DELETE FROM group_plugin_config WHERE group_id = ? AND plugin_name = ?",
                    (gid, key),
                )
            conn.commit()
            conn.close()
            self._json(200, {"ok": True, "key": key, "enabled": enabled})
            return
        if u.path == "/api/config":
            text = body.get("yaml")
            if not isinstance(text, str) or not text:
                self._json(400, {"detail": "yaml 不能为空"})
                return
            err = _validate_config(text)
            if err:
                self._json(400, {"detail": err})
                return
            path = config.CONFIG_PATH
            if path.is_file():
                shutil.copyfile(path, Path(str(path) + ".bak"))
            tmp = Path(str(path) + ".tmp")
            tmp.write_text(text, encoding="utf-8")
            os.replace(tmp, path)
            self._json(200, {"ok": True})
            return
        self._json(404, {"detail": "不存在"})


def make_server(host: str | None = None, port: int | None = None) -> ThreadingHTTPServer:
    return ThreadingHTTPServer(
        (host or config.PANEL_HOST, port if port is not None else config.PANEL_PORT),
        PanelHandler,
    )


def start_panel() -> None:
    """main.py 启动调用；失败仅告警，不阻断 bot。"""
    import logging

    logger = logging.getLogger(__name__)
    try:
        server = make_server()
        threading.Thread(target=server.serve_forever, daemon=True, name="web-panel").start()
        logger.info("监控面板已启动 http://%s:%s/", server.server_address[0], server.server_address[1])
    except OSError as exc:
        logger.warning("监控面板启动失败（端口占用或无权限？）：%s", exc)
