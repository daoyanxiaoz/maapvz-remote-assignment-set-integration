#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""处理投稿 Issue：解析 → 校验 → 规范化落盘（Action ① 的核心安全件）。

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
    jobs/<code>.json    作业集本体（剥掉 compiled、规范化格式）
    meta/<code>.json    author / desc / plant_costumes（装扮标注）

退出码恒为 0：投稿无效不是 Action 失败，是投稿本身的问题。
"""

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(ROOT, "jobs")
META_DIR = os.path.join(ROOT, "meta")
PLANTS_DB = os.path.join(ROOT, "data", "plants.json")

MAX_BYTES = 2 * 1024 * 1024  # 2MB 上限，防滥用

# ★ 安全红线：code 白名单，防路径注入。必须先于任何路径拼接执行。
CODE_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")

# 投稿人把 .json 文件拖进 Issue 后，GitHub 会上传成附件链接。
# ★ 只允许这个固定前缀（github.com 官方附件域），防 SSRF 骗机器人下载任意 URL。
ATTACH_RE = re.compile(
    r"https://github\.com/user-attachments/files/\d+/[A-Za-z0-9._\-]+")

# 19 个适用世界（与站点世界标签/立绘关键词同源），投稿必填至少一个
KNOWN_WORLDS = ["埃及", "海盗", "西部", "功夫", "未来", "黑暗", "沙滩", "冰河", "天空",
                "失落", "摇滚", "恐龙", "摩登", "蒸汽", "复兴", "平安", "童话",
                "亚特兰蒂斯", "月球"]


def download_attachment(url, max_bytes=MAX_BYTES):
    """下载 GitHub 附件（跟随重定向到官方对象存储）。返回 (文本, None) 或 (None, 错误)。"""
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "maapvz-jobset-bot"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read(max_bytes + 1)
    except Exception as e:
        return None, f"附件下载失败：{e}"
    if len(data) > max_bytes:
        return None, f"附件超过 2MB 上限。"
    try:
        return data.decode("utf-8-sig"), None
    except UnicodeDecodeError:
        return None, "附件不是 UTF-8 文本，请上传编辑器导出的原始 .json 文件。"


def resolve_json_field(raw):
    """「作业集 JSON」栏三种形态都支持：
    1) 直接粘贴的 JSON 文本；
    2) 拖文件生成的 GitHub 附件链接；
    3) 站点一键投稿生成的 deflate64: 压缩块（raw deflate + base64url）。
    返回 (JSON文本, None) 或 (None, 错误)。"""
    text = strip_code_fence(raw or "")
    if not text:
        return None, ("「作业集 JSON」一栏是空的。把编辑器导出的 .json 文件"
                      "**拖进那一栏**（GitHub 会自动上传成附件链接），或直接把 JSON 全文粘贴进去。")
    # 1) 先试直接解析
    try:
        json.loads(text)
        return text, None
    except json.JSONDecodeError:
        pass
    # 2) 附件链接
    m = ATTACH_RE.search(raw or "")
    if m:
        return download_attachment(m.group(0))
    # 3) deflate64 压缩块（一键投稿通道）
    m2 = re.search(r"deflate64:([A-Za-z0-9_\-]+)", raw or "")
    if m2:
        import base64
        import zlib
        payload = m2.group(1)
        try:
            blob = base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))
            text = zlib.decompressobj(-15).decompress(blob, MAX_BYTES + 1)
            if len(text) > MAX_BYTES:
                return None, "解压后的 JSON 超过 2MB 上限。"
            return text.decode("utf-8"), None
        except Exception as e:
            return None, f"deflate64 压缩块解压失败：{e}"
    return None, ("「作业集 JSON」里既没解析到 JSON，也没找到附件链接。\n"
                  "把编辑器导出的 .json 文件**拖进那一栏**，等它变成 "
                  "`https://github.com/user-attachments/files/...` 链接后再提交。")


# ---------- Issue Form 解析 ----------

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


# ---------- 作业集校验 ----------

def validate_jobset(raw):
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

    # 强制选卡编队：编队序号（deck）只在投稿人本机有效，别人无法复现，一律拒绝
    for i, t in enumerate(tables, 1):
        if not isinstance(t, dict):
            continue
        lu = t.get("lineup") or {}
        bl = t.get("boss_lineup") or {}
        if isinstance(lu, dict) and lu.get("deck"):
            return None, (f"表{i} 的阵容用了编队序号（编队{lu['deck']}）。"
                          "编队序号只在你自己的游戏里有效，别人无法复现——"
                          "请在编辑器里改成选卡编队（明确植物列表）再导出投稿。")
        if isinstance(bl, dict) and bl.get("deck"):
            return None, (f"表{i} 的 boss 关阵容用了编队序号（编队{bl['deck']}），"
                          "请改成明确的植物列表再投稿。")

    size = len(json.dumps(data, ensure_ascii=False).encode("utf-8"))
    if size > MAX_BYTES:
        return None, f"JSON 体积超过 2MB 上限（当前约 {size // 1024}KB）。"

    return data, None


# ---------- 植物集合与装扮标注 ----------

def collect_plants(jobset):
    """作业集全量植物名（保序去重）：
    lineup.plants ∪ boss_lineup.plants ∪ boardEarly/boardLate 中 type=plant 的格子。"""
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


def load_known_plants():
    """植物数据库（data/plants.json）的中文名集合。读不到则返回 None（跳过库内校验）。"""
    try:
        with open(PLANTS_DB, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return {p["name"] for p in data if isinstance(p, dict) and p.get("name")}
    except Exception as e:
        print(f"[warn] 植物数据库读取失败，跳过库内名校验：{e}")
        return None


def parse_costume_lines(text):
    """解析装扮标注：每行 `植物名:需要` / `植物名:不需要`（兼容中英文冒号）。
    返回 (标注dict name→bool, 行错误列表)。"""
    ann = {}
    errors = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(.+?)[:：]\s*(\S+)\s*$", line)
        if not m:
            errors.append(f"第 {i} 行格式不对（应为 `植物名:需要`）：`{line[:40]}`")
            continue
        name, val = m.group(1).strip(), m.group(2).strip()
        if val not in ("需要", "不需要"):
            errors.append(f"第 {i} 行「{name}」的值只能是 需要/不需要（当前：`{val}`）")
            continue
        ann[name] = (val == "需要")
    return ann, errors


def validate_costumes(raw_text, plants, known):
    """强制装扮标注校验。返回 (plant_costumes dict, None) 或 (None, 错误原因)。"""
    if not raw_text.strip():
        return None, ("装扮标注为空。作业集里出现的每一棵植物都要标注，每行一条，"
                      "如 `娜迦蛇皮果:需要`、`大嘴花:不需要`。")

    ann, errors = parse_costume_lines(raw_text)
    if errors:
        return None, "装扮标注有格式错误：\n" + "\n".join(f"- {e}" for e in errors[:10])

    if known is not None:
        unknown = [n for n in ann if n not in known]
        if unknown:
            return None, ("装扮标注里有植物数据库之外的名字："
                          + "、".join(f"`{n}`" for n in unknown[:10])
                          + "\n请核对植物名（与编辑器里的名字一字不差）。")

    plant_set = set(plants)
    extra = [n for n in ann if n not in plant_set]
    if extra:
        return None, ("装扮标注里混入了作业集之外的植物："
                      + "、".join(f"`{n}`" for n in extra[:10]))

    missing = [p for p in plants if p not in ann]
    if missing:
        return None, ("以下植物还没有装扮标注（每棵都要标，一颗不落）：\n"
                      + "\n".join(f"- `{p}`" for p in missing))

    return {p: ann[p] for p in plants}, None


def parse_worlds(raw_text):
    """解析「适用世界」栏：顿号/逗号/空白/换行分隔，必须在 19 个世界之内，至少一个。
    返回 (世界列表, None) 或 (None, 错误)。"""
    if not raw_text.strip():
        return None, ("「适用世界」为空。请至少填一个这份作业集能打的世界"
                      "（如：埃及、海盗），别的玩家需要靠它判断适不适用。")
    parts = [p for p in re.split(r"[、，,/\s]+", raw_text) if p]
    bad = [p for p in parts if p not in KNOWN_WORLDS]
    if bad:
        return None, ("「适用世界」里有不认识的名字："
                      + "、".join(f"`{p}`" for p in bad[:10])
                      + "\n可选项：" + "、".join(KNOWN_WORLDS))
    # 按官方顺序去重
    return [w for w in KNOWN_WORLDS if w in parts], None


# ---------- 落盘规范化 ----------

def strip_compiled(jobset):
    """剥掉所有 tables[].compiled 预编译块（占体积 70%~90% 且带时效性；
    使用者导入编辑器重存时会用最新编译器重新生成）。返回剥掉的块数。"""
    n = 0
    for t in jobset.get("tables") or []:
        if isinstance(t, dict) and "compiled" in t:
            t.pop("compiled")
            n += 1
    return n


# ---------- GitHub Actions 输出 ----------

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


def fail_with_comment(reason):
    comment = (
        "投稿校验未通过 😢\n\n"
        f"> {reason}\n\n"
        "请修改后**直接编辑本 Issue**（不用重开），机器人会自动重新校验。\n"
    )
    write_file(os.path.join(ROOT, "comment_invalid.md"), comment)
    write_output("status", "invalid")
    print(f"[invalid] {reason.splitlines()[0]}")
    return 0


def main():
    body = os.environ.get("ISSUE_BODY", "")
    number = os.environ.get("ISSUE_NUMBER", "0")
    issue_author = os.environ.get("ISSUE_AUTHOR", "")

    fields = parse_form(body)
    raw_json_field = clean_value(get_field(fields, "作业集 JSON", "body_json"))
    author = clean_value(get_field(fields, "作者昵称", "author"))
    desc = clean_value(get_field(fields, "一句话简介", "desc"))
    note = clean_value(get_field(fields, "补充说明", "note"))
    raw_costumes = clean_value(get_field(fields, "装扮标注"))
    raw_worlds = clean_value(get_field(fields, "适用世界"))

    # —— 1. 作业集 JSON 校验（支持附件链接 / 直接粘贴两种形态） ——
    json_text, err = resolve_json_field(raw_json_field)
    if err is not None:
        return fail_with_comment(err)
    data, err = validate_jobset(json_text)
    if err is not None:
        return fail_with_comment(err)

    code = data["code"]
    name = data["name"].strip()

    # ★ code 已过白名单，此处拼接路径是安全的
    job_path = os.path.join(JOBS_DIR, code + ".json")
    if os.path.exists(job_path):
        return fail_with_comment(
            f"code `{code}` 与站内已有作业集撞车。\n\n"
            "请换一个 `code`（比如加上你的昵称或日期后缀）后**直接编辑本 Issue**；"
            "如果你就是原作者、想更新这套作业集，请联系维护者处理。")

    # —— 2. 装扮标注强校验 ——
    plants = collect_plants(data)
    known = load_known_plants()
    plant_costumes, err = validate_costumes(raw_costumes, plants, known)
    if err is not None:
        return fail_with_comment(err)

    # —— 2.5 适用世界必填校验，写回作业集 worlds 字段（规范位置） ——
    worlds, err = parse_worlds(raw_worlds)
    if err is not None:
        return fail_with_comment(err)
    data["worlds"] = worlds

    # —— 3. 规范化落盘 ——
    stripped = strip_compiled(data)  # 剥预编译块
    os.makedirs(JOBS_DIR, exist_ok=True)
    write_file(job_path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")

    meta = {"plant_costumes": plant_costumes}
    if author:
        meta["author"] = author
    if desc:
        meta["desc"] = desc
    os.makedirs(META_DIR, exist_ok=True)
    write_file(os.path.join(META_DIR, code + ".json"),
               json.dumps(meta, ensure_ascii=False, indent=2) + "\n")

    # —— 4. PR 正文（校验摘要，引用原 issue） ——
    size_kb = os.path.getsize(job_path) // 1024
    worlds = data.get("worlds")
    worlds_str = "、".join(str(w) for w in worlds) if isinstance(worlds, list) and worlds else "未填写"
    need_costume = [p for p, v in plant_costumes.items() if v]
    lines = [
        "## 投稿校验通过 ✅",
        "",
        f"- 作业集：**{name}**（`{code}`）",
        f"- 投稿人：@{issue_author}" if issue_author else "- 投稿人：未知",
        f"- 策略表：{len(data['tables'])} 张",
        f"- 阵容植物：{len(plants)} 种",
        f"- 需装扮植物：{len(need_costume)} 种"
        + ("（" + "、".join(need_costume[:8]) + ("…" if len(need_costume) > 8 else "") + "）"
           if need_costume else ""),
        f"- 适用世界：{worlds_str}",
        f"- 已剥掉 compiled 预编译块 {stripped} 个，JSON 已规范化（UTF-8 无 BOM / 缩进 2）",
        f"- 落盘后大小：约 {size_kb}KB",
    ]
    if note:
        lines += ["", "### 投稿者补充说明", "", note]
    lines += ["", f"Closes #{number}", ""]
    write_file(os.path.join(ROOT, "pr_body.md"), "\n".join(lines))

    # outputs（name 压成单行，防 output 格式被破坏）
    write_output("status", "ok")
    write_output("code", code)
    write_output("name", re.sub(r"\s+", " ", name)[:100])
    write_output("branch", f"submission/{code}-{number}")
    print(f"[ok] 校验通过，已落盘 jobs/{code}.json + meta/{code}.json"
          f"（剥 compiled {stripped} 块，装扮标注 {len(plant_costumes)} 条）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
