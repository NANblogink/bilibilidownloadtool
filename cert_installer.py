#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
证书安装器 - 在新设备上安装 BilibiliDownloader 自签名证书

最终用户双击运行即可：
1. 以管理员权限安装证书到"受信任根证书颁发机构"
2. 安装到"受信任发布者"
3. 安装完成后，该设备运行 BilibiliDownloader.exe 不再报"未知发行者"

证书文件 BilibiliDownloader_dev.cer 需与本程序同目录
"""
import os
import sys
import ctypes
import subprocess
import tempfile


def is_admin():
    """检查是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def relaunch_as_admin():
    """以管理员权限重新启动自己"""
    params = " ".join(f'"{a}"' for a in sys.argv)
    try:
        # UAC 提权
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, params, None, 1  # SW_SHOWNORMAL
        )
        # ShellExecuteW 返回值 > 32 表示成功
        if ret > 32:
            return True
        return False
    except Exception:
        return False


def find_cert_file():
    """查找证书文件

    搜索顺序：
    1. exe 同目录（打包后主程序）
    2. _internal 目录（PyInstaller --onedir 布局）
    3. sys._MEIPASS（PyInstaller --onefile 解包临时目录）
    4. 脚本同目录（开发环境）
    5. 父目录
    """
    candidates = []

    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
        candidates.append(os.path.join(base, "BilibiliDownloader_dev.cer"))
        candidates.append(os.path.join(base, "_internal", "BilibiliDownloader_dev.cer"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "BilibiliDownloader_dev.cer"))
        candidates.append(os.path.join(os.path.dirname(base), "BilibiliDownloader_dev.cer"))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        candidates.append(os.path.join(base, "BilibiliDownloader_dev.cer"))
        candidates.append(os.path.join(os.path.dirname(base), "BilibiliDownloader_dev.cer"))

    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def is_cert_installed(cer_path):
    """检查证书是否已安装到本地计算机的根证书和受信任发布者

    返回 (root_ok: bool, publisher_ok: bool)
    """
    if sys.platform != "win32":
        return False, False
    try:
        # 用 certutil -verify 验证过于复杂，这里用 -store 查找证书指纹
        # 先从证书文件读取指纹（SHA1 哈希）
        import subprocess
        result = subprocess.run(
            ["certutil", "-dump", cer_path],
            capture_output=True, text=True, timeout=10,
            creationflags=0x08000000,
        )
        # 解析出证书指纹（Cert Hash(sha1)）
        thumbprint = ""
        for line in result.stdout.split("\n"):
            line = line.strip()
            if "Cert Hash(sha1):" in line:
                # 形如 "Cert Hash(sha1): ab cd ef ..."
                thumbprint = line.split(":", 1)[1].strip().replace(" ", "")
                break
        if not thumbprint:
            return False, False

        def _in_store(store_name):
            try:
                r = subprocess.run(
                    ["certutil", "-store", store_name, thumbprint],
                    capture_output=True, text=True, timeout=10,
                    creationflags=0x08000000,
                )
                # 输出包含证书指纹表示已存在
                return thumbprint.lower() in (r.stdout + r.stderr).lower()
            except Exception:
                return False

        return _in_store("Root"), _in_store("TrustedPublisher")
    except Exception:
        return False, False


def auto_install_cert(silent=True):
    """静默自动安装证书（调用方需已是管理员权限）

    参数:
        silent: True 时不打印任何信息（适合主程序启动时静默安装）

    返回:
        (success: bool, message: str)
    """
    if sys.platform != "win32":
        return False, "非Windows平台，跳过证书安装"

    if not is_admin():
        return False, "需要管理员权限"

    cer_path = find_cert_file()
    if not cer_path:
        return False, "未找到证书文件 BilibiliDownloader_dev.cer"

    # 检查是否已安装，避免重复安装
    try:
        root_ok, publisher_ok = is_cert_installed(cer_path)
        if root_ok and publisher_ok:
            return True, "证书已安装，跳过"
    except Exception:
        pass

    ok1, msg1 = install_cert(cer_path, "Root", "LocalMachine")
    ok2, msg2 = install_cert(cer_path, "TrustedPublisher", "LocalMachine")

    if not silent:
        print(f"[证书安装] Root: {'成功' if ok1 else '失败 - ' + msg1.strip()[:100]}")
        print(f"[证书安装] TrustedPublisher: {'成功' if ok2 else '失败 - ' + msg2.strip()[:100]}")

    if ok1 and ok2:
        return True, "证书安装成功"
    elif ok1:
        return True, "根证书安装成功，受信任发布者安装失败"
    elif ok2:
        return True, "受信任发布者安装成功，根证书安装失败"
    else:
        return False, f"证书安装失败: {(msg1 + msg2).strip()[:200]}"


def install_cert(cer_path, store_name, store_location="LocalMachine"):
    """用 certutil 安装证书到指定存储区"""
    # certutil -addstore -f <StoreLocation>\<StoreName> <cer_path>
    # 使用 -user 参数安装到 CurrentUser，否则需要管理员
    if store_location == "LocalMachine":
        args = ["certutil", "-addstore", "-f", store_name, cer_path]
    else:
        args = ["certutil", "-user", "-addstore", "-f", store_name, cer_path]

    try:
        # CREATE_NO_WINDOW 避免黑色窗口
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
        return result.returncode == 0, result.stdout + result.stderr
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("  BilibiliDownloader 证书安装器")
    print("  开发者: 寒烟似雪")
    print("=" * 60)
    print()

    # 检查管理员权限
    if not is_admin():
        print("[提示] 需要管理员权限来安装证书到系统存储区")
        print("[提示] 正在请求管理员权限...")
        print()
        if relaunch_as_admin():
            sys.exit(0)
        else:
            print("[错误] 用户取消了管理员权限请求")
            print("[提示] 请右键此程序 -> 以管理员身份运行")
            input("按回车键退出...")
            sys.exit(1)

    # 查找证书
    cer_path = find_cert_file()
    if not cer_path:
        print("[错误] 未找到证书文件 BilibiliDownloader_dev.cer")
        print("[提示] 请确保证书文件与本程序在同一目录")
        input("按回车键退出...")
        sys.exit(1)

    print(f"证书文件: {cer_path}")
    print()

    # 安装到受信任根证书颁发机构
    print("[1/2] 安装到受信任根证书颁发机构...")
    ok1, msg1 = install_cert(cer_path, "Root", "LocalMachine")
    if ok1:
        print("  [成功] 已添加到受信任根证书颁发机构")
    else:
        print(f"  [失败] {msg1.strip()[:200]}")
        print("  [提示] 请尝试手动双击 BilibiliDownloader_dev.cer 安装")

    # 安装到受信任发布者
    print("[2/2] 安装到受信任发布者...")
    ok2, msg2 = install_cert(cer_path, "TrustedPublisher", "LocalMachine")
    if ok2:
        print("  [成功] 已添加到受信任发布者")
    else:
        print(f"  [失败] {msg2.strip()[:200]}")

    print()
    print("=" * 60)
    if ok1 and ok2:
        print("  安装完成!")
        print()
        print("  现在 BilibiliDownloader.exe 在此设备上:")
        print("    - 不再显示'未知发行者'警告")
        print("    - 数字签名显示'寒烟似雪'")
        print()
        print("  注意:")
        print("    - 360 等行为检测类报毒需单独添加信任")
        print("    - 此证书仅信任 BilibiliDownloader 相关程序")
    else:
        print("  部分安装失败，请查看上方错误信息")
    print("=" * 60)
    print()
    input("按回车键退出...")


if __name__ == "__main__":
    main()
