#!/bin/bash
# selftest.sh —— 不依赖 Kindle，在 Mac 上验证整条链路
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
PY="${PYTHON:-python3}"
fail=0

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
ok()   { printf '   \033[32m✓\033[0m %s\n' "$1"; }
bad()  { printf '   \033[31m✗\033[0m %s\n' "$1"; fail=1; }

step "1/5 农历与节气锚点"
"$PY" render/lunar.py > /tmp/dash_lunar.txt 2>&1 && ok "全部锚点通过" \
    || { bad "农历自测失败"; cat /tmp/dash_lunar.txt; }

step "2/5 取济宁天气"
"$PY" -m render.weather > /tmp/dash_weather.txt 2>&1 && ok "取数成功（$(head -1 /tmp/dash_weather.txt)）" \
    || { bad "取数失败，检查外网"; cat /tmp/dash_weather.txt; }

step "3/5 渲染 600×800 灰度 PNG"
if "$PY" -m render.dash -o /tmp/dash_selftest.png > /tmp/dash_render.txt 2>&1; then
    "$PY" - <<'EOF'
from PIL import Image
im = Image.open('/tmp/dash_selftest.png')
assert im.size == (600, 800), im.size
assert im.mode == 'L', im.mode
print("   ✓ 尺寸/模式正确")
EOF
    [ $? -eq 0 ] || bad "PNG 尺寸或模式不对"
else
    bad "渲染失败"; cat /tmp/dash_render.txt
fi

step "4/5 启动服务并拉图"
PORT="${PORT:-8099}"
"$PY" server.py --port "$PORT" > /tmp/dash_server.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for _ in $(seq 1 20); do
    curl -sf --max-time 2 "http://127.0.0.1:$PORT/health" > /dev/null && break
    sleep 0.5
done
if curl -sf --max-time 10 -o /tmp/dash_served.png "http://127.0.0.1:$PORT/dash.png"; then
    "$PY" - <<'EOF'
from PIL import Image
im = Image.open('/tmp/dash_served.png')
assert im.size == (600, 800)
print("   ✓ /dash.png 返回 600×800 PNG")
EOF
    [ $? -eq 0 ] || bad "服务返回的图不对"
else
    bad "拉图失败"; cat /tmp/dash_server.log
fi

step "5/5 Kindle 脚本校验逻辑（模拟 PNG 头解析）"
"$PY" - <<'EOF'
import struct, zlib
raw = open('/tmp/dash_served.png','rb').read(24)
assert raw[:8] == b'\x89PNG\r\n\x1a\n', 'PNG 魔数不对'
w, h = struct.unpack('>II', raw[16:24])
assert (w, h) == (600, 800), (w, h)
print(f"   ✓ 魔数与 IHDR 宽高 {w}×{h}，Kindle 端会通过校验")
EOF
[ $? -eq 0 ] || bad "PNG 头解析异常"

printf '\n'
if [ "$fail" -eq 0 ]; then
    printf '\033[32m全部通过。\033[0m 预览图：preview/dash-preview.png\n'
else
    printf '\033[31m有步骤失败，见上面输出。\033[0m\n'
fi
exit "$fail"
