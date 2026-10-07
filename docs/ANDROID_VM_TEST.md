# Android VM 安装与运行记录

更新日期：2026-10-07

## 当前测试状态

当前测试使用 APKPure 分发的 REDnote `9.48.1` XAPK（SHA-256 `bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0`），不是从 Google Play 直接导出的 APK。XAPK 原始包、两个 split 和构建报告的来源信息见仓库 `output_apks/*build-report.json`。

API 35 Google APIs x86_64 KVM runner 已安装并启动当前的三个变体。原始包、换包名对照版和布局版都显示隐私协议首屏，PID 分别为 4357、4732、5090，20 秒观察未检测到崩溃。主进程初始化修复 `ae7aef4` 已重建到当前本地 APK。较早 API 30 深度预览的修复后对照版虽越过 NPE 并显示隐私协议，随后仍发生带 `libndk_translation.so` 栈帧的 `SIGABRT`。手机号、短信验证码和实际登录均未测试，当前结果不能判断服务端是否会触发“环境不安全”。

| 变体 | 安装与运行结果 | 证据 |
| --- | --- | --- |
| 原始 APKPure XAPK（base + ARM64 + xxhdpi split，`com.xingin.xhs`） | API 35 KVM smoke：split 安装成功并启动至隐私协议，短观察未见崩溃。更深预览同意隐私并点登录后 native `SIGABRT`，栈中包含 `libndk_translation.so`。 | [run 37598983597](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37598983597) |
| 原始 APKPure XAPK（`com.xingin.xhs`） | API 30 预览到隐私协议后 native `SIGSEGV`；本地预览记录没有可用 native backtrace。它不是登录风控提示。 | 本地预览记录 |
| 换包名对照版旧 APK（`com.kirikira.rednote.fold`） | 修复前 API 35 启动请求被接受后发生 `XhsActivity.getResources()` 的 Java NPE。此旧故障已由 `ae7aef4` 修复。 | [run 37599034582](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37599034582) |
| 当前三个变体 | API 35 run 37601174448 中均安装成功并显示隐私协议首屏；PID 4357 / 4732 / 5090，20 秒观察无崩溃。 | [run 37601174448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601174448) |
| 换包名对照版旧 APK | API 30 深度预览记录 `XhsActivity.getResources()` 相关 NPE；这是修复前结果。 | 本地预览记录 |
| 主进程修复后的换包名对照版 | 较早 API 30 run 37601175067 可同意隐私协议，未再出现 NPE；随后 native `SIGABRT`，状态码 6，native 栈包含 `libndk_translation.so`。 | [run 37601175067](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601175067) |

未修改 APK 在 API 35 的短时 smoke 中未崩溃，与更深预览中的 native crash 是不同观察阶段，不应合并成“稳定运行”。API 35 镜像声明 ABI `x86_64,arm64-v8a` 并带 `libndk_translation.so`；native 栈包含该库只能说明翻译路径出现于崩溃调用栈，不能单独证明它是根因。

## 克隆版启动兼容性

APKManifest 的重复 `{applicationId}.gcm.permission.C2D_MESSAGE` 已修复。当前三个 APK 均安装成功，所以较早记录的 `INSTALL_FAILED_DUPLICATE_PERMISSION` 已过时。

应用 `ddc/a` 中的主进程名硬编码检查曾导致改包名后跳过 `Application` 初始化，随后 `XhsActivity.getResources()` 抛 NPE。该兼容修复已提交并进入当前 APK，run 37601174448 确认两个克隆变体启动至隐私协议且 20 秒无崩溃。较早 API 30 run 37601175067 随后出现的 native abort 是独立待查故障，仍发生在登录前。ActivityManager 返回启动成功只表示启动请求被接受，不代表应用进程健康。

当前 [`output_apks/SHA256SUMS`](../output_apks/SHA256SUMS) 是已重建并包含 `ae7aef4` 的产物哈希：

| 文件 | 包名 | SHA-256 |
| --- | --- | --- |
| `rednote-9.48.1-renamed-control.apk` | `com.kirikira.rednote.fold` | `46c7c0203dfff70c4b12dcc0ead68a1155efe26dc98e2442e046d7b0c7ae9db8` |
| `rednote-9.48.1-fold-custom.apk` | `com.kirikira.rednote.fold` | `1e7b5f7abb45b7af92d8bee56d661e6ef09fc89fd3cc0cf0d841600b3b07669c` |

构建报告验证对照版仅改 `AndroidManifest.xml` 与 `classes17.dex`；布局版改这两项和 `classes4.dex`。独立 payload 审计确认原始 1,985 条目中其他条目哈希一致；编译 gate 检查通过，8 项单元测试通过。

## KVM 与 ARM Waydroid

API 35 x86_64 测试使用 Android Emulator 37.2.12、Google APIs system image 和可用 KVM。镜像提供 `libndk_translation.so` 并声明 ARM64 ABI，但这是 **x86_64 guest 中的 ARM native bridge**，不等同于原生 ARM Android 环境。

- 旧 run [37580918798](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37580918798) 验证 hosted runner 的 `/dev/kvm` 可用，并成功启动 API 35 emulator。它没有完成 APK 下载或安装。
- 旧 smoke run [37581654651](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37581654651) 的克隆安装曾因重复 custom permission 失败；该问题已在当前构建修复。该 run 的旧 APK 与哈希不代表现在的产物。
- [模块探测 run 37585019547](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37585019547) 已确认官方 extras 提供的 ARM/x86 Binder 模块可用。这验证了模块侧条件，不证明目标应用已在 Waydroid 中安装或启动。
- 原生 ARM Waydroid KVM run [37601728448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601728448) 因 LXC 缺少 `XDG_RUNTIME_DIR/pulse/native` 挂载而失败，没有完成应用测试。
- 补齐 PulseAudio 后的第三轮 [37602265414](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37602265414) 已实际到达 Android user 0 ready；LXC 状态 `RUNNING`，地址 `192.168.240.112`。这次未测试 APK，是因为脚本过早将未知地址 `UNKNOWN` 拼成 `UNKNOWN:5555` 并超时，不是 Waydroid 容器未启动。
- IP 发现修复 commit `b56cbad` 的第四轮 [37603857949](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37603857949) 已取消。日志显示 Android ready 且地址为 `192.168.240.112`；首次 `adb connect` 明确报告 `failed to authenticate`，后续返回 already connected，但 `adb get-state` 未变为 `device`。该次运行未执行 `show-full-ui`，随后 LXC 进入 `FROZEN`。这是自建 Android 的 ADB 主机认证和窗口生命周期问题，未安装或启动 APK。
- [37605217096](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37605217096) 成功完成 native ARM QEMU fold APK 构建，但旧连接脚本的 Android 初始化步骤已取消，APK 安装和应用测试均跳过。接下来先通过 `show-full-ui` 与 ADB 主机密钥信任流程确认 `adb get-state=device`，再运行 APK smoke；当前没有 native ARM 应用运行证据。

此前在本机用 TCG 软件模拟的 API 30/35 尝试有系统服务缺失或首次启动过慢的问题，不能代表上述 hosted KVM 结果，也不能作为当前应用测试结论。此前的 `INSTALL_FAILED_DUPLICATE_PERMISSION` 和克隆启动 NPE 均已修复；旧 NPE 记录不代表当前 APK。

## 登录与风控测试边界

所有当前预览记录都显示 `phone_input_performed=false`、`sms_requested=false`，且未显示手机号表单。未输入手机号、未请求验证码、未提交 OTP、未完成登录。20 秒 smoke 只到隐私协议首屏；较早 deep preview 的 native crash 也发生在手机号页前。`timeout` 表示预览流程没有达到目标状态，不表示服务器拒绝登录。

因此当前不能判断 REDnote 是否对这些环境提示“不安全”，也不能把本机软件 VM 的故障、native bridge 崩溃或改包启动异常称为风控。下一步先修复并验证原生 ARM Waydroid 的 UI 启动与 ADB 连接，再确认 APK 是否能到达登录页；登录结果需要单独记录明确的页面提示和发生阶段。
