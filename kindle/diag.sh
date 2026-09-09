#!/bin/sh
# diag.sh —— 一次性诊断：摸清原生系统里屏保相关的路径与工具
#
# 装完热修复后，把这个文件放到 /mnt/us/documents/，在书库里点一下。
# 结果会写到 /mnt/us/diagnostics.txt（同时用 fbink 显示在屏幕上）。

OUT=/mnt/us/diagnostics.txt
{
    echo "=== 时间 ==="
    date
    echo
    echo "=== 内核 ==="
    uname -a
    echo
    echo "=== 固件版本 ==="
    cat /etc/version.txt 2> /dev/null
    cat /etc/prettyversion.txt 2> /dev/null
    grep -i "software_version" /etc/*.txt 2> /dev/null | head -5
    echo
    echo "=== /usr/share/blanket ==="
    ls -la /usr/share/blanket/ 2>&1
    echo
    echo "=== /usr/share/blanket/screensaver ==="
    ls -la /usr/share/blanket/screensaver/ 2>&1
    echo
    echo "=== 屏保图尺寸（前 4 张）==="
    for f in /usr/share/blanket/screensaver/*.png; do
        [ -f "$f" ] || continue
        size=$(dd if="$f" bs=1 count=24 2> /dev/null | od -An -tu1 | tr -s ' \n' ' ')
        set -- $size
        if [ $# -ge 24 ]; then
            shift 16
            w=$(( ($1 << 24) | ($2 << 16) | ($3 << 8) | $4 ))
            h=$(( ($5 << 24) | ($6 << 16) | ($7 << 8) | $8 ))
            echo "$f  ${w}x${h}"
        else
            echo "$f  (无法解析)"
        fi
        break
    done
    echo
    echo "=== 其他可能的屏保目录 ==="
    find /usr/share -iname "*screen*" -maxdepth 4 2> /dev/null | head -20
    find /etc -iname "*screen*" -maxdepth 3 2> /dev/null | head -10
    echo
    echo "=== 挂载表 ==="
    mount | head -25
    echo
    echo "=== 可用工具 ==="
    for t in curl wget fbink eips lipc-set-prop md5sum od dd cmp chattr mntroot kindletool; do
        p=$(command -v "$t" 2> /dev/null)
        echo "$t: ${p:-missing}"
    done
    echo
    echo "=== eips 位置 ==="
    ls -la /usr/sbin/eips /usr/bin/eips /usr/local/bin/eips 2>&1
    echo
    echo "=== upstart 任务 ==="
    ls /etc/upstart/ 2> /dev/null | head -50
    echo
    echo "=== 越狱痕迹 ==="
    ls -la /etc/uks/ 2>&1
    ls -la /mnt/us/extensions/ 2>&1 | head
    echo
    echo "=== KPM ==="
    ls -la /var/local/kpm 2>&1 | head
    command -v kpm 2> /dev/null || echo "kpm: missing"
    echo
    echo "=== sh_integration ==="
    ls -la /mnt/us/documents/ 2>&1
} > "$OUT" 2>&1

sync
echo "诊断完成 -> /mnt/us/diagnostics.txt"
