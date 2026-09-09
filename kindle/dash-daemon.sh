#!/bin/sh
# dash-daemon.sh —— 常驻守护（由 upstart 任务 dash-autoupdate 拉起）
#
# 职责：
#   1) 定时刷新屏保图（挂钟判断，每 60 秒轮询一次）
#   2) 监听 powerd 事件，实现"睡着也能定时更新"
#
# 关于定时唤醒的关键结论（实机 + 社区逆向相互印证）：
#   直接把时间写进 /sys/class/rtc/rtc0/wakealarm 然后等系统自己休眠 —— 不会唤醒，
#   因为 powerd 在最后阶段会用 rtcWakeup 覆盖它。正确做法是在 readyToSuspend 阶段：
#       lipc-set-prop -i com.lab126.powerd rtcWakeup <秒>
#
# 事件时序：
#   熄屏 → goingToScreenSaver → readyToSuspend ×7 → suspending → 休眠
#   唤醒 → wakeupFromSuspend → resuming → outOfScreenSaver → exitingScreenSaver
#
# 配置（/mnt/us/dash.conf）：改完点一次 autostart-install 让守护进程重载
#   DASH_INTERVAL=1800        图片刷新检查间隔（秒，最小 300）
#   DASH_WAKE_INTERVAL=3600   RTC 唤醒间隔（秒；0 = 关闭）
#   DASH_WIFI=auto            auto=休眠前关无线、唤醒后开；never=不碰无线

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

CONF=/mnt/us/dash.conf
POLL=60
STAMP=/mnt/us/.dash_last_check
IMG=/mnt/us/screensaver-backup/.current.png
LOG=/mnt/us/dash.log
POWERD=com.lab126.powerd
EVENTS="goingToScreenSaver,wakeupFromSuspend,readyToSuspend"

log() { echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null; }

load_conf() {
    INTERVAL=1800
    WAKE=0
    WIFI_MODE=auto
    URL=http://192.168.1.10:8099/dash.png
    if [ -r "$CONF" ]; then
        eval "$(tr -d '\r' < "$CONF")"
        INTERVAL="${DASH_INTERVAL:-1800}"
        WAKE="${DASH_WAKE_INTERVAL:-0}"
        WIFI_MODE="${DASH_WIFI:-auto}"
        URL="${DASH_URL:-$URL}"
    fi
    case "$INTERVAL" in '' | *[!0-9]*) INTERVAL=1800 ;; esac
    case "$WAKE" in '' | *[!0-9]*) WAKE=0 ;; esac
    [ "$INTERVAL" -lt 300 ] && INTERVAL=300
    [ "$WAKE" -gt 0 ] && [ "$WAKE" -lt 120 ] && WAKE=120
    HOSTPORT=$(echo "$URL" | sed -e 's|^https\?://||' -e 's|/.*$||')
}

load_conf

# ---------------------------------------------------------------------------
# 网络诊断
# ---------------------------------------------------------------------------
net_probe() {
    command -v curl > /dev/null 2>&1 || return 1
    curl -fs -m 8 -o /dev/null "http://$HOSTPORT/health" 2> /dev/null
}

wifi_switch() {
    lipc-get-prop com.lab126.cmd wirelessEnable 2> /dev/null | tr -d '\r\n'
}

wifi_ip() {
    out=$(ifconfig wlan0 2> /dev/null | grep -i "inet" | head -1)
    [ -z "$out" ] && out=$(ip -4 addr show wlan0 2> /dev/null | grep -i "inet " | head -1)
    echo "$out" | sed 's/^ *//' | cut -c1-60
}

# 一行日志说明当前网络状态：开关 / IP / 默认路由
net_dump() {
    wl=$(wifi_switch)
    ipa=$(wifi_ip)
    rt=$(awk 'NR>1 && $2=="00000000" {print "有"} NR>1 && $2!="00000000" {n=1} END {if (n && !found) print ""}' /proc/net/route 2> /dev/null | head -1)
    [ -z "$rt" ] && rt="无"
    log "$1：无线=${wl:-?} IP=${ipa:-无} 默认路由=${rt}"
}

# ---------------------------------------------------------------------------
# 事件处理
# ---------------------------------------------------------------------------
handle_event() {
    line="$1"
    load_conf          # 允许改完 dash.conf 后不重启进程也生效

    case "$line" in
        readyToSuspend*)
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
                [ "$i" -ge 4 ] && log "readyToSuspend：设置 rtcWakeup 失败"
            fi
            if [ "$WIFI_MODE" = "auto" ]; then
                net_dump "休眠前"
                lipc-set-prop com.lab126.cmd wirelessEnable 0 > /dev/null 2>&1
                sleep 2
                net_dump "关无线后"
            fi
            ;;

        wakeupFromSuspend*)
            log "wakeupFromSuspend：开始更新"
            net_dump "唤醒瞬间"

            ok=0

            # ---- 策略 1：直接开无线 ----
            lipc-set-prop com.lab126.cmd wirelessEnable 1 > /dev/null 2>&1
            sleep 15
            net_dump "策略1后"
            probe=$(net_probe && echo OK || echo FAIL)
            log "策略1：探测=$probe"
            if [ "$probe" = "OK" ]; then
                /mnt/us/documents/ss-install.sh > /dev/null 2>&1 && { ok=1; log "策略1成功"; }
            fi

            # ---- 策略 2：关掉再打开 ----
            if [ "$ok" = "0" ]; then
                log "策略2：切换无线 0→1"
                lipc-set-prop com.lab126.cmd wirelessEnable 0 > /dev/null 2>&1
                sleep 5
                lipc-set-prop com.lab126.cmd wirelessEnable 1 > /dev/null 2>&1
                sleep 25
                net_dump "策略2后"
                probe=$(net_probe && echo OK || echo FAIL)
                log "策略2：探测=$probe"
                if [ "$probe" = "OK" ]; then
                    /mnt/us/documents/ss-install.sh > /dev/null 2>&1 && { ok=1; log "策略2成功"; }
                fi
            fi

            # ---- 策略 3：继续等，最多 150 秒 ----
            if [ "$ok" = "0" ]; then
                i=0
                while [ "$i" -lt 10 ]; do
                    i=$((i + 1))
                    sleep 15
                    probe=$(net_probe && echo OK || echo FAIL)
                    log "策略3：第 $i 次探测=$probe"
                    if [ "$probe" = "OK" ]; then
                        /mnt/us/documents/ss-install.sh > /dev/null 2>&1 && { ok=1; log "策略3成功（第 $i 次）"; }
                        break
                    fi
                done
                [ "$ok" = "0" ] && net_dump "策略3结束"
            fi

            [ "$ok" = "0" ] && log "三种策略都没连上网络"

            last=$(date +%s 2> /dev/null || echo 0)
            [ "$last" -gt 0 ] && date +%s > "$STAMP" 2> /dev/null
            [ -f "$IMG" ] && eips -g "$IMG" > /dev/null 2>&1
            log "wakeupFromSuspend：结束（ok=$ok）"
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
        sleep 5
    done
}

# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------
if command -v lipc-wait-event > /dev/null 2>&1; then
    WATCH_OK="是"
else
    WATCH_OK="否"
fi

log "守护启动：刷新间隔 ${INTERVAL}s，唤醒间隔 ${WAKE}s，无线策略=${WIFI_MODE}，事件监听=${WATCH_OK}"

watch_events &
WATCHER=$!
trap 'kill "$WATCHER" 2> /dev/null' EXIT INT TERM

last=$(cat "$STAMP" 2> /dev/null || echo 0)
case "$last" in '' | *[!0-9]*) last=0 ;; esac

while true; do
    load_conf
    now=$(date +%s 2> /dev/null || echo 0)
    if [ "$now" -gt 0 ] && [ $((now - last)) -ge "$INTERVAL" ]; then
        /mnt/us/documents/ss-install.sh > /dev/null 2>&1
        last=$(date +%s 2> /dev/null || echo "$now")
        date +%s > "$STAMP" 2> /dev/null
    fi
    sleep "$POLL"
done
