# inbox/ —— 上架包投递口

维护者把 <https://daoyanxiaoz.github.io/maapvz-remote-assignment-set-integration/publish.html> 生成的
`*.bundle.json` 传到这里，GitHub Actions（`apply-inbox.yml`）会自动：

1. 校验上架包；
2. 把作业集写进 `jobs/<分组>/<作业集>/<版本日期>/`，并补上 `作者.txt` / `说明.txt`；
3. 删掉已处理的上架包；
4. 重建 `index.json` 并提交。

## 怎么传（无需命令行）

1. 在 GitHub 网页打开本仓库 → `inbox` 文件夹；
2. **Add file → Upload files**；
3. 选中你下载的上架包 → **Commit changes**；
4. 等 1~2 分钟，刷新站点首页。

## 本地也能跑

```powershell
python -X utf8 tools/apply_inbox.py                        # 处理 inbox/ 里全部上架包
python -X utf8 tools/apply_inbox.py --dry-run              # 只看会写到哪里
python -X utf8 tools/apply_inbox.py 某个上架包.bundle.json  # 只处理指定文件
```

> 上架包是纯文本 JSON（作业集内容 base64 放在 `content_b64` 里），不会被执行。
> 校验失败的上架包会留在 `inbox/` 里并在 Actions 日志里报原因，删掉重传即可。
