from __future__ import annotations

import asyncio
import json
import threading
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse

from .compat import to_thread
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
    :root{
      color-scheme:light;
      --bg:#f4f6f8;
      --panel:#ffffff;
      --ink:#172033;
      --muted:#667085;
      --line:#d9e0ea;
      --line-strong:#b9c4d2;
      --brand:#2457d6;
      --brand-dark:#173b93;
      --good:#0f8f62;
      --warn:#b75e09;
      --bad:#bf2d3a;
      --teal:#0b7285;
      --shadow:0 10px 30px rgba(24,39,75,.08);
      --radius:8px;
    }
    *{box-sizing:border-box}
    body{
      margin:0;
      font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif;
      background:var(--bg);
      color:var(--ink);
      letter-spacing:0;
    }
    button,input,textarea,select{font:inherit}
    button{
      min-height:36px;
      border:1px solid var(--brand);
      border-radius:6px;
      background:var(--brand);
      color:#fff;
      padding:7px 12px;
      cursor:pointer;
      white-space:nowrap;
    }
    button:hover{background:var(--brand-dark);border-color:var(--brand-dark)}
    button.secondary{background:#fff;color:var(--ink);border-color:var(--line-strong)}
    button.secondary:hover{background:#eef2f7}
    button.ghost{background:transparent;color:#d7e2ff;border-color:rgba(255,255,255,.35)}
    button.ghost:hover{background:rgba(255,255,255,.12)}
    input,textarea,select{
      width:100%;
      min-height:36px;
      border:1px solid var(--line-strong);
      border-radius:6px;
      background:#fff;
      color:var(--ink);
      padding:7px 9px;
      outline:none;
    }
    input:focus,textarea:focus,select:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(36,87,214,.14)}
    textarea{min-height:84px;resize:vertical;line-height:1.5}
    label{display:block;margin:0 0 5px;color:#344054;font-size:13px;font-weight:650}
    .hidden{display:none!important}
    .shell{min-height:100vh;display:flex;flex-direction:column}
    .topbar{
      background:#101828;
      color:#fff;
      border-bottom:1px solid rgba(255,255,255,.1);
    }
    .topbar-inner{
      max-width:1440px;
      margin:0 auto;
      padding:14px 20px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:16px;
    }
    .brand{display:flex;align-items:center;gap:10px;min-width:0}
    .brand-mark{
      width:34px;
      height:34px;
      border-radius:7px;
      background:#f2b84b;
      color:#101828;
      display:grid;
      place-items:center;
      font-weight:800;
      flex:0 0 auto;
    }
    .brand-title{font-size:18px;font-weight:800;line-height:1.1}
    .brand-sub{font-size:12px;color:#b8c3d8;margin-top:3px}
    .userbar{display:flex;align-items:center;gap:9px;flex-wrap:wrap;justify-content:flex-end}
    .user-pill{
      border:1px solid rgba(255,255,255,.22);
      background:rgba(255,255,255,.08);
      border-radius:999px;
      padding:7px 10px;
      font-size:13px;
      color:#edf3ff;
    }
    main{width:100%;max-width:1440px;margin:0 auto;padding:18px 20px 28px}
    .login-layout{max-width:440px;margin:8vh auto 0}
    .login-panel{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:22px;
      box-shadow:var(--shadow);
    }
    .login-panel h1{font-size:22px;margin:0 0 18px}
    .form-stack{display:grid;gap:14px}
    .workspace{display:grid;grid-template-columns:236px minmax(0,1fr);gap:18px;align-items:start}
    nav{
      position:sticky;
      top:14px;
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:10px;
      box-shadow:var(--shadow);
    }
    .nav-title{font-size:12px;font-weight:800;color:var(--muted);padding:8px 10px;text-transform:uppercase}
    .tab{
      width:100%;
      display:flex;
      justify-content:space-between;
      align-items:center;
      margin:2px 0;
      padding:9px 10px;
      border:0;
      border-radius:6px;
      background:transparent;
      color:#263445;
      text-align:left;
    }
    .tab:hover,.tab.active{background:#eef3ff;color:#183a91}
    .tab .count{font-size:12px;color:var(--muted)}
    .content{display:grid;gap:16px;min-width:0}
    .section{
      background:var(--panel);
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:16px;
      box-shadow:var(--shadow);
      min-width:0;
    }
    .section-head{
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:flex-start;
      margin-bottom:14px;
    }
    h2{font-size:18px;line-height:1.25;margin:0}
    h3{font-size:15px;margin:0 0 10px}
    .muted{color:var(--muted);font-size:13px}
    .toolbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .toolbar input,.toolbar select{width:auto;min-width:180px}
    .metrics{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}
    .metric{
      background:#fff;
      border:1px solid var(--line);
      border-left:4px solid var(--brand);
      border-radius:var(--radius);
      padding:12px;
      min-width:0;
    }
    .metric:nth-child(2){border-left-color:var(--teal)}
    .metric:nth-child(3){border-left-color:var(--warn)}
    .metric:nth-child(4){border-left-color:var(--good)}
    .metric:nth-child(5){border-left-color:#7a4cc2}
    .metric:nth-child(6){border-left-color:#c04770}
    .metric-label{color:var(--muted);font-size:12px}
    .metric-value{font-size:26px;font-weight:800;margin-top:4px}
    .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
    .grid.tight{grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
    .item{
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:12px;
      background:#fff;
      min-width:0;
    }
    .item-title{display:flex;justify-content:space-between;gap:10px;align-items:flex-start;margin-bottom:8px}
    .item-title b{overflow-wrap:anywhere}
    .kv{display:grid;grid-template-columns:82px minmax(0,1fr);gap:5px 8px;font-size:13px;line-height:1.45}
    .kv span:nth-child(odd){color:var(--muted)}
    .kv span:nth-child(even){overflow-wrap:anywhere}
    .badge{
      display:inline-flex;
      align-items:center;
      min-height:22px;
      border-radius:999px;
      padding:2px 8px;
      font-size:12px;
      font-weight:700;
      background:#edf2f7;
      color:#344054;
      max-width:100%;
      overflow-wrap:anywhere;
      white-space:normal;
      text-align:left;
    }
    .badge.good{background:#e6f7ef;color:#08734e}
    .badge.warn{background:#fff1df;color:#9a4b02}
    .badge.bad{background:#ffe8eb;color:#a31f2d}
    .badge.blue{background:#e9efff;color:#2348ad}
    .divider{height:1px;background:var(--line);margin:14px 0}
    .form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
    .form-grid.two{grid-template-columns:repeat(2,minmax(0,1fr))}
    .wide{grid-column:1/-1}
    .actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:12px}
    pre{
      margin:0;
      white-space:pre-wrap;
      overflow:auto;
      max-height:420px;
      border:1px solid var(--line);
      border-radius:var(--radius);
      background:#0f172a;
      color:#e6edf8;
      padding:12px;
      line-height:1.55;
      font-size:13px;
    }
    .history-list{display:grid;gap:10px}
    .history-text{white-space:pre-wrap;line-height:1.55}
    .progress{
      height:7px;
      border-radius:999px;
      background:#e4e9f2;
      overflow:hidden;
      margin-top:6px;
    }
    .progress span{display:block;height:100%;background:var(--brand)}
    .progress.good span{background:var(--good)}
    .progress.warn span{background:var(--warn)}
    .progress.bad span{background:var(--bad)}
    .empty{
      border:1px dashed var(--line-strong);
      border-radius:var(--radius);
      padding:18px;
      color:var(--muted);
      background:#fbfcfe;
    }
    .toast{
      position:fixed;
      right:18px;
      bottom:18px;
      z-index:20;
      max-width:min(420px,calc(100vw - 36px));
      border-radius:var(--radius);
      padding:12px 14px;
      background:#101828;
      color:#fff;
      box-shadow:var(--shadow);
    }
    .toast.error{background:#8f1f2b}
    @media (max-width:1100px){
      .metrics{grid-template-columns:repeat(3,minmax(0,1fr))}
      .form-grid{grid-template-columns:repeat(2,minmax(0,1fr))}
    }
    @media (max-width:760px){
      .topbar-inner{align-items:flex-start;flex-direction:column}
      .userbar{justify-content:flex-start}
      main{padding:14px}
      .workspace{grid-template-columns:1fr}
      nav{position:static}
      .tab{display:inline-flex;width:auto;margin:2px}
      .metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
      .form-grid,.form-grid.two{grid-template-columns:1fr}
      .toolbar input,.toolbar select{width:100%;min-width:0}
    }
    @media (max-width:480px){
      .metrics{grid-template-columns:1fr}
      .grid{grid-template-columns:1fr}
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <div class="brand-mark">AC</div>
          <div>
            <div class="brand-title">学院都市文游后台</div>
            <div class="brand-sub">群文游世界控制台</div>
          </div>
        </div>
        <div class="userbar">
          <span id="userBadge" class="user-pill hidden"></span>
          <button id="refreshBtn" class="ghost hidden" type="button">刷新</button>
          <button id="logoutBtn" class="ghost hidden" type="button">退出</button>
        </div>
      </div>
    </header>

    <main>
      <section id="loginBox" class="login-layout">
        <div class="login-panel">
          <h1>登录后台</h1>
          <div class="form-stack">
            <div>
              <label for="loginUser">账号</label>
              <input id="loginUser" autocomplete="username" value="admin" />
            </div>
            <div>
              <label for="loginPass">密码</label>
              <input id="loginPass" type="password" autocomplete="current-password" />
            </div>
            <button id="loginBtn" type="button">登录</button>
          </div>
        </div>
      </section>

      <div id="app" class="workspace hidden">
        <nav>
          <div class="nav-title">工作台</div>
          <button class="tab active" type="button" data-tab="overview">总览 <span id="countOverview" class="count"></span></button>
          <button class="tab" type="button" data-tab="characters">角色 <span id="countCharacters" class="count"></span></button>
          <button class="tab adminOnly" type="button" data-tab="events">事件 <span id="countEvents" class="count"></span></button>
          <button class="tab" type="button" data-tab="shop">商店 <span id="countShop" class="count"></span></button>
          <button class="tab" type="button" data-tab="map">地图 <span id="countMap" class="count"></span></button>
          <button class="tab" type="button" data-tab="npcs">NPC <span id="countNpcs" class="count"></span></button>
          <button class="tab" type="button" data-tab="history">历史 <span id="countHistory" class="count"></span></button>
          <button class="tab" type="button" data-tab="worldbook">世界书 <span id="countWorldbook" class="count"></span></button>
          <button class="tab" type="button" data-tab="providers">模型路由</button>
          <button class="tab" type="button" data-tab="account">账号</button>
        </nav>

        <div class="content">
          <section id="tab-overview" class="section page">
            <div class="section-head">
              <div>
                <h2>世界总览</h2>
                <div class="muted" id="overviewSub"></div>
              </div>
              <div class="toolbar">
                <select id="groupFilter"></select>
                <input id="searchBox" placeholder="搜索角色、事件、商品、历史" />
              </div>
            </div>
            <div id="kpis" class="metrics"></div>
            <div class="divider"></div>
            <div id="worlds" class="grid"></div>
          </section>

          <section id="tab-characters" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>角色与状态</h2>
                <div class="muted" id="characterSub"></div>
              </div>
              <div class="toolbar">
                <button id="clearCharFormBtn" class="secondary adminOnly" type="button">清空表单</button>
              </div>
            </div>

            <div class="adminOnly">
              <h3>角色卡审核 / 编辑</h3>
              <div class="form-grid">
                <div><label for="charGroup">群号 group_id</label><input id="charGroup" /></div>
                <div><label for="charQq">QQ 号</label><input id="charQq" /></div>
                <div><label for="charName">游戏名</label><input id="charName" /></div>
                <div><label for="charPassword">初始 / 重置密码</label><input id="charPassword" type="password" /></div>
                <div><label for="charAudit">审核状态</label><select id="charAudit"><option value="approved">已通过</option><option value="pending">待审核</option><option value="rejected">已拒绝</option></select></div>
                <div><label for="charLoc">位置 key</label><input id="charLoc" value="school_gate" /></div>
                <div><label for="charPower">战斗力 / 能力等级</label><input id="charPower" value="Level 0" /></div>
                <div><label for="charFaction">阵营</label><input id="charFaction" /></div>
                <div class="wide"><label for="charIdentity">身份设定</label><textarea id="charIdentity"></textarea></div>
                <div class="wide"><label for="charAbility">能力设定</label><textarea id="charAbility"></textarea></div>
                <div><label for="charHp">生命</label><input id="charHp" type="number" min="0" max="100" value="100" /></div>
                <div><label for="charEnergy">精力</label><input id="charEnergy" type="number" min="0" max="100" value="100" /></div>
                <div><label for="charWater">水分</label><input id="charWater" type="number" min="0" max="100" value="80" /></div>
                <div><label for="charSatiety">饱食度</label><input id="charSatiety" type="number" min="0" max="100" value="80" /></div>
                <div><label for="charMood">心情</label><input id="charMood" type="number" min="0" max="100" value="70" /></div>
                <div><label for="charMoney">学都币</label><input id="charMoney" type="number" min="0" placeholder="留空使用默认值" /></div>
              </div>
              <div class="actions"><button id="saveCharacterBtn" type="button">保存角色</button></div>
              <div class="divider"></div>
            </div>

            <div id="characters" class="grid"></div>
          </section>

          <section id="tab-events" class="section page hidden adminOnly">
            <div class="section-head">
              <div>
                <h2>公共事件</h2>
                <div class="muted">下一轮触发队列、预设事件和效果调整</div>
              </div>
            </div>
            <h3>添加事件</h3>
            <div class="form-grid two">
              <div><label for="eventGroup">群号 group_id</label><input id="eventGroup" /></div>
              <div><label for="eventTitle">事件名称</label><input id="eventTitle" /></div>
              <div class="wide"><label for="eventDesc">事件描述</label><textarea id="eventDesc"></textarea></div>
              <div class="wide"><label for="eventEffect">效果 JSON</label><input id="eventEffect" value="{}" /></div>
            </div>
            <div class="actions">
              <button id="saveEventBtn" type="button">保存事件</button>
              <button id="saveEventNextBtn" type="button">保存并加入下一轮</button>
            </div>
            <div class="divider"></div>
            <div id="events" class="grid"></div>
          </section>

          <section id="tab-shop" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>商店</h2>
                <div class="muted" id="shopSub"></div>
              </div>
              <div class="toolbar">
                <button id="clearShopFormBtn" class="secondary adminOnly" type="button">清空表单</button>
              </div>
            </div>

            <div class="adminOnly">
              <h3>商品编辑</h3>
              <div class="form-grid">
                <div><label for="shopGroup">群号 group_id</label><input id="shopGroup" /></div>
                <div><label for="shopName">商品名</label><input id="shopName" /></div>
                <div><label for="shopPrice">价格</label><input id="shopPrice" type="number" min="0" value="10" /></div>
                <div><label for="shopStock">库存（-1 不限）</label><input id="shopStock" type="number" value="-1" /></div>
                <div><label for="shopActive">状态</label><select id="shopActive"><option value="1">上架</option><option value="0">下架</option></select></div>
                <div class="wide"><label for="shopDesc">描述</label><textarea id="shopDesc"></textarea></div>
                <div class="wide"><label for="shopEffect">效果 JSON</label><input id="shopEffect" value='{"water":20}' /></div>
              </div>
              <div class="actions"><button id="saveShopBtn" type="button">保存商品</button></div>
              <div class="divider"></div>
            </div>

            <div id="shop" class="grid"></div>
          </section>

          <section id="tab-npcs" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>NPC</h2>
                <div class="muted" id="npcSub"></div>
              </div>
            </div>
            <div id="npcs" class="grid"></div>
          </section>

          <section id="tab-map" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>地图路线</h2>
                <div class="muted" id="mapSub"></div>
              </div>
            </div>
            <div id="mapLocations" class="grid"></div>
          </section>

          <section id="tab-history" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>世界历史</h2>
                <div class="muted" id="historySub"></div>
              </div>
            </div>
            <div id="history" class="history-list"></div>
          </section>

          <section id="tab-worldbook" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>世界书</h2>
                <div class="muted">当前随插件打包的背景资料状态</div>
              </div>
            </div>
            <div id="worldbookInfo" class="grid tight"></div>
            <div class="divider"></div>
            <pre id="worldbookPreview"></pre>
          </section>

          <section id="tab-providers" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>模型路由</h2>
                <div class="muted">不同任务使用不同 provider；未配置专用项时会自动回退</div>
              </div>
            </div>
            <div id="providerInfo" class="grid"></div>
          </section>

          <section id="tab-account" class="section page hidden">
            <div class="section-head">
              <div>
                <h2>账号</h2>
                <div class="muted">修改当前登录账号密码</div>
              </div>
            </div>
            <div class="form-grid two">
              <div><label for="oldPass">旧密码</label><input id="oldPass" type="password" autocomplete="current-password" /></div>
              <div><label for="newPass">新密码</label><input id="newPass" type="password" autocomplete="new-password" /></div>
            </div>
            <div class="actions"><button id="changePasswordBtn" type="button">修改密码</button></div>
          </section>
        </div>
      </div>
    </main>
  </div>

  <div id="toast" class="toast hidden"></div>

<script>
let token = localStorage.getItem("tw_token") || "";
let state = null;
let activeTab = "overview";

const $ = id => document.getElementById(id);

function esc(value){
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&":"&amp;",
    "<":"&lt;",
    ">":"&gt;",
    "\"":"&quot;",
    "'":"&#39;"
  }[ch]));
}

function showToast(message, type="ok"){
  const box = $("toast");
  box.textContent = message;
  box.className = "toast" + (type === "error" ? " error" : "");
  clearTimeout(showToast.timer);
  showToast.timer = setTimeout(() => box.classList.add("hidden"), 2800);
}

async function api(path, opts={}){
  const headers = Object.assign({"Content-Type":"application/json"}, opts.headers || {});
  if(token) headers.Authorization = "Bearer " + token;
  const resp = await fetch(path, Object.assign({}, opts, {headers}));
  const raw = await resp.text();
  let payload = {};
  if(raw){
    try{ payload = JSON.parse(raw); }
    catch{ payload = {error: raw}; }
  }
  if(!resp.ok){
    if(resp.status === 401){
      token = "";
      localStorage.removeItem("tw_token");
    }
    throw new Error(payload.error || payload.message || resp.statusText);
  }
  return payload;
}

async function login(){
  const username = $("loginUser").value.trim();
  const password = $("loginPass").value;
  const data = await api("/api/login", {
    method:"POST",
    body:JSON.stringify({username, password})
  });
  token = data.token;
  localStorage.setItem("tw_token", token);
  await load();
  showToast("已登录");
}

async function load(){
  if(!token) return showLogin();
  try{
    state = await api("/api/snapshot");
    showApp();
    render();
  }catch(err){
    showLogin();
    if(String(err.message || "").toLowerCase() !== "unauthorized"){
      showToast(err.message || "加载失败", "error");
    }
  }
}

function showLogin(){
  $("loginBox").classList.remove("hidden");
  $("app").classList.add("hidden");
  $("userBadge").classList.add("hidden");
  $("refreshBtn").classList.add("hidden");
  $("logoutBtn").classList.add("hidden");
}

function showApp(){
  $("loginBox").classList.add("hidden");
  $("app").classList.remove("hidden");
  $("userBadge").classList.remove("hidden");
  $("refreshBtn").classList.remove("hidden");
  $("logoutBtn").classList.remove("hidden");
}

function logout(){
  token = "";
  state = null;
  localStorage.removeItem("tw_token");
  showLogin();
}

function isAdmin(){
  return state && state.user && state.user.role === "admin";
}

function roleLabel(role){
  return role === "admin" ? "管理员" : "玩家";
}

function groupValue(){
  return $("groupFilter").value || "__all__";
}

function queryValue(){
  return $("searchBox").value.trim().toLowerCase();
}

function groups(){
  const values = new Set();
  for(const w of state.worlds || []) values.add(String(w.group_id || ""));
  for(const c of state.characters || []) values.add(String(c.group_id || ""));
  for(const e of state.events || []) values.add(String(e.group_id || ""));
  for(const s of state.shop || []) values.add(String(s.group_id || ""));
  for(const n of state.npcs || []) values.add(String(n.group_id || ""));
  for(const l of state.locations || []) values.add(String(l.group_id || ""));
  return Array.from(values).filter(Boolean).sort();
}

function matchesGroup(row){
  const selected = groupValue();
  return selected === "__all__" || String(row.group_id || "") === selected;
}

function matchesQuery(row, fields){
  const q = queryValue();
  if(!q) return true;
  return fields.some(key => String(row[key] ?? "").toLowerCase().includes(q));
}

function filtered(list, fields){
  return (list || []).filter(row => matchesGroup(row) && matchesQuery(row, fields));
}

function syncGroupControls(){
  const current = $("groupFilter").value || "__all__";
  const options = ['<option value="__all__">全部群</option>']
    .concat(groups().map(id => `<option value="${esc(id)}">${esc(id)}</option>`));
  $("groupFilter").innerHTML = options.join("");
  $("groupFilter").value = groups().includes(current) ? current : "__all__";
  const selected = $("groupFilter").value === "__all__" ? groups()[0] : $("groupFilter").value;
  for(const id of ["charGroup","eventGroup","shopGroup"]){
    if($(id) && !$(id).value && selected) $(id).value = selected;
  }
}

function render(){
  if(!state) return;
  syncGroupControls();
  $("userBadge").textContent = `${state.user.username} / ${roleLabel(state.user.role)}`;
  document.querySelectorAll(".adminOnly").forEach(el => {
    el.style.display = isAdmin() ? "" : "none";
  });
  if(!isAdmin() && activeTab === "events") activeTab = "overview";
  renderTabs();
  renderOverview();
  renderCharacters();
  renderEvents();
  renderShop();
  renderMap();
  renderNpcs();
  renderHistory();
  renderWorldbook();
  renderProviders();
}

function renderTabs(){
  document.querySelectorAll(".tab").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.tab === activeTab);
  });
  document.querySelectorAll(".page").forEach(page => page.classList.add("hidden"));
  const target = $("tab-" + activeTab);
  if(target) target.classList.remove("hidden");

  $("countOverview").textContent = String((state.worlds || []).length);
  $("countCharacters").textContent = String((state.characters || []).length);
  $("countEvents").textContent = String((state.events || []).filter(e => Number(e.trigger_next) === 1).length);
  $("countShop").textContent = String((state.shop || []).length);
  $("countMap").textContent = String((state.locations || []).length);
  $("countNpcs").textContent = String((state.npcs || []).length);
  $("countHistory").textContent = String((state.history || []).length);
  $("countWorldbook").textContent = state.worldbook && state.worldbook.exists ? "已接入" : "未找到";
}

function renderOverview(){
  const worlds = filtered(state.worlds, ["group_id","name"]);
  const chars = filtered(state.characters, ["group_id","qq_id","game_name","identity","faction","ability"]);
  const events = filtered(state.events, ["group_id","title","description"]);
  const shop = filtered(state.shop, ["group_id","name","description"]);
  const history = filtered(state.history, ["group_id","kind","text"]);
  const npcs = filtered(state.npcs, ["group_id","name","role","faction"]);
  const locations = filtered(state.locations, ["group_id","location_key","name","description","tags"]);
  const pending = chars.filter(c => c.audit_status === "pending").length;
  const queued = events.filter(e => Number(e.trigger_next) === 1).length;
  const activeItems = shop.filter(s => Number(s.is_active) !== 0).length;
  $("overviewSub").textContent = `${roleLabel(state.user.role)}视图，当前筛选后 ${worlds.length} 个世界`;
  $("kpis").innerHTML = [
    metric("世界", worlds.length),
    metric("角色", chars.length),
    metric("待审核", pending),
    metric("下轮事件", queued),
    metric("商品", activeItems),
    metric("地点", locations.length)
  ].join("");
  $("worlds").innerHTML = worlds.length ? worlds.map(worldCard).join("") : empty("暂无世界");
}

function metric(label, value){
  return `<div class="metric"><div class="metric-label">${esc(label)}</div><div class="metric-value">${esc(value)}</div></div>`;
}

function worldCard(w){
  return `<article class="item">
    <div class="item-title"><b>${esc(w.name || "学院都市")}</b>${badge(Number(w.enabled) ? "运行中" : "已停用", Number(w.enabled) ? "good" : "bad")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(w.group_id)}</span>
      <span>轮次</span><span>第 ${esc(w.current_round)} 轮</span>
      <span>行动周期</span><span>${esc(w.cycle_minutes)} 分钟</span>
      <span>事件周期</span><span>${esc(w.event_cycle_minutes)} 分钟</span>
      <span>下次结算</span><span>${esc(fmtTime(w.next_tick_at))}</span>
      <span>下次事件</span><span>${esc(fmtTime(w.next_event_at))}</span>
    </div>
  </article>`;
}

function renderCharacters(){
  const chars = filtered(state.characters, ["group_id","qq_id","game_name","identity","faction","ability","power_level","audit_status"]);
  $("characterSub").textContent = isAdmin() ? `共 ${chars.length} 张角色卡` : `你的角色卡 ${chars.length} 张`;
  $("characters").innerHTML = chars.length ? chars.map(characterCard).join("") : empty("暂无角色");
}

function characterCard(c){
  const status = auditBadge(c.audit_status);
  return `<article class="item">
    <div class="item-title"><b>${esc(c.game_name || c.qq_id)}</b>${status}</div>
    <div class="kv">
      <span>群号</span><span>${esc(c.group_id)}</span>
      <span>QQ</span><span>${esc(c.qq_id)}</span>
      <span>身份</span><span>${esc(c.identity || "-")}</span>
      <span>阵营</span><span>${esc(c.faction || "-")}</span>
      <span>能力</span><span>${esc(c.ability || "-")}</span>
      <span>战斗力</span><span>${esc(c.power_level || "Level 0")}</span>
      <span>位置</span><span>${esc(c.location_key || "-")}</span>
      <span>货币</span><span>${esc(c.money)} 学都币</span>
    </div>
    <div class="divider"></div>
    ${meter("生命", c.hp)}
    ${meter("精力", c.energy)}
    ${meter("水分", c.water)}
    ${meter("饱食", c.satiety)}
    ${meter("心情", c.mood)}
    ${isAdmin() ? `<div class="actions"><button class="secondary" type="button" onclick="fillCharacter(${Number(c.id)})">编辑</button></div>` : ""}
  </article>`;
}

function auditBadge(status){
  if(status === "approved") return badge("已通过", "good");
  if(status === "rejected") return badge("已拒绝", "bad");
  return badge("待审核", "warn");
}

function meter(label, value){
  const n = Math.max(0, Math.min(100, Number(value) || 0));
  const tone = n <= 25 ? "bad" : n <= 55 ? "warn" : "good";
  return `<div class="muted">${esc(label)} ${n}/100</div><div class="progress ${tone}"><span style="width:${n}%"></span></div>`;
}

function fillCharacter(id){
  const c = (state.characters || []).find(item => Number(item.id) === Number(id));
  if(!c) return;
  $("charGroup").value = c.group_id || "";
  $("charQq").value = c.qq_id || "";
  $("charName").value = c.game_name || "";
  $("charPassword").value = "";
  $("charAudit").value = c.audit_status || "pending";
  $("charLoc").value = c.location_key || "school_gate";
  $("charPower").value = c.power_level || "Level 0";
  $("charFaction").value = c.faction || "";
  $("charIdentity").value = c.identity || "";
  $("charAbility").value = c.ability || "";
  $("charHp").value = c.hp ?? 100;
  $("charEnergy").value = c.energy ?? 100;
  $("charWater").value = c.water ?? 80;
  $("charSatiety").value = c.satiety ?? 80;
  $("charMood").value = c.mood ?? 70;
  $("charMoney").value = c.money ?? "";
  activeTab = "characters";
  renderTabs();
  window.scrollTo({top:0, behavior:"smooth"});
}

function clearCharacterForm(){
  for(const id of ["charQq","charName","charPassword","charFaction","charIdentity","charAbility","charMoney"]){
    $(id).value = "";
  }
  $("charAudit").value = "approved";
  $("charLoc").value = "school_gate";
  $("charPower").value = "Level 0";
  $("charHp").value = 100;
  $("charEnergy").value = 100;
  $("charWater").value = 80;
  $("charSatiety").value = 80;
  $("charMood").value = 70;
}

async function saveCharacter(){
  const payload = {
    group_id:$("charGroup").value.trim(),
    qq_id:$("charQq").value.trim(),
    game_name:$("charName").value.trim(),
    password:$("charPassword").value,
    identity:$("charIdentity").value,
    faction:$("charFaction").value,
    ability:$("charAbility").value,
    power_level:$("charPower").value,
    audit_status:$("charAudit").value,
    location_key:$("charLoc").value.trim() || "school_gate",
    hp:Number($("charHp").value),
    energy:Number($("charEnergy").value),
    water:Number($("charWater").value),
    satiety:Number($("charSatiety").value),
    mood:Number($("charMood").value)
  };
  if($("charMoney").value !== "") payload.money = Number($("charMoney").value);
  await api("/api/admin/character", {method:"POST", body:JSON.stringify(payload)});
  await load();
  showToast("角色已保存");
}

function renderEvents(){
  const events = filtered(state.events, ["group_id","title","description","used_at"]);
  $("events").innerHTML = events.length ? events.map(eventCard).join("") : empty("暂无预设事件");
}

function eventCard(e){
  const queued = Number(e.trigger_next) === 1;
  return `<article class="item">
    <div class="item-title"><b>${esc(e.title)}</b>${badge(queued ? "下轮触发" : "待命", queued ? "warn" : "blue")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(e.group_id)}</span>
      <span>描述</span><span>${esc(e.description || "-")}</span>
      <span>效果</span><span>${esc(effectText(e.effect_json))}</span>
      <span>使用时间</span><span>${esc(e.used_at ? fmtTime(e.used_at) : "-")}</span>
      <span>更新</span><span>${esc(fmtTime(e.updated_at))}</span>
    </div>
    <div class="actions"><button type="button" onclick="triggerEvent(${Number(e.id)})">加入下一轮</button></div>
  </article>`;
}

async function saveEvent(next){
  let effect = {};
  try{ effect = JSON.parse($("eventEffect").value || "{}"); }
  catch{ showToast("事件效果 JSON 格式错误", "error"); return; }
  await api("/api/admin/event", {
    method:"POST",
    body:JSON.stringify({
      group_id:$("eventGroup").value.trim(),
      title:$("eventTitle").value.trim(),
      description:$("eventDesc").value,
      effect,
      trigger_next:next
    })
  });
  $("eventTitle").value = "";
  $("eventDesc").value = "";
  $("eventEffect").value = "{}";
  await load();
  showToast(next ? "事件已加入下一轮" : "事件已保存");
}

async function triggerEvent(id){
  await api("/api/admin/event/trigger", {method:"POST", body:JSON.stringify({id})});
  await load();
  showToast("事件已加入下一轮");
}

function renderShop(){
  const items = filtered(state.shop, ["group_id","name","description","effect_json"]);
  $("shopSub").textContent = `当前可见 ${items.length} 个商品`;
  $("shop").innerHTML = items.length ? items.map(shopCard).join("") : empty("暂无商品");
}

function shopCard(s){
  const active = Number(s.is_active) !== 0;
  return `<article class="item">
    <div class="item-title"><b>${esc(s.name)}</b>${badge(active ? "上架" : "下架", active ? "good" : "bad")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(s.group_id)}</span>
      <span>价格</span><span>${esc(s.price)} 学都币</span>
      <span>库存</span><span>${esc(stockText(s.stock))}</span>
      <span>描述</span><span>${esc(s.description || "-")}</span>
      <span>效果</span><span>${esc(effectText(s.effect_json))}</span>
    </div>
    ${isAdmin() ? `<div class="actions"><button class="secondary" type="button" onclick="fillShop(${Number(s.id)})">编辑</button></div>` : ""}
  </article>`;
}

function fillShop(id){
  const s = (state.shop || []).find(item => Number(item.id) === Number(id));
  if(!s) return;
  $("shopGroup").value = s.group_id || "";
  $("shopName").value = s.name || "";
  $("shopPrice").value = s.price ?? 0;
  $("shopStock").value = s.stock ?? -1;
  $("shopActive").value = Number(s.is_active) === 0 ? "0" : "1";
  $("shopDesc").value = s.description || "";
  $("shopEffect").value = normalizeJson(s.effect_json);
  activeTab = "shop";
  renderTabs();
  window.scrollTo({top:0, behavior:"smooth"});
}

function clearShopForm(){
  $("shopName").value = "";
  $("shopPrice").value = 10;
  $("shopStock").value = -1;
  $("shopActive").value = "1";
  $("shopDesc").value = "";
  $("shopEffect").value = '{"water":20}';
}

async function saveShop(){
  let effect = {};
  try{ effect = JSON.parse($("shopEffect").value || "{}"); }
  catch{ showToast("商品效果 JSON 格式错误", "error"); return; }
  await api("/api/admin/shop", {
    method:"POST",
    body:JSON.stringify({
      group_id:$("shopGroup").value.trim(),
      name:$("shopName").value.trim(),
      description:$("shopDesc").value,
      price:Number($("shopPrice").value),
      stock:Number($("shopStock").value),
      is_active:$("shopActive").value === "1",
      effect
    })
  });
  await load();
  showToast("商品已保存");
}

function renderNpcs(){
  const npcs = filtered(state.npcs, ["group_id","npc_key","name","role","faction","location_key","disposition"]);
  $("npcSub").textContent = `当前可见 ${npcs.length} 个 NPC`;
  $("npcs").innerHTML = npcs.length ? npcs.map(npcCard).join("") : empty("暂无 NPC");
}

function renderMap(){
  const locations = filtered(state.locations, ["group_id","location_key","name","description","tags"]);
  $("mapSub").textContent = `当前可见 ${locations.length} 个地点，按路线约束角色移动`;
  $("mapLocations").innerHTML = locations.length ? locations.map(locationCard).join("") : empty("暂无地图地点");
}

function locationCard(loc){
  const tags = parseTags(loc.tags);
  const exits = (state.edges || [])
    .filter(edge => String(edge.group_id || "") === String(loc.group_id || "") && edge.from_location_key === loc.location_key)
    .map(edge => locationName(loc.group_id, edge.to_location_key));
  return `<article class="item">
    <div class="item-title"><b>${esc(loc.name || loc.location_key)}</b>${badge(loc.location_key || "-", "blue")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(loc.group_id)}</span>
      <span>标签</span><span>${esc(tags.length ? tags.join("、") : "-")}</span>
      <span>描述</span><span>${esc(loc.description || "-")}</span>
      <span>可前往</span><span>${esc(exits.length ? exits.join("、") : "无")}</span>
    </div>
  </article>`;
}

function locationName(groupId, key){
  const loc = (state.locations || []).find(item => String(item.group_id || "") === String(groupId || "") && item.location_key === key);
  return loc ? loc.name : key;
}

function parseTags(raw){
  try{
    const parsed = typeof raw === "string" ? JSON.parse(raw || "[]") : raw;
    return Array.isArray(parsed) ? parsed.map(String) : [];
  }catch{
    return [];
  }
}

function npcCard(n){
  return `<article class="item">
    <div class="item-title"><b>${esc(n.name)}</b>${badge(n.disposition || "中立", "blue")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(n.group_id)}</span>
      <span>编号</span><span>${esc(n.npc_key || "-")}</span>
      <span>身份</span><span>${esc(n.role || "-")}</span>
      <span>阵营</span><span>${esc(n.faction || "-")}</span>
      <span>位置</span><span>${esc(n.location_key || "-")}</span>
    </div>
  </article>`;
}

function renderHistory(){
  const rows = filtered(state.history, ["group_id","visibility","kind","text","created_at"]);
  $("historySub").textContent = `当前可见 ${rows.length} 条记录`;
  $("history").innerHTML = rows.length ? rows.map(historyCard).join("") : empty("暂无历史");
}

function historyCard(h){
  return `<article class="item">
    <div class="item-title"><b>${esc(h.kind || "history")}</b>${badge(h.visibility === "private" ? "私聊" : "公开", h.visibility === "private" ? "warn" : "good")}</div>
    <div class="kv">
      <span>群号</span><span>${esc(h.group_id)}</span>
      <span>轮次</span><span>${esc(h.round_no || 0)}</span>
      <span>时间</span><span>${esc(fmtTime(h.created_at))}</span>
    </div>
    <div class="divider"></div>
    <div class="history-text">${esc(h.text || "")}</div>
  </article>`;
}

function renderWorldbook(){
  const wb = state.worldbook || {};
  const enabled = !!wb.enabled;
  const exists = !!wb.exists;
  $("worldbookInfo").innerHTML = [
    infoBox("启用状态", enabled ? "已启用" : "已关闭", enabled ? "good" : "bad"),
    infoBox("文件状态", exists ? "已找到" : "未找到", exists ? "good" : "bad"),
    infoBox("文件大小", formatBytes(wb.size_bytes || 0), "blue"),
    infoBox("全文字符", wb.total_chars || 0, "blue"),
    infoBox("注入上限", `${wb.prompt_chars || 0} 字符`, "warn"),
    infoBox("配置路径", wb.configured_path || "-", "blue")
  ].join("");
  const preview = wb.preview || wb.error || "暂无预览";
  $("worldbookPreview").textContent = preview;
}

function renderProviders(){
  const p = state.providers || {};
  $("providerInfo").innerHTML = [
    providerCard("主模型", "建议 Claude 4.6o，负责默认高质量任务", p.main_provider_id, p.resolved_main_provider_id),
    providerCard("剧情模型", "每小时结算的公共公告和私聊润色优先使用", p.story_provider_id, p.resolved_story_provider_id),
    providerCard("快速模型", "预留给反作弊、摘要、轻量判定等低延迟任务", p.fast_provider_id, p.resolved_fast_provider_id),
    providerCard("旧默认", "兼容旧配置，专用 provider 未设置时参与回退", p.default_provider_id, p.default_provider_id)
  ].join("");
}

function providerCard(title, desc, configured, resolved){
  const isConfigured = !!configured;
  return `<article class="item">
    <div class="item-title"><b>${esc(title)}</b>${badge(isConfigured ? "已指定" : "走回退", isConfigured ? "good" : "warn")}</div>
    <div class="kv">
      <span>说明</span><span>${esc(desc)}</span>
      <span>配置值</span><span>${esc(configured || "-")}</span>
      <span>实际使用</span><span>${esc(resolved || "-")}</span>
    </div>
  </article>`;
}

function infoBox(label, value, tone){
  return `<article class="item"><div class="item-title"><b>${esc(label)}</b>${badge(String(value), tone)}</div></article>`;
}

function badge(text, tone="blue"){
  return `<span class="badge ${esc(tone)}">${esc(text)}</span>`;
}

function empty(text){
  return `<div class="empty">${esc(text)}</div>`;
}

function fmtTime(value){
  if(!value) return "-";
  const date = new Date(value);
  if(Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("zh-CN", {hour12:false});
}

function stockText(value){
  const n = Number(value);
  return n < 0 ? "不限" : String(n);
}

function effectText(raw){
  if(!raw) return "{}";
  try{
    const parsed = typeof raw === "string" ? JSON.parse(raw) : raw;
    return JSON.stringify(parsed);
  }catch{
    return String(raw);
  }
}

function normalizeJson(raw){
  try{
    const parsed = typeof raw === "string" ? JSON.parse(raw || "{}") : raw;
    return JSON.stringify(parsed);
  }catch{
    return String(raw || "{}");
  }
}

function formatBytes(bytes){
  const n = Number(bytes) || 0;
  if(n < 1024) return `${n} B`;
  if(n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

async function changePassword(){
  const old_password = $("oldPass").value;
  const new_password = $("newPass").value;
  const result = await api("/api/change-password", {
    method:"POST",
    body:JSON.stringify({old_password, new_password})
  });
  if(!result.ok){
    showToast(result.message || "修改失败", "error");
    return;
  }
  showToast("密码已修改，请重新登录");
  setTimeout(logout, 900);
}

function bindEvents(){
  $("loginBtn").addEventListener("click", () => login().catch(err => showToast(err.message || "登录失败", "error")));
  $("loginPass").addEventListener("keydown", event => {
    if(event.key === "Enter") login().catch(err => showToast(err.message || "登录失败", "error"));
  });
  $("refreshBtn").addEventListener("click", () => load().then(() => showToast("已刷新")));
  $("logoutBtn").addEventListener("click", logout);
  $("groupFilter").addEventListener("change", render);
  $("searchBox").addEventListener("input", render);
  document.querySelectorAll(".tab").forEach(btn => {
    btn.addEventListener("click", () => {
      activeTab = btn.dataset.tab || "overview";
      renderTabs();
    });
  });
  $("saveCharacterBtn").addEventListener("click", () => saveCharacter().catch(err => showToast(err.message || "保存失败", "error")));
  $("clearCharFormBtn").addEventListener("click", clearCharacterForm);
  $("saveEventBtn").addEventListener("click", () => saveEvent(false).catch(err => showToast(err.message || "保存失败", "error")));
  $("saveEventNextBtn").addEventListener("click", () => saveEvent(true).catch(err => showToast(err.message || "保存失败", "error")));
  $("saveShopBtn").addEventListener("click", () => saveShop().catch(err => showToast(err.message || "保存失败", "error")));
  $("clearShopFormBtn").addEventListener("click", clearShopForm);
  $("changePasswordBtn").addEventListener("click", () => changePassword().catch(err => showToast(err.message || "修改失败", "error")));
}

bindEvents();
load();
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
        await to_thread(self._start_sync)

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
                        token = service.db.create_session(
                            str(body.get("username") or ""),
                            str(body.get("password") or ""),
                        )
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

            def _headers(self, content_type: str, length: int) -> None:
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("X-Frame-Options", "DENY")

            def _send_html(self, text: str) -> None:
                data = text.encode("utf-8")
                self.send_response(200)
                self._headers("text/html; charset=utf-8", len(data))
                self.end_headers()
                self.wfile.write(data)

            def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
                data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                self.send_response(int(status))
                self._headers("application/json; charset=utf-8", len(data))
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
        await to_thread(server.shutdown)
        await to_thread(server.server_close)
        logger.info("[TextWorldWeb] stopped")
