import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outputDir = path.join(root, "docs", "map-guide");
const htmlPath = path.join(outputDir, "academy-city-map.html");

fs.mkdirSync(outputDir, { recursive: true });

const districts = [
  ["01", "第一学区", "司法行政区", "司法、行政、统括理事会相关机关集中，权限审查严格。", 420, 285, "admin"],
  ["02", "第二学区", "警备训练区", "警备员与风纪委员训练机构、新武器开发设施所在地。", 560, 430, "security"],
  ["03", "第三学区", "外交展示区", "对外展示设施、访客住宿和外部交流窗口集中。", 235, 395, "gateway"],
  ["04", "第四学区", "餐饮与农业大楼", "食品店、世界料理和农业大楼密集，日常补给充足。", 745, 905, "life"],
  ["05", "第五学区", "大学区", "大学、高级店铺和学术研究委托常在此流转。", 850, 690, "academy"],
  ["06", "第六学区", "娱乐休闲区", "娱乐设施为主的休闲学区，活动丰富，传闻流动快。", 700, 560, "life"],
  ["07", "第七学区", "中心学区", "故事主舞台。学校、医院、商业街和传闻在这里交汇。", 535, 640, "core"],
  ["08", "第八学区", "教师住宿区", "教师住宅与教育设施集中，治安相对安静。", 460, 805, "academy"],
  ["09", "第九学区", "工艺美术区", "工艺、美术和特殊教育设施集中，适合制作道具。", 380, 950, "craft"],
  ["10", "第十学区", "墓地与少年院", "墓地、少年院和高风险设施并存，都市阴影较重。", 225, 1055, "risk"],
  ["11", "第十一学区", "陆路物流口", "学院都市陆路枢纽口，物流车队与边界检查密集。", 110, 780, "gateway"],
  ["12", "第十二学区", "宗教与神学研究区", "宗教设施与神学研究学校分布，异国氛围浓厚。", 315, 170, "mystery"],
  ["13", "第十三学区", "幼小教育区", "幼儿园与小学为主，儿童能力开发相关传闻不少。", 455, 100, "academy"],
  ["14", "第十四学区", "留学生区", "海外留学生众多，多语种告示和外部文化交错。", 205, 135, "gateway"],
  ["15", "第十五学区", "商业与媒体中心", "最大商业中心，电视台、大众传媒和大型屏幕密集。", 620, 855, "commerce"],
  ["16", "第十六学区", "学生打工区", "学生兼职设施集中，适合打工、跑腿和小额委托。", 785, 1115, "life"],
  ["17", "第十七学区", "工业制造区", "制造工厂和高度机械化设施集中，也有监狱传闻。", 525, 1160, "industry"],
  ["18", "第十八学区", "能力开发名校区", "名校和附属研究机构集中，优等生与研究委托很多。", 985, 520, "academy"],
  ["19", "第十九学区", "再开发失败区", "再开发失败后的荒凉学区，废弃建筑和可疑交易较多。", 340, 1215, "risk"],
  ["20", "第二十学区", "运动工学区", "运动工学学校与都市运动协会本部所在地。", 535, 1035, "sport"],
  ["21", "第二十一学区", "水源与山岳区", "水源、水库、山岳与天文台所在地，自然地貌较多。", 915, 1050, "nature"],
  ["22", "第二十二学区", "地下街区", "面积小但地下高度发达，地下街和垂直轴风力设施复杂。", 800, 805, "underground"],
  ["23", "第二十三学区", "航空宇宙区", "航空、宇宙产业特化学区，拥有学院都市唯一机场。", 115, 560, "gateway"],
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
  ["A", "校门口", "第七学区校门口", "日常入口，公告栏、安保亭、校车站都在附近。", 250, 310, "entry"],
  ["B", "主干道", "第七学区主干道", "连接学校、医院、商业区和中心广场的交通主动脉。", 470, 325, "road"],
  ["C", "某高中", "第七学区某高中", "能力开发课程、补习、社团传闻和学生日常从这里开始。", 285, 520, "school"],
  ["D", "图书馆", "书库终端图书馆", "可查询公开资料，都市传闻常在书架之间流动。", 500, 555, "intel"],
  ["E", "实验楼", "能力开发实验楼", "进行能力测定、AIM观测和课程实验，出入登记严格。", 700, 520, "lab"],
  ["F", "宿舍", "第七学区学生宿舍", "休息、串门、小交易和深夜传闻的常见发生地。", 240, 755, "life"],
  ["G", "食堂", "学生食堂", "补充水分和饱食度的稳定地点，连接第四学区补给。", 480, 790, "life"],
  ["H", "商业街", "第十五学区商业街", "便利店、自动贩卖机、电子产品店和媒体屏幕密集。", 725, 770, "commerce"],
  ["I", "广场", "第七学区中心广场", "偶遇、公开事件、都市传闻最容易聚集的开阔地。", 510, 930, "core"],
  ["J", "医院", "冥土追魂医院", "重伤治疗、健康检查和奇怪医学传闻可能发生。", 760, 335, "hospital"],
  ["K", "学舍之园", "学舍之园", "由多所贵族女校组成的封闭校区，进入需要许可或邀请。", 145, 410, "academy"],
  ["L", "常盘台", "常盘台中学", "学舍之园内的顶级女校，Level 5 相关传闻集中。", 230, 515, "academy"],
  ["M", "栅川", "栅川中学", "适合日常线索、学生传闻和风纪委员支部事件切入。", 350, 665, "school"],
  ["N", "无窗大楼", "没有窗户的大楼", "统括理事会核心禁区，普通角色只能远望或听到流言。", 910, 280, "risk"],
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

const portals = [
  ["02", "第二学区"],
  ["04", "第四学区"],
  ["07", "第七学区外环"],
  ["15", "第十五学区"],
  ["18", "第十八学区"],
];

const districtById = Object.fromEntries(districts.map((district) => [district[0], district]));
const innerById = Object.fromEntries(innerLocations.map((location) => [location[0], location]));

const colors = {
  admin: "#6b5e9f",
  security: "#405d87",
  gateway: "#24747d",
  life: "#8f6d2f",
  academy: "#2f7661",
  core: "#b24a3d",
  craft: "#8a5b86",
  risk: "#725444",
  commerce: "#9a5b2e",
  industry: "#676f7a",
  sport: "#3d7774",
  nature: "#4f7d42",
  underground: "#5c6475",
  mystery: "#6d6092",
  entry: "#b24a3d",
  road: "#4f6378",
  school: "#2f7661",
  intel: "#5d6593",
  lab: "#6f5c9d",
  hospital: "#3d7f7b",
  risk: "#725444",
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function routeKey(a, b) {
  return [a, b].sort().join("-");
}

function routeListForDistricts() {
  const routes = new Map();
  for (const [a, b] of districtRoutes) {
    routes.set(routeKey(a, b), [a, b]);
  }
  return [...routes.values()]
    .map(([a, b]) => `${a} ${districtById[a][1]} ↔ ${b} ${districtById[b][1]}`)
    .join(" / ");
}

function districtLegendCards() {
  return districts
    .map(([id, name, role, desc, x, y, kind]) => `
      <article class="legend-card ${id === "07" ? "is-core" : ""}">
        <div class="legend-num" style="--accent:${colors[kind]}">${id}</div>
        <div>
          <h3>${name}<span>${role}</span></h3>
          <p>${desc}</p>
        </div>
      </article>`)
    .join("");
}

function districtChips() {
  return districts
    .map(([id, name, role, desc, x, y, kind]) => `
      <div class="chip" style="--accent:${colors[kind]}">
        <b>${id}</b><span>${name}</span>
      </div>`)
    .join("");
}

function districtRouteSvg({ showLabels = false } = {}) {
  const lines = districtRoutes
    .map(([a, b]) => {
      const [, , , , x1, y1] = districtById[a];
      const [, , , , x2, y2] = districtById[b];
      const className = a === "07" || b === "07" ? "route route-core" : "route";
      return `<line class="${className}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" />`;
    })
    .join("");

  const labels = showLabels
    ? districtRoutes
        .map(([a, b], index) => {
          const [, , , , x1, y1] = districtById[a];
          const [, , , , x2, y2] = districtById[b];
          const mx = (x1 + x2) / 2;
          const my = (y1 + y2) / 2;
          if (index % 3 !== 0 && a !== "07" && b !== "07") return "";
          return `<text class="route-code" x="${mx}" y="${my}">${a}-${b}</text>`;
        })
        .join("")
    : "";

  const nodes = districts
    .map(([id, name, role, desc, x, y, kind]) => {
      const radius = id === "07" ? 45 : 34;
      return `
        <g class="district-node ${id === "07" ? "core-node" : ""}" transform="translate(${x} ${y})">
          <circle r="${radius + 9}" fill="${colors[kind]}" opacity="0.18"></circle>
          <circle r="${radius}" fill="${colors[kind]}"></circle>
          <text class="node-id" y="8">${id}</text>
        </g>`;
    })
    .join("");

  return `
    <svg class="city-svg" viewBox="0 0 1110 1330" role="img" aria-label="学院都市二十三学区路线地图">
      <defs>
        <filter id="nodeShadow" x="-40%" y="-40%" width="180%" height="180%">
          <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#1f2d3d" flood-opacity="0.22"/>
        </filter>
        <linearGradient id="mapWater" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="#dbece8"/>
          <stop offset="1" stop-color="#edf2e2"/>
        </linearGradient>
      </defs>
      <rect x="35" y="35" width="1040" height="1260" rx="42" fill="url(#mapWater)" opacity="0.72"></rect>
      <path d="M60 380 C180 300 270 275 395 275 C585 275 730 330 860 450 C995 575 1035 775 930 980 C835 1168 650 1280 420 1270 C235 1263 105 1165 85 1008 C64 842 148 735 112 585 C92 500 15 460 60 380Z" fill="#fff8ec" opacity="0.78" stroke="#d4c6ac" stroke-width="3"></path>
      <path d="M805 120 C925 190 1003 278 1050 398" class="terrain-line"></path>
      <path d="M780 1165 C900 1088 970 990 1028 865" class="terrain-line"></path>
      <path d="M130 1190 C220 1235 345 1260 463 1242" class="terrain-line"></path>
      ${lines}
      ${labels}
      ${nodes}
    </svg>`;
}

function districtRouteTable() {
  const rows = districts.map(([id, name]) => {
    const neighbors = districtRoutes
      .filter(([a, b]) => a === id || b === id)
      .map(([a, b]) => (a === id ? b : a))
      .sort((a, b) => Number(a) - Number(b));
    return `
      <tr>
        <th>${id}</th>
        <td>${name}</td>
        <td>${neighbors.map((key) => `${key} ${districtById[key][1]}`).join("、")}</td>
      </tr>`;
  });
  return rows.join("");
}

function innerSvg() {
  const externalPoints = {
    "02": [930, 465],
    "04": [445, 1095],
    "07": [980, 900],
    "15": [910, 745],
    "18": [905, 590],
  };

  const externalNodes = portals
    .map(([id, name]) => {
      const [x, y] = externalPoints[id];
      return `
        <g class="portal-node" transform="translate(${x} ${y})">
          <rect x="-57" y="-26" width="114" height="52" rx="20"></rect>
          <text y="7">${id}</text>
        </g>`;
    })
    .join("");

  const lines = innerRoutes
    .map(([a, b]) => {
      const from = innerById[a] ? [innerById[a][4], innerById[a][5]] : externalPoints[a];
      const to = innerById[b] ? [innerById[b][4], innerById[b][5]] : externalPoints[b];
      return `<line class="${innerById[a] && innerById[b] ? "inner-route" : "inner-route portal-route"}" x1="${from[0]}" y1="${from[1]}" x2="${to[0]}" y2="${to[1]}" />`;
    })
    .join("");

  const nodes = innerLocations
    .map(([id, short, name, desc, x, y, kind]) => `
      <g class="inner-node ${id === "I" ? "inner-core" : ""}" transform="translate(${x} ${y})">
        <circle r="43" fill="${colors[kind]}"></circle>
        <text class="inner-id" y="8">${id}</text>
        <text class="inner-short" y="68">${short}</text>
      </g>`)
    .join("");

  return `
    <svg class="inner-svg" viewBox="0 0 1120 1220" role="img" aria-label="第七学区细节地图">
      <defs>
        <linearGradient id="innerGround" x1="0" x2="1" y1="0" y2="1">
          <stop offset="0" stop-color="#eaf0e8"/>
          <stop offset="1" stop-color="#f6eadc"/>
        </linearGradient>
      </defs>
      <rect x="35" y="45" width="1040" height="1110" rx="44" fill="url(#innerGround)" stroke="#d4c6ac" stroke-width="3"></rect>
      <path d="M120 315 H1010" class="main-road"></path>
      <path d="M500 270 C520 460 510 690 515 970" class="main-road secondary"></path>
      <path d="M215 755 C395 760 574 770 780 765" class="main-road secondary"></path>
      ${lines}
      ${externalNodes}
      ${nodes}
    </svg>`;
}

function innerLegendCards() {
  return innerLocations
    .map(([id, short, name, desc, x, y, kind]) => `
      <article class="legend-card compact">
        <div class="legend-num letter" style="--accent:${colors[kind]}">${id}</div>
        <div>
          <h3>${name}<span>${short}</span></h3>
          <p>${desc}</p>
        </div>
      </article>`)
    .join("");
}

function innerRouteTable() {
  const labels = Object.fromEntries(innerLocations.map(([id, short, name]) => [id, name]));
  for (const [id, name] of portals) labels[id] = name;
  const keys = [...innerLocations.map(([id]) => id), ...portals.map(([id]) => id)];
  const rows = keys.map((id) => {
    const neighbors = innerRoutes
      .filter(([a, b]) => a === id || b === id)
      .map(([a, b]) => (a === id ? b : a));
    return `
      <tr>
        <th>${id}</th>
        <td>${labels[id]}</td>
        <td>${neighbors.map((key) => `${key} ${labels[key]}`).join("、") || "无"}</td>
      </tr>`;
  });
  return rows.join("");
}

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学园都市地图</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #263238;
      --muted: #6c7472;
      --paper: #fbf7ef;
      --panel: #fffdf8;
      --line: #c7bda8;
      --route: #788a92;
      --route-core: #b45a4f;
      --blueprint: #2f5f73;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      padding: 42px;
      font-family: "Microsoft YaHei", "Noto Sans CJK SC", "PingFang SC", Arial, sans-serif;
      color: var(--ink);
      background:
        linear-gradient(120deg, rgba(85, 128, 140, 0.16), rgba(166, 128, 65, 0.12)),
        repeating-linear-gradient(0deg, rgba(40, 76, 87, 0.035) 0, rgba(40, 76, 87, 0.035) 1px, transparent 1px, transparent 18px),
        #eef1e7;
    }

    .sheet {
      width: 1680px;
      min-height: 2300px;
      margin: 0 auto 54px;
      padding: 58px;
      border: 1px solid rgba(77, 82, 80, 0.16);
      border-radius: 30px;
      background:
        linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(255, 250, 241, 0.94)),
        var(--paper);
      box-shadow: 0 30px 90px rgba(29, 44, 52, 0.18);
    }

    .title-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 32px;
      align-items: end;
      padding-bottom: 28px;
      border-bottom: 2px solid rgba(93, 101, 99, 0.22);
    }

    h1 {
      margin: 0;
      font-size: 62px;
      line-height: 1.05;
      font-weight: 900;
      letter-spacing: 0;
    }

    .subtitle {
      margin: 16px 0 0;
      font-size: 24px;
      line-height: 1.55;
      color: var(--muted);
      max-width: 1060px;
    }

    .stamp {
      min-width: 230px;
      padding: 18px 22px;
      border: 3px solid rgba(178, 74, 61, 0.76);
      color: #9c4038;
      text-align: center;
      font-weight: 900;
      font-size: 28px;
      transform: rotate(2deg);
      border-radius: 16px;
      background: rgba(255, 248, 240, 0.68);
    }

    .layout {
      display: grid;
      grid-template-columns: 1110px 1fr;
      gap: 34px;
      margin-top: 34px;
      align-items: start;
    }

    .map-panel {
      border-radius: 24px;
      background:
        radial-gradient(circle at 12% 14%, rgba(255, 255, 255, 0.82), transparent 24%),
        #f8f1e4;
      border: 1px solid rgba(110, 96, 76, 0.2);
      padding: 16px;
    }

    .city-svg,
    .inner-svg {
      display: block;
      width: 100%;
      height: auto;
    }

    .terrain-line {
      fill: none;
      stroke: rgba(81, 123, 120, 0.34);
      stroke-width: 16;
      stroke-linecap: round;
    }

    .route {
      stroke: var(--route);
      stroke-width: 7;
      stroke-linecap: round;
      opacity: 0.72;
    }

    .route-core {
      stroke: var(--route-core);
      stroke-width: 9;
      opacity: 0.86;
    }

    .district-node circle,
    .inner-node circle {
      filter: url(#nodeShadow);
      stroke: rgba(255, 255, 255, 0.78);
      stroke-width: 4;
    }

    .node-id,
    .inner-id {
      fill: #fff;
      text-anchor: middle;
      font-size: 30px;
      font-weight: 900;
      letter-spacing: 0;
    }

    .core-node .node-id {
      font-size: 34px;
    }

    .route-code {
      paint-order: stroke;
      stroke: #fff8ed;
      stroke-width: 8px;
      fill: #53656e;
      text-anchor: middle;
      font-size: 20px;
      font-weight: 800;
    }

    .legend {
      display: grid;
      grid-template-columns: 1fr;
      gap: 14px;
    }

    .legend-card {
      display: grid;
      grid-template-columns: 58px 1fr;
      gap: 14px;
      align-items: start;
      padding: 13px 14px;
      border: 1px solid rgba(89, 93, 88, 0.14);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.62);
    }

    .legend-card.is-core {
      border-color: rgba(178, 74, 61, 0.36);
      background: rgba(255, 244, 237, 0.82);
    }

    .legend-card.compact {
      grid-template-columns: 62px 1fr;
      padding: 15px 16px;
    }

    .legend-num {
      width: 52px;
      height: 52px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      background: var(--accent);
      color: white;
      font-size: 22px;
      line-height: 1;
      font-weight: 900;
      box-shadow: 0 10px 20px rgba(34, 45, 53, 0.18);
    }

    .legend-num.letter {
      font-size: 28px;
    }

    h3 {
      margin: 0;
      font-size: 22px;
      line-height: 1.2;
      letter-spacing: 0;
    }

    h3 span {
      display: block;
      margin-top: 4px;
      color: #786f65;
      font-size: 17px;
      font-weight: 700;
    }

    .legend-card p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 15px;
      line-height: 1.45;
    }

    .note-band {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 18px;
      margin-top: 28px;
    }

    .note {
      min-height: 118px;
      padding: 20px;
      border-left: 7px solid #b45a4f;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.62);
    }

    .note b {
      display: block;
      margin-bottom: 8px;
      font-size: 23px;
    }

    .note span {
      color: var(--muted);
      font-size: 18px;
      line-height: 1.5;
    }

    .chips {
      display: grid;
      grid-template-columns: repeat(8, 1fr);
      gap: 12px;
      margin-top: 32px;
    }

    .chip {
      display: flex;
      align-items: center;
      gap: 9px;
      min-height: 48px;
      padding: 8px 10px;
      border-radius: 10px;
      background: rgba(255, 255, 255, 0.62);
      border: 1px solid rgba(88, 96, 96, 0.16);
      font-size: 16px;
      font-weight: 800;
      white-space: nowrap;
    }

    .chip b {
      width: 30px;
      height: 30px;
      display: grid;
      place-items: center;
      flex: 0 0 auto;
      border-radius: 50%;
      background: var(--accent);
      color: #fff;
      font-size: 14px;
    }

    .wide-layout {
      margin-top: 34px;
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 30px;
      align-items: start;
    }

    .route-card {
      padding: 26px;
      border-radius: 20px;
      background: rgba(255, 255, 255, 0.64);
      border: 1px solid rgba(84, 91, 88, 0.16);
    }

    .route-card h2 {
      margin: 0 0 16px;
      font-size: 34px;
      letter-spacing: 0;
    }

    .route-card p {
      margin: 0;
      color: var(--muted);
      font-size: 20px;
      line-height: 1.55;
    }

    .route-list {
      margin-top: 18px;
      color: #34454b;
      font-size: 18px;
      line-height: 1.8;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      overflow: hidden;
      border-radius: 16px;
      background: rgba(255, 255, 255, 0.72);
      font-size: 17px;
    }

    th,
    td {
      padding: 12px 13px;
      border-bottom: 1px solid rgba(100, 104, 96, 0.14);
      vertical-align: top;
      line-height: 1.45;
    }

    th {
      width: 70px;
      color: #a3473d;
      font-size: 19px;
      text-align: left;
    }

    tr:last-child th,
    tr:last-child td {
      border-bottom: 0;
    }

    .inner-layout {
      display: grid;
      grid-template-columns: 1120px 1fr;
      gap: 32px;
      margin-top: 34px;
      align-items: start;
    }

    .inner-route {
      stroke: #65777f;
      stroke-width: 8;
      stroke-linecap: round;
      opacity: 0.72;
    }

    .portal-route {
      stroke-dasharray: 15 14;
      opacity: 0.54;
    }

    .main-road {
      fill: none;
      stroke: rgba(180, 90, 79, 0.34);
      stroke-width: 42;
      stroke-linecap: round;
    }

    .main-road.secondary {
      stroke: rgba(69, 116, 119, 0.2);
      stroke-width: 34;
    }

    .inner-short {
      fill: #2e383b;
      paint-order: stroke;
      stroke: #fbf7ef;
      stroke-width: 9px;
      text-anchor: middle;
      font-size: 24px;
      font-weight: 900;
      letter-spacing: 0;
    }

    .portal-node rect {
      fill: rgba(255, 255, 255, 0.88);
      stroke: rgba(90, 96, 94, 0.28);
      stroke-width: 3;
    }

    .portal-node text {
      fill: #52616a;
      text-anchor: middle;
      font-size: 25px;
      font-weight: 900;
    }

    .footer {
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid rgba(95, 100, 98, 0.18);
      display: flex;
      justify-content: space-between;
      gap: 20px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.5;
    }

    .small-table table {
      font-size: 16px;
    }
  </style>
</head>
<body>
  <section class="sheet" id="map-overview">
    <div class="title-row">
      <div>
        <h1>学园都市二十三学区总览图</h1>
        <p class="subtitle">供“群文游文字世界”玩家查看的世界地图。地图节点编号对应右侧学区说明，红色路线优先表示与第七学区相关的常用移动方向。</p>
      </div>
      <div class="stamp">玩家版地图</div>
    </div>
    <div class="layout">
      <div class="map-panel">${districtRouteSvg()}</div>
      <div class="legend">${districtLegendCards()}</div>
    </div>
    <div class="note-band">
      <div class="note"><b>移动规则</b><span>每小时行动只能前往当前位置相邻节点，不能跨图瞬移。</span></div>
      <div class="note"><b>剧情触发</b><span>玩家、NPC 或事件在同一地点交汇时，下一轮结算可能产生互动。</span></div>
      <div class="note"><b>默认主舞台</b><span>第七学区是中心区域，内部地点另有细节图。</span></div>
    </div>
    <div class="chips">${districtChips()}</div>
    <div class="footer">
      <span>数据来源：插件内置 DEFAULT_LOCATIONS 路线。</span>
      <span>版本：Academy City Map / 2026-05-08</span>
    </div>
  </section>

  <section class="sheet" id="map-routes">
    <div class="title-row">
      <div>
        <h1>学园都市路线图</h1>
        <p class="subtitle">用于判断角色本轮能否抵达目标地点。玩家行动、NPC移动和公共事件投放，都建议以这张路线图为准。</p>
      </div>
      <div class="stamp">移动判定用</div>
    </div>
    <div class="wide-layout">
      <div class="map-panel">${districtRouteSvg({ showLabels: true })}</div>
      <div class="route-card">
        <h2>阅读方式</h2>
        <p>圆点代表学区编号，连线代表一小时内允许移动的相邻路线。没有连线的两个学区，需要分多轮移动。</p>
        <div class="route-list">${routeListForDistricts()}</div>
      </div>
    </div>
    <div class="route-card" style="margin-top: 30px;">
      <h2>相邻地点速查</h2>
      <table>
        <tbody>${districtRouteTable()}</tbody>
      </table>
    </div>
    <div class="footer">
      <span>红色路线表示连接第七学区的高频路线。</span>
      <span>路线来自插件默认地图，可后续按客户地图继续替换。</span>
    </div>
  </section>

  <section class="sheet" id="map-inner">
    <div class="title-row">
      <div>
        <h1>第七学区细节图</h1>
        <p class="subtitle">第七学区是默认起点与主要剧情区。字母节点对应右侧地点说明，虚线通向其他学区。</p>
      </div>
      <div class="stamp">主舞台细节</div>
    </div>
    <div class="inner-layout">
      <div class="map-panel">${innerSvg()}</div>
      <div class="legend">${innerLegendCards()}</div>
    </div>
    <div class="route-card small-table" style="margin-top: 30px;">
      <h2>第七学区相邻地点速查</h2>
      <table>
        <tbody>${innerRouteTable()}</tbody>
      </table>
    </div>
    <div class="note-band">
      <div class="note"><b>补给地点</b><span>食堂、商业街适合恢复水分与饱食度，也适合商店和签到奖励落点。</span></div>
      <div class="note"><b>情报地点</b><span>图书馆、中心广场适合投放传闻、新闻、公共事件线索。</span></div>
      <div class="note"><b>风险地点</b><span>实验楼、医院可承接能力开发、受伤恢复和异常事件。</span></div>
    </div>
    <div class="footer">
      <span>虚线：可接入外部学区。实线：第七学区内部移动。</span>
      <span>建议将此图放入玩家说明书或 WebUI 地图页。</span>
    </div>
  </section>
</body>
</html>`;

fs.writeFileSync(htmlPath, html, "utf8");
console.log(htmlPath);
