# 学园都市地图图片

本目录存放“群文游文字世界”的玩家版地图素材。

## 成品图片

- `学园都市地图_总览.png`：二十三学区总览，适合发给玩家认识世界结构。
- `学园都市地图_路线图.png`：带相邻路线速查，适合管理员判定移动是否合法。
- `学园都市地图_第七学区细节.png`：默认主舞台内部地点图，适合玩家提交行动时参考。
- `学园都市地图_美术详细版_总览.png`：AI 生成城市鸟瞰底图，程序叠加准确编号和中文图例，适合展示给玩家。
- `学园都市地图_美术详细版_第七学区.png`：AI 生成第七学区鸟瞰底图，程序叠加地点、路线和中文图例。

## 源文件

- `academy-city-map.html`：地图排版源文件。
- `academy-city-art-map.html`：美术详细版地图排版源文件。
- `assets/academy_city_background_art.png`：总览美术底图。
- `assets/academy_city_district7_background_art.png`：第七学区美术底图。
- `tools/build_academy_city_map.mjs`：生成 HTML。
- `tools/render_academy_city_map.mjs`：使用 Playwright 截图导出 PNG。
- `tools/build_academy_city_art_map.mjs`：生成美术详细版 HTML。
- `tools/render_academy_city_art_map.mjs`：导出美术详细版 PNG。

路线以插件内置 `DEFAULT_LOCATIONS` 的默认相邻地点为准。后续如果客户提供正式地图，只需要替换脚本中的地点坐标、说明和路线关系，再重新渲染即可。
