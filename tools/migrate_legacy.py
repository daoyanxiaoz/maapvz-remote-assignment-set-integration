#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧版平铺 jobs/*.json → 新版目录树 jobs/<分组>/<作业集>/<日期>/ 的一次性迁移。

    python tools/migrate_legacy.py            # 预演（只打印会怎么搬）
    python tools/migrate_legacy.py --apply    # 真的搬

规则：
- 分组默认取作业集的主世界（没有世界 → 未分组），之后可以随时改目录名；
- 作业集目录名 = 作业集显示名，重名自动加 code 后缀区分；
- 版本目录 = 该文件最后一次 git 提交日期（没有 git 历史则用文件修改时间）；
- 作者信息：作业集 JSON 里有 author 字段就写一份 作者.txt，没有就留空（页面显示未知作者）。
"""

import os
import shutil
import sys

import joblib


def target_for(path, data):
    fields = joblib.job_fields(data)
    group = joblib.sanitize_component(fields.get("world_primary") or "未分组", "未分组")
    job = joblib.sanitize_component(fields.get("name") or os.path.splitext(os.path.basename(path))[0], "未命名作业集")
    date = (joblib.git_last_commit_time(path) or joblib.file_mtime_iso(path))[:10]
    job_dir = os.path.join(joblib.JOBS_DIR, group, job)
    if os.path.isdir(job_dir) and any(
        os.path.isdir(os.path.join(job_dir, d)) for d in os.listdir(job_dir)
    ):
        # 同组内重名 → 用 code 后缀区分
        code = joblib.sanitize_component(fields.get("code") or "dup", "dup")
        job_dir = os.path.join(joblib.JOBS_DIR, group, "%s（%s）" % (job, code))
    return job_dir, date, fields


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    apply_changes = "--apply" in argv
    if not os.path.isdir(joblib.JOBS_DIR):
        print("[warn] jobs/ 不存在")
        return 1

    moved = 0
    for fname in sorted(os.listdir(joblib.JOBS_DIR)):
        path = os.path.join(joblib.JOBS_DIR, fname)
        if not os.path.isfile(path) or not fname.lower().endswith(".json"):
            continue
        try:
            data = joblib.load_json_file(path)
        except Exception as e:
            print("[warn] 跳过 %s（不是合法 JSON：%s）" % (fname, e))
            continue
        if not joblib.looks_like_job(data):
            print("[warn] 跳过 %s（不像作业集）" % fname)
            continue

        job_dir, date, fields = target_for(path, data)
        target_dir = os.path.join(job_dir, date)
        target = os.path.join(target_dir, joblib.sanitize_component(os.path.splitext(fname)[0], "作业集") + ".json")
        print("%s\n  → %s" % (os.path.relpath(path, joblib.ROOT),
                              os.path.relpath(target, joblib.ROOT)))
        if not apply_changes:
            continue

        os.makedirs(target_dir, exist_ok=True)
        if os.path.exists(target):
            print("  ！目标已存在，跳过")
            continue
        shutil.move(path, target)
        author = fields.get("author")
        if isinstance(author, str) and author.strip():
            joblib.write_text_file(os.path.join(target_dir, "作者.txt"), author.strip())
        moved += 1

    if apply_changes:
        print("[ok] 已迁移 %d 个作业集，接下来运行：python tools/build_index.py" % moved)
    else:
        print("[dry-run] 加 --apply 才会真的搬文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
