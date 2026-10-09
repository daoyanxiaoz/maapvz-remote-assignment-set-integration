#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""处理投稿 Issue：解析 → 校验 → 落盘（Action ① 的核心安全件）。

★ 安全说明：issue body 是不可信输入。
    - 本脚本只通过【环境变量】读取 issue 内容，绝不拼接进 shell 命令；
    - code 白名单正则必须先于任何文件路径拼接执行（防 ../ 路径注入）；
    - 本脚本只写两个 JSON 文件，不执行投稿 JSON 里的任何内容。

输入（环境变量）：
    ISSUE_BODY      issue 正文（GitHub Issue Form 的 markdown）
    ISSUE_NUMBER    issue 编号
    ISSUE_AUTHOR    issue 作者 GitHub 用户名

输出：
    GITHUB_OUTPUT   status=ok|invalid、code、name、branch
    comment_invalid.md  校验失败时的评论内容（workflow 用 --body-file 发送）
    pr_body.md          校验通过时的 PR 正文

落盘（校验通过时）：
    jobs/<code>.json
    meta/<code>.json（author/desc 任一非空时）

退出码恒为 0：投稿无效不是 Action 失败，是投稿本身的问题。
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "jobs")
META_DIR = os.path.join(ROOT, "meta")

MAX_BYTES = 2 * 1024 * 1024  # 2MB 上限，防滥用

# ★ 安全红线：code 白名单，防路径注入。必须先于任何路径拼接执行。
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


def parse_form(body):
    """按 GitHub Issue Form 的 '### 字段名' 结构把 body 切成字段字典。"""
    fields = {}
    current = None
    buf = []
    for line in (body or "").splitlines():
        if line.startswith("### "):
            if current is not None:
                fields[current] = "\n".join(buf).strip()
            current = line[4:].strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        fields[current] = "\n".join(buf).strip()
    return fields


def get_field(fields, *names):
    """按完整名或前缀取字段，兼容 label 微调。"""
    for n in names:
        if n in fields:
            return fields[n]
    for k in fields:
        for n in names:
            if k.startswith(n):
                return fields[k]
    return ""


def clean_value(v):
    """去掉空白与 Issue Form 的空值占位符。"""
    if v is None:
        return ""
    v = v.strip()
    if v == "_No response_":
        return ""
    return v


def strip_code_fence(text):
    """Issue Form 的 render:json 会把内容包进 ```json 围栏，剥掉。"""
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def validate(raw):
    """校验投稿 JSON。返回 (data, None) 或 (None, 错误原因)。"""
    text = strip_code_fence(raw)
    if not text:
        return None, "作业集 JSON 为空，请完整粘贴编辑器导出的内容。"

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return None, f"JSON 解析失败：第 {e.lineno} 行第 {e.colno} 列（{e.msg}）。"

    if not isinstance(data, dict):
        return None, "作业集顶层必须是 JSON 对象（{...}）。"

    for key in ("code", "name", "tables"):
        if key not in data:
            return None, f"缺少必需字段 `{key}`。"

    code = data["code"]
    if not isinstance(code, str) or not code:
        return None, "`code` 必须是非空字符串。"
    # ★ 安全红线：白名单校验必须先于任何文件路径拼接
    if not CODE_RE.match(code):
        return None, ("`code` 含非法字符：仅允许字母、数字、下划线、连字符，长度 1~64。"
                      f"当前值：`{code[:80]}`")

    name = data["name"]
    if not isinstance(name, str) or not name.strip():
        return None, "`name` 必须是非空字符串。"

    tables = data["tables"]
    if not isinstance(tables, list) or not tables:
        return None, "`tables` 必须是非空数组（至少 1 张关卡段策略表）。"

    size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    if size > MAX_BYTES:
        return None, f"JSON 体积超过 2MB 上限（当前约 {size // 1024}KB）。"

    return data, None


def write_output(key, value):
    """写 GitHub Actions step output（单行值）。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(f"{key}={value}\n")
    else:
        print(f"[output] {key}={value}")


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def main():
    body = os.environ.get("ISSUE_BODY", "")
    number = os.environ.get("ISSUE_NUMBER", "0")
    issue_author = os.environ.get("ISSUE_AUTHOR", "")

    fields = parse_form(body)
    raw_json = clean_value(get_field(fields, "作业集 JSON", "body_json"))
    author = clean_value(get_field(fields, "作者昵称", "author"))
    desc = clean_value(get_field(fields, "一句话简介", "desc"))
    note = clean_value(get_field(fields, "补充说明", "note"))

    data, err = validate(raw_json)

    if err is not None:
        # —— 校验失败：写评论文件，打无效标记，正常退出 ——
        comment = (
            "投稿校验未通过 😢\n\n"
            f"> {err}\n\n"
            "请修改后**直接编辑本 Issue**（不用重开），机器人会自动重新校验。\n"
        )
        write_file(os.path.join(ROOT, "comment_invalid.md"), comment)
        write_output("status", "invalid")
        print(f"[invalid] {err}")
        return 0

    code = data["code"]
    name = data["name"].strip()

    # ★ code 已过白名单，此处拼接路径是安全的
    job_path = os.path.join(JOBS_DIR, code + ".json")
    if os.path.exists(job_path):
        comment = (
            "投稿校验未通过 😢\n\n"
            f"> code `{code}` 与站内已有作业集撞车。\n\n"
            "请换一个 `code`（比如加上你的昵称或日期后缀）后**直接编辑本 Issue**；"
            "如果你就是原作者、想更新这套作业集，请联系维护者处理。\n"
        )
        write_file(os.path.join(ROOT, "comment_invalid.md"), comment)
        write_output("status", "invalid")
        print(f"[invalid] code 撞车：{code}")
        return 0

    # —— 校验通过：落盘 ——
    os.makedirs(JOBS_DIR, exist_ok=True)
    write_file(job_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    meta = {}
    if author:
        meta["author"] = author
    if desc:
        meta["desc"] = desc
    if meta:
        os.makedirs(META_DIR, exist_ok=True)
        write_file(os.path.join(META_DIR, code + ".json"),
                   json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    # PR 正文（只含校验摘要，引用原 issue）
    size_kb = os.path.getsize(job_path) // 1024
    worlds = data.get("worlds")
    worlds_str = "、".join(str(w) for w in worlds) if isinstance(worlds, list) and worlds else "未填写"
    lines = [
        "## 投稿校验通过 ✅",
        "",
        f"- 作业集：**{name}**（`{code}`）",
        f"- 投稿人：@{issue_author}" if issue_author else "- 投稿人：未知",
        f"- 策略表：{len(data['tables'])} 张",
        f"- 适用世界：{worlds_str}",
    ]
    if isinstance(data.get("max_level"), (int, float)):
        lines.append(f"- 最高关卡：{data['max_level']}")
    lines.append(f"- 文件大小：约 {size_kb}KB")
    if note:
        lines += ["", "### 投稿者补充说明", "", note]
    lines += ["", f"Closes #{number}", ""]
    write_file(os.path.join(ROOT, "pr_body.md"), "\n".join(lines))

    # outputs（name 压成单行，防 output 格式被破坏）
    write_output("status", "ok")
    write_output("code", code)
    write_output("name", re.sub(r"\s+", " ", name)[:100])
    write_output("branch", f"submission/{code}-{number}")
    print(f"[ok] 校验通过，已落盘 jobs/{code}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
