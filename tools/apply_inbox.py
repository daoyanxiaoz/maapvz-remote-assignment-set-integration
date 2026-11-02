#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把「上架包」落库到 jobs/ 目录树（线上由 Action 自动跑，本地也能手动跑）。

上架包 = publish.html 生成的 *.bundle.json，结构：

    {
      "format": "maapvz-jobset-bundle",
      "schema": 1,
      "created": "2026-10-31T...",
      "items": [
        {"mode": "new"|"iterate", "group": "心塔", "job": "失落原大火龙果",
         "date": "2026-10-31", "author": "站长", "note": "改了 41 关",
         "filename": "失落原大火龙果.json", "content_b64": "..."}
      ]
    }

用法：
    python tools/apply_inbox.py                 # 处理 inbox/ 下所有上架包
    python tools/apply_inbox.py 包1.json 包2.json   # 只处理指定文件
    python tools/apply_inbox.py --dry-run       # 只打印会写到哪里

落库后自动重建 index.json。处理成功的上架包会被删除（仓库里不留垃圾）。
"""

import base64
import glob
import json
import os
import sys

import build_index
import joblib

MAX_BYTES = 8 * 1024 * 1024


def decode_item(item):
    """校验并解码一个上架项，返回 (group, job, date, filename, text, author, note)。"""
    if not isinstance(item, dict):
        raise ValueError("上架项不是对象")

    mode = str(item.get("mode") or "new").strip().lower()
    if mode not in ("new", "iterate"):
        raise ValueError("mode 只能是 new / iterate，收到：%r" % mode)

    group = joblib.sanitize_component(item.get("group"), "")
    job = joblib.sanitize_component(item.get("job"), "")
    if not job:
        raise ValueError("缺少作业集名 job")

    date = joblib.date_label_from(item.get("date")) or joblib.today_label()

    raw = item.get("content_b64")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("缺少 content_b64")
    try:
        payload = base64.b64decode(raw, validate=False)
    except Exception as e:
        raise ValueError("content_b64 解码失败：%s" % e)
    if len(payload) > MAX_BYTES:
        raise ValueError("作业集超过 8MB")
    for enc in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            text = payload.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        raise ValueError("作业集内容不是合法文本")

    try:
        data = joblib.load_json_text(text)
    except Exception as e:
        raise ValueError("作业集不是合法 JSON：%s" % e)
    if not joblib.looks_like_job(data):
        raise ValueError("作业集缺少 tables / code 字段")

    # ★ 上架强制规整：自动选卡 + 局外只留固定植物 + 不允许编队序号（deck）
    changes, problems = joblib.enforce_upload_rules(data)
    if problems:
        raise ValueError("不能用编队序号（deck），别人复现不了：%s。请在编辑器里改成「选卡」后再导出"
                         % "；".join(problems))
    if changes:
        text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"

    filename = joblib.sanitize_component(
        os.path.splitext(str(item.get("filename") or job))[0], job) + ".json"
    # 作者可以有多个：逗号/顿号/分号/换行都行，落库时一行一个
    authors = joblib.parse_authors(item.get("author"))
    author = "、".join(authors)[:200]
    note = str(item.get("note") or "").strip()[:200]
    return group, job, date, filename, text, author, note, changes


def apply_bundle(path, dry_run=False):
    """处理一个上架包，返回 (成功条数, [错误信息])。"""
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            bundle = json.load(f)
    except Exception as e:
        return 0, ["%s：读不出上架包（%s）" % (os.path.basename(path), e)]

    if not isinstance(bundle, dict) or bundle.get("format") != joblib.BUNDLE_FORMAT:
        return 0, ["%s：不是上架包（缺少 format=%s）" % (os.path.basename(path), joblib.BUNDLE_FORMAT)]

    items = bundle.get("items")
    if not isinstance(items, list) or not items:
        return 0, ["%s：items 为空" % os.path.basename(path)]

    ok = 0
    errors = []
    for idx, item in enumerate(items, 1):
        try:
            group, job, date, filename, text, author, note, changes = decode_item(item)
        except Exception as e:
            errors.append("%s 第 %d 项：%s" % (os.path.basename(path), idx, e))
            continue
        for c in changes:
            print("[fix] %s：%s" % (job, c))
        label = "%s/%s/%s" % (group, job, date)
        if dry_run:
            print("[dry-run] 将写入 jobs/%s/%s" % (label, filename))
        else:
            target = joblib.place_version(group, job, date, filename, text, author, note)
            print("[ok] 已写入 %s" % os.path.relpath(target, joblib.ROOT).replace(os.sep, "/"))
        ok += 1
    return ok, errors


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    dry_run = "--dry-run" in argv
    args = [a for a in argv if not a.startswith("--")]
    if "--keep" in argv:
        keep = True
    else:
        keep = dry_run  # dry-run 不动文件

    if args:
        bundles = [a for a in args if os.path.isfile(a)]
    else:
        bundles = sorted(glob.glob(os.path.join(joblib.INBOX_DIR, "*.json")))

    if not bundles:
        print("[info] inbox/ 里没有上架包")
        return 0

    total_ok = 0
    all_errors = []
    for path in bundles:
        ok, errors = apply_bundle(path, dry_run=dry_run)
        total_ok += ok
        all_errors.extend(errors)
        if ok and not keep:
            try:
                os.remove(path)
                print("[ok] 已消费 %s" % os.path.basename(path))
            except Exception as e:
                print("[warn] 上架包删除失败（可手动删）：%s" % e)

    for e in all_errors:
        print("[error] %s" % e)

    if not dry_run:
        index = build_index.build_index()
        build_index.write_index(index, quiet=True)

    print("[done] 本次落库 %d 项，失败 %d 项" % (total_ok, len(all_errors)))
    return 0 if total_ok or not all_errors else 1


if __name__ == "__main__":
    sys.exit(main())
