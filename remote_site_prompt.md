# 任务：为 MAAPVZ 远程作业集站搭建 GitHub Pages 静态站点 + Issue 投稿流水线

## 背景（必读）

MAAPVZ 是一个《植物大战僵尸2》无尽模式的自动化项目（基于 MAA 框架）。用户在本地的
网页编辑器里编排「作业集」（一组种植/收尾策略），导出为 JSON 文件。

现在要在**本仓库**（daoyanxiaoz/maapvz-remote-assignment-set-integration）搭一个
远程作业集分享站，让其他玩家可以：
1. **浏览/下载**别人分享的作业集（GitHub Pages 静态站）
2. **投稿**自己的作业集（开 GitHub Issue，维护者审核后上线）

GitHub Pages 已计划开启：Settings → Pages → Deploy from a branch → main / (root)。
站点地址将是 `https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/`

## 作业集 JSON 格式（校验和展示都依赖它）

作业集是单个 UTF-8 JSON 文件，顶层结构：

```json
{
  "code": "pvz_20261003_175933",       // 唯一标识（编辑器按时间戳生成，用户可能自定义）
  "name": "火蛇球果",                    // 作业集名称（展示用）
  "version": 1,
  "worlds": ["埃及"],                    // 适用世界，字符串数组
  "max_level": 149,
  "everyN": 10,                          // 循环动作间隔（秒）
  "swipeMs": 300,
  "outer_pick": { "...": "..." },        // 局外选卡配置，对象，可空
  "tables": [                            // ★ 核心：分关卡段的种植策略表，数组，至少 1 张
    {
      "from_level": 1,
      "to_level": 50,
      "lineup": { "plants": ["豌豆射手", "..."] },
      "non_boss": { "once_chain": [], "loop_chain": [], "end_chain": [] },
      "boss": { "...": "..." },
      "endType": "loops",
      "endLoopCount": 15
    }
  ],
  "format": "maapvz-jobset"
}
```

校验时只强依赖：`code`、`name`、`tables`（非空数组）。其余字段可能存在也可能缺。
注意 `tables` 里可能含 `compiled` 大块（预编译产物），文件可能较大（几十 KB 正常，
上限设 2MB 防滥用）。

## 仓库最终结构（你要创建的全部文件）

```
仓库根/
├── index.html                      ← 站点首页（卡片列表 + 搜索）
├── index.json                      ← 作业集清单（Action ② 自动维护，人工勿改）
├── jobs/
│   ├── .gitkeep
│   └── <code>.json                 ← 作业集本体（审核通过后由 Action ① 的 PR 放入）
├── meta/
│   ├── .gitkeep
│   └── <code>.json                 ← 可选 sidecar：{"author": "...", "desc": "..."}
├── tools/
│   ├── build_index.py              ← Action ② 用：扫描 jobs/+meta/ 重建 index.json
│   └── issue_to_pr.py              ← Action ① 用：解析 issue、校验、落盘
├── .github/
│   ├── workflows/
│   │   ├── issue-to-pr.yml         ← Action ①：投稿 Issue → 校验 → 自动开 PR
│   │   └── build-index.yml         ← Action ②：push 到 jobs/** 或 meta/** → 重建索引
│   └── ISSUE_TEMPLATE/
│       └── share-jobset.yml        ← 投稿表单（Issue Form 语法）
└── README.md                       ← 站点说明 + 投稿教程
```

## 详细规格

### 1. index.html（纯静态，无构建步骤，vanilla JS）

- 单文件，内联 CSS/JS，不依赖任何外部框架/CDN（Pages 环境离线可用性优先）
- 加载时 `fetch('index.json')`，渲染卡片网格（CSS Grid，自适应列数）
- 每张卡片显示：**名称**（大字）、code（等宽字体，点击复制）、世界标签、表数量、
  更新时间、作者和简介（有则显示）
- 每张卡片两个按钮：
  - **下载 JSON**：`<a href="jobs/<code>.json" download>` 直链
  - **复制下载链接**：把完整 URL 写剪贴板（`navigator.clipboard`，带成功提示）
- 顶部搜索框：实时过滤（匹配 name / code / author / desc，不区分大小写）
- 顶部显示作业集总数和索引更新时间（index.json 的 `updated` 字段）
- 空状态文案 + index.json 加载失败的错误提示
- 页脚：投稿指引链接（指向本仓库 Issues → New Issue → 投稿模板）
- 中文 UI，深色或简洁风格均可，移动端可读

### 2. index.json 格式（Action ② 生成）

```json
{
  "updated": "2026-10-10T12:34:56Z",
  "count": 2,
  "jobs": [
    {
      "code": "pvz_20261003_175933",
      "name": "火蛇球果",
      "worlds": ["埃及"],
      "tables": 6,
      "max_level": 149,
      "author": "道衍小道",
      "desc": "火蛇球果体系，表3/4收尾循环15次",
      "file": "jobs/pvz_20261003_175933.json",
      "updated": "2026-10-09T20:02:16Z",
      "size": 99123
    }
  ]
}
```

- `author`/`desc` 来自 `meta/<code>.json`（没有 sidecar 就省略这两个字段）
- `jobs` 按 `updated` 倒序
- 文件时间戳用 git 提交时间（`git log -1 --format=%cI -- <file>`），没有 git 历史时
  退化为当前时间

### 3. tools/build_index.py（Action ② 的核心）

- 扫描 `jobs/*.json`（跳过 `.gitkeep`）
- 每个文件：UTF-8（容忍 BOM）解析 → 提取 code（缺失则用文件名）、name、worlds、
  len(tables)、max_level、文件大小
- 若存在 `meta/<code>.json`：合并 author/desc
- 单个文件解析失败：打印警告并跳过（**不能因此让整个 Action 失败**）
- 输出 `index.json`（UTF-8 无 BOM、ensure_ascii=False、缩进 2）
- 纯标准库实现，不需要 pip install 任何东西

### 4. .github/workflows/build-index.yml（Action ②）

```yaml
触发: push，paths: ['jobs/**', 'meta/**']，且排除 index.json 自身（防循环）
权限: contents: write
步骤: checkout → setup-python → python tools/build_index.py
     → 若 index.json 有变化则 commit + push（author 用 github-actions[bot]，
       commit message 形如 "chore: rebuild index.json [skip ci]"）
```

### 5. .github/ISSUE_TEMPLATE/share-jobset.yml（投稿表单）

GitHub Issue Form 语法，字段：
- `body_json`（textarea，必填，label「作业集 JSON」，
  description 提示「在编辑器里导出/复制作业集 JSON，完整粘贴到这里」）
- `author`（input，可选，label「作者昵称」）
- `desc`（input，可选，label「一句话简介」）
- `note`（textarea，可选，label「补充说明（适用世界/关卡范围/注意事项）」）
- 自动加 label：`投稿`

### 6. tools/issue_to_pr.py + issue-to-pr.yml（Action ①，核心安全件）

**触发**：`issues: [opened, edited]`，且 issue 带 `投稿` label。

**tools/issue_to_pr.py 流程**（输入：环境变量里的 issue body / issue number / issue author）：

1. 从 issue body 提取表单各字段（GitHub Issue Form 的 body 是
   `### 字段名\n\n内容` 的 markdown 结构，按 `### ` 分段解析；注意防 `_No response_` 空值）
2. 校验 JSON（任一不过 → 在 issue 下评论错误原因，打 `无效投稿` label，退出码 0
   —— 失败不是 Action 失败，是投稿无效）：
   - 能解析、是 JSON 对象
   - 必有 `code`/`name`/`tables`，`tables` 是非空数组
   - `code` 匹配 `^[A-Za-z0-9_\-]{1,64}$`（★ 防路径注入 `../`，这条是安全红线）
   - 整个 JSON 序列化后 ≤ 2MB
   - `jobs/<code>.json` 不存在（撞车 → 评论提示投稿者改名或联系维护者更新）
3. 校验通过：
   - 写 `jobs/<code>.json`（内容原样格式化落盘，UTF-8 无 BOM）
   - 若 author/desc 非空 → 写 `meta/<code>.json`
   - 用 `peter-evans/create-pull-request` action 或 `gh pr create` 开 PR：
     - 分支名 `submission/<code>-<issue_number>`
     - PR 标题 `投稿：<name>（<code>）`
     - PR body 引用原 issue（`Closes #<issue_number>`）、附校验摘要
   - 在原 issue 评论 PR 链接

**工作流权限**（issue-to-pr.yml）：
```yaml
permissions:
  contents: write
  pull-requests: write
  issues: write
```
★ 安全要求：issue body 是**不可信输入**——
- 绝不把 issue 内容插进 shell 命令（一律通过环境变量或临时文件传给 python）
- code 白名单正则必须先于任何文件路径拼接执行
- PR 内容只含校验过的两个落盘文件，不执行投稿 JSON 里的任何内容

### 7. README.md

- 站点地址、截图占位
- 「下载作业集」教程：站点卡片下载 → MAAPVZ 编辑器里导入
- 「投稿」教程：New Issue → 投稿模板 → 粘 JSON → 等审核 → merge 后自动上站
- 维护者手册：手动上架（直接往 jobs/ 丢文件推送，Action ② 自动建索引）、
  如何修改作者/简介（改 meta/<code>.json）、如何下架（删 jobs/<code>.json 推送）
- 文件格式说明（作业集 JSON 顶层字段表）

### 8. 维护者前置设置（README 里也要写）

- Settings → Pages → Deploy from a branch → main / (root)
- Settings → Actions → General → Workflow permissions → Read and write permissions
- Settings → Issues 保持开启（投稿入口）

## 验收清单（全部完成才算交付）

- [ ] index.html 在本地用浏览器直接打开（file:// 会因 fetch 失败，需说明用
      `python -m http.server` 测试）能渲染卡片、搜索、复制链接
- [ ] 手动放一个示例作业集到 jobs/ 并跑 `python tools/build_index.py`，
      index.json 生成正确（含 meta 合并）
- [ ] build-index.yml 的 paths 过滤和 [skip ci] 防循环逻辑正确
- [ ] issue_to_pr.py 对以下输入行为正确：
      - 合法 JSON → 落盘 + 开 PR
      - 缺 tables → 评论报错 + 无效 label，不开 PR
      - code 含 `../` → 拒绝
      - code 撞车 → 评论提示
      - 超过 2MB → 拒绝
- [ ] README 包含完整的用户教程和维护者手册
- [ ] 全仓无外部 CDN 依赖，纯标准库 python，YAML 语法有效

## 风格要求

- 所有面向用户的中文文案简洁直白
- 代码注释用中文，关键安全点（路径注入、不可信输入）加 ★ 标记注释
- python 文件 UTF-8 无 BOM，LF 行尾；不要引入任何 pip 依赖
