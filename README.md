# MAAPVZ 远程作业集分享站

> **⚠️ 给 coding agent：本仓库当前有未完成的开发任务，先读文末
> [「开发任务书 v4」](#开发任务书-v4给-coding-agent) 再动手。**

《植物大战僵尸2》无尽模式自动化项目 [MAAPVZ](https://github.com/daoyanxiaoz/MAAPVZ) 的作业集分享站。
在这里可以浏览、下载其他玩家分享的作业集，也可以投稿自己的作品。

- 🌐 站点地址：<https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/>
- 📮 投稿入口：[New Issue → 分享作业集](https://github.com/daoyanxiaoz/maapvz-remote-assignment-set-integration/issues/new?template=share-jobset.yml)

<!-- 站点截图占位：上线后补一张首页截图放这里 -->

---

## 下载作业集（玩家）

1. 打开站点，用搜索框按名称 / code / 作者 / 简介筛选，
   或用筛选栏按 **世界 / 植物 / 装扮需求** 过滤；
2. 点卡片进详情页，可以查看只读的**关卡覆盖画板**和**种植布局画板**；
3. 点「下载 JSON」，在 MAAPVZ 编辑器里导入即可使用。

## 投稿作业集（玩家）

方式一（推荐）：站点导航栏点「上传作业集」，把 .json 文件拖进去 → 本地校验 → 逐棵标注装扮 → 一键打开 GitHub 投稿（标题正文已预填）。

方式二（手动）：

1. 打开[投稿入口](https://github.com/daoyanxiaoz/maapvz-remote-assignment-set-integration/issues/new?template=share-jobset.yml)，使用「分享作业集」模板开 Issue；
2. 把编辑器导出的 .json 文件**拖进「作业集 JSON」一栏**（GitHub 会自动上传成附件链接），或直接粘贴 JSON 全文；
3. **装扮标注必填**：作业集里出现的每一棵植物都要标注「需要/不需要」装扮，
   每行一条，如 `娜迦蛇皮果:需要`、`大嘴花:不需要`，一颗不落；
4. 作者昵称、一句话简介可选填；
5. 提交后机器人自动校验：
   - ✅ 通过 → 自动开 PR，等维护者审核合并后自动上站；
   - ❌ 未通过 → 机器人会在 Issue 下评论原因（缺漏的装扮标注会直接列出清单），
     **直接编辑原 Issue** 改好即可，机器人会重新校验；
6. 想改已投稿的内容：直接编辑原 Issue，PR 会自动同步更新。

校验规则速览：

| 规则 | 说明 |
| --- | --- |
| 必需字段 | `code`、`name`、`tables`（非空数组） |
| code 格式 | 仅字母、数字、下划线、连字符，1~64 位 |
| 体积上限 | 2MB |
| code 唯一 | 与站内已有作业集撞车会被拒绝 |
| **装扮标注** | **必填，作业集里每棵植物一条，不多不少；植物名须在植物数据库内** |

---

## 维护者手册

### 前置设置（一次性）

1. **Settings → Pages** → Deploy from a branch → `main` / `(root)`；
2. **Settings → Actions → General** → Workflow permissions →
   勾选 **Read and write permissions**；
3. **Settings → Issues** 保持开启（投稿入口）；
4. 建两个 label：`投稿`、`无效投稿`（Issues → Labels → New label，
   机器人打标签和投稿模板都依赖它们）。

### 手动上架

直接把作业集 JSON 丢进 `jobs/` 推送即可，
Action「重建作业集索引」会自动重建 `index.json`，几分钟后站点可见。

### 修改作者 / 简介 / 装扮标注

编辑 `meta/<code>.json`：

```json
{
  "author": "作者昵称",
  "desc": "一句话简介",
  "plant_costumes": { "娜迦蛇皮果": true, "大嘴花": false }
}
```

推送后索引自动更新。

### 下架作业集

删除 `jobs/<code>.json`（连同 `meta/<code>.json` 可一起删），推送即可。

### 投稿审核

带「投稿」标签的 Issue 会被机器人自动校验并开 PR：

- PR 正文含校验摘要，`Closes #<issue>` 合并后自动关闭原 Issue；
- 审核时**可以也应该修改格式**：merge 前在 PR 里直接改
  `jobs/<code>.json` 本体或 `meta/<code>.json`（修正装扮标注、补简介等）；
- 无效投稿会被打「无效投稿」标签，投稿人编辑 Issue 后会自动重试。

---

## 作业集 JSON 格式

顶层字段一览（校验只强依赖 `code` / `name` / `tables`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | string | 唯一标识，白名单 `^[A-Za-z0-9_\-]{1,64}$` |
| `name` | string | 作业集名称（展示用） |
| `version` | number | 格式版本 |
| `worlds` | string[] | 适用世界（**目前普遍是空数组**，空时不显示世界维度） |
| `max_level` | number | 最高关卡（普遍 149，弱化展示） |
| `everyN` | number | 循环动作间隔（秒） |
| `swipeMs` | number | 滑动时长（毫秒） |
| `outer_pick` | object | 局外选卡配置，可空 |
| `tables` | array | ★ 核心：分关卡段的种植策略表，至少 1 张 |
| `format` | string | 固定为 `maapvz-jobset` |

`tables` 元素关键字段：

| 字段 | 说明 |
| --- | --- |
| `levels` / `cover.picks` | **显式关卡号数组**（可能离散，如只挑 5 的倍数关）。画覆盖用这个，**别用 from_level/to_level 区间画** |
| `from_level` / `to_level` | 范围摘要（null = 到 149），仅作文字显示 |
| `lineup.plants` | 阵容植物中文名数组；**可为空**（编队换阵型，显示「编队换阵」） |
| `lineup.artifact` | 携带神器（如「葫芦神器」） |
| `boardEarly` / `boardLate` | 前期/后期种植布局：行数组 × 9 列，格子为 `[]` 或 `{label, type, mode, col, row, seq, plant:{name, img}}` |
| `supplyPicks` | 补给优先序 `[{id, name, img, pinned?}]` |
| `endType` / `endLoopCount` | 收尾模式：detect=识别最后一波 / loops=循环 N 次后收尾 |
| `boss_lineup` / `boss` | boss 关单独配置（有则展示「boss 关单独配置」标记） |
| `compiled` | 预编译产物，展示时忽略 |

### 装扮标注的存储

**作者投稿时逐棵标注**（机器人强制校验齐全），落两处之一：

- 投稿通道：Action ① 把标注写进 `meta/<code>.json` 的 `plant_costumes`；
- 兼容：作业集 JSON 里的 `plant_meta`（表级优先于全局）详情页同样识别。

`tier`（1~5 阶数角标）仍可选；`costume: true/false` 为装扮标记。

## 仓库结构

```
├── index.html            首页：作业集卡片列表 + 搜索 + 三维筛选
├── job.html              详情页：关卡覆盖画板 / 种植布局画板 / 阵容装扮 / 补给
├── submit.html           上传作业集：本地校验 + 一键投稿
├── about.html            关于（待开发）
├── style.css             全站共享样式（本地文件，无外部依赖）
├── index.json            作业集清单（Action 自动维护，勿手改）
├── jobs/<code>.json      作业集本体
├── meta/<code>.json      sidecar：作者 / 简介 / 装扮标注
├── data/                 plants.json / artifacts.json（名称映射表）
├── img/                  植物/神器/阶数/世界立绘/挂件图
├── tools/
│   ├── build_index.py    重建 index.json
│   └── issue_to_pr.py    投稿 Issue → 校验 → 自动开 PR
└── .github/
    ├── workflows/        两个 Action：索引重建、投稿处理
    └── ISSUE_TEMPLATE/   投稿表单
```

## 本地预览

```bash
python -m http.server 8000
# 打开 http://localhost:8000
```

## 许可

见 [LICENSE](LICENSE)。

---

# 开发任务书 v4（给 coding agent）

> 本节是给开发 AI 的任务说明，完成后由维护者删除。
> 主项目仓库在 `D:\maapvz\MAAPVZ`（只读参考，**不要改动它**）。
> v4 修正：画板范围、审核改格式由机器人自动执行、卡片内容、筛选确认。

## 0. 立即执行：清场

- 删除 `jobs/` 下**所有**现有作业集（含 pvz_demo_huoshe 示例）；
- 重建空 index.json，站点显示空状态；
- 之后维护者本人会走投稿流程上传一个远程测试作业集验证全链路。

## 1. 详情页：两个只读画板（都要）

数据获取：点卡片进详情页时 `fetch('jobs/<code>.json')`（按需加载，不进 index.json）。

### 1a. 关卡覆盖画板（复刻编辑器「🧩 布局配置」）

编辑器里的布局配置是 1-149 关的**宫格涂层板**：表列表 = 图层栈，
上面的表优先盖住下面的表。详情页把它**只读复刻**：

- 1~149 宫格矩阵（编辑器样式参考：`D:\maapvz\MAAPVZ\game_assist_tools\endless_setup\static\js\34-jobset-layout.js`），每格一个关卡号；
- 每表一色（草坪绿系轮换），用 `tables[].levels`（或 `cover.picks`）着色——
  **是显式关卡号数组，可能离散**（例：某表只覆盖 51,56,61,66… 逢五关），
  严禁用 from_level/to_level 连成区间画；
- **格子可被多表同时覆盖**（图层模式：数组先出现的表优先）——交叠格画
  先出现表的颜色，tooltip 注明「表1、表2 都覆盖此关，实际用表1」；
- 5 的倍数关（boss 关）加角标；某关无任何表覆盖标红（非法作业集）；
- 左侧/上方放表列表（图层栈顺序展示），点表名高亮该表的格子；
- 只读，hover 出 tooltip，无任何编辑。

### 1b. 草坪种植布局画板（boardEarly / boardLate）

- 草坪 5 行 × 9 列，深绿/浅绿棋盘格底；
- 格子放植物立绘：`plant.img` 是 `static/plant/xxx.webp`，**改写前缀为
  本仓库 `img/plant/xxx.webp`**（资产已复制，注意核对实际目录名）；
- 格子角标：mode（once=单次 / loop=循环）与 seq 顺序号；
- `type != "plant"` 的格子（feed=喂豆 / shovel=铲子等）用文字标签；
- 前期/后期两个 Tab 切换；只读。

### 1c. 详情页其余信息

阵容植物列表（逐棵带「需装扮」徽标，见第 3 节）、携带神器、补给优先序
（配 img/supply 图标）、收尾模式徽标（「识别收尾」「循环×N 收尾」）、
boss 关单独配置标记、everyN。

## 2. 主页

### 2a. 卡片内容（三样，勿加戏）

1. **基础信息**：名称、code（点击复制）、作者/更新时间（有则显示）；
2. **关卡覆盖预览条**：1~149 迷你横条，按 tables 图层规则分段着色
   （离散覆盖照样画点，规则同 1a），一眼看出几张表怎么分关卡；
3. **阵容植物图标**：该作业集全量植物（去重）的小图标一排，
   图标用 `img/plant/<en>.webp`，中英映射查 `data/plants.json`；
   超过一排的数量折行或「+N」。

### 2b. 三维筛选（可叠加，已确认）

| 维度 | 数据来源 | 交互 |
| --- | --- | --- |
| 世界 | index.json `worlds` | 多选标签组；数据普遍为空数组，**全部为空时隐藏该维度** |
| 植物 | index.json 每条 `plants` 数组 | 可搜索多选；「阵容含此植物」 |
| 装扮 | index.json 每条 `costume` 聚合 | 三态：全部 / 全无需装扮 / 含需装扮植物 |

**build_index.py 配套**：
- 每条目从作业集提取全量植物名集合（`lineup.plants` ∪ `boss_lineup.plants` ∪
  `boardEarly/boardLate` 中 `type=plant` 格子的 label ∪ boss 对应字段），
  去重写入 `plants`；同时写入图层规则的 `coverage`（供预览条：
  每表 `{levels: [...]}` 或压缩为区间+散点）；
- 从 `meta/<code>.json` 的 `plant_costumes` 聚合 `costume: "none"|"required"`；
- 主页筛选与卡片**只走 index.json**，禁止为主页 fetch 作业集全量。

## 3. 投稿：机器人自动改格式 + 强制装扮标注

### 3a. 机器人自动改格式（Action ① 负责，规则固定）

投稿 JSON 校验通过后，落盘前自动做：

1. **剥掉所有 `tables[].compiled` 块**——这是编辑器保存时的预编译快照
   （占文件 70%~90% 体积，且带时效性：守卫 ROI 等变了就是过期数据）。
   剥掉后使用者导入编辑器重存时会用**最新编译器**重新生成。
   ★ 依据：主项目 runtime 对无 compiled 的作业集会明确提示「去编辑器重新
   保存一次」，这正是设计的导入路径（download → 导入编辑器 → 重存）。
2. **JSON 规范化落盘**：UTF-8 无 BOM、ensure_ascii=False、缩进 2；
3. **写 `meta/<code>.json`**：author / desc / plant_costumes。

维护者 merge 前仍可在 PR 里手改任何内容（内容审核在人）。

### 3b. 强制装扮标注（维护者原话：每个植物都要标注，作者严格配置）

- Issue 表单必填 textarea「装扮标注」：每行 `植物名:需要` 或 `植物名:不需要`；
- Action ① 校验：**作业集内每棵植物都有标注（漏→评论缺漏清单）、
  无作业集外植物（多→报错）、植物名在 data/plants.json 内、
  值仅「需要/不需要」**；失败评论缺漏清单，作者编辑 Issue 重触发；
- 通过 → 写 `meta/<code>.json` 的 `plant_costumes`；
- 展示：详情页阵容列表逐棵徽标（需装扮用阳光黄醒目色）。

## 4. 风格（已定：PVZ 种子包风，勿推翻）

羊皮纸卡片 `#f7ecc9` + 木棕 `#6b4423` 描边 + 阳光黄主按钮 `#ffd93b` +
夜空草坪背景 `#16301b→#1e4023` 渐变；术语与编辑器同源
（单次链/循环链/收尾链/补给/神器/表/覆盖）；纯静态零 CDN；
textContent 防注入；移动端可读。

## 5. 真实参考数据（只读）

主项目 `D:\maapvz\MAAPVZ\assets\resource\jobs\` 下有 5 份真实作业集
（心喷/蛇果/火珊冰大/阿金/沙滩无尽挂机，11111 是测试集）——
**仅作开发素材读取，不许发布上站**。注意它们的 worlds 全是空数组、
蛇果表2 只覆盖逢五关（离散 levels 的真实样例）、火珊冰大 lineup.plants 为空。

## 6. 验收清单

- [ ] jobs/ 已清空，空索引，空状态正常
- [ ] 覆盖画板用 levels 数组着色，离散覆盖（逢五关）渲染正确，交叠格不串色，
      点表名能高亮该表格子
- [ ] 种植布局画板植物立绘路径改写正确，无 404；feed/shovel 格子显示文字
- [ ] 卡片三要素齐全：基础信息 + 覆盖预览条 + 阵容图标排
- [ ] 三维筛选可叠加，全部 worlds 为空时世界维度隐藏
- [ ] 投稿后 PR 里的 JSON 已无 compiled 块、JSON 规范化、meta 三件齐全
- [ ] 投稿缺装扮标注 → 评论缺漏清单；补齐 → PR 开出
- [ ] 标注混入作业集外植物 / 数据库外名字 / 非法值 → 拒绝
- [ ] 详情页阵容逐棵显示装扮徽标；主页装扮筛选生效
