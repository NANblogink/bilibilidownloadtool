#!/usr/bin/env bash
# 需要一个可自由分发的中文字体，用来解决 Kivy 默认字体不含汉字导致的乱码。
# 优先 Noto Sans SC（OFL 许可，可商用可再分发）。
set -u
cd "$HOME"

URLS=(
  "https://mirrors.tuna.tsinghua.edu.cn/CTAN/fonts/noto-cjk/NotoSansCJKsc-Regular.otf"
  "https://mirrors.aliyun.com/CTAN/fonts/noto-cjk/NotoSansCJKsc-Regular.otf"
  "https://mirrors.cloud.tencent.com/CTAN/fonts/noto-cjk/NotoSansCJKsc-Regular.otf"
  "https://github.com/notofonts/noto-cjk/raw/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
  "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/SubsetOTF/SC/NotoSansSC-Regular.otf"
)

OK=0
for u in "${URLS[@]}"; do
    echo "  尝试: $u"
    if timeout 120 curl -fsSL --connect-timeout 20 -o /tmp/noto_sc.otf "$u" 2>/dev/null; then
        sz=$(stat -c%s /tmp/noto_sc.otf 2>/dev/null || echo 0)
        if [ "$sz" -gt 1000000 ]; then
            mv /tmp/noto_sc.otf "$HOME/NotoSansSC-Regular.otf"
            echo "    成功 ($((sz / 1024)) KB)"
            OK=1
            break
        fi
        echo "    文件过小 ($sz)"
    else
        echo "    失败"
    fi
done

if [ "$OK" != "1" ]; then
    echo
    echo "  !! 所有源均失败，尝试 pip 安装的字体包"
    /usr/bin/python3 -m pip download --no-deps -d /tmp/fontpkg fonttools 2>&1 | tail -2
fi

echo
echo "=== 结果 ==="
ls -la "$HOME"/*.otf "$HOME"/*.ttf 2>/dev/null | sed 's/^/  /'
