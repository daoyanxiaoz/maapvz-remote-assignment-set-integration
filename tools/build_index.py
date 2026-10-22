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


def collect_plants(jobset):
    """作业集全量植物名（保序去重）：
    lineup.plants ∪ boss_lineup.plants ∪ boardEarly/boardLate 中 type=plant 的格子。
    （不含 outer_pick.plants —— 那是局外选卡候选池，auto 模式能灌 80 个，
      不是真实阵容。）
    与 tools/issue_to_pr.py 的 collect_plants 同一口径。"""
    names = []
    seen = set()

    def add(n):
        if isinstance(n, str) and n and n not in seen:
            seen.add(n)
            names.append(n)

    for t in jobset.get("tables") or []:
        if not isinstance(t, dict):
            continue
        for key in ("lineup", "boss_lineup"):
            lu = t.get(key)
            if isinstance(lu, dict):
                for p in lu.get("plants") or []:
                    add(p)
        for bkey in ("boardEarly", "boardLate"):
            board = t.get(bkey)
            if not isinstance(board, list):
                continue
            for row in board:
                if not isinstance(row, list):
                    continue
                for cell in row:
                    entries = cell.get("value") if isinstance(cell, dict) else None
                    if not isinstance(entries, list):
                        continue
                    for ent in entries:
                        if isinstance(ent, dict) and ent.get("type") == "plant":
                            plant = ent.get("plant") if isinstance(ent.get("plant"), dict) else {}
                            add(ent.get("label") or plant.get("name"))
    return names


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

    # 关卡覆盖（图层模型：levels 是权威覆盖，空则退化为 [from_level, to_level) 区间；
    # to_level 为 None 表示到 MAX）
    coverage = []
    plants_max = 0
    if isinstance(tables, list):
        for t in tables:
            if not isinstance(t, dict):
                continue
            cov = {}
            if isinstance(t.get("from_level"), (int, float)):
                cov["from"] = t["from_level"]
            cov["to"] = t["to_level"] if isinstance(t.get("to_level"), (int, float)) else None
            if isinstance(t.get("levels"), list) and t["levels"]:
                cov["levels"] = t["levels"]
            if cov.get("from") is not None:
                coverage.append(cov)
            lu = t.get("lineup")
            if isinstance(lu, dict) and isinstance(lu.get("plants"), list):
                plants_max = max(plants_max, len([p for p in lu["plants"] if p]))
    if coverage:
        entry["coverage"] = coverage
    if plants_max:
        entry["plants_max"] = plants_max

    # 局外选卡模式（auto=自动选卡）
    op = data.get("outer_pick")
    if isinstance(op, dict) and op.get("mode"):
        entry["outer_pick"] = str(op["mode"])

    # 从第一张表提取阵容植物和神器（首页卡片图标条 / 详情页用）
    if isinstance(tables, list) and tables and isinstance(tables[0], dict):
        first = tables[0]
        lineup = first.get("lineup")
        if isinstance(lineup, dict) and isinstance(lineup.get("plants"), list):
            plants = [str(p) for p in lineup["plants"] if p]
            if plants:
                entry["plants"] = plants[:8]  # 8 个槽位封顶
        if first.get("artifact"):
            entry["artifact"] = str(first["artifact"])
        if first.get("artifact_en"):
            entry["artifact_en"] = str(first["artifact_en"])
        # 收尾方式徽标（术语与编辑器同源）
        et = first.get("endType")
        if et == "detect":
            entry["end_desc"] = "识别收尾"
        elif et == "loops":
            entry["end_desc"] = "循环×%s收尾" % (first.get("endLoopCount") or "?")
        elif et == "once":
            entry["end_desc"] = "单次收尾"
        # 补给优先序（只留 id+name，图标站点按 id 自己映射）
        sp = first.get("supplyPicks")
        if isinstance(sp, list):
            supply = [
                {"id": str(s.get("id")), "name": str(s.get("name", s.get("id")))}
                for s in sp if isinstance(s, dict) and s.get("id")
            ]
            if supply:
                entry["supply"] = supply

    # 全量植物集合（阵容 ∪ boss 阵容 ∪ 棋盘格子，保序去重）——筛选和装扮统计用
    all_plants = collect_plants(data)
    if all_plants:
        entry["plants"] = all_plants  # 覆盖上面的首表槽位（全量 ⊇ 槽位）

    # 合并 sidecar 作者/简介/装扮标注（meta/<code>.json）
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
                    # 装扮聚合：none=全不需要 / required=含需装扮（供主页筛选）
                    pc = meta.get("plant_costumes")
                    if isinstance(pc, dict) and pc:
                        entry["costume"] = "required" if any(pc.values()) else "none"
            except Exception as e:
                print(f"[warn] meta/{code}.json 解析失败，忽略 sidecar：{e}")
    # 作业集内 plant_notes 的装扮标注也参与聚合（新版编辑器导出）
    notes = data.get("plant_notes")
    if isinstance(notes, dict) and "costume" not in entry:
        if any(isinstance(v, dict) and v.get("costume") for v in notes.values()):
            entry["costume"] = "required"
        elif notes:
            entry["costume"] = "none"
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
