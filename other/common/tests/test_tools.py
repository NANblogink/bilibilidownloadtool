"""tool_manager 跨平台行为测试：工具目录解析 + 压缩包解压。"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import install_paths  # noqa: E402

PROJECT_ROOT = install_paths()

import tool_manager as tm  # noqa: E402
from platform_utils import app_data_dir, IS_WINDOWS  # noqa: E402

fails = []


def check(name, cond, extra=""):
    print(("  PASS " if cond else "  FAIL ") + name + (" " + str(extra) if extra else ""))
    if not cond:
        fails.append(name)


print("== _app_tool_dirs ==")
dirs = tm._app_tool_dirs()
for d in dirs:
    print("   ", d)
if IS_WINDOWS:
    print("  (Windows 平台，反斜杠属正常)")
else:
    check("no backslash paths on posix",
          all('\\' not in d for d in dirs), dirs)
    check("no Windows AppData literal on posix",
          not any('AppData' in d for d in dirs), dirs)

print()
print("== _extract_archive dispatch ==")
td = tempfile.mkdtemp(prefix="tooltest_")

# 建tar.xz验证
import tarfile
src_dir = os.path.join(td, "src")
os.makedirs(os.path.join(src_dir, "ffmpeg-7.0-amd64-static"), exist_ok=True)
fake = os.path.join(src_dir, "ffmpeg-7.0-amd64-static", "ffmpeg")
with open(fake, "w") as f:
    f.write("#!/bin/sh\necho fake\n")
os.chmod(fake, 0o755)

tar_path = os.path.join(td, "ffmpeg.tar.xz")
with tarfile.open(tar_path, "w:xz") as tf:
    tf.add(os.path.join(src_dir, "ffmpeg-7.0-amd64-static"),
           arcname="ffmpeg-7.0-amd64-static")

out_dir = os.path.join(td, "out_tar")
ok, err = tm._extract_archive(tar_path, out_dir)
check("tar.xz extraction succeeds", ok, err)
found = os.path.join(out_dir, "ffmpeg-7.0-amd64-static", "ffmpeg")
check("extracted binary exists", os.path.isfile(found), found)

# zip still works
import zipfile
zip_path = os.path.join(td, "b.zip")
with zipfile.ZipFile(zip_path, "w") as z:
    z.writestr("bento4/bin/mp4decrypt", "fake")
out_zip = os.path.join(td, "out_zip")
ok2, err2 = tm._extract_archive(zip_path, out_zip)
check("zip extraction still works", ok2, err2)
check("zip content extracted",
      os.path.isfile(os.path.join(out_zip, "bento4", "bin", "mp4decrypt")))

print()
print("== tar path traversal is blocked ==")
evil = os.path.join(td, "evil.tar")
evil_target = os.path.join(td, "ESCAPED.txt")
with tarfile.open(evil, "w") as tf:
    info = tarfile.TarInfo("../ESCAPED.txt")
    payload = b"pwned"
    import io as _io
    info.size = len(payload)
    tf.addfile(info, _io.BytesIO(payload))
out_evil = os.path.join(td, "out_evil")
tm._extract_archive(evil, out_evil)
check("path traversal blocked", not os.path.exists(evil_target),
      "escaped file created!" if os.path.exists(evil_target) else "good")

print()
print("TOTAL FAILURES:", len(fails), fails)
sys.exit(1 if fails else 0)
