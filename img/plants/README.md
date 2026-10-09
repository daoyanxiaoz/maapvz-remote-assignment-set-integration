# 站点图片资源

## 目录说明

| 目录 | 来源 | 内容 |
| --- | --- | --- |
| `img/plants/` | MAAPVZ 主仓 `game_assist_tools/endless_setup/static/plant/` | 植物图标全套（317 张 webp，约 100×100），整套照搬 |
| `img/artifacts/` | `作业站代办/主图标/` | 神器主图标（`artifact_<en>.png`） |
| `img/artifacts/bodytype/` | MAAPVZ 主仓 `static/artifact/artifact_calabash/bodytype/` | 葫芦神器体型图（small/mid/big） |
| `img/rank/` | `作业站代办/阶数/` | 阶数角标 1~5 |
| `img/worlds/` | `作业站代办/选择世界图/` | 世界立绘（透明底，19 张） |
| `img/items/` | `作业站代办/挂件图标/` | 挂件图标（备用） |

## 数据表

- `data/plants.json`：植物中文名 → 英文名/图（317 条，来自编辑器静态数据）
- `data/artifacts.json`：神器中文名 → 英文名（38 条，来自编辑器静态数据）

游戏出新植物/神器时：往主仓对应目录加图 + 更新 plants.json/artifacts.json，
然后整套复制过来即可，站点代码零改动。
