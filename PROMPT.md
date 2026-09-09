# 交给 AI 助手的提示词

不想逐条对照文档的话，把下面整段复制给你的 AI 助手（需要能读写本机文件、执行命令，
例如 Claude Code、Cursor、Codex 等）。

**前提**：Kindle 已越狱、已装热修复、已通过 USB 连接电脑。

---

```
你是我的技术助手。现在有一台已越狱并装好热修复的 Kindle，通过 USB 连在这台电脑上，
挂载为一个可移动磁盘。

请按开源方案 https://github.com/fanzhh/kindle-calendar-weather 把它改造成
「日历 + 天气」休眠屏保。尽量自己完成，只在必须我在设备屏幕上操作时才停下来告诉我。

一、先诊断，不要急着改
1. 定位挂载点：macOS 通常 /Volumes/Kindle，Linux 通常 /media/$USER/Kindle。
2. 读 <挂载点>/system/version.txt，记录固件版本。
3. 判断越狱/热修复状态：
   - <挂载点>/documents/ 中是否有可点击执行的 .sh
   - <挂载点>/libkh/bin/fbink 是否存在
   - <挂载点>/extensions/ 是否存在
4. 克隆仓库到本地，先读完 README.md、docs/hardware.md、docs/pitfalls.md 再动手。
5. 向我汇报：型号、固件版本、屏幕分辨率、越狱状态、还缺哪些前置条件。

二、按分辨率定参数
- 屏幕 600×800：用默认值。
- 其他分辨率（如 1072×1448）：同时改 render/dash.py 的 W, H 与
  kindle/ss-install.sh 的 WANT_W / WANT_H。
- 屏保目录若不是 /usr/share/blanket/screensaver/，一并修正。

三、服务端
1. 在常开的机器上执行 bash setup-mac.sh（macOS）或等价步骤（Linux）。
2. 问我天气城市的名称或经纬度，改 render/weather.py 里的 JINING。
3. 执行 bash selftest.sh，五项必须全部通过才能进入下一步。

四、设备端
1. 把 kindle/*.sh 与 config/dash.conf.example（改名为 dash.conf 并填入本机局域网 IP）
   拷贝到设备。
2. 拷完删除 macOS 生成的 ._* 文件。
3. 停下来告诉我：需要在 Kindle 书库里依次点击哪些脚本，每一步预期看到什么。

硬性约束
- 改设备前，屏保原图必须备份到 /mnt/us/screensaver-backup/。
- 只操作 /mnt/us 与 /usr/share/blanket/screensaver/，不要动 /etc/uks 之外的系统文件，
  不要碰安卓分区。
- 每次写入设备后执行 sync。
- 若现象与 docs/pitfalls.md 描述不符，停下来报告，不要猜测继续。
- 全程说明你在做什么、为什么。

验收
我休眠设备后，屏保应显示当月月历 + 农历/节气/节日 + 天气。
若仍显示旧图，按 docs/pitfalls.md 排查。
```

---

## 为什么提示词里要写那两条约束

**「先诊断再动手」**：老设备的固件版本、分辨率、屏保路径都可能和文档不同。
不先采集实际数据就套用默认参数，写进去的图尺寸不对，轻则屏保不显示，重则让框架出问题。

**「现象不符就停下来报告」**：改造过程中最危险的不是报错，而是**看起来成功但其实是错的**。
比如 `;log` 没反应曾被误判成越狱失败（它其实是热修复才装的命令）。
让助手停下来汇报，比让它猜着继续要安全得多。

如果你用的是能连 Kindle 的 AI 助手，也欢迎让它读一遍
[`docs/pitfalls.md`](docs/pitfalls.md) 再开工。
