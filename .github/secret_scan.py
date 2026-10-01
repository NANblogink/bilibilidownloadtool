#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
敏感内容扫描 —— 提交/推送前的最后一道防线。

用法：
    python .github/secret_scan.py              # 扫描已跟踪文件 + 暂存区
    python .github/secret_scan.py --staged     # 只扫描暂存区（pre-commit 钩子用）
    python .github/secret_scan.py --all        # 扫描工作区全部未忽略文件

退出码 0 = 干净；1 = 发现疑似敏感内容。

安装为本地钩子（一次性）：
    python .github/secret_scan.py --install-hook

设计原则：
  - 宁可少报也不要满屏误报：只匹配「值」不匹配「键名」。
    例如 SESSDATA 作为 cookie 字段名出现在代码里是正常的，
    只有 SESSDATA=<一长串真实值> 才会被判定。
  - 已知的历史泄露值只存 SHA-256 指纹，不存原文，避免本文件二次扩散。
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys

try:
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------- 已知泄露值指纹
# 只存指纹。任何内容一旦命中，说明该值曾泄露过，绝不能再出现在提交里。
KNOWN_LEAKED_FINGERPRINTS = {
    "2af836230645457224f6d6cec0237a499c818b8ebe4f89b31081685b1b494c62": "旧云端 API Token",
    "3f99a3e2e029073daa70a442c40faf8c94216b013297d0cf8a2a5f16c8bf19b2": "旧云端 AES 密钥",
    "2cef67e531c4756331f8251b1b6950ab2b15b772ddc549bcb930bae268601e05": "旧云端固定 IV",
    "3387b47b51ffbfb023c3bd7096e372acf7b0b2cd2a62cbb54b393562ef9f18ab": "旧云端后台密码",
}

# ---------------------------------------------------------------- 内容规则
# (名称, 正则, 说明) —— 正则必须捕获「值」，不能只匹配键名
CONTENT_RULES = [
    ("PRIVATE_KEY",
     re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----"),
     "私钥内容"),

    ("BILI_SESSDATA",
     re.compile(r"""SESSDATA["']?\s*[=:]\s*["']?([A-Za-z0-9%_\-]{24,})"""),
     "B 站 SESSDATA 真实值"),

    ("BILI_JCT",
     re.compile(r"""bili_jct["']?\s*[=:]\s*["']?([0-9a-f]{24,})"""),
     "B 站 bili_jct 真实值"),

    ("BILI_SID",
     re.compile(r"""\bsid["']?\s*[=:]\s*["']?([a-z0-9]{8,})["']?\s*[,;\n]"""),
     "B 站 sid 真实值"),

    ("AWS_ACCESS_KEY",
     re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
     "AWS Access Key"),

    ("GITHUB_TOKEN",
     re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
     "GitHub Token"),

    ("OPENAI_KEY",
     re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
     "OpenAI 风格密钥"),

    ("SLACK_TOKEN",
     re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}\b"),
     "Slack Token"),

    # 赋值型密钥：要求值足够长且像随机串，避免匹配 "password": "请输入密码"
    ("HARDCODED_SECRET",
     re.compile(
         r"""(?:password|passwd|pwd|secret|token|api_?key|access_?key|private_?key)"""
         r"""["']?\s*[=:]\s*["']([A-Za-z0-9!@#$%^&*_\-+]{16,})["']""",
         re.IGNORECASE),
     "疑似硬编码口令/密钥（长度 ≥16）"),
]

# 这些文件里出现 password 之类字样属于正常（表单、变量名、示例），跳过内容规则
CONTENT_SKIP_SUFFIX = (".svg", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".pdf",
                       ".mp4", ".mp3", ".zip", ".7z", ".exe", ".dll", ".pyd",
                       ".so", ".qm", ".ttf", ".otf", ".woff", ".woff2", ".wasm")
CONTENT_SKIP_PATH_PARTS = ("docs/reference/", "_整理/", "other/android/.build_stage/")

# 占位值白名单：这些「值」是文档/示例里的假数据，不算泄露
VALUE_ALLOWLIST = {
    "test_value", "test_csrf", "your_password", "your_password_here",
    "change_me", "changeme", "placeholder", "xxxxxxxx", "example",
    "PUT_YOUR_API_TOKEN_HERE", "PUT_YOUR_BCRYPT_HASH_HERE",
    "PUT_YOUR_BASE64_KEY_HERE", "PUT_YOUR_USERNAME_HERE",
    "changeit", "password", "1234567890",
    # 微软 Windows 清单里的标准 publicKeyToken（出现在所有 UAC manifest 中）
    "6595b64144ccf1df",
    # PyInstaller / NSIS 等构建产物中的常见固定串
    "0000000000000000", "ffffffffffffffff",
}

# ---------------------------------------------------------------- 文件名规则
# 未忽略且将被提交时报警的敏感文件名
SENSITIVE_NAME_PATTERNS = [
    (re.compile(r"^cookie[s]?\.(txt|json)$", re.IGNORECASE), "Cookie 凭据文件"),
    (re.compile(r"^admin_config\.php$"), "云端私有配置（含密钥）"),
    (re.compile(r"^\.env(\..+)?$"), "环境变量文件"),
    (re.compile(r"\.(pem|key|p12|pfx|jks|keystore|mobileprovision)$", re.IGNORECASE), "密钥/证书文件"),
    (re.compile(r"^id_(rsa|ed25519)(\.pub)?$"), "SSH 私钥"),
    (re.compile(r"^secrets?\.json$", re.IGNORECASE), "密钥清单"),
]


def run_git(args):
    try:
        out = subprocess.run(["git"] + args, cwd=ROOT, capture_output=True,
                             timeout=120)
        return out.stdout.decode("utf-8", "replace")
    except Exception:
        return ""


def list_files(mode):
    if mode == "staged":
        raw = run_git(["diff", "--cached", "--name-only", "--diff-filter=ACM"])
    elif mode == "all":
        raw = run_git(["ls-files", "--cached", "--others", "--exclude-standard"])
    else:
        raw = run_git(["ls-files", "--cached"])
    return [l.strip() for l in raw.splitlines() if l.strip()]


def read_blob(path, staged):
    """读取文件内容；staged 模式优先读暂存区版本。"""
    if staged:
        try:
            out = subprocess.run(["git", "show", ":" + path], cwd=ROOT,
                                 capture_output=True, timeout=60)
            if out.returncode == 0:
                return out.stdout.decode("utf-8", "replace")
        except Exception:
            pass
    full = os.path.join(ROOT, path.replace("/", os.sep))
    if not os.path.isfile(full):
        return None
    try:
        with open(full, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except Exception:
        return None


def scan(mode):
    files = list_files(mode)
    findings = []

    for path in files:
        norm = path.replace("\\", "/")

        # ---- 文件名规则 ----
        base = os.path.basename(norm)
        for pat, desc in SENSITIVE_NAME_PATTERNS:
            if pat.search(base):
                findings.append((path, "文件名", desc, base))
                break

        # ---- 内容规则 ----
        if norm.endswith(CONTENT_SKIP_SUFFIX):
            continue
        if any(p in norm for p in CONTENT_SKIP_PATH_PARTS):
            continue

        text = read_blob(path, staged=(mode == "staged"))
        if not text:
            continue

        for name, pat, desc in CONTENT_RULES:
            for m in pat.finditer(text):
                value = m.group(1) if m.groups() else m.group(0)
                if value in VALUE_ALLOWLIST:
                    continue
                if value.startswith("PUT_YOUR"):
                    continue
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append((path, f"第 {line_no} 行", desc, value[:12] + "…"))
                break

        # ---- 已知泄露值指纹 ----
        for m in re.finditer(r"""["']([A-Za-z0-9!@#$%^&*_\-+/=.]{8,120})["']""", text):
            cand = m.group(1)
            if cand in VALUE_ALLOWLIST:
                continue
            fp = hashlib.sha256(cand.encode()).hexdigest()
            if fp in KNOWN_LEAKED_FINGERPRINTS:
                line_no = text.count("\n", 0, m.start()) + 1
                findings.append((path, f"第 {line_no} 行",
                                 "命中历史泄露值：" + KNOWN_LEAKED_FINGERPRINTS[fp],
                                 cand[:12] + "…"))

    return files, findings


def install_hook():
    hook_dir = os.path.join(ROOT, ".git", "hooks")
    if not os.path.isdir(hook_dir):
        print("未找到 .git/hooks，跳过钩子安装")
        return 1
    hook_path = os.path.join(hook_dir, "pre-commit")
    script = (
        "#!/bin/sh\n"
        "# 由 .github/secret_scan.py --install-hook 生成\n"
        'python "$(git rev-parse --show-toplevel)/.github/secret_scan.py" --staged || {\n'
        '  echo ""\n'
        '  echo "提交被拦截：疑似敏感内容。确认无风险可用 git commit --no-verify 跳过。"\n'
        "  exit 1\n"
        "}\n"
    )
    with open(hook_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(script)
    try:
        os.chmod(hook_path, 0o755)
    except Exception:
        pass
    print("已安装 pre-commit 钩子: %s" % hook_path)
    return 0


def main():
    ap = argparse.ArgumentParser(description="敏感内容扫描")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--staged", action="store_true", help="只扫描暂存区")
    g.add_argument("--all", action="store_true", help="扫描全部未忽略文件")
    ap.add_argument("--install-hook", action="store_true", help="安装 pre-commit 钩子")
    args = ap.parse_args()

    if args.install_hook:
        return install_hook()

    mode = "staged" if args.staged else ("all" if args.all else "tracked")
    files, findings = scan(mode)

    print("=" * 68)
    print(" 敏感内容扫描（模式：%s）" % mode)
    print("=" * 68)
    print("扫描文件数：%d" % len(files))

    if not findings:
        print("\n未发现疑似敏感内容 ✅")
        return 0

    # 去重（同一文件同一描述只报一次）
    seen = set()
    uniq = []
    for f in findings:
        key = (f[0], f[2])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(f)

    print("\n发现 %d 处疑似敏感内容 ❌\n" % len(uniq))
    print("%-46s %-12s %-30s %s" % ("文件", "位置", "类型", "值(截断)"))
    print("-" * 68)
    for path, loc, desc, val in uniq:
        print("%-46s %-12s %-30s %s" % (path[:45], loc, desc[:29], val))

    print("\n处理建议：")
    print("  1. 若是真实凭据 → 立即轮换，并从文件里删除（轮换比删除更重要）")
    print("  2. 若是占位/示例值 → 加入 secret_scan.py 的 VALUE_ALLOWLIST")
    print("  3. 若该文件本不该入库 → 加进 .gitignore 并 git rm --cached")
    return 1


if __name__ == "__main__":
    sys.exit(main())
