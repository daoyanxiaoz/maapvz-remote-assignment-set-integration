#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 jobs/ 目录树，重建站点索引 index.json。

用法：
    python tools/build_index.py            # 重建索引
    python tools/build_index.py --quiet    # 只在有变化时说话（Action 用）

约定见 tools/joblib.py 顶部注释：jobs/<分组>/<作业集>/<版本日期>/<作业集文件 + 作者.txt>。
本脚本不读任何手写清单——**目录树就是真相**，所以新人只要把文件拖进目录即可上架。

- 纯标准库，无 pip 依赖
- 单个作业集解析失败只警告并跳过，绝不让整个 Action 失败
- 输出 UTF-8 无 BOM、ensure_ascii=False、缩进 2、LF
"""

import json
import os
import sys

import joblib


def iso_of(path, fallback_date):
    """版本时间：优先 git 最后提交时间，退化为文件修改时间 / 版本目录日期。"""
    ts = joblib.git_last_commit_time(path)
    if ts:
        return ts
    if os.path.isfile(path):
        return joblib.file_mtime_iso(path)
    return (fallback_date or joblib.today_label()) + "T00:00:00Z"


def build_entries():
    entries = []
    total_versions = 0
    group_names = {g["id"]: g["name"] for g in joblib.list_groups()}
    for rec in joblib.scan_jobs():
        versions = rec["versions"]
        if not versions:
            continue
        latest = versions[0]
        try:
            fields = latest["fields"]
        except Exception as e:  # 理论上 scan 已经解析过，这里只是兜底
            print("[warn] 跳过 %s：%s" % (rec["dir"], e))
            continue

        entry = {
            "id": "/".join(p for p in (rec["group"], rec["job"]) if p),
            "group": rec["group"],
            "group_name": group_names.get(rec["group"], rec["group"]),
            "name": fields.get("name") or rec["job"],
            "dir": rec["dir"],
            "code": fields.get("code") or "",
            "date": latest["date"],
            "updated": iso_of(os.path.join(joblib.ROOT, latest["file"]), latest["date"]),
            "version_count": len(versions),
            "versions": [],
        }
        entry["authors"] = list(latest.get("authors") or fields.get("authors") or [])
        entry["author"] = "、".join(entry["authors"])

        for v in versions:
            vf = v["fields"]
            v_authors = list(v.get("authors") or vf.get("authors") or [])
            entry["versions"].append({
                "label": v["label"],
                "date": v["date"],
                "file": v["file"],
                "name": vf.get("name") or rec["job"],
                "code": vf.get("code") or "",
                "authors": v_authors,
                "author": "、".join(v_authors),
                "note": v["note"] or vf.get("desc") or "",
                "size": v["size"],
            })
            total_versions += 1

        # 其余字段（世界/植物/覆盖/标签…）沿用旧版卡片契约，只取最新版本
        for key, value in fields.items():
            if key in ("name", "code", "author", "authors", "desc"):
                continue
            entry[key] = value
        if fields.get("desc"):
            entry["desc"] = fields["desc"]

        entries.append(entry)

    entries.sort(key=lambda e: (e["updated"], e["id"]), reverse=True)
    return entries, total_versions


def build_groups(entries):
    """分组由目录推导，_group.json 只用来补名字/简介/排序。"""
    by_id = {}
    for meta in joblib.list_groups():
        by_id[meta["id"]] = {
            "id": meta["id"],
            "name": meta["name"],
            "desc": meta["desc"],
            "icon": meta["icon"],
            "order": meta["order"],
            "count": 0,
            "version_count": 0,
            "updated": "",
            "jobs": [],
        }
    for e in entries:
        if not e["group"]:
            continue  # 不归入阵型的作业集只在「全部」里出现
        g = by_id.setdefault(e["group"], {
            "id": e["group"], "name": e["group"], "desc": "", "icon": "",
            "order": 999, "count": 0, "version_count": 0, "updated": "", "jobs": [],
        })
        g["count"] += 1
        g["version_count"] += e["version_count"]
        g["jobs"].append(e["id"])
        if e["updated"] > g["updated"]:
            g["updated"] = e["updated"]
    groups = [g for g in by_id.values() if g["count"]]
    groups.sort(key=lambda g: (-g["count"], g["order"], g["id"]))
    return groups


def build_index():
    entries, total_versions = build_entries()
    return {
        "schema": joblib.SCHEMA,
        "updated": joblib.now_iso(),
        "count": len(entries),
        "version_count": total_versions,
        "groups": build_groups(entries),
        "jobs": entries,
    }


def write_index(index, quiet=False):
    """落盘；内容没变就不动文件（避免 Action 空提交 / 无意义 diff）。"""
    old = None
    if os.path.isfile(joblib.INDEX_FILE):
        try:
            with open(joblib.INDEX_FILE, "r", encoding="utf-8") as f:
                old = json.load(f)
        except Exception:
            old = None
    payload = dict(index)
    if old:
        # 只比内容，不比 generated 时间戳
        a, b = dict(old), dict(payload)
        a.pop("updated", None)
        b.pop("updated", None)
        if a == b:
            if not quiet:
                print("[ok] index.json 无变化")
            return False
    joblib.dump_json_file(joblib.INDEX_FILE, payload)
    print("[ok] index.json 已更新：%d 个作业集 / %d 个版本 / %d 个分组"
          % (payload["count"], payload["version_count"], len(payload["groups"])))
    return True


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    index = build_index()
    write_index(index, quiet="--quiet" in argv)
    return 0


if __name__ == "__main__":
    sys.exit(main())
