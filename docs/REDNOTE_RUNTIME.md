# RedNote / Waydroid 运行环境与测试记录

本文记录当前工作区的运行时探测结果，以及在具备相应宿主机能力时的可复现测试流程。它不记录账号、手机号、验证码或未经脱敏的诊断日志，也不包含规避平台安全检查的方法。

## 当前待测 APK 来源与架构

当前待测输入是 APKPure 的 RedNote `9.48.1`（`versionCode=9481803`）XAPK，包含 base、`arm64-v8a` 和 `xxhdpi` split。它不是从 Google Play 导出的 APK，也不能据此声称与 Google Play 当前分发包二进制等价、安装来源等价或行为等价。若取得实际 Play 控制组，应单独记录其来源、安装方式、哈希和签名。

该 XAPK 的 native ABI 是 `arm64-v8a`，而当前工作区宿主为 x86_64。Waydroid 的 Android 镜像 ABI 必须能加载 APK 中的 native 库：x86_64 镜像不能原生加载 arm64 `.so`。没有与 Android 镜像兼容且正常工作的 ARM native bridge 时，安装可能因 ABI 不匹配失败，或安装后在启动/调用 native 代码时失败。即使界面启动成功，也不能据此认定所有 native 功能正常。

因此优先在真实 ARM64 Android 设备上验证原始 split 集合；若使用 x86_64 Waydroid，先确认镜像的 ABI 列表和 native bridge 状态，并把它作为单独的兼容性测试环境。不要把镜像启动成功或 APK 安装成功当作 APK 可运行的充分证据。

## 当前工作区探测结果

探测日期：2026-10-07。初始只读检查之后，已实际执行 privileged Docker 探测，并启动直接运行 Android 的软件模拟虚拟机。后续运行结果见 [ANDROID_VM_TEST.md](ANDROID_VM_TEST.md)。没有安装 Waydroid。

| 项目 | 探测结果 |
| --- | --- |
| 系统 | Debian GNU/Linux 13；Linux `6.18.44`，x86_64 |
| 执行环境 | 容器（`systemd-detect-virt` 返回 `container-other`）；PID 1 是 `tail -f /dev/null`，systemd 状态为 `offline` |
| 当前用户/权限 | `uid=1000(agent)`；有效和允许 capability 集合为空（`CapEff=0`、`CapPrm=0`） |
| CPU 虚拟化标志 | `/proc/cpuinfo` 未暴露 `vmx` 或 `svm` |
| KVM 设备/内核 | `/dev/kvm`、`/sys/module/kvm` 不存在；可读内核配置只显示 `CONFIG_KVM_GUEST=y`，没有 KVM host 支持项 |
| Binder 设备/内核 | `/dev/binder`、`/dev/hwbinder`、`/dev/vndbinder`、`/dev/binderfs`、`/sys/fs/binderfs` 不存在；配置明确显示 `CONFIG_ANDROID_BINDER_IPC` 未启用 |
| Waydroid 工具 | 未安装（`waydroid` 命令不可用） |
| Docker | CLI 可连接 Docker 28.4 daemon；实际运行 `busybox:1.37` privileged 容器后，仍没有 `/dev/kvm`、KVM 模块或 CPU `vmx`/`svm` 标志 |

**结论：当前工作区不能运行 Waydroid，也不能建立 KVM 加速的虚拟机。** 仅安装用户态包无法补上缺失的宿主机内核驱动、设备节点和权限。Waydroid 本身以 Linux 容器方式运行 Android；KVM 不是 Waydroid 的必要条件，只有在 Waydroid 所在 Linux 主机还要作为嵌套虚拟机运行时才需要 KVM。当前环境缺少 Waydroid 所需的 Binder 支持，因此即使不使用 KVM 也不可行。

这不排除直接运行 Android 虚拟机：其 Binder 由 Android 来宾内核提供，不依赖宿主 Binder。实际已使用官方 Android Emulator 的 `-accel off` / QEMU TCG 启动 API 30 和 API 35 Google APIs 镜像；这属于软件模拟，不能称为 KVM 加速。APK 安装、应用启动与登录结果须按后续运行记录分别核对。

## 有权限的 Linux 主机前置条件

准备专用测试主机或虚拟机，并按所用发行版与 Waydroid 当前文档核对要求：

- Linux 内核启用了 Android Binder IPC，且能提供 Waydroid 所需的 Binder 设备；优先使用启用 binderfs 的内核。新内核通常通过 memfd 提供共享内存，是否需要 ashmem 取决于所选内核和 Android 镜像。
- 主机提供 Waydroid/LXC 所需的 cgroup、命名空间、网络和服务管理能力。不能只在普通无特权容器里安装 Waydroid 包来代替这些宿主机能力。
- 图形界面需要可用的 Wayland 或 X11 会话。开始测试前确认主机有足够的内存、磁盘空间和网络连接。
- 若还需要在该主机内运行 KVM 虚拟机，虚拟化平台必须启用嵌套虚拟化；CPU 要向来宾暴露 `vmx`（Intel）或 `svm`（AMD），且来宾中 `/dev/kvm` 可访问。裸机 Waydroid 不因缺少 KVM 而不能启动。
- 若要验证 Google Play 分发版，需明确测试的是通过 Play 安装的应用，还是从 Play 来源取得后侧载的 APK。侧载会改变安装来源；使用 Google 服务还要求镜像提供相应服务。两者的结果不可混为一谈。
- 本次 APKPure XAPK 只有 arm64-v8a native split。优先使用真实 ARM64 Android 设备；x86_64 Waydroid 只有在 Android 镜像 ABI 与该 APK 匹配，或已有兼容的 ARM native bridge 时才适合继续测。确认 `ro.product.cpu.abilist`、`ro.dalvik.vm.native.bridge` 和实际 native 库加载结果；缺少 bridge 时记录为 ABI 不兼容，不通过修改设备属性来掩盖。

在主机上先做只读检查：

```sh
uname -a
grep -m1 -Eo 'vmx|svm' /proc/cpuinfo | sort -u
test -c /dev/kvm && stat /dev/kvm
ls -ld /dev/binderfs /dev/binder /dev/hwbinder /dev/vndbinder 2>&1
zcat /proc/config.gz 2>/dev/null | grep -E 'CONFIG_(KVM|ANDROID_BINDER|ASHMEM)'
id
grep -E '^Cap(Eff|Prm):' /proc/self/status
systemctl is-system-running
cat /sys/fs/cgroup/cgroup.controllers
```

`/proc/config.gz` 不存在时，检查发行版提供的 `/boot/config-$(uname -r)`。配置文件只能说明内核构建选项；还应确认实际设备节点存在且当前用户/服务能访问。

## 安装与测试流程

在专用测试主机上按发行版的 Waydroid 安装文档安装软件包，再初始化一个单独的测试实例。下面是常见 systemd 主机的命令示例，具体选项以所安装版本的文档为准：

```sh
sudo waydroid init -s GAPPS
sudo systemctl enable --now waydroid-container
waydroid session start
waydroid show-full-ui
```

若不需要 Play 服务，可使用该版本支持的标准镜像类型。只在新建的测试实例中初始化，避免覆盖已有实例数据。确认容器启动、系统界面可见后，记录 Android 镜像类型、版本、宿主机内核、Waydroid 版本、网络类型和显示后端。

对每个 APK 变体单独记录文件 SHA-256、版本号、包名、签名证书指纹和安装方式。使用隔离的应用数据或独立实例，避免上一个变体残留的数据影响下一个变体。下面的命令适用于单 APK；XAPK 原始 split 集合按下一节使用 `adb install-multiple` 安装：

```sh
waydroid app install ./variant.apk
waydroid app list
```

### XAPK split 安装与 builder 合并产物

原始 XAPK 与 builder 生成的单 APK 是不同测试对象，不能混称为同一个 APK。保留原始 XAPK 和各 APK split 的 SHA-256；先核对 split 列表、包名、版本号、签名及 ABI，再分别安装。若通过 ADB 侧载原始 split 集合，解压后使用该 XAPK 中实际文件名：

```sh
adb connect <WAYDROID_IP>:5555
adb -s <WAYDROID_IP>:5555 install-multiple base.apk <arm64-split.apk> <xxhdpi-split.apk>
```

在 ARM64 设备上也可用该设备的 ADB 连接地址运行同一 `install-multiple` 命令。必须安装同一 XAPK 的完整、签名一致的 split 集合；只安装 base 不能代表原包完整安装。

builder 合并 split 并重签名的产物另行安装、另行记录哈希和签名。合并过程会改变 APK 的打包结构，资源合并可能影响资源表、密度资源或 split 配置；不要把合并产物称为原始 split APK，也不要称为 Play 等价包。记录 builder 版本/提交、输入 split 清单与哈希、合并输出哈希、最终包名/版本/签名，以及资源和 `lib/<abi>/` 文件清单。若启动失败，区分安装阶段的 split/ABI 错误、启动阶段的 Java 崩溃和 native 库加载失败。

在 Android 来宾中可只读核对架构和 native bridge：

```sh
adb -s <WAYDROID_IP>:5555 shell getprop ro.product.cpu.abilist
adb -s <WAYDROID_IP>:5555 shell getprop ro.dalvik.vm.native.bridge
```

启动后先检查启动、页面布局和崩溃情况。若账号所有者决定继续验证登录，只记录是否出现提示及提示原文；出现安全或环境提示后停止该轮，不重复提交，不记录手机号或验证码。不要尝试伪装设备、签名或安装来源来绕过提示。

### 截图与日志

- 优先在不输入账号信息的状态下截图。若提示页截图中出现个人信息，先在本地裁剪或遮盖，再用于报告；原始截图不提交到仓库、CI 或公开链接。
- 可用桌面截图工具截取 Waydroid 窗口。若该 Waydroid 版本开放 ADB，按 `waydroid status` 显示的地址连接；例如：

  ```sh
  adb connect <WAYDROID_IP>:5555
  adb -s <WAYDROID_IP>:5555 exec-out screencap -p > screenshot.png
  ```

  保存前检查截图内容并去除个人信息。
- 需要观察崩溃时，可短时运行 `adb -s <WAYDROID_IP>:5555 logcat -v time`，复现一次后按 `Ctrl-C` 停止并在本地检查。也可使用 `waydroid log` 查看容器日志。不要把原始 logcat、包含账号信息的日志或认证 token/cookie 保存到仓库或 CI artifact；报告只保留脱敏后的时间、进程、错误类别和必要堆栈片段。
- 记录测试时间、Android/Waydroid 版本、APK 哈希、安装方式、结果类别（正常打开、崩溃、提示登录或提示环境异常）及是否已脱敏。不要记录手机号、验证码、会话 token 或完整账号标识。

## 对照矩阵

在相同主机、Waydroid 镜像、网络和显示配置下逐项比较。每个变体使用干净的应用数据；若换包名导致系统把它视作独立应用，明确标记这一差异。矩阵用于定位变量与复现提示，不用于规避平台检查。

| 编号 | APK 变体 | 与基线相比的变量 | 主要观察项 |
| --- | --- | --- | --- |
| A | APKPure 原始 XAPK，base + arm64-v8a + xxhdpi splits，按完整 split 集合侧载 | 当前下载源/侧载方式；保留 XAPK 中的 split 与签名 | 安装是否接受完整 split、ABI 是否匹配、启动/native 库加载、页面和提示类别 |
| B | builder 合并后的单 APK，重签名，原包名 | 相对 A 改变打包结构/资源合并和签名；记录 builder 资源变化 | 安装/启动/资源与 native 错误；不要将结果归因于单一签名因素 |
| C | builder 合并重签后改为新包名 | 在 B 基础上改变包名及相关 manifest/引用 | 安装、启动、组件和链接兼容性；提示类别 |
| D | builder 合并重签的布局补丁版 | 在 B 的同包名、同测试签名和同构建方式上只增加布局补丁 | 布局、启动/崩溃、资源加载和提示类别；与 B 对照 |
| E | Google Play 安装的未修改版本（待取得，独立控制组） | Play 来源及官方签名/代码；必须记录通过 Play 安装还是侧载 | 提供真正的 Play 对照。当前 APKPure XAPK 不替代此行，也不能据此声称 Play 等价 |

建议结果表至少包含：`编号、XAPK 与各 split SHA-256、builder 版本/提交、合并 APK SHA-256、版本、包名、签名指纹、安装来源、宿主/来宾架构与 ABI 列表、native bridge 状态、镜像/系统版本、启动结果、布局结果、提示类别、脱敏截图编号、脱敏日志摘要`。对无法保持相同的条件逐项注明，避免将相关性写成结论。

## 参考

- Waydroid 官方安装文档：https://docs.waydro.id/usage/install-on-desktops
- Waydroid 官方命令行文档：https://docs.waydro.id/usage/waydroid-command-line-options
