# 玩家图文说明书

本目录包含给玩家看的图片版说明书。

## 成品图片

- `玩家图文说明书_完整长图.png`：完整玩家说明书，适合发给客户确认。
- `玩家图文说明书_01_开局流程.png`：第一次进群流程。
- `玩家图文说明书_02_角色卡.png`：角色卡写法。
- `玩家图文说明书_03_行动写法.png`：每小时行动写法。
- `玩家图文说明书_04_指令速查.png`：玩家常用指令速查。
- `玩家图文说明书_04_全指令速查.png`：所有常用指令的汇总版。
- `玩家图文说明书_05_系统后台规则.png`：系统节奏、后台和世界书说明。

## 可编辑源文件

- `player-guide.html`：图文说明书源稿。
- `../../tools/render_player_guide.mjs`：PNG 渲染脚本。

重新导出：

```powershell
$env:NODE_PATH='C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tools\render_player_guide.mjs
```
