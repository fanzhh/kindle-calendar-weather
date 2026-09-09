#!/bin/sh
# autostart-install.sh —— 安装「后台自动更新」常驻任务
#
# 写一个 upstart 任务 /etc/upstart/dash-autoupdate.conf：
#   start on started framework   开机 / 框架启动时拉起
#   stop  on stopping framework  框架停止时一并退出
#   respawn                      意外退出自动重拉
#   exec  /mnt/us/documents/dash-daemon.sh
#
# 效果：设备开机后每 30 分钟（可配）检查一次面板图，有变化就静默替换，
# 不重启框架、不打断阅读。休眠时进程被冻结，唤醒后继续。
#
# 放在 /mnt/us/documents/，书库里点一下即可。卸载用 autostart-remove.sh。

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

JOB=/etc/upstart/dash-autoupdate.conf
LOG=/mnt/us/dash.log

say() { echo "$*"; echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

say "=== 安装自动更新任务 ==="

if [ ! -f /mnt/us/documents/dash-daemon.sh ]; then
    say "缺少 /mnt/us/documents/dash-daemon.sh，先把它拷进去"
    exit 1
fi

mntroot rw || { say "mntroot rw 失败"; exit 1; }

cat > "$JOB" << 'JOB_EOF'
description "Kindle dash auto update"
author "kindle-custom"

start on started framework
stop on stopping framework

respawn
respawn limit 10 300

exec /mnt/us/documents/dash-daemon.sh
JOB_EOF

sync
mntroot ro

if [ -f "$JOB" ]; then
    say "已写入 $JOB"
else
    say "写入失败"
    exit 1
fi

# 先停后起：确保加载的是最新版 dash-daemon.sh（重跑本脚本即可升级守护进程）
initctl stop dash-autoupdate > /dev/null 2>&1 \
    || stop dash-autoupdate > /dev/null 2>&1
sleep 1

if initctl start dash-autoupdate > /dev/null 2>&1; then
    say "已启动自动更新任务"
elif start dash-autoupdate > /dev/null 2>&1; then
    say "已启动自动更新任务"
else
    say "任务已安装，将在下次框架启动时自动运行"
fi

say "完成。之后每 30 分钟静默刷新一次（间隔见 dash.conf 的 DASH_INTERVAL）。"
