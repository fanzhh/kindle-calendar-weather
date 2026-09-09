# 越狱与热修复

本页只写**本项目需要的前置**，并给出官方链接。本仓库**不打包任何第三方二进制**。

> ⚠️ 越狱有风险。请先确认**准确的机型和固件版本**，并做好备份。

---

## 0. 先确认机型和固件

- **机型**：看设备背面的 `MODEL NO.`。例如 `WP63GW` = Kindle 7（2014，第 7 代，代号 KT2）。
  对照表：<https://www.epubor.com/identify-kindle-model.html>
- **固件**：设置 → 设备选项 → 设备信息。或连 USB 后读 `<Kindle盘>/system/version.txt`。

## 1. 选对越狱方式

以 KT2 为例（其他机型见官方 wizard）：

| 固件 | 越狱 |
|---|---|
| 5.10.3 – 5.13.3（不含 5.12.2.2） | [KindleBreak](https://kindlemodding.org/jailbreaking/Legacy/KindleBreak/) |
| 5.12.2.2、5.13.4 – 5.14.2 | [WatchThis](https://kindlemodding.org/jailbreaking/Legacy/WatchThis/) |
| ≥ 5.14.3 | LanguageBreak / WinterBreak 等（见官网） |

官方选择器：<https://kindlemodding.org/jailbreak-wizard.html>

### KindleBreak 步骤（5.11.1.1 实测）

1. **开飞行模式**（防止联网自动更新）
2. 下载 `jb-kindlebreak.zip` 解压，把 `jb`、`jb.sh`、`kindlebreak.html`、`kindlebreak.jxr`
   四个文件拷到 Kindle 根目录
3. 下载 `file__0.localstorage`，放到
   `/.active_content_sandbox/browser/resource/LocalStorage/`（目录不存在就建）
4. 弹出磁盘、拔线，打开**体验版浏览器**
   - 该载荷的 `lastUrl` 指向 `file:///mnt/us/kindlebreak.html`，浏览器一启动就会加载
   - 没反应就手动在地址栏输入 `file:///mnt/us/kindlebreak.html`（注意是三个斜杠）
5. 浏览器会卡死/崩溃 → 等 1–5 分钟 → 设备自动重启 → 出现
   `Application Error` / `Collecting Debug Info` 弹窗 = **越狱完成**

下载地址（官方）：
- `jb-kindlebreak.zip`：<https://kindlemodding.org/jailbreaking/Legacy/KindleBreak/>
- `file__0.localstorage`：同页

**验证**：`/mnt/us/kindlebreak_log.txt` 里有 `Created developer key` 等记录。

## 2. 装热修复（关键）

热修复带来三样东西，本项目全都依赖：

| 组件 | 作用 |
|---|---|
| `sh_integration` | `documents/` 里的 `.sh` 出现在书库，点击以 **root** 执行，stdout 走 fbink 显示 |
| `;log` 命令 | 搜索框输入 `;log` 弹提示 = 环境正常 |
| FBInk | `/mnt/us/libkh/bin/fbink` |

步骤：

1. 从 [KindleModding/Hotfix releases](https://github.com/KindleModding/Hotfix/releases) 下载
   `Update_hotfix_universal.bin`
2. 拷到 Kindle **根目录**（先确认根目录没有其他 `.bin` 或 `update.bin.tmp.partial`）
3. 弹出、拔线 → 设置 → 右上角三个点 → **更新您的 Kindle** → 确认
4. 重启后在**书库**里点一次 **Run Hotfix**
5. 搜索框输入 `;log`，弹出提示框即成功

## 3. 屏蔽官方 OTA（强烈建议）

刷了双系统或想长期保留越狱，**务必屏蔽官方更新**——官方固件更新会覆盖越狱环境，
双系统机型还可能破坏分区。

本仓库的 `kindle/ota-block.sh` 做的事和社区里的 renametobin 一样：
把 `/etc/uks/pubprodkey01.pem`、`pubprodkey02.pem` 改名，设备就无法校验官方更新包；
我们自己的脚本走开发者密钥，不受影响。

## 4. 探测你的设备（可选但推荐）

把 `kindle/diag.sh` 拷到 `documents/` 点一下，它会输出一份报告到
`/mnt/us/diagnostics.txt`，包含：

- 固件版本、内核
- 屏保目录与图片分辨率
- 挂载表（rootfs 是否只读）
- 可用工具（curl / eips / lipc-set-prop / mntroot …）
- RTC 与 upstart 任务

移植到别的机型时，先跑这个再改参数。

---

## 相关链接

- KindleModding Wiki：<https://kindlemodding.org/>
- Universal Hotfix：<https://github.com/KindleModding/Hotfix>
- MobileRead 论坛（Kindle 开发者区）：<https://www.mobileread.com/forums/forumdisplay.php?f=150>
