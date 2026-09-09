#!/bin/sh
# dash-daemon.sh —— 常驻守护（由 upstart 任务 dash-autoupdate 拉起）
#
# 两件事：
#   1) 定时刷新屏保图：用挂钟时间判断，每 60 秒轮询一次
#      （不用 sleep 长间隔：busybox 的 sleep 走 CLOCK_MONOTONIC，休眠期间不走）
#   2) 监听 powerd 事件，在**正确时机**设置 RTC 唤醒，实现"睡着也能定时更新"
#
# 关于第 2 点的关键结论（实机 + 社区逆向相互印证）：
#   直接把时间写进 /sys/class/rtc/rtc0/wakealarm 然后等系统自己休眠 —— 不会唤醒。
#   因为 powerd 在休眠前的最后阶段会用 rtcWakeup 覆盖掉它。
#   正确做法：在 readyToSuspend 事件里执行
#       lipc-set-prop -i com.lab126.powerd rtcWakeup <秒>
#   提前或之后设置都不生效。
#
# 事件时序（powerd 发出）：
#   熄屏 → goingToScreenSaver → readyToSuspend ×7（每 5s）→ suspending → 休眠
#   唤醒 → wakeupFromSuspend → resuming → outOfScreenSaver → exitingScreenSaver
#   定时器唤醒只会发 wakeupFromSuspend，屏幕不会亮、屏保也不会切出去。
#
# 配置（/mnt/us/dash.conf）：
#   DASH_INTERVAL=1800        图片刷新检查间隔（秒，最小 300）
#   DASH_WAKE_INTERVAL=3600   RTC 唤醒间隔（秒；0 = 关闭该功能）
#   DASH_WIFI=auto            auto=休眠前关 WiFi、唤醒后开（定时唤醒后重连更可靠）

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

CONF=/mnt/us/dash.conf
[ -r "$CONF" ] && eval "$(tr -d '\r' < "$CONF")"

INTERVAL="${DASH_INTERVAL:-1800}"
WAKE="${DASH_WAKE_INTERVAL:-0}"
WIFI_MODE="${DASH_WIFI:-auto}"

case "$INTERVAL" in '' | *[!0-9]*) INTERVAL=1800 ;; esac
case "$WAKE" in '' | *[!0-9]*) WAKE=0 ;; esac
[ "$INTERVAL" -lt 300 ] && INTERVAL=300
[ "$WAKE" -gt 0 ] && [ "$WAKE" -lt 120 ] && WAKE=120

POLL=60
STAMP=/mnt/us/.dash_last_check
IMG=/mnt/us/screensaver-backup/.current.png
LOG=/mnt/us/dash.log

POWERD=com.lab126.powerd
EVENTS="goingToScreenSaver,wakeupFromSuspend,readyToSuspend"

log() { echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

# ---------------------------------------------------------------------------
# 事件处理
# ---------------------------------------------------------------------------
handle_event() {
    line="$1"

    case "$line" in
        readyToSuspend*)
            # 这是唯一能成功设置唤醒时间的时机
            if [ "$WAKE" -gt 0 ]; then
                i=0
                while [ "$i" -lt 4 ]; do
                    if lipc-set-prop -i "$POWERD" rtcWakeup "$WAKE" > /dev/null 2>&1; then
                        log "readyToSuspend：已设置 rtcWakeup=${WAKE}s"
                        break
                    fi
                    i=$((i + 1))
                    sleep 1
                done
                [ "$i" -ge 4 ] && log "readyToSuspend：设置 rtcWakeup 失败（共试 4 次）"
            fi
            # 休眠前关掉 WiFi，唤醒后再开——定时唤醒后这样重连最可靠
            if [ "$WIFI_MODE" = "auto" ]; then
                lipc-set-prop com.lab126.cmd wirelessEnable 0 > /dev/null 2>&1
            fi
            ;;

        wakeupFromSuspend*)
            log "wakeupFromSuspend：开始更新"
            if [ "$WIFI_MODE" = "auto" ]; then
                lipc-set-prop com.lab126.cmd wirelessEnable 1 > /dev/null 2>&1
                sleep 12
            fi
            /mnt/us/documents/ss-install.sh > /dev/null 2>&1
            last=$(date +%s 2> /dev/null || echo 0)
            [ "$last" -gt 0 ] && date +%s > "$STAMP" 2> /dev/null
            # 定时唤醒时屏幕不会自己刷新，主动把新图画上去
            [ -f "$IMG" ] && eips -g "$IMG" > /dev/null 2>&1
            log "wakeupFromSuspend：更新完成"
            ;;

        goingToScreenSaver*)
            log "goingToScreenSaver"
            ;;
    esac
}

watch_events() {
    while true; do
        lipc-wait-event -m "$POWERD" "$EVENTS" 2> /dev/null \
            | while read -r line; do
                [ -n "$line" ] && handle_event "$line"
            done
        # lipc-wait-event 退出（工具缺失或异常）就等一会重试
        sleep 5
    done
}

# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if command -v lipc-wait-event > /dev/null 2>&1; then
    WATCH_OK="是"
else
    WATCH_OK="否（找不到 lipc-wait-event，定时唤醒不可用）"
fi

log "守护启动：刷新间隔 ${INTERVAL}s，轮询 ${POLL}s，唤醒间隔 ${WAKE}s，事件监听=${WATCH_OK}"

watch_events &
WATCHER=$!
trap 'kill "$WATCHER" 2> /dev/null' EXIT INT TERM

# 上次刷新的时间点（跨重启保留）
last=$(cat "$STAMP" 2> /dev/null || echo 0)
case "$last" in '' | *[!0-9]*) last=0 ;; esac

# ---------------------------------------------------------------------------
# 主循环：定时刷新
# ---------------------------------------------------------------------------
while true; do
    now=$(date +%s 2> /dev/null || echo 0)
    if [ "$now" -gt 0 ] && [ $((now - last)) -ge "$INTERVAL" ]; then
        /mnt/us/documents/ss-install.sh > /dev/null 2>&1
        last=$(date +%s 2> /dev/null || echo "$now")
        date +%s > "$STAMP" 2> /dev/null
    fi
    sleep "$POLL"
done
