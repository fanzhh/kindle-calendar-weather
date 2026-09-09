#!/bin/sh
# ota-block.sh —— 屏蔽亚马逊官方 OTA 更新
#
# 为什么需要：这台机器是「原生 + 安卓」双系统，官方固件更新会破坏双系统分区，
# 也可能把越狱环境搅乱。屏蔽方法就是社区里 renametobin 做的事：
# 把亚马逊的生产签名密钥改名，设备就无法验证官方更新包。
# 我们自己的包走 /etc/uks/pubdevkey01.pem（越狱装的开发者密钥），不受影响。
#
# 放在 /mnt/us/documents/，书库里点一下即可。开机后连 WiFi 之前先跑这个。

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

LOG=/mnt/us/dash.log
say() { echo "$*"; echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

say "=== 屏蔽 OTA 更新 ==="

mntroot rw || { say "mntroot rw 失败"; exit 1; }

for k in /etc/uks/pubprodkey01.pem /etc/uks/pubprodkey02.pem; do
    if [ -f "$k" ]; then
        mv "$k" "$k.bak" 2> /dev/null && say "已改名: $k -> $(basename "$k").bak"
    elif [ -f "$k.bak" ]; then
        say "已经是屏蔽状态: $(basename "$k").bak"
    else
        say "未找到 $k"
    fi
done

sync
mntroot ro

say "完成。官方更新包将无法通过校验。"
say "（要恢复：把 .bak 改回原名）"
