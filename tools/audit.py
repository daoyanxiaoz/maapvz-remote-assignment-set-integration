#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""仓库体检：把「能跑但会坑人」的状态列出来。

    python tools/audit.py                 # 只报告
    python tools/audit.py --clean         # 顺手删掉空目录（阵型/作业集删空后的残留）

检查项：
    - jobs/ 顶层散落的文件（旧平铺结构残留）
    - 空目录（空阵型 / 空作业集）
    - 版本目录名不是日期
    - 同一 code 出现在多个作业集（真·重复）
    - 跨阵型同名作业集
    - 作业集目录名与作业集内写的名称不一致
"""

import sys

import joblib


LEVEL_MARK = {"error": "✗", "warn": "!"}


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    if "--clean" in argv:
        removed = joblib.clean_empty_dirs()
        if removed:
            print("[clean] 删除空目录 %d 个：" % len(removed))
            for p in removed:
                print("   - %s" % p)
        else:
            print("[clean] 没有空目录需要清理")

    issues = joblib.audit_jobs()
    if not issues:
        print("[ok] 体检通过：没有发现问题")
        return 0

    errors = [i for i in issues if i["level"] == "error"]
    warns = [i for i in issues if i["level"] != "error"]
    print("体检结果：%d 个错误 / %d 个提醒\n" % (len(errors), len(warns)))
    for i in errors + warns:
        print("%s [%s] %s" % (LEVEL_MARK.get(i["level"], "?"), i["path"], i["message"]))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
