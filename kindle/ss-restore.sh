#!/bin/sh
# ss-restore.sh —— 还原成官方原生屏保
#
# 把 /mnt/us/screensaver-backup/ 里备份的原图拷回
# /usr/share/blanket/screensaver/，并重启框架。
#
# 同样放在 /mnt/us/documents/，书库里点一下即可。

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

SS_DIR=/usr/share/blanket/screensaver
BACKUP=/mnt/us/screensaver-backup
LOG=/mnt/us/dash.log

say() { echo "$*"; echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

if [ ! -d "$BACKUP" ]; then
    say "找不到备份目录 $BACKUP，无法还原"
    exit 1
fi

n=0
for f in "$BACKUP"/bg_ss*.png; do
    [ -f "$f" ] || continue
    n=$((n + 1))
done

if [ "$n" -eq 0 ]; then
    say "备份目录里没有 bg_ss*.png，无法还原"
    exit 1
fi

say "找到 $n 张备份图，开始还原"
mntroot rw || { say "mntroot rw 失败"; exit 1; }

for f in "$BACKUP"/bg_ss*.png; do
    [ -f "$f" ] || continue
    cp "$f" "$SS_DIR/$(basename "$f")" 2> /dev/null || say "还原失败: $f"
done
sync
mntroot ro

rm -f "$BACKUP/.current.png" /mnt/us/.dash_applied 2> /dev/null

say "还原完成，2 秒后重启框架"
( sleep 2; restart framework > /dev/null 2>&1 \
    || /etc/init.d/framework restart > /dev/null 2>&1 ) &
