#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把仓库里已有的作业集统一规整成「自动选卡 + 固定植物」。

    python tools/normalize_jobs.py            # 预演：只列出会改什么
    python tools/normalize_jobs.py --apply    # 真改写文件并重建索引

规整规则（与上架通道完全一致，见 tools/joblib.py 的 normalize_job）：
  - tables 里的 lineup.deck（编队序号）不动，只处理局外选卡；
  - outer_pick.mode = "auto"；
  - outer_pick.plants = 本作业集阵容实际用到的植物（保序去重）。

原始文件在 git 历史里都有，改坏了可以 git checkout 回来。
"""

import json
import os
import sys

import build_index
import joblib


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    apply_changes = "--apply" in argv
    touched = 0
    seen_jobs = 0

    for rec in joblib.scan_jobs():
        seen_jobs += 1
        for v in rec["versions"]:
            path = os.path.join(joblib.ROOT, v["file"])
            text = joblib.read_text(path)
            try:
                data = joblib.load_json_text(text)
            except Exception as e:
                print("[warn] %s 解析失败，跳过：%s" % (v["file"], e))
                continue
            changes = joblib.normalize_job(data)
            if not changes:
                continue
            touched += 1
            print("%s/%s @ %s" % (rec["group"], rec["job"], v["label"]))
            for c in changes:
                print("    - %s" % c)
            if apply_changes:
                new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
                joblib.write_text_file(path, new_text)

    if not touched:
        print("[ok] %d 个作业集全部已符合「自动选卡 + 固定植物」，无需改动" % seen_jobs)
        return 0

    if not apply_changes:
        print("[dry-run] 共 %d 个版本需要规整；加 --apply 才会真的写文件" % touched)
        return 0

    index = build_index.build_index()
    build_index.write_index(index)
    print("[ok] 已规整 %d 个版本文件，索引已重建" % touched)
    return 0


if __name__ == "__main__":
    sys.exit(main())
