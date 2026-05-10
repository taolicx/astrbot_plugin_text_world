import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outputDir = path.join(root, "docs", "map-guide");
const htmlPath = path.join(outputDir, "academy-city-art-map.html");

const overviewBg = "assets/academy_city_background_art.png";
const innerBg = "assets/academy_city_district7_background_art.png";

const districts = [
  ["01", "第一学区", "司法行政区", 505, 462, "#6b5e9f"],
  ["02", "第二学区", "警备训练区", 670, 572, "#405d87"],
  ["03", "第三学区", "外交展示区", 215, 225, "#24747d"],
  ["04", "第四学区", "餐饮与农业大楼", 604, 1152, "#9a7726"],
  ["05", "第五学区", "大学区", 376, 782, "#2f7661"],
  ["06", "第六学区", "娱乐休闲区", 260, 1128, "#a17925"],
  ["07", "第七学区", "中心学区", 528, 700, "#bd4a3f"],
  ["08", "第八学区", "教师住宿区", 430, 906, "#2f7661"],
  ["09", "第九学区", "工艺美术区", 255, 880, "#8a5b86"],
  ["10", "第十学区", "墓地与少年院", 150, 1270, "#725444"],
  ["11", "第十一学区", "陆路物流口", 192, 1380, "#24747d"],
  ["12", "第十二学区", "宗教与神学研究区", 392, 1110, "#6d6092"],
  ["13", "第十三学区", "幼小教育区", 304, 638, "#2f7661"],
  ["14", "第十四学区", "留学生区", 165, 520, "#24747d"],
  ["15", "第十五学区", "商业与媒体中心", 300, 255, "#ab6128"],
  ["16", "第十六学区", "学生打工区", 610, 915, "#9a7726"],
  ["17", "第十七学区", "工业制造区", 835, 382, "#676f7a"],
  ["18", "第十八学区", "能力开发名校区", 686, 716, "#2f7661"],
  ["19", "第十九学区", "再开发失败区", 785, 648, "#725444"],
  ["20", "第二十学区", "运动工学区", 402, 435, "#3d7774"],
  ["21", "第二十一学区", "水源与山岳区", 704, 188, "#4f7d42"],
  ["22", "第二十二学区", "地下街区", 894, 525, "#5c6475"],
  ["23", "第二十三学区", "航空宇宙区", 815, 1032, "#24747d"],
];

const districtRoutes = [
  ["01", "02"], ["01", "03"], ["01", "07"], ["01", "12"],
  ["02", "07"], ["02", "17"],
  ["03", "11"], ["03", "14"], ["03", "23"],
  ["04", "05"], ["04", "15"], ["04", "16"],
  ["05", "06"], ["05", "18"],
  ["06", "07"], ["06", "20"],
  ["07", "08"], ["07", "15"], ["07", "18"], ["07", "22"], ["07", "23"],
  ["08", "09"], ["08", "13"],
  ["09", "10"], ["09", "20"],
  ["10", "11"], ["10", "19"],
  ["11", "17"], ["11", "23"],
  ["12", "13"], ["12", "14"],
  ["13", "14"],
  ["14", "15"],
  ["15", "16"],
  ["16", "17"],
  ["17", "19"],
  ["18", "21"],
  ["19", "20"],
  ["20", "21"],
  ["21", "22"],
  ["22", "23"],
];

const innerLocations = [
  ["A", "第七学区校门口", "校门口", 220, 186, "#bd4a3f"],
  ["B", "第七学区主干道", "主干道", 506, 330, "#4f6378"],
  ["C", "第七学区某高中", "某高中", 275, 525, "#2f7661"],
  ["D", "书库终端图书馆", "图书馆", 500, 620, "#5d6593"],
  ["E", "能力开发实验楼", "实验楼", 735, 545, "#6f5c9d"],
  ["F", "第七学区学生宿舍", "宿舍", 258, 825, "#9a7726"],
  ["G", "学生食堂", "食堂", 510, 842, "#9a7726"],
  ["H", "第十五学区商业街", "商业街", 742, 1032, "#ab6128"],
  ["I", "第七学区中心广场", "广场", 516, 1184, "#bd4a3f"],
  ["J", "冥土追魂医院", "医院", 778, 170, "#3d7f7b"],
  ["K", "学舍之园", "封闭校区", 155, 362, "#8a5b86"],
  ["L", "常盘台中学", "名校", 182, 460, "#6d6092"],
  ["M", "栅川中学", "中学", 350, 730, "#2f7661"],
  ["N", "没有窗户的大楼", "禁区", 930, 300, "#725444"],
  ["02", "第二学区入口", "外部", 916, 500, "#405d87"],
  ["04", "第四学区入口", "外部", 510, 1450, "#9a7726"],
  ["07", "第七学区外环", "外环", 900, 1330, "#bd4a3f"],
  ["15", "第十五学区入口", "外部", 890, 1010, "#ab6128"],
  ["18", "第十八学区入口", "外部", 918, 640, "#2f7661"],
];

const innerRoutes = [
  ["A", "B"], ["A", "C"], ["A", "F"], ["A", "07"],
  ["B", "I"], ["B", "J"], ["B", "15"], ["B", "07"],
  ["C", "D"], ["C", "E"], ["C", "I"],
  ["D", "I"], ["D", "18"],
  ["E", "J"], ["E", "02"], ["E", "18"],
  ["F", "G"], ["F", "I"],
  ["G", "H"], ["G", "04"],
  ["H", "I"], ["H", "15"], ["H", "04"],
  ["I", "07"],
  ["J", "07"],
  ["A", "K"], ["K", "L"], ["L", "M"], ["M", "D"],
  ["B", "N"], ["N", "02"], ["N", "07"],
];

function byId(items) {
  return Object.fromEntries(items.map((item) => [item[0], item]));
}

function pinSvg(items, routes, { externalDashed = false, showRoutes = true } = {}) {
  const lookup = byId(items);
  const lines = showRoutes ? routes.map(([a, b]) => {
    const from = lookup[a];
    const to = lookup[b];
    const isCore = a === "07" || b === "07" || a === "I" || b === "I";
    const isExternal = externalDashed && (a.length === 2 || b.length === 2);
    return `<line class="${isCore ? "route core-route" : "route"} ${isExternal ? "dash-route" : ""}" x1="${from[3]}" y1="${from[4]}" x2="${to[3]}" y2="${to[4]}"></line>`;
  }).join("") : "";
  const pins = items.map(([id, name, role, x, y, color]) => {
    const isCentral = id === "07" || id === "I";
    const radius = isCentral ? 31 : 25;
    return `
      <g class="pin ${isCentral ? "central" : ""}" transform="translate(${x} ${y})">
        <circle class="halo" r="${radius + 12}" fill="${color}"></circle>
        <circle class="dot" r="${radius}" fill="${color}"></circle>
        <text y="${id.length === 1 ? 9 : 8}">${id}</text>
      </g>`;
  }).join("");
  return `${lines}${pins}`;
}

function districtLegend() {
  return districts.map(([id, name, role, x, y, color]) => `
    <div class="legend-row">
      <span style="--c:${color}">${id}</span>
      <b>${name}</b>
      <em>${role}</em>
    </div>`).join("");
}

function innerLegend() {
  return innerLocations.map(([id, name, role, x, y, color]) => `
    <div class="legend-row">
      <span style="--c:${color}">${id}</span>
      <b>${name}</b>
      <em>${role}</em>
    </div>`).join("");
}

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学园都市美术详细版地图</title>
  <style>
    * { box-sizing: border-box; }
    body {
      margin: 0;
      padding: 44px;
      font-family: "Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", Arial, sans-serif;
      color: #203036;
      background:
        radial-gradient(circle at 18% 10%, rgba(91, 135, 150, .22), transparent 32%),
        linear-gradient(135deg, #eef3ea, #f8efe2);
    }
    .sheet {
      width: 1760px;
      min-height: 2360px;
      margin: 0 auto 56px;
      padding: 52px;
      border-radius: 34px;
      background: rgba(255, 252, 246, .94);
      box-shadow: 0 28px 86px rgba(24, 38, 45, .22);
      border: 1px solid rgba(80, 92, 96, .15);
    }
    .header {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 30px;
      align-items: end;
      margin-bottom: 30px;
      padding-bottom: 24px;
      border-bottom: 2px solid rgba(70, 83, 86, .17);
    }
    h1 {
      margin: 0;
      font-size: 58px;
      line-height: 1.08;
      font-weight: 900;
      letter-spacing: 0;
    }
    .subtitle {
      max-width: 1120px;
      margin: 14px 0 0;
      color: #657276;
      font-size: 23px;
      line-height: 1.55;
    }
    .badge {
      min-width: 258px;
      padding: 18px 24px;
      border-radius: 18px;
      border: 3px solid rgba(181, 77, 64, .76);
      color: #a4473e;
      text-align: center;
      font-size: 27px;
      font-weight: 900;
      transform: rotate(1.6deg);
    }
    .layout {
      display: grid;
      grid-template-columns: 1080px 1fr;
      gap: 32px;
      align-items: start;
    }
    .art-frame {
      position: relative;
      width: 1080px;
      height: 1620px;
      border-radius: 28px;
      overflow: hidden;
      background: #dfe8e2;
      border: 1px solid rgba(73, 82, 81, .24);
      box-shadow: inset 0 0 0 8px rgba(255, 255, 255, .34);
    }
    .art-frame img {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      object-fit: cover;
      filter: saturate(1.03) contrast(1.02);
    }
    .art-frame::after {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(20,35,42,.12)),
        radial-gradient(circle at 50% 50%, transparent 42%, rgba(255, 249, 235, .18));
      pointer-events: none;
    }
    .overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 2;
    }
    .route {
      stroke: rgba(38, 59, 64, .66);
      stroke-width: 8;
      stroke-linecap: round;
      filter: drop-shadow(0 2px 2px rgba(255,255,255,.72));
    }
    .core-route {
      stroke: rgba(190, 76, 62, .82);
      stroke-width: 11;
    }
    .dash-route {
      stroke-dasharray: 18 14;
      opacity: .72;
    }
    .pin .halo {
      opacity: .2;
    }
    .pin .dot {
      stroke: rgba(255, 255, 255, .92);
      stroke-width: 5;
      filter: drop-shadow(0 10px 12px rgba(14, 26, 32, .36));
    }
    .pin text {
      fill: #fff;
      text-anchor: middle;
      font-size: 24px;
      font-weight: 900;
      paint-order: stroke;
      stroke: rgba(0,0,0,.14);
      stroke-width: 2px;
      letter-spacing: 0;
    }
    .pin.central text { font-size: 27px; }
    .legend {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .legend.single {
      grid-template-columns: 1fr;
    }
    .legend-row {
      display: grid;
      grid-template-columns: 52px 1fr;
      grid-template-rows: auto auto;
      column-gap: 12px;
      min-height: 76px;
      padding: 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, .76);
      border: 1px solid rgba(79, 88, 88, .14);
    }
    .legend-row span {
      grid-row: 1 / span 2;
      width: 48px;
      height: 48px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      color: #fff;
      background: var(--c);
      font-size: 19px;
      font-weight: 900;
      box-shadow: 0 9px 18px rgba(23, 38, 46, .18);
    }
    .legend-row b {
      align-self: end;
      font-size: 20px;
      line-height: 1.15;
    }
    .legend-row em {
      margin-top: 4px;
      color: #697478;
      font-style: normal;
      font-weight: 700;
      font-size: 15px;
      line-height: 1.3;
    }
    .notes {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      margin-top: 30px;
    }
    .note {
      padding: 20px 22px;
      border-radius: 14px;
      background: rgba(255, 255, 255, .72);
      border-left: 7px solid #b84f43;
      font-size: 18px;
      line-height: 1.45;
      color: #607074;
    }
    .note b {
      display: block;
      margin-bottom: 8px;
      color: #213137;
      font-size: 24px;
    }
    .footer {
      margin-top: 28px;
      padding-top: 18px;
      display: flex;
      justify-content: space-between;
      gap: 24px;
      border-top: 1px solid rgba(76, 84, 84, .18);
      color: #68777a;
      font-size: 17px;
      line-height: 1.45;
    }
  </style>
</head>
<body>
  <section class="sheet" id="art-overview">
    <div class="header">
      <div>
        <h1>学园都市地图｜美术详细版</h1>
        <p class="subtitle">保留上一版判定地图，新增更具体的城市美术底图。圆点编号与右侧说明对应，路线仍按插件默认相邻地点绘制。</p>
      </div>
      <div class="badge">详细展示版</div>
    </div>
    <div class="layout">
      <div class="art-frame">
        <img src="${overviewBg}" alt="" />
        <svg class="overlay" viewBox="0 0 1024 1536" aria-label="学园都市详细美术总览地图">
          ${pinSvg(districts, districtRoutes, { showRoutes: false })}
        </svg>
      </div>
      <div class="legend">${districtLegend()}</div>
    </div>
    <div class="notes">
      <div class="note"><b>怎么用</b>玩家看图选地点，实际移动路线请配合上一版清晰路线图判定。</div>
      <div class="note"><b>更具体</b>底图加入了机场、山岳水源、工业设施、校园、商业街、道路和单轨。</div>
      <div class="note"><b>不覆盖旧版</b>上一版清晰判定图继续保留，这张用于展示和发给玩家。</div>
    </div>
    <div class="footer">
      <span>AI 底图生成，程序叠加准确中文标注；路线见清晰判定版。</span>
      <span>文件：学园都市地图_美术详细版_总览.png</span>
    </div>
  </section>

  <section class="sheet" id="art-inner">
    <div class="header">
      <div>
        <h1>第七学区地图｜美术详细版</h1>
        <p class="subtitle">第七学区作为默认主舞台，新增校园、医院、实验楼、商业街和中心广场的具体鸟瞰画面。</p>
      </div>
      <div class="badge">主舞台展示</div>
    </div>
    <div class="layout">
      <div class="art-frame">
        <img src="${innerBg}" alt="" />
        <svg class="overlay" viewBox="0 0 1024 1536" aria-label="第七学区详细美术地图">
          ${pinSvg(innerLocations, innerRoutes, { externalDashed: true })}
        </svg>
      </div>
      <div class="legend single">${innerLegend()}</div>
    </div>
    <div class="notes">
      <div class="note"><b>实线</b>表示第七学区内部移动路线，适合玩家提交小时行动。</div>
      <div class="note"><b>虚线</b>表示接入外部学区的方向，例如第二、第四、第十五、第十八学区。</div>
      <div class="note"><b>剧情点</b>图书馆、实验楼、医院、中心广场适合投放传闻、检查和公共事件。</div>
    </div>
    <div class="footer">
      <span>底图无文字，所有中文标签均由程序叠加，方便后续维护。</span>
      <span>文件：学园都市地图_美术详细版_第七学区.png</span>
    </div>
  </section>
</body>
</html>`;

fs.writeFileSync(htmlPath, html, "utf8");
console.log(htmlPath);
