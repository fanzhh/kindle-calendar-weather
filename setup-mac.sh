#!/bin/bash
# setup-mac.sh —— 在 Mac（mini）上装好渲染服务并注册开机自启
#
#     bash setup-mac.sh              # 默认端口 8099
#     bash setup-mac.sh 8123         # 换端口
#     bash setup-mac.sh 8099 --no-load   # 只装环境，不注册 launchd

set -euo pipefail

PORT="${1:-8099}"
NO_LOAD="${2:-}"
PROJECT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$PROJECT/.venv"
LABEL="com.local.kindle-dash"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

echo "==> 项目目录: $PROJECT"
echo "==> 端口: $PORT"

if ! command -v python3 > /dev/null 2>&1; then
    echo "找不到 python3，请先装：brew install python" >&2
    exit 1
fi

# 找一个能 import PIL 的解释器：优先已有 venv，其次系统 python3，最后才建 venv
PY=""
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import PIL" > /dev/null 2>&1; then
    PY="$VENV/bin/python"
    echo "==> 复用已有虚拟环境: $VENV"
elif python3 -c "import PIL" > /dev/null 2>&1; then
    PY="$(command -v python3)"
    echo "==> 系统 python3 已带 Pillow，直接使用: $PY"
else
    echo "==> 创建虚拟环境并安装 Pillow"
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet -r "$PROJECT/requirements.txt"
    PY="$VENV/bin/python"
fi

echo "==> 渲染一张测试图"
(cd "$PROJECT" && "$PY" -m render.dash -o "$PROJECT/preview/dash-preview.png")

if [ "$NO_LOAD" = "--no-load" ]; then
    echo "==> 跳过 launchd 注册"
else
    echo "==> 注册 launchd 自启: $PLIST"
    mkdir -p "$(dirname "$PLIST")"
    cat > "$PLIST" <<PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>$LABEL</string>
    <key>ProgramArguments</key>
    <array>
        <string>$PY</string>
        <string>$PROJECT/server.py</string>
        <string>--port</string>
        <string>$PORT</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$PROJECT</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$PROJECT/cache/server.log</string>
    <key>StandardErrorPath</key>
    <string>$PROJECT/cache/server.err</string>
</dict>
</plist>
PLIST_EOF

    launchctl unload "$PLIST" 2> /dev/null || true
    launchctl load "$PLIST"
    sleep 2
fi

IP="$(ipconfig getifaddr en0 2> /dev/null || ipconfig getifaddr en1 2> /dev/null || echo 127.0.0.1)"
cat <<TIPS

==> 完成

  预览:      http://$IP:$PORT/
  面板图:    http://$IP:$PORT/dash.png
  健康检查:  http://$IP:$PORT/health

把下面这一行写进 Kindle 的 /mnt/us/dash.conf：

  DASH_URL=http://$IP:$PORT/dash.png

查看日志: tail -f "$PROJECT/cache/server.err"
停掉服务: launchctl unload "$PLIST"
TIPS
