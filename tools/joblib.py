#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""joblib.py —— 作业集仓库的底层约定（全站点唯一真相源）。

目录约定（分三层，全部可自动发现，不需要人工维护索引）：

    jobs/
      心塔/                              ← 总分组（同类型作业集放一起）
        _group.json                      ← 可选：分组元数据 {name, desc, order, icon}
        失落原大火龙果/                    ← 作业集（一次新建 = 一个目录）
          2026-10-19/                    ← 版本目录（创建日期，建议 YYYY-MM-DD）
            失落原大火龙果.json            ← 作业集本体（编辑器导出，.json 或 .txt 均可）
            作者.txt                       ← 作者名（首行有效）
            说明.txt                       ← 可选：这一版改了什么

兼容写法（不用重排也能被认出来）：
    jobs/未分组/某个作业集.json            → 分组 + 单版本
    jobs/某个作业集.json                   → 未分组 + 单版本

本文件只依赖标准库，供 build_index.py / apply_inbox.py / publish.py 共用。
"""

import json
import os
import re
import subprocess
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "jobs")
INDEX_FILE = os.path.join(ROOT, "index.json")
INBOX_DIR = os.path.join(ROOT, "inbox")

SCHEMA = 2
BUNDLE_FORMAT = "maapvz-jobset-bundle"

# 文件名/目录名里不允许出现的字符（Windows 最严格，GitHub 也能接受）
ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')
DATE_RE = re.compile(r"(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})")
AUTHOR_HINTS = ("作者", "author", "作者名")
NOTE_HINTS = ("说明", "备注", "更新", "note", "desc", "介绍")
JOB_EXTS = (".json", ".txt")
# 一行里多个作者的分隔符：逗号 / 顿号 / 斜杠 / 分号 / 竖线
AUTHOR_SPLIT_RE = re.compile(r"[,，、/;；|]+")
AUTHOR_PREFIX_RE = re.compile(r"^(作者|author|作者名)\s*[:：]\s*", re.I)


# ---------------------------------------------------------------- 基础工具

def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_label():
    return datetime.now().strftime("%Y-%m-%d")


def read_text(path):
    """读取文本文件：容忍 BOM、GBK 兜底（老站长的记事本）。"""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def load_json_text(text):
    """宽容地解析 JSON 文本：容忍 BOM、前后空白、尾部多余逗号。"""
    text = text.lstrip("\ufeff").strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    # 兜底：去掉对象/数组尾部多余逗号再试一次
    patched = re.sub(r",(\s*[}\]])", r"\1", text)
    return json.loads(patched)


def load_json_file(path):
    return load_json_text(read_text(path))


def dump_json_file(path, data, indent=2):
    """统一落盘格式：UTF-8 无 BOM、LF、ensure_ascii=False。

    先写临时文件再 os.replace —— 就算同时开了维护工具 + 预览工具两个进程，
    也不会出现「写一半被读到」的坏 JSON。
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
        f.write("\n")
    os.replace(tmp, path)


def write_text_file(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, path)


def sanitize_component(name, fallback="未命名"):
    """目录名清洗：去掉非法字符、首尾空格/点、限长。中文原样保留。"""
    s = ILLEGAL_CHARS.sub("", str(name or "")).strip().strip(".")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        s = fallback
    return s[:48]


def unique_dir(parent, name):
    """在 parent 下取一个不冲突的目录名（重名自动加 _2、_3…）。"""
    candidate = name
    i = 2
    while os.path.exists(os.path.join(parent, candidate)):
        candidate = "%s_%d" % (name, i)
        i += 1
    return candidate


def git_last_commit_time(path):
    """取文件最近一次 git 提交时间（UTC，Z 结尾）；没有 git 历史时返回 None。"""
    try:
        rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", rel],
            cwd=ROOT, capture_output=True, text=True, timeout=15,
        )
        ts = out.stdout.strip()
        if out.returncode == 0 and ts:
            return datetime.fromisoformat(ts).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass
    return None


def file_mtime_iso(path):
    try:
        return datetime.fromtimestamp(os.path.getmtime(path), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return now_iso()


def date_label_from(label):
    """从版本目录名里抽日期：2026-10-19 / 2026_10_19 / 20261019 → 2026-10-19。"""
    m = DATE_RE.search(str(label or ""))
    if not m:
        return None
    y, mo, d = m.group(1), m.group(2), m.group(3)
    try:
        datetime(int(y), int(mo), int(d))
    except ValueError:
        return None
    return "%s-%s-%s" % (y, mo, d)


def parse_authors(value):
    """作者可以多人：一行一个，或用 、 , ， / ; | 分隔，也接受数组。

    "导演小z、某某" / ["导演小z", "某某"] / 多行文本 → ["导演小z", "某某"]
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        out = []
        for item in value:
            for name in parse_authors(item):
                if name not in out:
                    out.append(name)
        return out

    out = []
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    for line in text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):   # # 开头的整行是注释（模板/说明用）
            continue
        line = AUTHOR_PREFIX_RE.sub("", line)
        for chunk in AUTHOR_SPLIT_RE.split(line):
            name = chunk.strip().strip("·").strip()
            if name and name not in out:
                out.append(name)
    return out


def author_text(authors):
    """作者列表 → 写进 作者.txt 的文本（一行一个，方便人看和手改）。"""
    return "\n".join(parse_authors(authors))


# ---------------------------------------------------------------- 作业集解析

def looks_like_job(data):
    """一个 JSON 是不是作业集：有 tables 数组，或有 code 字符串。"""
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("tables"), list):
        return True
    code = data.get("code")
    return isinstance(code, str) and bool(code.strip())


def collect_plants(jobset):
    """作业集全量植物名（保序去重）：
    lineup.plants ∪ boss_lineup.plants ∪ boardEarly/boardLate 中 type=plant 的格子。
    （不含 outer_pick.plants —— 那是局外选卡候选池，auto 模式能灌 80 个，不是真实阵容。）"""
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


def job_fields(data, fallback_name="未命名作业集"):
    """把作业集 JSON 压成站点要用的字段（与旧版 index.json 字段保持兼容）。"""
    if not isinstance(data, dict):
        raise ValueError("顶层不是 JSON 对象")

    code = data.get("code")
    if not isinstance(code, str) or not code.strip():
        code = ""
    code = code.strip()

    tables = data.get("tables")
    name = data.get("name")
    name = str(name).strip() if isinstance(name, str) and name.strip() else fallback_name

    # 世界：兼容三代格式（旧 worlds / 新 world + sub_worlds），语义去重留全名
    worlds = []

    def add_w(x):
        s = str(x).strip() if x is not None else ""
        if not s:
            return
        for i, e in enumerate(worlds):
            if e == s:
                return
            if e in s or s in e:
                if len(s) > len(e):
                    worlds[i] = s
                return
        worlds.append(s)

    if isinstance(data.get("worlds"), list):
        for x in data["worlds"]:
            add_w(x)
    primary = data.get("world")
    if isinstance(primary, str):
        add_w(primary)
    if isinstance(data.get("sub_worlds"), list):
        for x in data["sub_worlds"]:
            add_w(x)

    out = {
        "code": code,
        "name": name,
        "worlds": worlds,
        "world_primary": primary.strip() if isinstance(primary, str) and primary.strip() else None,
        "tables": len(tables) if isinstance(tables, list) else 0,
    }
    if not out["world_primary"] and worlds:
        out["world_primary"] = worlds[0]

    if isinstance(data.get("tags"), list):
        tags = [str(t).strip() for t in data["tags"]
                if isinstance(t, (str, int, float)) and str(t).strip()]
        if tags:
            out["tags"] = tags

    for key in ("max_level", "everyN"):
        if isinstance(data.get(key), (int, float)):
            out[key] = data[key]

    # 关卡覆盖（图层模型：levels 权威，空则退化为 [from_level, to_level)）
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
        out["coverage"] = coverage
    if plants_max:
        out["plants_max"] = plants_max

    if isinstance(data.get("outer_pick"), dict) and data["outer_pick"].get("mode"):
        out["outer_pick"] = str(data["outer_pick"]["mode"])

    if isinstance(tables, list) and tables and isinstance(tables[0], dict):
        first = tables[0]
        lu = first.get("lineup")
        if isinstance(lu, dict) and isinstance(lu.get("plants"), list):
            plants = [str(p) for p in lu["plants"] if p]
            if plants:
                out["plants"] = plants[:8]
        if first.get("artifact"):
            out["artifact"] = str(first["artifact"])
        if first.get("artifact_en"):
            out["artifact_en"] = str(first["artifact_en"])
        et = first.get("endType")
        if et == "detect":
            out["end_desc"] = "识别收尾"
        elif et == "loops":
            out["end_desc"] = "循环×%s收尾" % (first.get("endLoopCount") or "?")
        elif et == "once":
            out["end_desc"] = "单次收尾"
        sp = first.get("supplyPicks")
        if isinstance(sp, list):
            supply = [{"id": str(s.get("id")), "name": str(s.get("name", s.get("id")))}
                      for s in sp if isinstance(s, dict) and s.get("id")]
            if supply:
                out["supply"] = supply

    all_plants = collect_plants(data)
    if all_plants:
        out["plants"] = all_plants

    # 装扮聚合：plant_notes 里任一 costume=true → required；有标注但都不需要 → none
    notes = data.get("plant_notes")
    if isinstance(notes, dict) and notes:
        if any(isinstance(v, dict) and v.get("costume") for v in notes.values()):
            out["costume"] = "required"
        else:
            out["costume"] = "none"
    if isinstance(data.get("desc"), str) and data["desc"].strip():
        out["desc"] = data["desc"].strip()
    if isinstance(data.get("author"), (str, list)):
        authors = parse_authors(data.get("author"))
        if authors:
            out["authors"] = authors
    return out


# ---------------------------------------------------------------- 作业集规整

def normalize_job(data):
    """强制统一成「自动选卡 + 固定植物」的局外选卡配置。

    维护者口径（对所有上架作业集一律强制执行）：
      - `outer_pick.mode` 恒为 `auto`：别人导入后不需要手点「确认选卡」；
      - `outer_pick.plants` 恒为**本作业集阵容实际用到的植物**（保序去重），
        既不是空池（confirm 时代留下的 `[]`），也不是编辑器里的 80 株全量池。

    返回改动说明列表；空列表表示本来就是合规的。
    """
    changes = []
    if not isinstance(data, dict):
        return changes

    plants = collect_plants(data)
    op = data.get("outer_pick")
    if not isinstance(op, dict):
        op = {}
        data["outer_pick"] = op
        changes.append("outer_pick 缺失，已补建")

    old_mode = op.get("mode")
    if old_mode != "auto":
        op["mode"] = "auto"
        changes.append("mode %s → auto" % (old_mode if old_mode else "(空)"))

    old_plants = op.get("plants")
    old_list = old_plants if isinstance(old_plants, list) else []
    if plants and old_list != plants:
        op["plants"] = plants
        changes.append("plants %d 株 → %d 株（固定植物）" % (len(old_list), len(plants)))
    return changes


def prepare_job_text(text, normalize=True):
    """上架前的统一加工：解析 → 强制自动选卡/固定植物 → 需要时重新序列化。

    返回 (data, new_text, changes)；没有改动时 new_text 原样返回（不动原文件格式）。
    """
    data = load_json_text(text)
    changes = normalize_job(data) if normalize else []
    new_text = text
    if changes:
        new_text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return data, new_text, changes


DECK_LINEUP_KEYS = ("lineup", "boss_lineup")


def strip_decks(data):
    """去掉 tables[].lineup.deck / boss_lineup.deck（编队序号只在作者本机有效，别人复现不了）。

    返回 (changes, problems)：
      - 表里已经有 plants（显式选卡）→ 直接去掉 deck，记一条 change；
      - 只有 deck、没有 plants → 记一条 problem（没法自动转，需要在编辑器里改成选卡再导出）。
    """
    changes, problems = [], []
    tables = data.get("tables") if isinstance(data, dict) else None
    if not isinstance(tables, list):
        return changes, problems
    for i, t in enumerate(tables, 1):
        if not isinstance(t, dict):
            continue
        for key in DECK_LINEUP_KEYS:
            lu = t.get(key)
            if not isinstance(lu, dict) or not lu.get("deck"):
                continue
            plants = [p for p in (lu.get("plants") or []) if isinstance(p, str) and p.strip()]
            if plants:
                lu["deck"] = None
                changes.append("表%d %s：去掉编队序号（已有选卡）" % (i, key))
            else:
                problems.append("表%d %s：只有编队序号（deck），没有选卡植物" % (i, key))
    return changes, problems


def enforce_upload_rules(data):
    """上架统一规整：自动选卡 + 局外固定植物 + 不允许编队序号。

    返回 (changes, problems)。problems 非空 → 这套作业集别人复现不了，上架应拒绝并提示作者。
    """
    changes = normalize_job(data)
    deck_changes, problems = strip_decks(data)
    return changes + deck_changes, problems


def find_decks(data):
    """只读检查：返回还带着编队序号的表（给体检用，不改数据）。"""
    found = []
    tables = data.get("tables") if isinstance(data, dict) else None
    if not isinstance(tables, list):
        return found
    for i, t in enumerate(tables, 1):
        if not isinstance(t, dict):
            continue
        for key in DECK_LINEUP_KEYS:
            lu = t.get(key)
            if isinstance(lu, dict) and lu.get("deck"):
                plants = [p for p in (lu.get("plants") or []) if isinstance(p, str) and p.strip()]
                found.append("表%d %s（%s）" % (i, key, "有选卡可删 deck" if plants else "只有 deck，需人工改"))
    return found


# ---------------------------------------------------------------- 目录扫描

def classify_dir(dirpath, filenames):
    """把一个目录里的文件分成：作业集文件 / 作者 / 说明。

    返回 (job_files, authors, note)。job_files 是 [(filename, data)]，
    authors 是作者列表（支持多人：一行一个或用 、 , / ; 分隔）。
    """
    job_files = []
    authors = []
    note = ""

    def add_authors(text):
        for name in parse_authors(text):
            if name not in authors:
                authors.append(name)

    for fname in sorted(filenames):
        if fname.startswith("."):
            continue
        low = fname.lower()
        if not low.endswith(JOB_EXTS):
            continue
        path = os.path.join(dirpath, fname)
        data = None
        try:
            data = load_json_file(path)
        except Exception:
            data = None
        if looks_like_job(data):
            job_files.append((fname, data))
            continue
        # 不是作业集 → 可能是作者/说明文本
        text = ""
        try:
            text = read_text(path).strip()
        except Exception:
            text = ""
        first_line = text.splitlines()[0].strip() if text else ""
        first_line = AUTHOR_PREFIX_RE.sub("", first_line).strip()
        if any(h in low for h in NOTE_HINTS):
            note = note or first_line
        elif any(h in low for h in AUTHOR_HINTS):
            add_authors(text)
        elif first_line and not text.startswith("{"):
            add_authors(text)
    return job_files, authors, note


def scan_jobs():
    """扫描 jobs/ 目录树，返回作业集记录列表。

    目录约定（v3，用固定前缀把「阵型」和「作业集」分开，一眼能看出层级）：

        jobs/g<阵型名>/<作业集>/<版本>/**    ← g 开头 = 阵型目录（g 后面才是站点显示名）
        jobs/<作业集>/<版本>/**              ← 不带 g = 不归入阵型的作业集

    每条记录：
        {group, job, dir, versions: [{label, date, dir, file, filename, author, note, size, data}]}
    """
    records = {}
    if not os.path.isdir(JOBS_DIR):
        return []

    for dirpath, dirnames, filenames in os.walk(JOBS_DIR):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith((".", "_")))
        if os.path.samefile(dirpath, JOBS_DIR):
            continue  # jobs/ 根目录本身不收
        job_files, authors, note = classify_dir(dirpath, filenames)
        if not job_files:
            continue

        rel = os.path.relpath(dirpath, JOBS_DIR).replace(os.sep, "/").split("/")

        # 第一层以 g 开头 = 阵型目录；其余一律当作业集目录
        if len(rel[0]) > 1 and rel[0].startswith("g"):
            group = rel[0]
            rest = rel[1:]
        else:
            group = ""
            rest = rel

        # rest[0] 是作业集目录，剩下的都算版本标签（允许 <版本>/<子目录> 这种）
        job_fixed = rest[0] if rest else None
        version_label = "/".join(rest[1:]) if len(rest) > 1 else ""

        # 同一目录里若混了多个作业集，按各自的 name 分开各算一版
        for fname, data in job_files:
            fields = job_fields(data, fallback_name=os.path.splitext(fname)[0])
            job_name = job_fixed or fields["name"] or os.path.splitext(fname)[0]
            mtime_iso = file_mtime_iso(os.path.join(dirpath, fname))
            mtime_date = mtime_iso[:10]

            label = version_label or mtime_date
            date = date_label_from(label) or mtime_date

            key = (group, job_name)
            rec = records.setdefault(key, {
                "group": group,
                "job": job_name,
                "dir": "/".join(p for p in ("jobs", group, job_name) if p),
                "versions": [],
            })
            rec["versions"].append({
                "label": label,
                "date": date,
                "file": os.path.relpath(os.path.join(dirpath, fname), ROOT).replace(os.sep, "/"),
                "filename": fname,
                "authors": authors,
                "author": "、".join(authors),
                "note": note,
                "size": os.path.getsize(os.path.join(dirpath, fname)),
                "data": data,
                "fields": fields,
            })

    out = []
    for rec in records.values():
        rec["versions"].sort(key=lambda v: (v["date"], v["label"]), reverse=True)
        out.append(rec)
    out.sort(key=lambda r: (r["group"], r["job"]))
    return out


def group_display_name(group):
    """阵型目录名 → 站点显示名：去掉开头的 g（jobs/g心塔 → 心塔）。"""
    gid = str(group or "")
    if len(gid) > 1 and gid.startswith("g"):
        return gid[1:]
    return gid


def read_group_meta(group):
    """读取 jobs/g<阵型>/_group.json（可选）：{name, desc, order, icon}。"""
    path = os.path.join(JOBS_DIR, group, "_group.json")
    meta = {}
    if os.path.isfile(path):
        try:
            data = load_json_file(path)
            if isinstance(data, dict):
                meta = data
        except Exception as e:
            print("[warn] %s 解析失败：%s" % (path, e))
    default_name = group_display_name(group)
    return {
        "name": str(meta.get("name") or default_name).strip() or default_name,
        "desc": str(meta.get("desc") or "").strip(),
        "order": meta.get("order") if isinstance(meta.get("order"), (int, float)) else 999,
        "icon": str(meta.get("icon") or "").strip(),
    }


# ---------------------------------------------------------------- 落库（上架）

def job_dir_path(group, job):
    """jobs/<阵型>/<作业集> ；group 为空时就是 jobs/<作业集>（不归入阵型）。"""
    parts = ["jobs"]
    g = sanitize_component(group, "") if group else ""
    if g:
        parts.append(g)
    parts.append(sanitize_component(job, "未命名作业集"))
    return os.path.join(JOBS_DIR, *parts[1:])


def place_version(group, job, date_label, filename, content_text, author="", note=""):
    """把一个作业集版本写进仓库目录树（上架的唯一落库实现）。

    返回写入的版本目录绝对路径。同一天重复上架不会覆盖旧版本（自动 2026-10-19_2）。
    """
    parent_job_dir = job_dir_path(group, job)
    os.makedirs(parent_job_dir, exist_ok=True)
    base = sanitize_component(date_label or today_label(), today_label())
    target = os.path.join(parent_job_dir, base)
    if os.path.isdir(target) and os.listdir(target):
        base = unique_dir(parent_job_dir, base)
        target = os.path.join(parent_job_dir, base)
    os.makedirs(target, exist_ok=True)

    safe_name = sanitize_component(os.path.splitext(filename)[0], "作业集") + ".json"
    write_text_file(os.path.join(target, safe_name), content_text)
    names = parse_authors(author)
    if names:
        write_text_file(os.path.join(target, "作者.txt"), author_text(names))
    if str(note or "").strip():
        write_text_file(os.path.join(target, "说明.txt"), str(note).strip())
    return target


def list_groups():
    """页面上可选的阵型（分组）列表。

    由扫描结果推导——jobs/ 下面既有阵型目录、也有「不归入阵型」的作业集目录，
    不能只看目录名，否则会把作业集当成阵型。
    """
    seen = []
    for rec in scan_jobs():
        gid = rec["group"]
        if gid and gid not in seen:
            seen.append(gid)
    groups = []
    for gid in sorted(seen):
        meta = read_group_meta(gid)
        groups.append({"id": gid, "name": meta["name"], "desc": meta["desc"],
                       "order": meta["order"], "icon": meta["icon"]})
    groups.sort(key=lambda g: (g["order"], g["id"]))
    return groups


# ---------------------------------------------------------------- 体检 / 清理

def _dir_has_files(path):
    for dirpath, _dirnames, filenames in os.walk(path):
        if any(not f.startswith(".") for f in filenames):
            return True
        if any(f in (".gitkeep",) for f in filenames):
            continue
    return False


def audit_jobs():
    """仓库体检：把「看起来能用、其实会坑人」的状态列出来。

    返回 [{level, kind, path, message}]，level = "error" | "warn"。
    """
    issues = []

    def add(level, kind, path, message):
        issues.append({"level": level, "kind": kind,
                       "path": rel_path(path), "message": message})

    if not os.path.isdir(JOBS_DIR):
        add("warn", "no-jobs-dir", JOBS_DIR, "还没有 jobs/ 目录")
        return issues

    # 1) jobs/ 顶层散落的文件（旧平铺结构残留，会被当成作业集）
    for name in sorted(os.listdir(JOBS_DIR)):
        full = os.path.join(JOBS_DIR, name)
        if os.path.isfile(full) and not name.startswith("."):
            add("warn", "loose-file", full,
                "jobs/ 顶层散落的文件（旧平铺结构），建议整理进 <作业集>/<版本>/ 目录")

    # 2) 空目录（阵型或作业集删空了，目录还留着）
    for dirpath, dirnames, filenames in os.walk(JOBS_DIR):
        if os.path.samefile(dirpath, JOBS_DIR):
            continue
        if not _dir_has_files(dirpath):
            add("warn", "empty-dir", dirpath, "空目录：没有任何作业集文件，可以删掉")

    recs = scan_jobs()

    # 3) 版本目录名不像日期 → 扫描器会把它当作业集/阵型，容易错乱
    for rec in recs:
        for v in rec["versions"]:
            if date_label_from(v["label"]) is None:
                add("warn", "bad-version", os.path.join(ROOT, v["file"]),
                    "版本目录名不是日期（%s），建议改成 2026-10-19 这种" % v["label"])

    # 4) 重复 code（同一份作业集被复制成了两个；同一作业集的多个版本共用 code 是正常的）
    by_code = {}
    for rec in recs:
        for v in rec["versions"]:
            code = v["fields"].get("code")
            if code:
                by_code.setdefault(code, set()).add((rec["group"], rec["job"]))
    for code, owners in by_code.items():
        if len(owners) > 1:
            first = sorted(owners)[0]
            add("error", "dup-code", os.path.join(JOBS_DIR, first[1]),
                "code「%s」出现在多个作业集里：%s" % (
                    code, "；".join(sorted("%s → %s" % (g or "（不归入阵型）", j) for g, j in owners))))

    # 5) 同名作业集（跨阵型重名，卡片上看起来像两个一样的）
    by_name = {}
    for rec in recs:
        by_name.setdefault(rec["job"], []).append(rec["group"] or "（不归入阵型）")
    for name, owners in by_name.items():
        if len(owners) > 1:
            add("warn", "dup-name", os.path.join(JOBS_DIR, name),
                "同名作业集「%s」出现在：%s" % (name, "、".join(owners)))

    # 6) 作业集目录名和作业集里写的 name 不一致（站点显示 name，目录名只是身份）
    for rec in recs:
        latest = rec["versions"][0]["fields"].get("name")
        if latest and latest.strip() and latest.strip() != rec["job"]:
            add("warn", "name-mismatch", os.path.join(JOBS_DIR, rec["job"]),
                "目录名「%s」与作业集里写的名称「%s」不一致" % (rec["job"], latest.strip()))

    # 7) 空阵型：只剩 _group.json、里面没有任何作业集（站点的阵型列表里看不到，只能在工具里删）
    seen_groups = {rec["group"] for rec in recs if rec["group"]}
    for name in sorted(os.listdir(JOBS_DIR)):
        full = os.path.join(JOBS_DIR, name)
        if not os.path.isdir(full) or name.startswith((".", "_")):
            continue
        if name in seen_groups:
            continue
        if os.path.isfile(os.path.join(full, "_group.json")):
            add("warn", "empty-group", full, "空阵型：只剩 _group.json，里面没有作业集（可在工具里删掉）")

    # 8) 还带着编队序号（deck）的作业集：别人复现不了，应该改成选卡
    for rec in recs:
        for v in rec["versions"]:
            decks = find_decks(v["data"])
            if decks:
                add("warn", "deck", os.path.join(ROOT, v["file"]),
                    "还用着编队序号：%s —— 别人导入复现不了，建议改成选卡" % "、".join(decks))

    return issues


def rel_path(path):
    try:
        return os.path.relpath(path, ROOT).replace(os.sep, "/")
    except Exception:
        return str(path)


def clean_empty_dirs():
    """删掉 jobs/ 下所有空目录（含空阵型、空作业集）。返回删除的路径列表。"""
    removed = []
    if not os.path.isdir(JOBS_DIR):
        return removed
    # 自底向上删，先删子目录
    for dirpath, dirnames, _filenames in os.walk(JOBS_DIR, topdown=False):
        if os.path.samefile(dirpath, JOBS_DIR):
            continue
        if _dir_has_files(dirpath):
            continue
        try:
            os.rmdir(dirpath)
            removed.append(rel_path(dirpath))
        except OSError:
            pass
    return removed
