# MAAPVZ 远程作业集分享站

《植物大战僵尸2》无尽模式自动化项目 [MAAPVZ](https://github.com/daoyanxiaoz/MAAPVZ) 的作业集分享站。
纯静态站点（无后端、无数据库、无 CDN），GitHub Pages 托管；**仓库目录树就是唯一数据源**。

- 🌐 站点：<https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/>
- 🚀 上架向导：<https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/publish.html>
- 👋 不懂开发也能上架：见 [`docs/维护者上架指南.md`](docs/维护者上架指南.md)

---

## 玩家：浏览 / 下载

1. 首页顶部「阵型 → 常见阵型 ▾」下拉按打法类型过滤（例如 `心塔`），再用 **世界 / 植物 / 装扮** 或搜索框收窄；
   卡片上只显示**主世界**一个世界标签 + 紫色 `#标签`，副世界在详情页里看；
2. 点卡片进详情页：关卡覆盖画板、总览配置、策略表，以及**版本历史**（每一版都能单独下载）；
3. 点「下载 JSON」，在 MAAPVZ 编辑器里导入即可使用。

## 维护者：上架一份作业集

五条等价的路，选一条即可（都不需要改代码、不需要手改索引）：

| 方式 | 适合谁 | 怎么做 |
| --- | --- | --- |
| **本地维护工具（最省事）** | 有仓库副本的人 | 双击 `启动维护工具.bat` → 浏览器里拖文件、改作者/说明、重命名、删版本 |
| **网页向导** | 只有网页权限的维护者 | 打开 `publish.html` → 拖入作业集 → 选「迭代 / 新建」→ 生成上架包 → 传到 `inbox/` |
| **inbox 投递** | 有仓库写权限的人 | 把 `*.bundle.json` 上传到 `inbox/`，Action 自动拆包落库并重建索引 |
| **本地命令** | 喜欢命令行的人 | `python tools/publish.py 作业集.json --group 心塔 --author 名字` |
| **纯手动** | 想完全掌控的人 | 按目录约定把文件放进 `jobs/<阵型>/<作业集>/<版本日期>/`，再写一份 `作者.txt` |

跑完自动重建索引（本地工具会顺带重建 `index.json`，跟着你的 commit 一起提交；手动也可）：

```powershell
python -X utf8 tools/build_index.py     # 重建 index.json
```

> ⚠ 仓库里**没有**「每次 push 就自动重建索引并提交」的机器人（v2 已删除 `build-index.yml`）。
> 所以：`index.json` 由你（或本地维护工具）生成并提交；只有往 `inbox/` 传上架包时，Action 才会代你提交一次。

### 上架时的强制规整（所有通道一致）

`tools/joblib.py` 的 `normalize_job()` 会对每份上架/规整的作业集统一处理：

- `outer_pick.mode` **强制 `auto`**（别人导入后不用手点确认选卡）；
- `outer_pick.plants` **强制 = 本作业集阵容实际用到的植物**（保序去重）；
  既不是空池，也不是编辑器里的 80 株全量池。

已有作业集可以用 `python -X utf8 tools/normalize_jobs.py --apply` 一次性规整（幂等）。

### 目录约定（唯一真相源）

```
jobs/
  心塔/                              ← 阵型（可选：同类型打法放一起；目录名 = 站点阵型名）
    _group.json                      ← 可选：{"name","desc","order","icon"}
    失落原大火龙果/                    ← 作业集（一次新建 = 一个目录）
      2026-10-19/                    ← 版本目录（名字必须是日期 YYYY-MM-DD）
        失落原大火龙果.json            ← 作业集本体（.json / .txt 均可）
        作者.txt                      ← 作者名（一行一个，支持多人）
        说明.txt                      ← 可选：这一版改了什么
      2026-10-25/                    ← 再迭代一次 = 多一个日期目录，旧版保留
        失落原大火龙果.json
        作者.txt

  火气珊瑚/                          ← 不归入阵型：直接放在 jobs/ 下，同样三层结构
    2026-10-30/
      火气珊瑚.json
      作者.txt
```

- **阵型层是可选的**：`jobs/` 下的直接子目录如果里面是「日期目录」就算作业集（不归入阵型）；
  如果里面还有作业集目录，那就是阵型。
- **版本目录名必须像日期**（`2026-10-19` / `2026_10_19` / `20261019`），扫描器靠它区分作业集和版本。
- 兼容写法：`jobs/<阵型>/xxx.json`、`jobs/xxx.json`（单版本）照样能扫出来。
- 模板见 [`docs/模板作业集/`](docs/模板作业集/)。

### 日常操作

- **迭代**：同目录下加一个日期目录（或用向导选「迭代」）。
- **改作者 / 说明**：直接编辑对应版本目录里的 `作者.txt` / `说明.txt`。
- **下架**：删掉 `jobs/[阵型/]<作业集>/` 整个目录。
- **只撤某一版**：删掉那个版本目录。
- **换阵型 / 阵型改名**：在本地维护工具里用每个作业集下面的「阵型」下拉 + 「移动」；或直接把作业集目录挪进/挪出阵型文件夹
  （阵型层可省略，挪到 `jobs/` 顶层就是不归入阵型）；阵型改名就是重命名阵型文件夹（可同时改 `_group.json` 的 `name`）。
- 以上任何改动完成后，要重建一次 `index.json` 再推送：本地维护工具自动做；
  手工改文件的话跑 `python -X utf8 tools/build_index.py`（或在 Actions 里手动点「重建作业集索引（手动）」）。

---

## 仓库结构

```
├── index.html            首页：阵型（常见阵型下拉）+ 卡片列表 + 搜索 + 世界/植物/装扮筛选
├── job.html              详情页：总览 / 覆盖画板 / 策略表 / 版本历史
├── publish.html          上架向导（线上）：拖文件 → 迭代 or 新建 → 生成上架包（零依赖）
├── admin.html            维护工具（本地）：上传 / 改信息 / 重命名 / 删版本
├── 启动维护工具.bat       双击 = 起本地服务 + 打开 admin.html（可写）
├── 启动作业站预览工具.bat   双击 = 起本地预览 + 打开 index.html（只读，写接口全关）
├── about.html            关于 + 维护指南
├── style.css             全站样式（PVZ 种子包风，本地文件，零 CDN）
├── index.json            站点清单（脚本生成，勿手改）
├── jobs/[阵型/]<作业集>/<版本>/     ★ 作业集目录树（唯一数据源；阵型层可选）
├── inbox/                上架包投递口（Action 自动消费，见 inbox/README.md）
├── data/                 plants.json / artifacts.json / pendants.json（名称映射）
├── img/                  植物 / 神器 / 阶数 / 世界立绘 / 挂件 / 稀有度底图
├── docs/                 模板作业集 + 给非开发者的上架指南
├── tools/
│   ├── joblib.py         目录约定 + 解析 + 规整 + 落库（所有脚本的公共库）
│   ├── build_index.py    扫描目录树 → index.json
│   ├── dev_server.py     本地维护服务器（127.0.0.1，提供 admin.html 用的 /api/*）
│   ├── apply_inbox.py    消费 inbox/*.bundle.json → 落库 → 重建索引
│   ├── publish.py        本地命令行上架
│   ├── normalize_jobs.py 批量把作业集规整成「自动选卡 + 固定植物」
│   ├── audit.py          仓库体检（空目录 / 重复 code / 同名 / 版本目录名），--clean 删空目录
│   └── migrate_legacy.py 旧版平铺 jobs/*.json 迁移（一次性，幂等）
└── .github/workflows/
    ├── apply-inbox.yml    inbox/ 有新包 → 拆包落库 → 重建 index.json（唯一会自动提交的 Action）
    └── rebuild-index.yml  手动触发：Actions 里点一下才重建 index.json（平时用不到）
```

## index.json（schema 2）

```jsonc
{
  "schema": 2,
  "updated": "2026-10-31T00:00:00Z",
  "count": 10,               // 作业集数
  "version_count": 12,       // 版本总数
  "groups": [                // 阵型
    { "id": "心塔", "name": "心塔", "desc": "", "count": 3, "version_count": 5,
      "updated": "...", "jobs": ["心塔/失落原大火龙果"] }
  ],
  "jobs": [
    {
      "id": "心塔/失落原大火龙果",   // 作业集身份 = 阵型/名称（目录身份）
      "group": "心塔", "name": "失落原大火龙果", "dir": "jobs/心塔/失落原大火龙果",
      "code": "pvz_20261019_143143",  // 最新版本的 code（旧链接兼容用）
      "author": "站长", "date": "2026-10-25", "updated": "...",   // author 为兼容字段
      "version_count": 3,
      "versions": [                   // 新的在前
        { "label": "2026-10-25", "date": "2026-10-25", "file": "jobs/...",
          "name": "...", "code": "...", "authors": ["站长", "某某"], "author": "站长、某某",
          "note": "...", "size": 12345 }
      ],
      // 以下为最新版本聚合出来的卡片字段（与旧版契约兼容）
      "worlds": [], "world_primary": "...", "tags": [], "tables": 2,
      "max_level": 149, "coverage": [], "plants": [], "plants_max": 8,
      "outer_pick": "auto", "artifact": "...", "artifact_en": "...",
      "end_desc": "...", "supply": [], "costume": "none|required", "desc": "..."
    }
  ]
}
```

页面只依赖 `index.json` + 版本文件本身，**不会**为主页去 fetch 全部作业集。

---

## 作业集 JSON 字段速查

| 字段 | 说明 |
| --- | --- |
| `code` | 唯一 ID，白名单 `^[A-Za-z0-9_\-]{1,64}$`（缺省用文件名兜底） |
| `name` | 显示名（下载文件名也用它） |
| `worlds` / `world` / `sub_worlds` | 世界：兼容三代格式；索引生成时做语义去重（留全名） |
| `tags` | 标签数组，紫色 `#标签` 直接铺在卡片上，参与搜索（不做筛选） |
| `max_level` / `everyN` / `swipeMs` | 最高关 / 循环间隔 / 滑动时长 |
| `plant_notes` | 植物标注 `{植物: {tier, pendant, pendantTier, costume}}`（表级覆盖全局） |
| `artifact_notes` | 神器阶数 `{神器: {tier}}` |
| `outer_pick` | 局外选卡（候选池不计入阵容统计） |
| `tables[]` | 关卡段策略表：`levels`/`cover.picks`（权威离散覆盖）、`from_level`/`to_level`、`lineup`、`boss_lineup`、`supplyPicks`、`non_boss`/`boss` 动作链、`endType`/`endLoopCount` |
| `boardEarly` / `boardLate` | 种植布局（站点不画板，但计入植物并集） |
| `compiled` | 编辑器预编译快照，站点忽略 |

- 覆盖画板/预览条只认 `levels`（或 `cover.picks`）这类**显式关卡号数组**（可能离散），不拿 `from_level`/`to_level` 连成区间画。
- 阵容植物 = `lineup.plants` ∪ `boss_lineup.plants` ∪ 棋盘 `type=plant` 格子，去重后统计。
- 装扮筛选聚合自 `plant_notes[*].costume`。

## 详情页展示规范

1. **总览**：全部表并集 —— 植物（阶数/挂件/装扮徽标）、神器、补给；
2. **关卡覆盖画板**（只读）：1~149 宫格 + 图层栈，交叠关归先出现的表，boss 关描金，未覆盖标红；点表名只显示那张表；
3. **策略表卡片**：阵容 → 神器 → boss 阵容 → 动作链规模 → 补给 → 收尾；
4. **版本历史**：每版的作者 / 日期 / 说明 / 大小 + 查看与下载。

---

## 本地预览

```powershell
# 最省事：双击 启动作业站预览工具.bat（浏览器自动打开，只读）
# 或者手动起一个静态服务器：
python -m http.server 8931 --bind 127.0.0.1 --directory .
# 打开 http://127.0.0.1:8931
```

## GitHub Actions 前置设置（一次性）

1. **Settings → Pages** → Deploy from a branch → `main` / `(root)`；
2. **Settings → Actions → General** → Workflow permissions → **Read and write permissions**
   （只有 inbox 拆包 / 手动重建索引这两个 Action 需要提交，其余都是纯读取）；
3. 仓库必须有 `.nojekyll`（否则 Pages 走 Jekyll 会卡住不部署）。

## 许可

见 [LICENSE](LICENSE)。
