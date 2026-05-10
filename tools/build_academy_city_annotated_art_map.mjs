import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..");
const outputDir = path.join(root, "docs", "map-guide");
const htmlPath = path.join(outputDir, "academy-city-annotated-art-map.html");

const overviewBg = "assets/academy_city_background_art.png";
const innerBg = "assets/academy_city_district7_background_art.png";

const districts = [
  ["01", "第一学区", "司法行政区", "政府街 / 审查严格", 505, 462, 548, 392, "#6b5e9f"],
  ["02", "第二学区", "警备训练区", "警备员训练 / 武器开发", 670, 572, 706, 510, "#405d87"],
  ["03", "第三学区", "外交展示区", "访客窗口 / 展示设施", 215, 225, 66, 170, "#24747d"],
  ["04", "第四学区", "餐饮与农业大楼", "食品补给 / 农业大楼", 604, 1152, 654, 1198, "#9a7726"],
  ["05", "第五学区", "大学区", "大学 / 学术委托", 376, 782, 218, 730, "#2f7661"],
  ["06", "第六学区", "娱乐休闲区", "娱乐设施 / 活动传闻", 260, 1128, 102, 1082, "#a17925"],
  ["07", "第七学区", "中心学区", "主舞台 / 学校医院", 528, 700, 560, 635, "#bd4a3f"],
  ["08", "第八学区", "教师住宿区", "教师住宅 / 教育设施", 430, 906, 484, 936, "#2f7661"],
  ["09", "第九学区", "工艺美术区", "制作道具 / 艺术设施", 255, 880, 64, 878, "#8a5b86"],
  ["10", "第十学区", "墓地与少年院", "高风险 / 都市阴影", 150, 1270, 52, 1212, "#725444"],
  ["11", "第十一学区", "陆路物流口", "外墙大门 / 物流车队", 192, 1380, 236, 1422, "#24747d"],
  ["12", "第十二学区", "宗教与神学研究区", "异国氛围 / 神学研究", 392, 1110, 310, 1164, "#6d6092"],
  ["13", "第十三学区", "幼小教育区", "小学幼儿园 / 治安较好", 304, 638, 94, 650, "#2f7661"],
  ["14", "第十四学区", "留学生区", "多语告示 / 外部文化", 165, 520, 42, 540, "#24747d"],
  ["15", "第十五学区", "商业与媒体中心", "商业街 / 电视台", 300, 255, 260, 178, "#ab6128"],
  ["16", "第十六学区", "学生打工区", "兼职 / 跑腿委托", 610, 915, 654, 885, "#9a7726"],
  ["17", "第十七学区", "工业制造区", "工厂 / 高等级监狱传闻", 835, 382, 826, 314, "#676f7a"],
  ["18", "第十八学区", "能力开发名校区", "名校 / 研究机构", 686, 716, 732, 752, "#2f7661"],
  ["19", "第十九学区", "再开发失败区", "废弃建筑 / 可疑交易", 785, 648, 828, 678, "#725444"],
  ["20", "第二十学区", "运动工学区", "运动工学 / 训练", 402, 435, 246, 382, "#3d7774"],
  ["21", "第二十一学区", "水源与山岳区", "水库 / 山岳 / 天文台", 704, 188, 736, 128, "#4f7d42"],
  ["22", "第二十二学区", "地下街区", "地下街 / 垂直风力", 894, 525, 850, 576, "#5c6475"],
  ["23", "第二十三学区", "航空宇宙区", "机场 / 航空宇宙", 815, 1032, 842, 1088, "#24747d"],
];

const innerLocations = [
  ["A", "第七学区校门口", "入口 / 公告栏", "集合、公告、校车站", 220, 186, 102, 238, "#bd4a3f"],
  ["B", "第七学区主干道", "交通主轴", "去学校、医院、商业区", 506, 330, 534, 258, "#4f6378"],
  ["C", "第七学区某高中", "学习 / 社团", "角色默认日常起点", 275, 525, 74, 508, "#2f7661"],
  ["D", "书库终端图书馆", "情报 / 查询", "公开资料与传闻线索", 500, 620, 348, 660, "#5d6593"],
  ["E", "能力开发实验楼", "能力测定", "AIM观测、实验事件", 735, 545, 748, 474, "#6f5c9d"],
  ["F", "第七学区学生宿舍", "休息 / 生活", "串门、小交易、夜间传闻", 258, 825, 78, 820, "#9a7726"],
  ["G", "学生食堂", "补给", "恢复水分与饱食度", 510, 842, 376, 872, "#9a7726"],
  ["H", "第十五学区商业街", "商店 / 媒体", "购物、打听消息", 742, 1032, 770, 962, "#ab6128"],
  ["I", "第七学区中心广场", "公共事件", "偶遇、公告、新闻传闻", 516, 1184, 330, 1194, "#bd4a3f"],
  ["J", "冥土追魂医院", "医疗 / 恢复", "受伤治疗、异常医学事件", 778, 170, 728, 232, "#3d7f7b"],
  ["K", "学舍之园", "封闭校区", "贵族女校群、进入需许可", 155, 362, 50, 314, "#8a5b86"],
  ["L", "常盘台中学", "名校 / Level 5传闻", "学舍之园内的顶级女校", 182, 460, 54, 426, "#6d6092"],
  ["M", "栅川中学", "日常 / 风纪线索", "初春、佐天相关学生传闻", 350, 730, 110, 700, "#2f7661"],
  ["N", "没有窗户的大楼", "禁区 / 统括理事会", "只能远望或接触外围流言", 930, 300, 798, 278, "#725444"],
  ["02", "第二学区入口", "外部接入", "警备训练区方向", 916, 500, 818, 390, "#405d87"],
  ["04", "第四学区入口", "外部接入", "餐饮补给方向", 510, 1450, 374, 1370, "#9a7726"],
  ["07", "第七学区外环", "外部接入", "返回二十三学区总览", 900, 1330, 770, 1260, "#bd4a3f"],
  ["15", "第十五学区入口", "外部接入", "商业媒体中心方向", 890, 1010, 784, 1088, "#ab6128"],
  ["18", "第十八学区入口", "外部接入", "能力开发名校区方向", 918, 640, 800, 705, "#2f7661"],
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

function pins(items) {
  return items.map(([id, name, role, detail, x, y, labelX, labelY, color]) => {
    const central = id === "07" || id === "I";
    const radius = central ? 31 : 24;
    return `
      <g class="pin ${central ? "central" : ""}" transform="translate(${x} ${y})">
        <circle class="halo" r="${radius + 12}" fill="${color}"></circle>
        <circle class="dot" r="${radius}" fill="${color}"></circle>
        <text y="${id.length === 1 ? 9 : 8}">${id}</text>
      </g>`;
  }).join("");
}

function routes(items, routePairs) {
  const lookup = byId(items);
  return routePairs.map(([a, b]) => {
    const from = lookup[a];
    const to = lookup[b];
    const external = a.length === 2 || b.length === 2;
    const core = a === "I" || b === "I" || a === "07" || b === "07";
    return `<line class="route ${core ? "core-route" : ""} ${external ? "dash-route" : ""}" x1="${from[4]}" y1="${from[5]}" x2="${to[4]}" y2="${to[5]}"></line>`;
  }).join("");
}

function callouts(items, { compact = false } = {}) {
  const width = compact ? 165 : 174;
  const height = compact ? 58 : 62;
  return items.map(([id, name, role, detail, x, y, labelX, labelY, color]) => {
    const lineX = labelX + (labelX < x ? width : 0);
    const lineY = labelY + height / 2;
    return `
      <g class="callout ${compact ? "compact" : ""}">
        <path d="M ${x} ${y} L ${lineX} ${lineY}" stroke="${color}"></path>
        <rect x="${labelX}" y="${labelY}" width="${width}" height="${height}" rx="12"></rect>
        <text class="callout-title" x="${labelX + 12}" y="${labelY + 23}">${id} ${name}</text>
        <text class="callout-role" x="${labelX + 12}" y="${labelY + 43}">${role}</text>
        <text class="callout-detail" x="${labelX + 12}" y="${labelY + 57}">${detail}</text>
      </g>`;
  }).join("");
}

function sideRows(items) {
  return items.map(([id, name, role, detail, x, y, labelX, labelY, color]) => `
    <article class="side-row">
      <span style="--c:${color}">${id}</span>
      <div>
        <b>${name}</b>
        <em>${role}</em>
        <p>${detail}</p>
      </div>
    </article>`).join("");
}

const html = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>学园都市美术详细标注版地图</title>
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
      width: 1880px;
      min-height: 2460px;
      margin: 0 auto 56px;
      padding: 52px;
      border-radius: 34px;
      background: rgba(255, 252, 246, .95);
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
      max-width: 1260px;
      margin: 14px 0 0;
      color: #657276;
      font-size: 23px;
      line-height: 1.55;
    }
    .badge {
      min-width: 270px;
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
      grid-template-columns: 1180px 1fr;
      gap: 32px;
      align-items: start;
    }
    .art-frame {
      position: relative;
      width: 1180px;
      height: 1770px;
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
      filter: saturate(1.03) contrast(1.02) brightness(.98);
    }
    .art-frame::after {
      content: "";
      position: absolute;
      inset: 0;
      background:
        linear-gradient(180deg, rgba(255,255,255,.05), rgba(20,35,42,.10)),
        radial-gradient(circle at 50% 50%, transparent 48%, rgba(255, 249, 235, .16));
      pointer-events: none;
    }
    .overlay {
      position: absolute;
      inset: 0;
      width: 100%;
      height: 100%;
      z-index: 2;
    }
    .pin .halo { opacity: .22; }
    .pin .dot {
      stroke: rgba(255, 255, 255, .95);
      stroke-width: 5;
      filter: drop-shadow(0 10px 12px rgba(14, 26, 32, .36));
    }
    .pin text {
      fill: #fff;
      text-anchor: middle;
      font-size: 23px;
      font-weight: 900;
      paint-order: stroke;
      stroke: rgba(0,0,0,.18);
      stroke-width: 2px;
      letter-spacing: 0;
    }
    .pin.central text { font-size: 27px; }
    .route {
      stroke: rgba(34, 53, 58, .55);
      stroke-width: 7;
      stroke-linecap: round;
      filter: drop-shadow(0 2px 2px rgba(255,255,255,.65));
    }
    .core-route {
      stroke: rgba(190, 76, 62, .76);
      stroke-width: 10;
    }
    .dash-route {
      stroke-dasharray: 16 13;
      opacity: .68;
    }
    .callout path {
      fill: none;
      stroke-width: 3;
      opacity: .78;
      stroke-linecap: round;
      stroke-dasharray: 5 5;
      paint-order: stroke;
    }
    .callout rect {
      fill: rgba(255, 253, 247, .88);
      stroke: rgba(40, 51, 54, .18);
      stroke-width: 1.4;
      filter: drop-shadow(0 8px 12px rgba(19, 32, 38, .18));
    }
    .callout text {
      fill: #1f3036;
      letter-spacing: 0;
      paint-order: stroke;
      stroke: rgba(255,255,255,.7);
      stroke-width: 2px;
    }
    .callout-title {
      font-size: 15px;
      font-weight: 900;
    }
    .callout-role {
      font-size: 13px;
      font-weight: 800;
      fill: #4d5f64;
    }
    .callout-detail {
      font-size: 11px;
      font-weight: 700;
      fill: #6a7476;
    }
    .callout.compact .callout-title { font-size: 15px; }
    .callout.compact .callout-role { font-size: 13px; }
    .callout.compact .callout-detail { font-size: 11px; }
    .side {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
    }
    .side.single {
      grid-template-columns: 1fr;
    }
    .side-row {
      display: grid;
      grid-template-columns: 46px 1fr;
      gap: 12px;
      min-height: 86px;
      padding: 12px;
      border-radius: 12px;
      background: rgba(255, 255, 255, .76);
      border: 1px solid rgba(79, 88, 88, .14);
    }
    .side-row span {
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      color: #fff;
      background: var(--c);
      font-size: 18px;
      font-weight: 900;
      box-shadow: 0 9px 18px rgba(23, 38, 46, .18);
    }
    .side-row b {
      display: block;
      font-size: 18px;
      line-height: 1.1;
    }
    .side-row em {
      display: block;
      margin-top: 4px;
      color: #617176;
      font-style: normal;
      font-weight: 800;
      font-size: 14px;
    }
    .side-row p {
      margin: 5px 0 0;
      color: #758083;
      font-size: 12px;
      line-height: 1.35;
      font-weight: 700;
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
  <section class="sheet" id="annotated-overview">
    <div class="header">
      <div>
        <h1>学园都市地图｜美术详细标注版</h1>
        <p class="subtitle">在美术详细版底图上直接标出二十三学区名称、职能和关键用途。此图用于展示和玩家认路；精确移动路线仍可参考清晰路线图。</p>
      </div>
      <div class="badge">详细标注版</div>
    </div>
    <div class="layout">
      <div class="art-frame">
        <img src="${overviewBg}" alt="" />
        <svg class="overlay" viewBox="0 0 1024 1536" aria-label="学园都市美术详细标注总览地图">
          ${callouts(districts)}
          ${pins(districts)}
        </svg>
      </div>
      <div class="side">${sideRows(districts)}</div>
    </div>
    <div class="notes">
      <div class="note"><b>标注内容</b>每个学区都标出编号、名称、职能和常见玩法用途。</div>
      <div class="note"><b>路线判定</b>此图主打展示，精确相邻路线请看“学园都市地图_路线图.png”。</div>
      <div class="note"><b>用途建议</b>适合发给玩家当世界总览，也适合放进 WebUI 地图页。</div>
    </div>
    <div class="footer">
      <span>AI 底图生成，全部中文标注由程序叠加。</span>
      <span>文件：学园都市地图_美术详细标注版_总览.png</span>
    </div>
  </section>

  <section class="sheet" id="annotated-inner">
    <div class="header">
      <div>
        <h1>第七学区地图｜美术详细标注版</h1>
        <p class="subtitle">直接标注默认主舞台内的校门、主干道、高中、图书馆、实验楼、宿舍、食堂、商业街、广场、医院，以及外部学区入口。</p>
      </div>
      <div class="badge">主舞台标注</div>
    </div>
    <div class="layout">
      <div class="art-frame">
        <img src="${innerBg}" alt="" />
        <svg class="overlay" viewBox="0 0 1024 1536" aria-label="第七学区美术详细标注地图">
          ${routes(innerLocations, innerRoutes)}
          ${callouts(innerLocations, { compact: true })}
          ${pins(innerLocations)}
        </svg>
      </div>
      <div class="side single">${sideRows(innerLocations)}</div>
    </div>
    <div class="notes">
      <div class="note"><b>实线</b>表示第七学区内部移动路线，适合玩家提交小时行动。</div>
      <div class="note"><b>虚线</b>表示外部接入口，连接第二、第四、第十五、第十八学区等方向。</div>
      <div class="note"><b>剧情提示</b>图书馆查情报，实验楼做能力事件，医院处理受伤，广场触发公共事件。</div>
    </div>
    <div class="footer">
      <span>第七学区标注版可直接发给玩家作为行动参考。</span>
      <span>文件：学园都市地图_美术详细标注版_第七学区.png</span>
    </div>
  </section>
</body>
</html>`;

fs.writeFileSync(htmlPath, html, "utf8");
console.log(htmlPath);
