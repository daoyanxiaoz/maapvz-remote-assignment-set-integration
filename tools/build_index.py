#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描 jobs/ 与 meta/，重建站点索引 index.json（Action ② 的核心）。

用法：
    python tools/build_index.py

说明：
    - 纯标准库，无需 pip install
    - 单个作业集解析失败只警告并跳过，绝不让整个 Action 失败
    - 输出 UTF-8 无 BOM、ensure_ascii=False、缩进 2
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "jobs")
META_DIR = os.path.join(ROOT, "meta")
OUT_FILE = os.path.join(ROOT, "index.json")

# ★ 与投稿校验同一套白名单：拼 meta 文件路径前必须先过这道关
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json_tolerant(path):
    """UTF-8 读取，容忍 BOM。"""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def git_last_commit_time(path):
    """取文件最近一次 git 提交时间（UTC，Z 结尾）；没有 git 历史时退化为当前时间。"""
    try:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=ROOT, capture_output=True, text=True, timeout=10,
        )
        ts = out.stdout.strip()
        if out.returncode == 0 and ts:
            dt = datetime.fromisoformat(ts)
            return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return now_iso()


def build_entry(path, fname):
    """解析单个作业集文件，返回索引条目；失败抛异常由调用方捕获。"""
    data = load_json_tolerant(path)
    if not isinstance(data, dict):
        raise ValueError("顶层不是 JSON 对象")

    code = data.get("code")
    if not isinstance(code, str) or not code:
        code = os.path.splitext(fname)[0]  # 缺 code 时用文件名兜底

    tables = data.get("tables")
    worlds = data.get("worlds")

    entry = {
        "code": code,
        "name": data.get("name") or code,
        "worlds": [str(w) for w in worlds] if isinstance(worlds, list) else [],
        "tables": len(tables) if isinstance(tables, list) else 0,
        "file": "jobs/" + fname,
        "updated": git_last_commit_time(path),
        "size": os.path.getsize(path),
    }
    if isinstance(data.get("max_level"), (int, float)):
        entry["max_level"] = data["max_level"]

    # 合并 sidecar 作者/简介（meta/<code>.json）
    if CODE_RE.match(code):
        meta_path = os.path.join(META_DIR, code + ".json")
        if os.path.isfile(meta_path):
            try:
                meta = load_json_tolerant(meta_path)
                if isinstance(meta, dict):
                    if meta.get("author"):
                        entry["author"] = str(meta["author"])
                    if meta.get("desc"):
                        entry["desc"] = str(meta["desc"])
            except Exception as e:
                print(f"[warn] meta/{code}.json 解析失败，忽略 sidecar：{e}")
    return entry


def main():
    entries = []
    if not os.path.isdir(JOBS_DIR):
        print(f"[warn] 目录不存在：{JOBS_DIR}")
    else:
        for fname in sorted(os.listdir(JOBS_DIR)):
            if not fname.lower().endswith(".json"):
                continue  # 跳过 .gitkeep 等
            path = os.path.join(JOBS_DIR, fname)
            try:
                entries.append(build_entry(path, fname))
            except Exception as e:
                # ★ 单个文件坏了不能拖垮整个 Action
                print(f"[warn] 解析失败，已跳过 jobs/{fname}：{e}")

    # 按更新时间倒序
    entries.sort(key=lambda e: e["updated"], reverse=True)

    index = {
        "updated": now_iso(),
        "count": len(entries),
        "jobs": entries,
    }
    with open(OUT_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[ok] index.json 已生成，共 {len(entries)} 个作业集")


if __name__ == "__main__":
    main()
