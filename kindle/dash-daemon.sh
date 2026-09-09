#!/bin/sh
# dash-daemon.sh —— 常驻守护（由 upstart 任务 dash-autoupdate 拉起）
#
# 两件事：
#   1) 定时刷新屏保图：用挂钟时间（date +%s）判断是否到点，每 60 秒轮询一次。
#      不用 sleep 长间隔，因为 busybox 的 sleep 走 CLOCK_MONOTONIC，设备休眠
#      期间这个时钟不走，唤醒后可能还要再等半小时才刷新。
#   2) RTC 定时唤醒（可选）：设备休眠时靠 /sys/class/rtc/rtc*/wakealarm 每小时
#      唤醒一次 → 拉新图 → 把新图画到屏上 → 再睡回去。这样"睡着时"屏保也是新的。
#
# 配置（/mnt/us/dash.conf）：
#   DASH_INTERVAL=1800        图片刷新检查间隔（秒，最小 300）
#   DASH_WAKE_INTERVAL=3600   RTC 唤醒间隔（秒；0 = 关闭该功能）
#   DASH_AUTO_SUSPEND=auto    auto=唤醒后主动睡回去；never=交给系统自己睡
#
# 安全阀：
#   /mnt/us/DISABLE_DASH_SLEEP  存在 → 从不主动休眠
#   电源键任何时候都能唤醒设备

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

CONF=/mnt/us/dash.conf
[ -r "$CONF" ] && eval "$(tr -d '\r' < "$CONF")"

INTERVAL="${DASH_INTERVAL:-1800}"
WAKE="${DASH_WAKE_INTERVAL:-0}"
SUSPEND="${DASH_AUTO_SUSPEND:-auto}"

case "$INTERVAL" in '' | *[!0-9]*) INTERVAL=1800 ;; esac
case "$WAKE" in '' | *[!0-9]*) WAKE=0 ;; esac
[ "$INTERVAL" -lt 300 ] && INTERVAL=300
[ "$WAKE" -gt 0 ] && [ "$WAKE" -lt 600 ] && WAKE=600

POLL=60
STAMP=/mnt/us/.dash_last_check
IMG=/mnt/us/screensaver-backup/.current.png
LOG=/mnt/us/dash.log

log() { echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

# 找到可写的 RTC 唤醒闹钟
RTC=""
for c in /sys/class/rtc/rtc*/wakealarm; do
    [ -w "$c" ] && { RTC="$c"; break; }
done

arm_alarm() {
    [ -n "$RTC" ] || return 1
    now=$(date +%s 2> /dev/null || echo 0)
    [ "$now" -gt 0 ] || return 1
    echo 0 > "$RTC" 2> /dev/null
    echo $((now + WAKE)) > "$RTC" 2> /dev/null
    v=$(cat "$RTC" 2> /dev/null | tr -d '\r\n')
    [ -n "$v" ] && [ "$v" != "0" ]
}

powerd_state() {
    lipc-get-prop com.lab126.powerd state 2> /dev/null | tr -d '\r\n'
}

log "自动更新守护启动，刷新间隔 ${INTERVAL}s，轮询 ${POLL}s，RTC唤醒 ${WAKE}s，RTC=${RTC:-无}"

# 上一轮已经刷新过的时间点（跨重启保留）
last=$(cat "$STAMP" 2> /dev/null || echo 0)
case "$last" in '' | *[!0-9]*) last=0 ;; esac

while true; do
    # ---------- 1) 武装下一次唤醒闹钟 ----------
    armed=0
    if [ "$WAKE" -gt 0 ]; then
        if arm_alarm; then
            armed=1
        else
            log "RTC 闹钟设置失败（RTC=${RTC:-无}），本轮不主动休眠"
        fi
    fi

    # ---------- 2) 需要就刷新图片 ----------
    now=$(date +%s 2> /dev/null || echo 0)
    if [ "$now" -gt 0 ] && [ $((now - last)) -ge "$INTERVAL" ]; then
        /mnt/us/documents/ss-install.sh > /dev/null 2>&1
        last=$(date +%s 2> /dev/null || echo "$now")
        date +%s > "$STAMP" 2> /dev/null
    fi

    # ---------- 3) 睡回去 ----------
    before=$(date +%s 2> /dev/null || echo 0)
    sleep "$POLL"
    after=$(date +%s 2> /dev/null || echo 0)

    # 挂钟跳了一大截 = 刚才被 RTC 唤醒过
    if [ "$before" -gt 0 ] && [ $((after - before)) -gt 180 ]; then
        if [ "$SUSPEND" = "auto" ] && [ "$armed" = "1" ] \
           && [ ! -f /mnt/us/DISABLE_DASH_SLEEP ]; then
            st=$(powerd_state)
            if [ "$st" = "screensaver" ] || [ "$st" = "" ]; then
                # 把最新面板画到屏上，再手动休眠，保证睡着时显示的是日历
                [ -f "$IMG" ] && eips -g "$IMG" > /dev/null 2>&1
                sync
                log "唤醒后更新完毕，主动休眠（${WAKE}s 后自动再唤醒）"
                echo mem > /sys/power/state 2> /dev/null
                log "已被唤醒，继续循环"
            else
                log "刚被唤醒但 powerd 状态为 ${st}（用户在用？），不主动休眠"
            fi
        fi
    fi
done
