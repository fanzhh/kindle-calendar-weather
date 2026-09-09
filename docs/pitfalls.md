# 踩坑记录

这份文档是项目的另一半价值：**哪些路走不通、为什么、怎么验证**。
按"现象 → 原因 → 验证 → 对策"组织，全部来自实机（Kindle 7 / KT2 / 固件 5.11.1.1）。

---

## 1. `;log` 搜索框没反应 ≠ 越狱失败

**现象**：按 KindleBreak 教程越狱、重启后，搜索框输入 `;log` 毫无反应，看起来像没越狱成功。

**原因**：`;log` **不是越狱自带命令，而是热修复（Hotfix）装的**。官方文档原话：

> We use `;log` as the MRPI installation command because previous versions of Kindle firmware
> contained it as a stock command that we overwrote. Nowadays, the command is added to the
> list of commands and installed entirely from the hotfix.

**验证**：越狱脚本会把结果写到 `/mnt/us/kindlebreak_log.txt`，内容类似：

```
Loaded logging functions
Removed existing developer key
Created developer key (0)
Updated permissions for developer key
Enabled developer flag
Finished installing jailbreak, restarting...
```

有这份日志 + `/etc/uks/pubdevkey01.pem` 存在 = **越狱确实成功了**，只是还没装热修复。

**对策**：先装热修复，再验 `;log`。

---

## 2. 固件版本决定越狱方式，5.12.2.2 是个坑

**现象**：查教程说 KindleBreak 支持 5.10.3–5.13.3，但自己的 5.12.2.2 却不行。

**原因**：`5.12.2.2` 虽然版本号看着在区间内，**实际比 5.13.3 还新**，修补了 KindleBreak 的漏洞。

**对策**（KT2 / PW2 同架构机型）：

| 固件 | 越狱 |
|---|---|
| 5.10.3 – 5.13.3（**不含** 5.12.2.2） | KindleBreak |
| 5.12.2.2、5.13.4 – 5.14.2 | WatchThis |

官方支持表：<https://kindlemodding.gitbook.io/kindlemodding/jailbreak-software/kindlebreak-5.10.3-5.13.3.md>

---

## 3. PEKI 要求固件 ≥ 5.12.2.2

**现象**：按官方 KUAL 安装指引下载 PEKI，在老固件上装不上或点了没反应。

**原因**：PEKI 仓库 README 明确写着 **"5.12.2.2+ Only, on Universal Hotfix 2.3.7 MAX."**

**对策**：老固件别折腾 KUAL——见第 4 条。

---

## 4. linkss（ScreenSavers Hack）的公开下载基本失效

**现象**：搜到的教程都指向 linkss，但下载链接要么是论坛附件（需登录）、要么是网盘（需客户端）、
要么已经 404。

**对策**：**自己换屏保**。linkss 底层做的就是替换 `/usr/share/blanket/screensaver/bg_ss*.png`，
我们用热修复自带的 `sh_integration` 拿 root 执行权限，直接做同样的事，反而更可控。

---

## 5. 替换屏保图后**不需要**重启框架（与直觉相反）

**现象**：linkss 的文档说"改图后必须重启 Kindle 才生效"，于是以为自己也必须重启框架。

**实测**：不需要。验证方法（可复现）：

1. 让服务返回一张**带明显横幅**的图：`GET /dash.png?banner=测试`
2. 设备上执行替换脚本，**配置 `DASH_RESTART=never`**（明确不重启框架）
3. 直接按电源键休眠
4. 如果屏保上出现横幅 → **框架是在休眠时现读图片文件的，没有缓存**

**对策**：把 `DASH_RESTART` 设成 `never`，更新过程完全无感，不打断阅读。

---

## 6. busybox 的 `sleep` 在休眠期间不走

**现象**：守护脚本写 `sleep 1800` 做定时刷新，结果设备唤醒后最长要等半小时才刷新。

**原因**：busybox 的 `sleep` 走 `CLOCK_MONOTONIC`，**系统挂起期间这个时钟不前进**，
所以"睡 30 分钟"在唤醒后可能还剩 30 分钟。

**对策**：改用**挂钟时间**（`date +%s`，RTC 在休眠中继续走）判断是否到点，
外层用短轮询：

```sh
while true; do
    now=$(date +%s); last=$(cat /mnt/us/.dash_last_check 2>/dev/null || echo 0)
    [ $((now - last)) -ge "$INTERVAL" ] && { ss-install.sh; date +%s > /mnt/us/.dash_last_check; }
    sleep 60
done
```

---

## 7. shell 里 `$17` 不是第 17 个参数

**现象**：用 `set -- $(od -An -tu1 ...)` 解析 PNG 头时，宽高算出来是天文数字。

**原因**：POSIX shell 里 `$17` 会被解析成 **`$1` 后跟字符 `7`**，多位数位置参数必须写 `${17}`。

**对策**：先 `shift 16`，再用 `$1`/`$2`/`$3`/`$4` 取宽高：

```sh
shift 16
w=$(( ($1 << 24) | ($2 << 16) | ($3 << 8) | $4 ))
h=$(( ($5 << 24) | ($6 << 16) | ($7 << 8) | $8 ))
```

---

## 8. macOS 往 FAT32 拷文件会留下 `._*` 资源叉

**现象**：从 macOS 拷脚本到 Kindle 后，根目录多出 `._ss-install.sh` 之类的文件。

**原因**：macOS 在非 HFS/APFS 文件系统上会写 AppleDouble 元数据。

**对策**：拷完删掉 `._*`；官方越狱/热修复指南也要求根目录干净（尤其别留 `.bin` 和
`update.bin.tmp.partial`）。

---

## 9. 必须校验 PNG 再覆盖屏保

**现象**：网络抖动时下载到半截文件或错误页面，直接覆盖会让屏保变成一片乱码。

**对策**：`ss-install.sh` 校验两件事——**PNG 魔数**（前 8 字节
`137 80 78 71 13 10 26 10`）和 **IHDR 里的宽高必须等于屏幕分辨率**，
不通过就丢弃，原图不动。

---

## 10. rootfs 只读

**现象**：直接 `cp` 到 `/usr/share/blanket/screensaver/` 报 `Read-only file system`。

**原因**：`/dev/root on / type ext3 (ro,...)`，rootfs 默认只读挂载。

**对策**：`mntroot rw` → 写入 → `mntroot ro`，并先 `df -k /` 检查剩余空间。

---

## 11. 常驻日志会把 `/mnt/us` 写满

**现象**：守护进程每 30 分钟写一次日志，长期运行后日志文件越来越大。

**对策**：脚本里加简单的体积裁剪（超过 200KB 就只留最后 300 行）。

---

## 12. CrackDroid 不是越狱，是刷安卓

**现象**：看到"已越狱"以为还是原生系统，其实设备已经刷成了 **安卓 + 原生双系统**。

**要点**：

- CrackDroid 是通过 fastboot 刷入的安卓 4.4.2 ROM，支持 Kindle 7/499（KT2）等机型
- 刷完后**原生系统会被重置**，越狱、KUAL 全没了，需要重新越狱原生侧
- 双系统切换：原生 → 安卓是「设置 → 设备选项 → 重启」；安卓 → 原生是
  「Eink 设置 → 启动 Kindle」
- **刷机后必须屏蔽官方 OTA**，否则官方更新会破坏分区（见 `kindle/ota-block.sh`）

---

## 13. 一个容易忽略的前提：热修复才带来 `sh_integration`

`sh_integration` 让 `documents/` 里的 `.sh` 出现在书库、点一下以 root 执行，
并且用 fbink 把 stdout 打到屏幕上——这是**本项目所有 Kindle 端脚本的执行入口**。

它来自 [Universal Hotfix](https://github.com/KindleModding/Hotfix)，装法：
`.bin` 放根目录 → 设置 → 更新您的 Kindle → 重启后在书库点一次 **Run Hotfix**。
