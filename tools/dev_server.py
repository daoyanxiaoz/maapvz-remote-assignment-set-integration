#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""本地服务器，两个用途（对应仓库根目录两个 .bat）：

    「启动维护工具.bat」  → python tools/dev_server.py            （可写：上传/改信息/重命名/删版本）
    「启动作业站预览工具.bat」→ python tools/dev_server.py --preview   （只读：只看站点效果，关闭所有 /api 写接口）

设计约束：
    - 只监听 127.0.0.1（外部机器连不进来），仅标准库；
    - 静态文件服务 = 仓库根目录（和线上页面完全一致，所见即所得）；
    - `/api/*` 写操作会直接改 jobs/ 目录树并重建 index.json（预览模式下一律拒绝）；
    - 只接受本工具页面发起的写请求（需要自定义请求头，挡住跨站表单/脚本）；
    - 所有路径都由服务端自己从目录树推导，不接受客户端传任意路径，杜绝穿越。

命令行：
    python tools/dev_server.py                 # 维护工具：起服务并自动开 admin.html
    python tools/dev_server.py --preview       # 预览工具：起服务并自动开 index.html（只读）
    python tools/dev_server.py --port 9000     # 指定端口
    python tools/dev_server.py --no-open       # 不自动开浏览器
"""

import base64
import functools
import json
import os
import shutil
import socket
import sys
import traceback
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import apply_inbox
import build_index
import joblib

HOST = "127.0.0.1"
ROOT = joblib.ROOT
TOOL_HEADER = "X-Maapvz-Tool"
MAX_BODY = 24 * 1024 * 1024


class ApiError(Exception):
    pass


# ---------------------------------------------------------------- 写操作实现

def rebuild():
    index = build_index.build_index()
    changed = build_index.write_index(index, quiet=True)
    return "索引已重建" + ("（有变化）" if changed else "（无变化）")


def v_dir_of(rel_file):
    """把 index.json 里的版本文件路径换算成磁盘路径，并做安全校验。"""
    rel = str(rel_file or "").replace("\\", "/").lstrip("/")
    parts = [p for p in rel.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise ApiError("路径非法：%s" % rel_file)
    if parts[0] != "jobs":
        raise ApiError("只能操作 jobs/ 下的文件")
    # 只认 jobs/[阵型/]作业集/版本/文件 这 3~4 层结构：
    # 挡掉 jobs/xxx.json、jobs/<阵型>/xxx.json（会把阵型/作业集目录当成版本目录删掉）
    if len(parts) < 3:
        raise ApiError("这个作业集不是标准版本目录结构，请先按 "
                       "jobs/[阵型/]作业集/版本/ 整理：%s" % rel)
    path = os.path.join(ROOT, *parts)
    if not os.path.exists(path):
        raise ApiError("文件不存在：%s" % rel)
    vdir = os.path.dirname(path)
    if vdir == joblib.JOBS_DIR:
        raise ApiError("拒绝操作 jobs/ 根目录")
    return vdir


def job_dir_of(group, job):
    g = joblib.sanitize_component(group, "") if group else ""
    j = joblib.sanitize_component(job, "")
    if not j:
        raise ApiError("作业集名为空")
    path = os.path.join(joblib.JOBS_DIR, g, j) if g else os.path.join(joblib.JOBS_DIR, j)
    if not os.path.isdir(path):
        raise ApiError("找不到作业集：%s" % (("%s/%s" % (g, j)) if g else j))
    return path


def group_dir_of(group):
    g = joblib.sanitize_component(group, "")
    if not g:
        raise ApiError("分组名为空")
    path = os.path.join(joblib.JOBS_DIR, g)
    if not os.path.isdir(path):
        raise ApiError("找不到分组：%s" % g)
    return path


def api_upload(payload):
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise ApiError("没有要上传的文件")
    group = payload.get("group")
    if group == "__new__":
        group = str(payload.get("newGroup") or "").strip()
        if not group:
            raise ApiError("请填写新阵型名")
    group = str(group or "").strip()   # 空字符串 = 不归入阵型
    date = payload.get("date")
    author = payload.get("author")
    note = payload.get("note")

    written = []
    warnings = []
    # 查重快照：同 code / 同名作业集（同阵型下追加版本是正常的，这里只提醒真正会「变成两个」的情况）
    snapshot = joblib.scan_jobs()
    name_owners = {}
    code_owners = {}
    for rec in snapshot:
        name_owners.setdefault(rec["job"], set()).add(rec["group"])
        for v in rec["versions"]:
            c = v["fields"].get("code")
            if c:
                code_owners.setdefault(c, set()).add((rec["group"], rec["job"]))

    for it in items:
        item = {
            "mode": payload.get("mode") or "new",
            "group": group,
            "job": it.get("job"),
            "date": date,
            "author": author,
            "note": note,
            "filename": it.get("filename"),
            "content_b64": it.get("content_b64"),
        }
        try:
            g, j, d, fname, text, auth, nt, changes = apply_inbox.decode_item(item)
        except Exception as e:
            raise ApiError("%s：%s" % (it.get("filename") or "文件", e))

        other_groups = name_owners.get(j, set()) - {g}
        if other_groups:
            warnings.append("「%s」在阵型「%s」里已经有同名作业集（会变成两个）"
                            % (j, "、".join(sorted(x or "（不归入阵型）" for x in other_groups))))
        try:
            code = joblib.job_fields(joblib.load_json_text(text)).get("code")
        except Exception:
            code = None
        if code:
            others = code_owners.get(code, set()) - {(g, j)}
            if others:
                warnings.append("code「%s」已存在于：%s" % (
                    code, "、".join(sorted("%s/%s" % (a or "（不归入阵型）", b) for a, b in others))))

        target = joblib.place_version(g, j, d, fname, text, auth, nt)
        rel = os.path.relpath(target, ROOT).replace(os.sep, "/")
        written.append({"path": rel, "job": j, "changes": changes})
    msg = rebuild()
    return {"ok": True, "written": written, "warnings": warnings,
            "message": "已写入 %d 份 · %s" % (len(written), msg)}


def api_version_meta(payload):
    vdir = v_dir_of(payload.get("file"))
    authors = joblib.parse_authors(payload.get("author"))
    note = str(payload.get("note") or "").strip()

    for fname, value in (("作者.txt", joblib.author_text(authors)), ("说明.txt", note)):
        path = os.path.join(vdir, fname)
        if value:
            joblib.write_text_file(path, value)
        elif os.path.isfile(path):
            # 清空时连同同目录下其它被识别为作者/说明的文本一起清掉
            for other in os.listdir(vdir):
                low = other.lower()
                if not low.endswith(".txt"):
                    continue
                if fname == "作者.txt" and ("作者" in other or "author" in low):
                    os.remove(os.path.join(vdir, other))
                elif fname == "说明.txt" and any(h in low for h in ("说明", "备注", "更新", "note")):
                    os.remove(os.path.join(vdir, other))
    return {"ok": True, "message": rebuild()}


def _set_job_name_in_versions(job_dir, new_name):
    """重命名作业集时，把各版本 JSON 里的 name 一起改掉（站点标题用的就是它）。"""
    changed = 0
    for dirpath, _dirnames, filenames in os.walk(job_dir):
        for fname in filenames:
            if not fname.lower().endswith((".json", ".txt")):
                continue
            path = os.path.join(dirpath, fname)
            try:
                data = joblib.load_json_file(path)
            except Exception:
                continue
            if not joblib.looks_like_job(data):
                continue
            if data.get("name") != new_name:
                data["name"] = new_name
                joblib.dump_json_file(path, data)
                changed += 1
    return changed


def api_rename_job(payload):
    src = job_dir_of(payload.get("group"), payload.get("job"))
    name = joblib.sanitize_component(payload.get("to"), "")
    if not name:
        raise ApiError("新名字为空")
    old = os.path.basename(src)
    if name == old:
        return {"ok": True, "message": "名字没变，无需重命名"}
    dst = os.path.join(os.path.dirname(src), name)
    if os.path.exists(dst):
        raise ApiError("同一位置已有同名作业集：%s" % name)
    os.rename(src, dst)
    fixed = _set_job_name_in_versions(dst, name)
    return {"ok": True,
            "message": "已重命名为 %s（同步改了 %d 个版本里的 name）· %s" % (name, fixed, rebuild())}


def api_rename_group(payload):
    src = group_dir_of(payload.get("group"))
    old = os.path.basename(src)
    name = joblib.sanitize_component(payload.get("to"), "")
    if not name:
        raise ApiError("新阵型名为空")
    if name == old:
        return {"ok": True, "message": "阵型名没变，无需重命名"}
    dst = os.path.join(joblib.JOBS_DIR, name)
    if os.path.exists(dst):
        raise ApiError("同名阵型已存在：%s" % name)

    # _group.json 的 name 是站点显示名：它正好等于旧目录名时一起改，免得改了目录站点还显示旧名
    meta_path = os.path.join(src, "_group.json")
    if os.path.isfile(meta_path):
        try:
            meta = joblib.load_json_file(meta_path)
            if isinstance(meta, dict) and str(meta.get("name") or "").strip() in ("", old):
                meta["name"] = name
                joblib.dump_json_file(meta_path, meta)
        except Exception as e:
            print("[warn] _group.json 更新失败：%s" % e)

    os.rename(src, dst)
    return {"ok": True, "message": "阵型已重命名为 %s · %s" % (name, rebuild())}


def api_move_job(payload):
    src = job_dir_of(payload.get("group"), payload.get("job"))
    to_group = joblib.sanitize_component(payload.get("toGroup"), "")
    dst_dir = os.path.join(joblib.JOBS_DIR, to_group) if to_group else joblib.JOBS_DIR
    dst = os.path.join(dst_dir, os.path.basename(src))

    norm = lambda p: os.path.normcase(os.path.abspath(p))
    src_abs, dst_abs, dst_dir_abs = norm(src), norm(dst), norm(dst_dir)

    if dst_abs == src_abs:
        return {"ok": True, "message": "本来就在这个阵型里，没有移动"}
    # 阵型名不小心和作业集同名 → 会变成「自己套自己」，直接拒掉并说清楚
    if dst_dir_abs == src_abs or dst_dir_abs.startswith(src_abs + os.sep) or dst_abs.startswith(src_abs + os.sep):
        raise ApiError("阵型名不能和作业集自己同名（%s）；想让它不归入阵型请选「（不归入阵型）」" % to_group)

    os.makedirs(dst_dir, exist_ok=True)
    if os.path.exists(dst):
        raise ApiError("目标阵型里已有同名作业集：%s" % to_group)
    os.rename(src, dst)
    return {"ok": True, "message": "已移动到 %s · %s" % (to_group or "（不归入阵型）", rebuild())}


def api_delete_job(payload):
    path = job_dir_of(payload.get("group"), payload.get("job"))
    if not payload.get("confirm"):
        raise ApiError("删除作业集需要二次确认")
    shutil.rmtree(path)
    return {"ok": True, "message": "已删除作业集 · %s" % rebuild()}


def api_delete_group(payload):
    path = group_dir_of(payload.get("group"))
    if not payload.get("confirm"):
        raise ApiError("删除阵型需要二次确认")

    # moveJobs=True：先把这个阵型里的作业集挪到 jobs/ 顶层（= 不归入阵型），再删阵型目录
    move_jobs = bool(payload.get("moveJobs"))
    job_names = [d for d in sorted(os.listdir(path)) if os.path.isdir(os.path.join(path, d))]
    moved = []
    if move_jobs:
        # 先整体检查冲突，避免搬一半
        for name in job_names:
            if os.path.exists(os.path.join(joblib.JOBS_DIR, name)):
                raise ApiError("jobs/ 下已经有同名作业集「%s」，先挪开或改名再删这个阵型" % name)
        for name in job_names:
            os.rename(os.path.join(path, name), os.path.join(joblib.JOBS_DIR, name))
            moved.append(name)

    shutil.rmtree(path)
    if moved:
        msg = "已删除阵型，%d 个作业集移到「不归入阵型」：%s" % (len(moved), "、".join(moved))
    elif move_jobs:
        msg = "已删除空阵型"
    else:
        msg = "已删除阵型（连同 %d 个作业集）" % len(job_names)
    return {"ok": True, "message": msg + " · " + rebuild()}


def api_delete_version(payload):
    vdir = v_dir_of(payload.get("file"))
    if os.path.dirname(vdir) == joblib.JOBS_DIR or not vdir.startswith(joblib.JOBS_DIR):
        raise ApiError("拒绝删除：不是版本目录")
    if not payload.get("confirm"):
        raise ApiError("删除版本需要二次确认")
    shutil.rmtree(vdir)
    return {"ok": True, "message": "已删除该版本 · %s" % rebuild()}


def api_set_group_meta(payload):
    gdir = group_dir_of(payload.get("group"))
    name = str(payload.get("name") or "").strip()
    desc = str(payload.get("desc") or "").strip()
    path = os.path.join(gdir, "_group.json")
    if not name and not desc:
        if os.path.isfile(path):
            os.remove(path)
        return {"ok": True, "message": "已清空分组信息 · %s" % rebuild()}
    meta = {}
    if os.path.isfile(path):
        try:
            meta = joblib.load_json_file(path)
            if not isinstance(meta, dict):
                meta = {}
        except Exception:
            meta = {}
    meta["name"] = name or os.path.basename(gdir)
    if desc:
        meta["desc"] = desc
    else:
        meta.pop("desc", None)
    joblib.dump_json_file(path, meta)
    return {"ok": True, "message": "分组信息已保存 · %s" % rebuild()}


def api_rebuild(payload):
    return {"ok": True, "message": rebuild()}


def api_audit(payload=None):
    issues = joblib.audit_jobs()
    return {
        "ok": True,
        "issues": issues,
        "error_count": sum(1 for i in issues if i.get("level") == "error"),
        "warn_count": sum(1 for i in issues if i.get("level") != "error"),
    }


def api_cleanup_empty(payload):
    removed = joblib.clean_empty_dirs()
    msg = ("已清理 %d 个空目录：%s" % (len(removed), "、".join(removed))) if removed else "没有空目录需要清理"
    return {"ok": True, "removed": removed, "message": msg + " · " + rebuild()}


ROUTES = {
    "upload": api_upload,
    "version_meta": api_version_meta,
    "rename_job": api_rename_job,
    "rename_group": api_rename_group,
    "move_job": api_move_job,
    "delete_job": api_delete_job,
    "delete_group": api_delete_group,
    "delete_version": api_delete_version,
    "set_group_meta": api_set_group_meta,
    "rebuild": api_rebuild,
    "audit": api_audit,
    "cleanup_empty": api_cleanup_empty,
}


# ---------------------------------------------------------------- HTTP 层

class Handler(SimpleHTTPRequestHandler):
    server_version = "MaapvzTool/1.0"

    def __init__(self, *args, directory=None, preview=False, **kwargs):
        self.preview = preview
        super().__init__(*args, directory=directory, **kwargs)

    def log_message(self, fmt, *args):
        sys.stdout.write("[http] " + (fmt % args) + "\n")
        sys.stdout.flush()

    def end_headers(self):
        # 工具里的改动是「立即生效」的：页面/索引/JSON 一律不缓存，
        # 不然浏览器会拿旧副本，看起来像没生效（线上 Pages 走 no-store，这里保持一致口径）
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def _host_ok(self):
        host = (self.headers.get("Host") or "").split(":")[0].strip().lower()
        return host in ("127.0.0.1", "localhost", "[::1]", "::1")

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/"):
            if self.preview:
                return self._json({"ok": False, "error": "这是预览模式，不提供写接口"}, 403)
            if not self._host_ok():
                return self._json({"ok": False, "error": "只允许本机访问"}, 403)
            if self.path.startswith("/api/ping"):
                return self._json({"ok": True, "root": ROOT, "version": 1})
            if self.path.startswith("/api/audit"):
                return self._json(api_audit({}))
            return self._json({"ok": False, "error": "未知接口"}, 404)
        if self.path in ("/", ""):
            self.path = "/index.html" if self.preview else "/admin.html"
        return super().do_GET()

    def do_POST(self):
        if self.preview:
            return self._json({"ok": False, "error": "这是预览模式，改了不会生效；请用「启动维护工具.bat」"}, 403)
        if not self.path.startswith("/api/"):
            return self._json({"ok": False, "error": "只有 /api/* 接受 POST"}, 404)
        if not self._host_ok():
            return self._json({"ok": False, "error": "只允许本机访问"}, 403)
        if self.headers.get(TOOL_HEADER) != "1":
            return self._json({"ok": False, "error": "缺少工具标记：请从维护工具页面操作"}, 403)
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        if length <= 0:
            return self._json({"ok": False, "error": "空请求体"}, 400)
        if length > MAX_BODY:
            return self._json({"ok": False, "error": "请求体过大"}, 413)
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except Exception as e:
            return self._json({"ok": False, "error": "请求体不是 JSON：%s" % e}, 400)
        if not isinstance(payload, dict):
            return self._json({"ok": False, "error": "请求体必须是对象"}, 400)

        action = payload.get("action")
        handler = ROUTES.get(action)
        if not handler:
            return self._json({"ok": False, "error": "未知操作：%s" % action}, 404)
        try:
            return self._json(handler(payload))
        except ApiError as e:
            return self._json({"ok": False, "error": str(e)}, 400)
        except Exception as e:
            traceback.print_exc()
            return self._json({"ok": False, "error": "服务器错误：%s" % e}, 500)


class LocalServer(ThreadingHTTPServer):
    # Windows 上 allow_reuse_address=True 会让两个进程同时绑定同一端口（新旧版本混跑），
    # 这里显式关掉，占用时宁可换端口。
    allow_reuse_address = False
    daemon_threads = True
    # 浏览器用不到反向 DNS，省掉每个请求一次的解析卡顿
    request_queue_size = 64


def port_free(port):
    """端口空着才用：直接尝试连接，连得上说明已经有人在监听。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.2)
        return s.connect_ex((HOST, port)) != 0


def open_server(preferred=8932, tries=40, preview=False):
    handler = functools.partial(Handler, directory=ROOT, preview=preview)
    for port in range(preferred, preferred + tries):
        if not port_free(port):
            continue
        try:
            return LocalServer((HOST, port), handler), port
        except OSError:
            continue
    return None, 0


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    preview = "--preview" in argv
    port = None
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])

    # 预览工具默认 8931（和线上无关），维护工具默认 8932，两者可以同时开
    httpd, port = open_server(port or (8931 if preview else 8932), preview=preview)
    if httpd is None:
        print("[error] 找不到可用端口（被占用了 40 个）")
        return 1
    url = "http://%s:%d/%s" % (HOST, port, "index.html" if preview else "admin.html")

    print("=" * 68)
    if preview:
        print("MAAPVZ 作业集站点 · 本地预览（只读）")
        print("仓库目录：%s" % ROOT)
        print("预览地址：%s" % url)
        print("")
        print("· 这个窗口要一直开着；关掉窗口 = 关闭预览")
        print("· 只读模式：上传 / 改信息 / 重命名等写接口全部关闭")
        print("· 要改内容请用「启动维护工具.bat」")
    else:
        print("MAAPVZ 作业集维护工具（本地）")
        print("仓库目录：%s" % ROOT)
        print("工具地址：%s" % url)
        print("")
        print("· 这个窗口要一直开着；关掉窗口 = 关闭工具")
        print("· 改动直接写进 jobs/ 目录，改完在 GitHub Desktop / 命令行 commit + push 才会上线")
        print("· 只想看站点效果？用「启动作业站预览工具.bat」")
    print("· 只监听本机回环地址，别人连不进来")
    print("=" * 68)

    if "--no-open" not in argv:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[bye] 已关闭")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
