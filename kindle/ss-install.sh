#!/bin/sh
# ss-install.sh —— 把日历+天气图装成 Kindle 原生休眠屏保
#
# 原理：原生屏保图在 /usr/share/blanket/screensaver/bg_ss00..19.png（600×800）。
# 本脚本从 Mac 拉取面板图，备份原图后把 20 张全部替换成同一张，
# 这样无论框架随机挑哪张，休眠时看到的都是日历。
#
# 已实测：替换后**不需要重启框架**，下一次休眠就会显示新图。
#
# 放在 /mnt/us/documents/，在书库里点一下即可（sh_integration 提供 root 权限）。
# 配置文件 /mnt/us/dash.conf：
#     DASH_URL=http://192.168.1.10:8099/dash.png
#     DASH_RESTART=never    # 实测无需重启；设 always 可强制重启框架
#     DASH_WIFI=auto        # auto=WiFi 关着时临时打开再关掉；never=只用现有连接
#
# 配套：ss-restore.sh 还原官方屏保；autostart-install.sh 装后台自动更新。

set -u

PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH
export PATH

CONF=/mnt/us/dash.conf
[ -r "$CONF" ] && eval "$(tr -d '\r' < "$CONF")"

URL="${DASH_URL:-http://192.168.1.10:8099/dash.png}"
RESTART="${DASH_RESTART:-never}"
WIFI_MODE="${DASH_WIFI:-auto}"

SS_DIR=/usr/share/blanket/screensaver
BACKUP=/mnt/us/screensaver-backup
STAMP=/mnt/us/.dash_applied
TMP=/tmp/dash.new.png
LOG=/mnt/us/dash.log
LOCK=/tmp/ss-install.pid
MAX_LOG_KB=200

WANT_W=600
WANT_H=800

say() {
    echo "$*"
    echo "$(date '+%F %T') $*" >> "$LOG" 2> /dev/null
}

# 日志太大就裁掉，避免常驻循环把 /mnt/us 写满
trim_log() {
    [ -f "$LOG" ] || return 0
    size_k=$(du -k "$LOG" 2> /dev/null | awk '{print $1}')
    case "$size_k" in
        '' | *[!0-9]*) return 0 ;;
    esac
    if [ "$size_k" -gt "$MAX_LOG_KB" ]; then
        tail -n 300 "$LOG" > "$LOG.tmp" 2> /dev/null && mv "$LOG.tmp" "$LOG"
    fi
}

# 单实例，防止书库里连点两下 / 与后台循环撞车
if [ -f "$LOCK" ] && kill -0 "$(cat "$LOCK" 2> /dev/null)" 2> /dev/null; then
    say "已有实例在运行，退出"
    exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT INT TERM

trim_log

# ---------- WiFi ----------
WIFI_WAS=""

wifi_state() {
    lipc-get-prop com.lab126.cmd wirelessEnable 2> /dev/null | tr -d '\r\n'
}

wifi_prepare() {
    [ "$WIFI_MODE" = "never" ] && return 0
    WIFI_WAS="$(wifi_state)"
    if [ "$WIFI_WAS" != "1" ]; then
        say "WiFi 当前关闭，临时打开"
        lipc-set-prop com.lab126.cmd wirelessEnable 1 > /dev/null 2>&1
        sleep 8
    fi
}

wifi_restore() {
    if [ "$WIFI_WAS" != "" ] && [ "$WIFI_WAS" != "1" ]; then
        lipc-set-prop com.lab126.cmd wirelessEnable 0 > /dev/null 2>&1
        say "已恢复 WiFi 关闭状态"
    fi
}

# ---------- 下载 ----------
fetch() {
    if command -v curl > /dev/null 2>&1; then
        curl -fs -m 30 -o "$TMP" "$URL" 2> /dev/null
    else
        wget -q -T 30 -O "$TMP" "$URL" 2> /dev/null
    fi
}

# ---------- 校验 PNG 魔数与 IHDR 尺寸 ----------
validate() {
    [ -s "$1" ] || return 1
    # 注意 $17 会被当成 $1 加字符 7，所以先 shift
    set -- $(dd if="$1" bs=1 count=24 2> /dev/null | od -An -tu1 | tr -s ' \n' ' ')
    [ $# -ge 24 ] || return 1
    [ "$1 $2 $3 $4 $5 $6 $7 $8" = "137 80 78 71 13 10 26 10" ] || return 1
    shift 16
    w=$(( ($1 << 24) | ($2 << 16) | ($3 << 8) | $4 ))
    h=$(( ($5 << 24) | ($6 << 16) | ($7 << 8) | $8 ))
    [ "$w" = "$WANT_W" ] && [ "$h" = "$WANT_H" ] || {
        say "尺寸不符: ${w}x${h}（期望 ${WANT_W}x${WANT_H}）"
        return 1
    }
    return 0
}

# ---------- 备份（只做一次） ----------
backup_once() {
    [ -d "$BACKUP" ] && [ -f "$BACKUP/bg_ss00.png" ] && return 0
    say "备份原屏保 -> $BACKUP"
    mkdir -p "$BACKUP" 2> /dev/null
    cp "$SS_DIR"/bg_ss*.png "$BACKUP"/ 2> /dev/null
}

# ---------- 替换 ----------
install_images() {
    free_k=$(df -k / 2> /dev/null | awk 'NR==2 {print $4}')
    case "$free_k" in
        '' | *[!0-9]*) free_k=999999 ;;
    esac
    if [ "$free_k" -lt 1024 ]; then
        say "rootfs 剩余空间不足（${free_k}KB），中止"
        return 1
    fi

    say "挂载 rootfs 为可写"
    mntroot rw || { say "mntroot rw 失败"; return 1; }

    n=0
    for f in "$SS_DIR"/bg_ss*.png; do
        [ -f "$f" ] || continue
        if cp "$TMP" "$f" 2> /dev/null; then
            n=$((n + 1))
        else
            say "写入失败: $f"
        fi
    done
    sync

    say "已替换 $n 张屏保图"
    mntroot ro
    [ "$n" -gt 0 ]
}

restart_framework() {
    case "$RESTART" in
        never)
            say "按配置不重启框架（实测换图无需重启）"
            return 0 ;;
        auto)
            if [ "$(cat "$STAMP" 2> /dev/null)" = "$(date '+%F %T')" ]; then
                return 0
            fi ;;
    esac
    say "2 秒后重启框架"
    ( sleep 2; restart framework > /dev/null 2>&1 \
        || /etc/init.d/framework restart > /dev/null 2>&1 ) &
}

# ---------- 主流程 ----------
say "=== 更新屏保 ==="
say "URL: $URL"

wifi_prepare

if ! fetch; then
    say "下载失败：检查 WiFi、URL、Mac 上服务是否在跑"
    wifi_restore
    rm -f "$TMP"
    exit 1
fi
wifi_restore

say "下载完成 $(wc -c < "$TMP" 2> /dev/null) 字节"

if ! validate "$TMP"; then
    say "校验失败，丢弃（原屏保未改动）"
    rm -f "$TMP"
    exit 1
fi

# 内容没变就早退
if [ -f "$BACKUP/.current.png" ] && cmp -s "$TMP" "$BACKUP/.current.png"; then
    say "图片与上次相同，无需替换"
    rm -f "$TMP"
    exit 0
fi

backup_once
install_images || { rm -f "$TMP"; exit 1; }
cp "$TMP" "$BACKUP/.current.png" 2> /dev/null
rm -f "$TMP"
date '+%F %T' > "$STAMP" 2> /dev/null

say "完成。休眠后即可看到最新面板。"
