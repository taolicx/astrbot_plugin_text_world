from __future__ import annotations

import asyncio
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .service_v2 import TextWorldService

try:
    from astrbot.api import logger
except Exception:
    import logging

    logger = logging.getLogger("astrbot_plugin_text_world.webapp")

MAX_BODY_BYTES = 256 * 1024


HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学院都市文游后台</title>
  <style>
    body{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;background:#f6f7f9;color:#1f2937}
    header{background:#111827;color:#fff;padding:14px 22px;display:flex;justify-content:space-between;align-items:center}
    main{max-width:1180px;margin:0 auto;padding:22px}
    section{background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:16px;margin-bottom:16px}
    h1,h2{margin:0 0 12px}
    input,textarea,select,button{font:inherit;border:1px solid #d1d5db;border-radius:6px;padding:8px;box-sizing:border-box}
    textarea{min-height:86px}
    button{background:#2563eb;color:#fff;border-color:#2563eb;cursor:pointer}
    button.secondary{background:#fff;color:#1f2937;border-color:#d1d5db}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
    .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .card{border:1px solid #e5e7eb;border-radius:8px;padding:12px;background:#fff}
    .muted{color:#6b7280;font-size:13px}
    pre{white-space:pre-wrap;background:#f3f4f6;border-radius:6px;padding:10px;max-height:360px;overflow:auto}
    label{display:block;font-size:13px;color:#374151;margin-bottom:4px}
    .hidden{display:none}
  </style>
</head>
<body>
  <header><strong>学院都市文游后台</strong><span id="user"></span></header>
  <main>
    <section id="loginBox">
      <h2>登录</h2>
      <div class="grid">
        <div><label>账号</label><input id="loginUser" value="admin"></div>
        <div><label>密码</label><input id="loginPass" type="password" value=""></div>
      </div>
      <p><button onclick="login()">登录</button></p>
      <p class="muted">默认管理员账号和密码可在 AstrBot 插件配置中修改。</p>
    </section>

    <div id="app" class="hidden">
      <section>
        <h2>账号安全</h2>
        <div class="grid">
          <div><label>旧密码</label><input id="oldPass" type="password"></div>
          <div><label>新密码</label><input id="newPass" type="password"></div>
        </div>
        <p><button class="secondary" onclick="changePassword()">修改密码</button></p>
      </section>

      <section>
        <h2>世界概览</h2>
        <div id="worlds" class="grid"></div>
      </section>

      <section>
        <h2>我的角色</h2>
        <div id="playerCharacters" class="grid"></div>
      </section>

      <section class="adminOnly">
        <h2>玩家角色</h2>
        <div class="grid">
          <div><label>群号 group_id</label><input id="charGroup"></div>
          <div><label>QQ号</label><input id="charQq"></div>
          <div><label>游戏名</label><input id="charName"></div>
          <div><label>初始/重置密码（可空，默认QQ后6位）</label><input id="charPassword" type="password"></div>
          <div><label>身份</label><input id="charIdentity"></div>
          <div><label>阵营</label><input id="charFaction"></div>
          <div><label>能力</label><input id="charAbility"></div>
          <div><label>战斗力</label><input id="charPower" value="D"></div>
          <div><label>审核状态</label><select id="charAudit"><option value="approved">已通过</option><option value="pending">待审核</option><option value="rejected">已拒绝</option></select></div>
          <div><label>位置key</label><input id="charLoc" value="school_gate"></div>
          <div><label>学都币（留空则不修改）</label><input id="charMoney" type="number" placeholder="新角色默认使用配置值"></div>
        </div>
        <p><button onclick="saveCharacter()">保存/审核角色</button></p>
        <div id="characters" class="grid"></div>
      </section>

      <section class="adminOnly">
        <h2>预设事件</h2>
        <div class="grid">
          <div><label>群号 group_id</label><input id="eventGroup"></div>
          <div><label>事件名称</label><input id="eventTitle"></div>
        </div>
        <p><label>事件描述</label><textarea id="eventDesc"></textarea></p>
        <p class="row"><button onclick="saveEvent(false)">保存事件</button><button onclick="saveEvent(true)">保存并加入下一轮</button></p>
        <div id="events" class="grid"></div>
      </section>

      <section>
        <h2>商店</h2>
        <div id="playerShop" class="grid"></div>
      </section>

      <section class="adminOnly">
        <h2>商店商品</h2>
        <div class="grid">
          <div><label>群号 group_id</label><input id="shopGroup"></div>
          <div><label>商品名</label><input id="shopName"></div>
          <div><label>价格</label><input id="shopPrice" type="number" value="10"></div>
          <div><label>库存（-1不限）</label><input id="shopStock" type="number" value="-1"></div>
        </div>
        <p><label>描述</label><textarea id="shopDesc"></textarea></p>
        <p><label>效果JSON，例如 {"water":20}</label><input id="shopEffect" value='{"water":20}' style="width:100%"></p>
        <p><button onclick="saveShop()">保存商品</button></p>
        <div id="shop" class="grid"></div>
      </section>

      <section>
        <h2>世界历史</h2>
        <pre id="history"></pre>
      </section>
    </div>
  </main>
<script>
let token = localStorage.getItem("tw_token") || "";
async function api(path, opts={}){
  opts.headers = Object.assign({"Content-Type":"application/json"}, opts.headers||{});
  if(token) opts.headers.Authorization = "Bearer " + token;
  const resp = await fetch(path, opts);
  if(!resp.ok) throw new Error(await resp.text());
  return resp.json();
}
async function login(){
  const data = await api("/api/login",{method:"POST",body:JSON.stringify({username:loginUser.value,password:loginPass.value})});
  token=data.token; localStorage.setItem("tw_token", token); await load();
}
function esc(value){
  return String(value ?? "").replace(/[&<>"']/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[ch]));
}
async function load(){
  if(!token) return;
  const data = await api("/api/snapshot");
  loginBox.classList.add("hidden"); app.classList.remove("hidden");
  user.textContent = `${data.user.username} / ${data.user.role}`;
  document.querySelectorAll(".adminOnly").forEach(el => el.style.display = data.user.role === "admin" ? "" : "none");
  worlds.innerHTML = data.worlds.map(w=>`<div class=card><b>${esc(w.name)}</b><p>群号：${esc(w.group_id)}</p><p>轮次：${esc(w.current_round)}</p><p>下次结算：${esc(w.next_tick_at)}</p></div>`).join("");
  playerCharacters.innerHTML = data.characters.map(c=>`<div class=card><b>${esc(c.game_name)}</b><p>群：${esc(c.group_id)}</p><p>身份：${esc(c.identity || "未设定")}</p><p>位置：${esc(c.location_key)}</p><p>状态：HP ${esc(c.hp)} / 精力 ${esc(c.energy)} / 水 ${esc(c.water)} / 饱 ${esc(c.satiety)} / 心情 ${esc(c.mood)} / 币 ${esc(c.money)}</p></div>`).join("");
  characters.innerHTML = data.characters.map(c=>`<div class=card><b>${esc(c.game_name)}</b><p>QQ：${esc(c.qq_id)}</p><p>群：${esc(c.group_id)}</p><p>审核：${esc(c.audit_status)}</p><p>状态：HP ${esc(c.hp)} / 水 ${esc(c.water)} / 饱 ${esc(c.satiety)} / 币 ${esc(c.money)}</p></div>`).join("");
  events.innerHTML = data.events.map(e=>`<div class=card><b>${esc(e.title)}</b><p>${esc(e.description)}</p><p>群：${esc(e.group_id)}</p><button onclick="triggerEvent(${Number(e.id)})">加入下一轮</button></div>`).join("");
  playerShop.innerHTML = data.shop.map(s=>`<div class=card><b>${esc(s.name)}</b><p>群：${esc(s.group_id)}</p><p>${esc(s.description)}</p><p>${esc(s.price)} 学都币 / 库存 ${esc(s.stock < 0 ? "不限" : s.stock)}</p></div>`).join("");
  shop.innerHTML = data.shop.map(s=>`<div class=card><b>${esc(s.name)}</b><p>群：${esc(s.group_id)}</p><p>${esc(s.description)}</p><p>${esc(s.price)} 学都币</p></div>`).join("");
  history.textContent = data.history.map(h=>`[${h.created_at}] ${h.group_id} #${h.round_no} ${h.visibility}\n${h.text}`).join("\n\n");
}
async function saveCharacter(){
  const payload = {group_id:charGroup.value,qq_id:charQq.value,game_name:charName.value,password:charPassword.value,identity:charIdentity.value,faction:charFaction.value,ability:charAbility.value,power_level:charPower.value,audit_status:charAudit.value,location_key:charLoc.value};
  if(charMoney.value !== "") payload.money = Number(charMoney.value);
  await api("/api/admin/character",{method:"POST",body:JSON.stringify(payload)});
  await load();
}
async function changePassword(){
  await api("/api/change-password",{method:"POST",body:JSON.stringify({old_password:oldPass.value,new_password:newPass.value})});
  alert("密码已修改，请重新登录");
  localStorage.removeItem("tw_token"); location.reload();
}
async function saveEvent(next){
  await api("/api/admin/event",{method:"POST",body:JSON.stringify({group_id:eventGroup.value,title:eventTitle.value,description:eventDesc.value,trigger_next:next})});
  await load();
}
async function triggerEvent(id){
  await api("/api/admin/event/trigger",{method:"POST",body:JSON.stringify({id})});
  await load();
}
async function saveShop(){
  let effect={}; try{effect=JSON.parse(shopEffect.value||"{}")}catch(e){alert("效果JSON格式错误");return}
  await api("/api/admin/shop",{method:"POST",body:JSON.stringify({group_id:shopGroup.value,name:shopName.value,description:shopDesc.value,price:Number(shopPrice.value),stock:Number(shopStock.value),effect})});
  await load();
}
load().catch(()=>{});
</script>
</body>
</html>"""


class WebPanel:
    def __init__(self, service: TextWorldService, host: str, port: int):
        self.service = service
        self.host = host
        self.port = port
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    async def start(self) -> None:
        if self._server:
            return
        await asyncio.to_thread(self._start_sync)

    def _start_sync(self) -> None:
        service = self.service

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt: str, *args: Any) -> None:
                logger.debug("[TextWorldWeb] " + fmt, *args)

            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path == "/":
                    self._send_html(HTML)
                    return
                if parsed.path == "/api/snapshot":
                    user = self._auth()
                    if not user:
                        self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                        return
                    self._send_json(service.dashboard_snapshot(user))
                    return
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

            def do_POST(self) -> None:
                parsed = urlparse(self.path)
                try:
                    body = self._body()
                    if parsed.path == "/api/login":
                        token = service.db.create_session(str(body.get("username") or ""), str(body.get("password") or ""))
                        if not token:
                            self._send_json({"error": "账号或密码错误"}, HTTPStatus.UNAUTHORIZED)
                            return
                        self._send_json({"token": token})
                        return
                    user = self._auth()
                    if not user:
                        self._send_json({"error": "unauthorized"}, HTTPStatus.UNAUTHORIZED)
                        return
                    if parsed.path == "/api/change-password":
                        ok, msg = service.db.change_password(
                            int(user["id"]),
                            str(body.get("old_password") or ""),
                            str(body.get("new_password") or ""),
                        )
                        self._send_json({"ok": ok, "message": msg}, HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST)
                        return
                    if parsed.path == "/api/admin/character":
                        self._require_admin(user)
                        self._send_json(service.admin_update_character(body))
                        return
                    if parsed.path == "/api/admin/event":
                        self._require_admin(user)
                        self._send_json(service.admin_event_preset(body))
                        return
                    if parsed.path == "/api/admin/event/trigger":
                        self._require_admin(user)
                        event_id = self._int_body(body, "id")
                        if event_id <= 0:
                            raise ValueError("事件 id 不正确。")
                        if not service.admin_trigger_event(event_id):
                            raise ValueError("事件不存在。")
                        self._send_json({"ok": True})
                        return
                    if parsed.path == "/api/admin/shop":
                        self._require_admin(user)
                        self._send_json(service.admin_shop_item(body))
                        return
                    self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                except PermissionError as exc:
                    self._send_json({"error": str(exc)}, HTTPStatus.FORBIDDEN)
                except Exception as exc:
                    logger.exception(f"[TextWorldWeb] request failed: {exc}")
                    self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

            def _auth(self) -> dict[str, Any] | None:
                auth = self.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    return service.db.user_by_session(auth[7:].strip())
                return None

            def _require_admin(self, user: dict[str, Any]) -> None:
                if user.get("role") != "admin":
                    raise PermissionError("需要管理员权限")

            def _body(self) -> dict[str, Any]:
                try:
                    length = int(self.headers.get("Content-Length", "0") or "0")
                except ValueError as exc:
                    raise ValueError("Content-Length 不正确。") from exc
                if length > MAX_BODY_BYTES:
                    raise ValueError("请求体过大。")
                raw = self.rfile.read(length).decode("utf-8") if length else "{}"
                if self.headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
                    return {key: value[-1] for key, value in parse_qs(raw).items()}
                parsed = json.loads(raw or "{}")
                if not isinstance(parsed, dict):
                    raise ValueError("请求 JSON 必须是对象。")
                return parsed

            def _int_body(self, body: dict[str, Any], key: str) -> int:
                try:
                    return int(body.get(key, 0) or 0)
                except (TypeError, ValueError):
                    return 0

            def _send_html(self, text: str) -> None:
                data = text.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(int(status))
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._server = ThreadingHTTPServer((self.host, self.port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        logger.info(f"[TextWorldWeb] started at http://{self.host}:{self.port}")

    async def stop(self) -> None:
        if not self._server:
            return
        server = self._server
        self._server = None
        await asyncio.to_thread(server.shutdown)
        await asyncio.to_thread(server.server_close)
        logger.info("[TextWorldWeb] stopped")
