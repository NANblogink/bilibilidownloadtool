#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打包 Windows 内测包（IS_BETA_BUILD=True）。

内测包与正式包的**唯一代码差异**是 core/app_config.py 里的开关：
    IS_BETA_BUILD = True   → 启动需输入授权QQ验证，更新检查走 beta 通道
    IS_BETA_BUILD = False  → 无授权限制，更新检查走 stable 通道

本脚本在打包期间把开关置为 True，结束后（含异常/中断）无条件还原，
避免把内测开关误提交进仓库。

产物全部落在 *_beta 目录，**不覆盖正式包**：
    dist_beta/BilibiliDownloader/               完整程序目录
    dist_beta/uninstaller.exe                   卸载器
    dist_beta/_lean/BilibiliDownloader/         精简程序目录
    output_beta/BilibiliDownloader_<v>_full.zip 完整包（服务端 download_url 指向它）
    output_beta/BilibiliDownloader_<v>.zip      精简包
    output_beta/<v>_installer.exe               在线安装器
    output_beta/<v>_installer_embedded.exe      内嵌安装器
    output_beta/cert_installer.exe              证书安装器

用法：
    python other/windows/build_beta.py
    python other/windows/build_beta.py --skip-embedded    # 跳过 321MB 内嵌安装器
    python other/windows/build_beta.py --only main        # 只跑某一步（调试用）

服务端注册（必须由人工完成，否则内测用户收不到）：
    app_version 表插入一行，channel='beta'，download_url 指向上面那个 full.zip。
    注意 version 列是单列 UNIQUE：2.2.1 若已作为 stable 存在，需先改其 channel
    或改用更高的版本号，否则会撞唯一约束。
"""
import argparse
import atexit
import importlib.util
import os
import re
import shutil
import signal
import subprocess
import sys
import time


def _find_root(start):
    """向上查找包含 core/app_config.py 的目录作为项目根。"""
    cur = os.path.abspath(start)
    for _ in range(6):
        if os.path.isfile(os.path.join(cur, "core", "app_config.py")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    raise RuntimeError("未找到项目根目录（缺少 core/app_config.py）")


ROOT = _find_root(__file__)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "core"))
import _pathsetup  # noqa: E402,F401
from app_config import APP_NAME_EN as APP_NAME, VERSION_NUM  # noqa: E402

APP_CONFIG = os.path.join(ROOT, "core", "app_config.py")

DIST_BETA = os.path.join(ROOT, "dist_beta")
OUTPUT_BETA = os.path.join(ROOT, "output_beta")
WORK_BETA = os.path.join(ROOT, "build_win_beta")

MAIN_DIR = os.path.join(DIST_BETA, APP_NAME)
LEAN_MAIN_DIR = os.path.join(DIST_BETA, "_lean", APP_NAME)

PY = sys.executable


def log(m):
    print("[%s] %s" % (time.strftime("%H:%M:%S"), m), flush=True)


def load_build_main():
    """按路径加载同目录的 build_main.py，复用它的复制/压缩函数。"""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "build_main.py")
    spec = importlib.util.spec_from_file_location("build_main", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------- 内测开关

def get_beta_flag():
    """读取当前 IS_BETA_BUILD 的值。"""
    with open(APP_CONFIG, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"^IS_BETA_BUILD\s*=\s*(True|False)\s*$", content, re.M)
    if not m:
        raise RuntimeError("未在 core/app_config.py 中找到 IS_BETA_BUILD")
    return m.group(1) == "True"


def set_beta_flag(want):
    """把 IS_BETA_BUILD 设为 want，并回读确认已落盘。

    刻意不返回「原值」——那种设计下连续调用两次就会把返回值当成
    「原值」去还原，从而把开关留在 True。要保存原值请显式调用
    get_beta_flag() 后再 set_beta_flag(original)。
    """
    with open(APP_CONFIG, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"^IS_BETA_BUILD\s*=\s*(True|False)\s*$", content, re.M)
    if not m:
        raise RuntimeError("未在 core/app_config.py 中找到 IS_BETA_BUILD")
    target = "True" if want else "False"
    if m.group(1) != target:
        content = content[:m.start(1)] + target + content[m.end(1):]
        with open(APP_CONFIG, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    # 回读复验，防止「报成功但未落盘」
    got = get_beta_flag()
    if got != want:
        raise RuntimeError("开关写入失败：期望 %s 实际 %s" % (want, got))
    return got


# 开关备份标记：进程被强杀（TerminateProcess 不触发 finally/atexit）时，
# 靠这个文件在下次运行时自愈，避免内测开关永久残留在仓库里。
FLAG_MARKER = os.path.join(WORK_BETA, ".beta_flag_backup")


def _read_marker():
    try:
        with open(FLAG_MARKER, "r", encoding="utf-8") as f:
            return f.read().strip() == "True"
    except Exception:
        return None


def _write_marker(value):
    os.makedirs(WORK_BETA, exist_ok=True)
    with open(FLAG_MARKER, "w", encoding="utf-8") as f:
        f.write("True" if value else "False")


def _clear_marker():
    try:
        os.remove(FLAG_MARKER)
    except Exception:
        pass


def restore_flag():
    """把开关还原成标记文件里记录的原值，并清除标记。幂等。"""
    original = _read_marker()
    if original is None:
        return
    set_beta_flag(original)
    _clear_marker()
    log("IS_BETA_BUILD 已还原为 %s" % original)


def self_heal():
    """启动时自愈：上次若被强杀留下标记，先还原再继续。"""
    if os.path.isfile(FLAG_MARKER):
        original = _read_marker()
        log("[自愈] 发现上次构建残留标记，IS_BETA_BUILD 还原为 %s" % original)
        restore_flag()


def _install_exit_guards():
    atexit.register(restore_flag)

    def _on_signal(signum, _frame):
        log("收到信号 %d，还原开关后退出" % signum)
        restore_flag()
        sys.exit(128 + signum)

    for sig in ("SIGINT", "SIGTERM", "SIGBREAK"):
        s = getattr(signal, sig, None)
        if s is None:
            continue
        try:
            signal.signal(s, _on_signal)
        except Exception:
            pass


# ---------------------------------------------------------------- 构建步骤

def move_aside(path):
    """把已存在的输出目录改名让开，返回新路径（不存在则返回 None）。

    PyInstaller 的 COLLECT 在 --noconfirm 下会先 rmtree 掉同名输出目录。
    目录里有 2500+ 文件时会触发沙箱的批量删除保护
    （[safe-delete][SAFE_DELETE_BULK_CONFIRM_REQUIRED]），删除被拒 →
    COLLECT 中断 → distpath 里留着的还是上一次的旧产物，
    而构建过程本身却「看起来成功」。改名是瞬时操作，不受该限制影响。
    """
    if not os.path.exists(path):
        return None
    aside = path.rstrip("\\/") + "_prev_" + time.strftime("%Y%m%d_%H%M%S")
    os.rename(path, aside)
    log("旧目录已改名让开: %s" % os.path.basename(aside))
    return aside


def run_pyinstaller(spec_path, distpath, workpath, extra=None):
    args = [PY, "-m", "PyInstaller", spec_path, "--noconfirm",
            "--distpath=" + distpath, "--workpath=" + workpath]
    if extra:
        args += extra
    log("PyInstaller: %s" % os.path.basename(spec_path))
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError("PyInstaller 失败(%d): %s" % (r.returncode, spec_path))
    return True


def step_main():
    """完整主程序（含 PyQt5）→ dist_beta/BilibiliDownloader/"""
    move_aside(MAIN_DIR)
    run_pyinstaller(os.path.join(ROOT, "BilibiliDownloader.spec"),
                    DIST_BETA, os.path.join(WORK_BETA, "main"))
    if not os.path.isdir(MAIN_DIR):
        raise RuntimeError("COLLECT 未产出 %s（检查是否有批量删除被拦截）" % MAIN_DIR)


def step_uninstaller():
    """卸载器（单文件）→ dist_beta/uninstaller.exe"""
    run_pyinstaller(os.path.join(ROOT, "uninstaller.spec"),
                    DIST_BETA, os.path.join(WORK_BETA, "uninstaller"))


def step_lean():
    """精简主程序（入口 boot.py，剥离 PyQt5）→ dist_beta/_lean/"""
    move_aside(LEAN_MAIN_DIR)
    build_lean = os.path.join(ROOT, "other", "windows", "build_lean.py")
    args = [PY, build_lean,
            "--distpath=" + os.path.join(DIST_BETA, "_lean"),
            "--workpath=" + os.path.join(WORK_BETA, "lean")]
    log("精简包构建（剥离 PyQt5）")
    r = subprocess.run(args, cwd=ROOT)
    if r.returncode != 0:
        raise RuntimeError("精简包构建失败(%d)" % r.returncode)
    if not os.path.isdir(LEAN_MAIN_DIR):
        raise RuntimeError("精简包未产出 %s" % LEAN_MAIN_DIR)


def step_assemble_full(bm):
    """复制工具 + 卸载器进完整包目录，并打 zip。"""
    bm.MAIN_DIR = MAIN_DIR
    bm.DIST_DIR = DIST_BETA
    bm.INTERNAL_DIR = os.path.join(MAIN_DIR, "_internal")
    bm.OUTPUT_DIR = OUTPUT_BETA
    os.makedirs(OUTPUT_BETA, exist_ok=True)

    if not os.path.isdir(MAIN_DIR):
        raise RuntimeError("完整包目录不存在: %s" % MAIN_DIR)

    un = os.path.join(DIST_BETA, "uninstaller.exe")
    if os.path.isfile(un):
        shutil.copy2(un, os.path.join(MAIN_DIR, "uninstaller.exe"))
        log("已复制 uninstaller.exe (%.1f MB)" % (os.path.getsize(un) / 1048576))

    t1 = bm.copy_ffmpeg()
    t2 = bm.copy_mpv()
    t3 = bm.copy_bento4()
    log("工具合计: %.1f MB" % ((t1 + t2 + t3) / 1048576))

    zip_path = os.path.join(OUTPUT_BETA, "%s_%s_full.zip" % (APP_NAME, VERSION_NUM))
    if not bm.make_zip(MAIN_DIR, zip_path, "完整包(含 ffmpeg/mpv/bento4)"):
        raise RuntimeError("完整包压缩失败")
    return zip_path


def step_assemble_lean(bm):
    """复制 mpv + 卸载器进精简包目录，并打 zip。"""
    bm.LEAN_MAIN_DIR = LEAN_MAIN_DIR
    bm.DIST_DIR = DIST_BETA
    bm.OUTPUT_DIR = OUTPUT_BETA
    os.makedirs(OUTPUT_BETA, exist_ok=True)

    if not os.path.isdir(LEAN_MAIN_DIR):
        raise RuntimeError("精简包目录不存在: %s" % LEAN_MAIN_DIR)

    lean_internal = os.path.join(LEAN_MAIN_DIR, "_internal")
    os.makedirs(lean_internal, exist_ok=True)
    t = bm.copy_mpv_to(lean_internal)

    # 防御：确认精简包里确实没有 PyQt5 / ffmpeg / bento4
    for bad in ("PyQt5", "ffmpeg", "bento4"):
        p = os.path.join(lean_internal, bad)
        if os.path.exists(p):
            log("[警告] 精简包内意外存在 %s，已移除" % bad)
            shutil.rmtree(p, ignore_errors=True)

    un = os.path.join(DIST_BETA, "uninstaller.exe")
    if os.path.isfile(un):
        shutil.copy2(un, os.path.join(LEAN_MAIN_DIR, "uninstaller.exe"))
        log("已复制 uninstaller.exe (%.1f MB)" % (os.path.getsize(un) / 1048576))

    log("mpv 合计: %.1f MB" % (t / 1048576))
    zip_path = os.path.join(OUTPUT_BETA, "%s_%s.zip" % (APP_NAME, VERSION_NUM))
    if not bm.make_zip(LEAN_MAIN_DIR, zip_path, "精简包(无 PyQt5，仅 mpv)"):
        raise RuntimeError("精简包压缩失败")
    return zip_path


def step_cert_installer():
    run_pyinstaller(os.path.join(ROOT, "cert_installer.spec"),
                    OUTPUT_BETA, os.path.join(WORK_BETA, "cert"))


def step_installer_online():
    spec = os.path.join(ROOT, "%s_installer.spec" % VERSION_NUM)
    if not os.path.isfile(spec):
        raise RuntimeError("找不到安装器 spec: %s" % spec)
    run_pyinstaller(spec, OUTPUT_BETA, os.path.join(WORK_BETA, "installer"))


def step_installer_embedded():
    """内嵌安装器需要把 full.zip 打进包内。

    原 spec 里 datas 写死了 output/ 路径，内测包要改成 output_beta/，
    因此这里生成一份临时 spec（放在工作目录，不污染项目根）。
    """
    src = os.path.join(ROOT, "%s_installer_embedded.spec" % VERSION_NUM)
    if not os.path.isfile(src):
        raise RuntimeError("找不到内嵌安装器 spec: %s" % src)
    with open(src, "r", encoding="utf-8") as f:
        content = f.read()

    full_zip = os.path.join(OUTPUT_BETA, "%s_%s_full.zip" % (APP_NAME, VERSION_NUM))
    if not os.path.isfile(full_zip):
        raise RuntimeError("内嵌安装器需要先产出 full.zip: %s" % full_zip)

    # spec 是 Python 源码，里面的 Windows 路径是双反斜杠转义形式
    # （'E:\\旧桌面备份\\...\\output\\xxx.zip'），所以搜索串也必须转义，
    # 直接用单反斜杠的 os.path.join 是匹配不上的。
    old_esc = ROOT.replace("\\", "\\\\") + "\\\\output\\\\"
    new_esc = OUTPUT_BETA.replace("\\", "\\\\") + "\\\\"
    patched = content.replace(old_esc, new_esc)

    if patched == content:
        # 退路：万一 spec 被改成单反斜杠或正斜杠写法
        for old_f, new_f in ((ROOT + "\\output\\", OUTPUT_BETA + "\\"),
                             (ROOT.replace("\\", "/") + "/output/",
                              OUTPUT_BETA.replace("\\", "/") + "/")):
            if old_f in content:
                patched = content.replace(old_f, new_f)
                break

    if patched == content:
        raise RuntimeError("未能改写内嵌 spec 的 datas 路径，请检查 spec 内容")

    # 临时 spec 必须放在项目根目录，不能放工作目录：
    # spec 里的 icon=['logo.ico'] 是相对路径，PyInstaller 按 SPECPATH
    # （即 spec 所在目录）解析，放到 build_win_beta/ 下会找不到图标。
    tmp_spec = os.path.join(ROOT, "%s_installer_embedded_beta.spec" % VERSION_NUM)
    with open(tmp_spec, "w", encoding="utf-8") as f:
        f.write(patched)

    try:
        run_pyinstaller(tmp_spec, OUTPUT_BETA, os.path.join(WORK_BETA, "installer_emb"))
    finally:
        try:
            os.remove(tmp_spec)
        except Exception:
            pass


# ---------------------------------------------------------------- 主流程

STEPS = [
    ("main",            "完整主程序（PyInstaller）",        step_main),
    ("uninstaller",     "卸载器（PyInstaller）",            step_uninstaller),
    ("full",            "组装完整包 + zip",                 None),   # 需要 bm，特殊处理
    ("lean",            "精简主程序（PyInstaller）",        step_lean),
    ("leanzip",         "组装精简包 + zip",                 None),
    ("cert",            "证书安装器",                       step_cert_installer),
    ("installer",       "在线安装器",                       step_installer_online),
    ("embedded",        "内嵌安装器（321MB）",              step_installer_embedded),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embedded", action="store_true",
                    help="跳过内嵌安装器（体积 321MB，耗时较长）")
    ap.add_argument("--only", default=None,
                    help="只执行指定步骤（main/uninstaller/full/lean/leanzip/cert/installer/embedded）")
    ap.add_argument("--keep-going", action="store_true",
                    help="某步失败后继续跑后续步骤（默认遇到失败立即停止）")
    args = ap.parse_args()

    _install_exit_guards()
    self_heal()

    bm = load_build_main()

    log("=" * 62)
    log("打包 Windows 内测包  V%s" % VERSION_NUM)
    log("输出: %s" % OUTPUT_BETA)
    log("=" * 62)

    # 先把原值写进标记文件，再改开关。顺序不能反：
    # 若在写标记前就被强杀，就没有任何线索知道原值是什么了。
    original = get_beta_flag()
    _write_marker(original)
    set_beta_flag(True)
    log("IS_BETA_BUILD 已置为 True（原值 %s，结束后还原）" % original)

    failed = []
    try:
        for key, desc, fn in STEPS:
            if args.only and key != args.only:
                continue
            if key == "embedded" and args.skip_embedded:
                log("跳过: %s（--skip-embedded）" % desc)
                continue
            t0 = time.time()
            log("-" * 62)
            log("步骤 [%s] %s" % (key, desc))
            try:
                if key == "full":
                    step_assemble_full(bm)
                elif key == "leanzip":
                    step_assemble_lean(bm)
                else:
                    fn()
                log("完成 [%s] %.1f 秒" % (key, time.time() - t0))
            except Exception as e:
                log("!!! 失败 [%s] %s" % (key, e))
                failed.append((key, str(e)))
                # 打包步骤彼此有依赖（后一步要用前一步的产物），
                # 继续跑只会把旧产物打进包里，产出一个「看起来成功」的坏包。
                if not args.keep_going:
                    log("遇到失败，停止后续步骤（用 --keep-going 可强制继续）")
                    break
    finally:
        restore_flag()

    log("=" * 62)
    if failed:
        log("打包结束，%d 个步骤失败：" % len(failed))
        for k, e in failed:
            log("  ✗ [%s] %s" % (k, e))
        return 1
    log("内测包全部构建完成 ✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
