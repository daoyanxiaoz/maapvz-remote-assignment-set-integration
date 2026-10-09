# MAAPVZ 远程作业集分享站

《植物大战僵尸2》无尽模式自动化项目 [MAAPVZ](https://github.com/daoyanxiaoz) 的作业集分享站。
在这里可以浏览、下载其他玩家分享的作业集，也可以投稿自己的作品。

- 🌐 站点地址：<https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/>
- 📮 投稿入口：[New Issue → 分享作业集](https://github.com/daoyanxiaoz/maapvz-remote-assignment-set-integration/issues/new?template=share-jobset.yml)

<!-- 站点截图占位：上线后补一张首页截图放这里 -->

---

## 下载作业集（玩家）

1. 打开站点，用搜索框按名称 / code / 作者 / 简介筛选；
2. 点卡片上的「下载 JSON」，保存作业集文件；
3. 在 MAAPVZ 编辑器里导入该 JSON，即可使用。

## 投稿作业集（玩家）

1. 点上方「投稿入口」，使用「分享作业集」模板开 Issue；
2. 把编辑器导出的作业集 JSON **完整粘贴**到「作业集 JSON」一栏，
   作者昵称、一句话简介可选填；
3. 提交后机器人自动校验：
   - ✅ 通过 → 自动开 PR，等维护者审核合并后自动上站；
   - ❌ 未通过 → 机器人会在 Issue 下评论原因并打上「无效投稿」标签，
     **直接编辑原 Issue** 改好即可，机器人会重新校验；
4. 想改已投稿的内容：直接编辑原 Issue，PR 会自动同步更新。

校验规则速览：

| 规则 | 说明 |
| --- | --- |
| 必需字段 | `code`、`name`、`tables`（非空数组） |
| code 格式 | 仅字母、数字、下划线、连字符，1~64 位 |
| 体积上限 | 2MB |
| code 唯一 | 与站内已有作业集撞车会被拒绝 |

---

## 维护者手册

### 前置设置（一次性）

1. **Settings → Pages** → Deploy from a branch → `main` / `(root)`；
2. **Settings → Actions → General** → Workflow permissions →
   勾选 **Read and write permissions**；
3. **Settings → Issues** 保持开启（投稿入口）。

### 手动上架

直接把作业集 JSON 丢进 `jobs/` 推送即可，
Action「重建作业集索引」会自动重建 `index.json`，几分钟后站点可见。

### 修改作者 / 简介

编辑 `meta/<code>.json`：

```json
{
  "author": "作者昵称",
  "desc": "一句话简介"
}
```

推送后索引自动更新。没有 sidecar 的作业集，卡片上不显示作者和简介。

### 下架作业集

删除 `jobs/<code>.json`（连同 `meta/<code>.json` 可一起删），推送即可。

### 投稿审核

带「投稿」标签的 Issue 会被机器人自动校验并开 PR：

- PR 正文含校验摘要，`Closes #<issue>` 合并后自动关闭原 Issue；
- 合并前请扫一眼 `jobs/<code>.json` 内容是否有明显异常；
- 无效投稿会被打「无效投稿」标签，投稿人编辑 Issue 后会自动重试。

---

## 作业集 JSON 格式

顶层字段一览（校验只强依赖 `code` / `name` / `tables`）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `code` | string | 唯一标识，白名单 `^[A-Za-z0-9_\-]{1,64}$` |
| `name` | string | 作业集名称（展示用） |
| `version` | number | 格式版本 |
| `worlds` | string[] | 适用世界 |
| `max_level` | number | 最高关卡 |
| `everyN` | number | 循环动作间隔（秒） |
| `swipeMs` | number | 滑动时长（毫秒） |
| `outer_pick` | object | 局外选卡配置，可空 |
| `tables` | array | ★ 核心：分关卡段的种植策略表，至少 1 张 |
| `format` | string | 固定为 `maapvz-jobset` |

`tables` 元素含 `from_level` / `to_level` / `lineup` / `non_boss` / `boss` /
`endType` / `endLoopCount` 等字段，并可能带大块的 `compiled` 预编译产物
（几十 KB 属正常）。

## 仓库结构

```
├── index.html            站点首页（纯静态，无外部依赖）
├── index.json            作业集清单（Action 自动维护，勿手改）
├── jobs/<code>.json      作业集本体
├── meta/<code>.json      可选 sidecar：作者 / 简介
├── tools/
│   ├── build_index.py    重建 index.json
│   └── issue_to_pr.py    投稿 Issue → 校验 → 自动开 PR
└── .github/
    ├── workflows/        两个 Action：索引重建、投稿处理
    └── ISSUE_TEMPLATE/   投稿表单
```

## 本地预览

浏览器直开 `index.html`（file://）无法读取 `index.json`，请起个本地服务：

```bash
python -m http.server 8000
# 打开 http://localhost:8000
```

## 许可

见 [LICENSE](LICENSE)。
