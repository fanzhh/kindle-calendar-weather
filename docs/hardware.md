# 硬件与系统实测数据

本页记录 Kindle 7（KT2 / WP63GW）上实测到的路径、工具和接口。
移植到其他机型时，先用 `kindle/diag.sh` 采集一份自己的数据再对照修改。

---

## 设备

| 项目 | 值 |
|---|---|
| 型号 | WP63GW = Kindle 7（2014，第 7 代，代号 KT2 / BASIC） |
| 屏幕 | 6" E Ink，600×800（竖屏，宽×高），167 ppi，16 级灰阶 |
| 前置灯 | 无 |
| 内核 | `Linux 3.0.35-lab126 ... armv7l` |
| 固件 | `001-juno_110101_bourbon_wario-352853`（即 5.11.1.1） |
| 用户分区 | 约 1 GB，挂载在 `/mnt/us`（`fsp`，底层 `/mnt/base-us` vfat） |

## 屏保

| 项目 | 值 |
|---|---|
| 目录 | `/usr/share/blanket/screensaver/` |
| 文件 | `bg_ss00.png` … `bg_ss19.png`（共 20 张） |
| 规格 | 600×800 PNG |
| rootfs | `ext3 (ro)`，写入前需 `mntroot rw`，写完 `mntroot ro` |

框架在**休眠时读取图片文件**，替换后无需重启框架（见 [pitfalls.md](pitfalls.md#5-替换屏保图后不需要重启框架与直觉相反)）。

## 可用工具（固件自带）

| 工具 | 路径 | 用途 |
|---|---|---|
| `curl` | `/usr/bin/curl` | 拉图 |
| `wget` | busybox | 拉图（备用） |
| `eips` | `/usr/sbin/eips` | 直接往 framebuffer 画图/文字 |
| `lipc-get-prop` / `lipc-set-prop` | `/usr/bin/` | 读写系统属性 |
| `mntroot` | `/usr/sbin/mntroot` | rootfs 读写切换 |
| `md5sum` / `od` / `dd` / `cmp` | busybox | 校验与解析 PNG 头 |
| `chattr` | `/bin/chattr` | 解除/设置不可变位（越狱脚本用） |
| `fbink` | `/mnt/us/libkh/bin/fbink` | 热修复提供，用于把脚本输出画到屏幕 |

## 常用 LIPC 属性

```sh
# 电源状态：值可能是 active / screensaver / suspended
lipc-get-prop com.lab126.powerd state

# 详细状态（含 idle 倒计时、电量）
lipc-get-prop com.lab126.powerd status

# 阻止自动休眠（调试常驻脚本时有用）
lipc-set-prop com.lab126.powerd preventScreenSaver 1

# 无线开关
lipc-get-prop com.lab126.cmd wirelessEnable
lipc-set-prop com.lab126.cmd wirelessEnable 1
```

## 休眠与定时唤醒

```sh
# 找到可写的 RTC 唤醒闹钟（不同机型可能是 rtc0 / rtc1）
ls /sys/class/rtc/rtc*/wakealarm

# 设置"现在 + 3600 秒"唤醒（绝对时间戳更通用）
now=$(date +%s)
echo 0 > /sys/class/rtc/rtc0/wakealarm
echo $((now + 3600)) > /sys/class/rtc/rtc0/wakealarm

# 读回确认
cat /sys/class/rtc/rtc0/wakealarm

# 主动休眠
echo mem > /sys/power/state
```

> ⚠️ 主动休眠前务必确认闹钟已成功设置，否则设备会一直睡到按电源键。
> `dash-daemon.sh` 里有这个保护。

## 越狱留下的痕迹

| 路径 | 说明 |
|---|---|
| `/etc/uks/pubdevkey01.pem` | 越狱安装的开发者密钥（允许装自制 `.bin`） |
| `/etc/uks/pubprodkey01.pem.bak` | 被 `ota-block.sh` 改名的官方密钥（存在即已屏蔽 OTA） |
| `/mnt/us/kindlebreak_log.txt` | KindleBreak 的执行日志 |
| `/etc/upstart/dash-autoupdate.conf` | 本项目安装的自动更新任务 |

## 双系统（CrackDroid）

- CrackDroid 是**刷安卓**（Android 4.4.2）的 ROM，不是越狱；刷机后原生侧会被重置
- 切换：原生 → 安卓 = 设置 → 设备选项 → 重启；安卓 → 原生 = 「Eink 设置」→「启动 Kindle」
- 刷机后**必须**重新越狱原生侧，并屏蔽官方 OTA
