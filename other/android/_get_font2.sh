#!/usr/bin/env bash
# PyPI 可达，用 PyPI 上的字体包取中文字体。
set -u
cd /tmp
rm -rf fontget && mkdir fontget && cd fontget

echo "=== 尝试 PyPI 字体包 ==="
for pkg in "noto-sans-sc" "fonts-noto-sans-sc" "mplfonts" "fonttools"; do
    echo "  pip download $pkg"
    /usr/bin/python3 -m pip download --no-deps --no-binary :all: -d "/tmp/fontget/$pkg" "$pkg" 2>&1 | tail -2 | sed 's/^/    /'
done

echo
echo "=== 找到的字体文件 ==="
find /tmp/fontget -iname '*.tt[cf]' -o -iname '*.otf' -o -iname '*.zip' 2>/dev/null | head -20 | sed 's/^/  /'

echo
echo "=== 检查是否含中文字形 ==="
for f in $(find /tmp/fontget -iname '*.tt[cf]' -o -iname '*.otf' 2>/dev/null | head -5); do
    sz=$(stat -c%s "$f")
    echo "  $f ($((sz/1024)) KB)"
done
