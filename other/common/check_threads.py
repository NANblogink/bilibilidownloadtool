#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查非守护线程（non-daemon thread）—— 跨平台退出挂起风险。

背景
====
Python 解释器退出时会等待所有**非守护线程**结束。桌面版里有若干后台线程
用于网络请求（WBI 密钥、cookie 校验等），如果漏写 daemon=True：

  * Windows 上通常不明显（进程被窗口销毁流程带走）
  * Linux / macOS 上表现为**关闭窗口后程序不退出**，一直挂在终端

这是一个真实出现过的 bug（bilibili_parser 的 _update_wbi_keys 曾漏写），
本脚本用 AST 静态分析确保不再复发。

判定规则
========
对每个 threading.Thread(...) 调用，满足任一即视为安全：
  1. 调用处显式传了 daemon=...
  2. 结果赋给变量 x 后，紧接着 6 行内出现 x.daemon = ...
  3. 调用处显式传了 daemon=False（有意为之，也放行但会提示）

用法：
    python other/common/check_threads.py

退出码 0 表示通过。
"""
import ast
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(HERE))

SKIP_DIRS = {
    '.git', '__pycache__', 'dist', 'dist_beta', 'build', 'build_dist',
    'build_dist_beta', 'build_parts', 'build_parts_beta', 'output',
    'output_beta', 'temp', 'bento4', 'ffmpeg', 'mpv', 'Resources',
    'assets', 'copyright', '_整理', '云端', 'upx_tool', 'other',
}


def has_daemon_kwarg(call):
    return any(kw.arg == 'daemon' for kw in call.keywords)


def is_thread_call(node):
    f = node.func
    if isinstance(f, ast.Attribute) and f.attr == 'Thread':
        return True
    if isinstance(f, ast.Name) and f.id == 'Thread':
        return True
    return False


class ThreadVisitor(ast.NodeVisitor):
    def __init__(self, path, lines):
        self.path = path
        self.lines = lines
        self.issues = []

    def visit_Call(self, node):
        if is_thread_call(node) and not has_daemon_kwarg(node):
            end = getattr(node, 'end_lineno', node.lineno)
            # 往后看几行，是否有 xxx.daemon = ...
            tail = '\n'.join(self.lines[end:end + 6])
            if '.daemon' not in tail:
                self.issues.append(
                    (node.lineno, self.lines[node.lineno - 1].strip()[:110]))
        self.generic_visit(node)


def main():
    issues = []
    scanned = 0
    for dp, dn, fn in os.walk(PROJECT_ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            if not f.endswith('.py'):
                continue
            p = os.path.join(dp, f)
            # 跳过本脚本自身与分析脚本
            if f.startswith('_') or f in ('check_threads.py',):
                continue
            try:
                src = open(p, encoding='utf-8', errors='replace').read()
                tree = ast.parse(src)
            except Exception:
                continue
            scanned += 1
            v = ThreadVisitor(p, src.splitlines())
            v.visit(tree)
            for ln, txt in v.issues:
                issues.append((os.path.relpath(p, PROJECT_ROOT), ln, txt))

    print("=" * 68)
    print("非守护线程检查（非守护线程会导致 Linux/macOS 关闭窗口后不退出）")
    print("=" * 68)
    print("已扫描 %d 个 Python 文件" % scanned)

    if issues:
        print("\n发现 %d 处非守护线程：" % len(issues))
        for rel, ln, txt in issues:
            print("  %s:%d\n      %s" % (rel, ln, txt))
        print("\n修复方式：为 threading.Thread(...) 增加 daemon=True，")
        print("          或在其后设置 thread.daemon = True。")
        return 1

    print("\n全部线程均为守护线程或已显式指定 daemon。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
