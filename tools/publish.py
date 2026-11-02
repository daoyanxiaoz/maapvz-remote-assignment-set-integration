#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地维护者的上架命令：把一份作业集文件直接放进 jobs/<分组>/<作业集>/<日期>/。

    python tools/publish.py 作业集.json --group 心塔 --author 站长
    python tools/publish.py 作业集.json --group 心塔 --job 失落原大火龙果 --date 2026-10-31 --note "41 关换双机枪"
    python tools/publish.py --list                 # 看仓库里现在有哪些分组 / 作业集

不带 --job 时用作业集自带的 name 作目录名；已存在的同名作业集会自动成为新版本。
跑完记得 git add / commit / push（推送由有仓库权限的人执行）。
"""

import argparse
import json
import os
import sys

import build_index
import joblib


def cmd_list():
    groups = {g["id"]: g for g in joblib.list_groups()}
    if not groups and not os.path.isdir(joblib.JOBS_DIR):
        print("还没有 jobs/ 目录")
        return 0
    for rec in joblib.scan_jobs():
        g = groups.get(rec["group"], {"name": rec["group"]})
        print("%s\t%s\t%d 个版本\t最新 %s" % (
            g["name"], rec["job"], len(rec["versions"]), rec["versions"][0]["label"]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="把作业集文件上架到 jobs/ 目录树")
    parser.add_argument("file", nargs="?", help="作业集 JSON 文件路径")
    parser.add_argument("--group", help="总分组（不存在会自动创建），默认用主世界")
    parser.add_argument("--job", help="作业集名（目录名），默认用作业集自带 name")
    parser.add_argument("--author", default="", help="作者名，多人用、分开（写进 作者.txt，一行一个）")
    parser.add_argument("--date", default="", help="版本日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--note", default="", help="这一版改了什么，写进 说明.txt")
    parser.add_argument("--list", action="store_true", help="列出仓库现有分组 / 作业集")
    args = parser.parse_args(argv)

    if args.list:
        return cmd_list()
    if not args.file:
        parser.print_help()
        return 2

    path = args.file
    if not os.path.isfile(path):
        print("[error] 文件不存在：%s" % path)
        return 1
    text = joblib.read_text(path)
    try:
        data = joblib.load_json_text(text)
    except Exception as e:
        print("[error] 不是合法 JSON：%s" % e)
        return 1
    if not joblib.looks_like_job(data):
        print("[error] 看起来不是作业集（缺少 tables / code）")
        return 1

    fields = joblib.job_fields(data, fallback_name=os.path.splitext(os.path.basename(path))[0])
    group = args.group or ""          # 不传 --group 就「不归入阵型」
    job = args.job or fields.get("name") or os.path.splitext(os.path.basename(path))[0]
    date = joblib.date_label_from(args.date) or joblib.today_label()

    # ★ 上架强制规整：自动选卡 + 固定植物 + 不允许编队序号（deck）
    changes, problems = joblib.enforce_upload_rules(data)
    if problems:
        print("[error] 不能用编队序号（deck），别人复现不了：%s" % "；".join(problems))
        print("        请在编辑器里改成「选卡」后再导出。")
        return 1
    if changes:
        for c in changes:
            print("[fix] %s" % c)
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    target = joblib.place_version(group, job, date, os.path.basename(path),
                                 text, args.author, args.note)
    rel = os.path.relpath(target, joblib.ROOT).replace(os.sep, "/")
    print("[ok] 已上架 → %s" % rel)

    index = build_index.build_index()
    build_index.write_index(index)
    print("     下一步：git add -A && git commit -m \"feat: 上架 %s\" && git push" % job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
