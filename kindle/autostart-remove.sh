#!/bin/sh
# autostart-remove.sh —— 卸载「后台自动更新」常驻任务
#
# 停掉并删除 /etc/upstart/dash-autoupdate.conf。
# 已装好的屏保图不受影响（要还原官方屏保用 ss-restore.sh）。

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

JOB=/etc/upstart/dash-autoupdate.conf
LOG=/mnt/us/dash.log

say() { echo "$*"; echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

say "=== 卸载自动更新任务 ==="

initctl stop dash-autoupdate > /dev/null 2>&1 \
    || stop dash-autoupdate > /dev/null 2>&1

if [ -f "$JOB" ]; then
    mntroot rw || { say "mntroot rw 失败"; exit 1; }
    rm -f "$JOB"
    sync
    mntroot ro
    say "已删除 $JOB"
else
    say "任务文件不存在，无需删除"
fi

say "完成。屏保图保持现状，只是不再自动刷新。"
