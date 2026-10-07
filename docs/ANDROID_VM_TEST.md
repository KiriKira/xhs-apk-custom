# Android VM 安装与运行记录

更新日期：2026-10-07

## 当前测试状态

此前三个非原版变体是未迁移生产签名兼容 helper 的启动对照，不能代表完整国内版 patch 流程。后续 `control-compat` / `fold-compat` 迁移 production Application hook、改为 REDnote 输入证书及克隆包名，并保留 `XINGIN` v1 条目名，单独记录构建与实际登录结果。两组最新预览均已到 +86 表单且 helper installed，无崩溃；首次手机号传入等待超时，run 37636029064 的 fold-compat 已实际提交手机号、进入验证码页且用户确认收到短信；当前未验证 OTP/最终登录。

当前测试使用 APKPure 分发的 REDnote `9.48.1` XAPK（SHA-256 `bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0`），不是从 Google Play 直接导出的 APK。XAPK 原始包、两个 split 和构建报告的来源信息见仓库 `output_apks/*build-report.json`。

此前 API 35 Google APIs x86_64 KVM runner 中，原始包、换包名对照版和布局版都显示隐私协议首屏，PID 分别为 4357、4732、5090，20 秒观察未检测到崩溃。最新原生 ARM Waydroid 对照中，原版到达手机号登录表单且 PID 4077 健康；原包名重签、换包名 control、fold 三组则在隐私操作后以 `SIGNALED` / status 6 退出。后三组没有 native frames 或 abort message，不能据此确认签名校验或服务端风控。

最新原版 [run 37614160907](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37614160907) 已在确认 +86 后实际输入授权手机号，点击一次 Next 并到达验证码页；`phone_entered=true`、`get_code_clicked=true`、`otp_input_visible=true`。未检测到环境不安全提示，该轮未提交 OTP 或确认最终登录结果，验证码等待已结束；后续测试关注完整 patched REDnote。此前 helper 返回 welcome 或国家列表定位失败的轮次没有输入号码，不能代表服务器拒绝。

| 变体 | 安装与运行结果 | 证据 |
| --- | --- | --- |
| 原始 APKPure XAPK（base + ARM64 + xxhdpi split，`com.xingin.xhs`） | API 35 KVM smoke：split 安装成功并启动至隐私协议，短观察未见崩溃。更深预览同意隐私并点登录后 native `SIGABRT`，栈中包含 `libndk_translation.so`。 | [run 37598983597](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37598983597) |
| 原始 APKPure XAPK（`com.xingin.xhs`） | API 30 预览到隐私协议后 native `SIGSEGV`；本地预览记录没有可用 native backtrace。它不是登录风控提示。 | 本地预览记录 |
| 换包名对照版旧 APK（`com.kirikira.rednote.fold`） | 修复前 API 35 启动请求被接受后发生 `XhsActivity.getResources()` 的 Java NPE。此旧故障已由 `ae7aef4` 修复。 | [run 37599034582](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37599034582) |
| 当前三个变体 | API 35 run 37601174448 中均安装成功并显示隐私协议首屏；PID 4357 / 4732 / 5090，20 秒观察无崩溃。 | [run 37601174448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601174448) |
| 换包名对照版旧 APK | API 30 深度预览记录 `XhsActivity.getResources()` 相关 NPE；这是修复前结果。 | 本地预览记录 |
| 主进程修复后的换包名对照版 | 较早 API 30 run 37601175067 可同意隐私协议，未再出现 NPE；随后 native `SIGABRT`，状态码 6，native 栈包含 `libndk_translation.so`。 | [run 37601175067](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601175067) |
| A：APKPure 原始完整 split、原包名和输入签名 | 原生 ARM [run 37611437295](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611437295) 到达手机号登录表单，PID 4077 健康。stock 窗口 1080×1920、密度 420，欢迎页按钮完整显示。 | 表单可见；`phone_entered=false`、`get_code=false`。未输入号码或请求短信。 |
| A 最新实际手机号提交 | 原生 ARM [run 37614160907](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37614160907)：+86 表单、PID 4031 健康，复用当前页面。 | 已输入授权手机号并点击一次 Next，进入验证码页；未检测到环境不安全。未提交 OTP，验证码等待已结束，尚未完成登录。 |
| B：原包名，仅重签输入的三 split | 原生 ARM [run 37611717935](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611717935)；审计确认所有非签名 payload hashes 一致。隐私操作后以 `SIGNALED` / status 6 退出；无 native frames、无 abort message。 | 未输入号码或请求短信。 |
| C：换包名 control | 原生 ARM [run 37611443776](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611443776)；隐私操作后 `SIGNALED` / status 6 退出，无 native frames、无 abort message。 | 未输入号码或请求短信。 |
| D：换包名 fold | 原生 ARM [run 37611440851](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611440851)；与 control 一样以 `SIGNALED` / status 6 退出，无 native frames、无 abort message。 | 未输入号码或请求短信。 |

未修改 APK 在 API 35 的短时 smoke 中未崩溃，与更深预览中的 native crash 是不同观察阶段，不应合并成“稳定运行”。API 35 镜像声明 ABI `x86_64,arm64-v8a` 并带 `libndk_translation.so`；native 栈包含该库只能说明翻译路径出现于崩溃调用栈，不能单独证明它是根因。

## 克隆版启动兼容性

APKManifest 的重复 `{applicationId}.gcm.permission.C2D_MESSAGE` 已修复。当前三个 APK 均安装成功，所以较早记录的 `INSTALL_FAILED_DUPLICATE_PERMISSION` 已过时。

应用 `ddc/a` 中的主进程名硬编码检查曾导致改包名后跳过 `Application` 初始化，随后 `XhsActivity.getResources()` 抛 NPE。该兼容修复已提交并进入当前 APK；API 35 x86 KVM run 37601174448 确认两个克隆变体到达隐私协议且 20 秒无崩溃。原生 ARM 后续对照中，重签原包名版、改包名 control、fold 均在隐私操作后退出；这与 API 35 短时 smoke 是不同环境与阶段。ActivityManager 返回启动成功只表示启动请求被接受，不代表应用进程健康。

原项目签名兼容 helper 只调整应用进程内 `PackageInfo` / `SigningInfo` Java 查询可见值，且硬编码目标包名 `com.xingin.xhs`；它不会改变 Android 实际安装 signer，也不能说明 REDnote native 代码如何校验。Morphe 的 Reddit Java 查询兼容实现同样有限于该查询路径，不能据此推断本次 SIGNALED 6 的根因。详见 [签名与完整性说明](SIGNATURE_PROTECTION.md)。

当前 [`output_apks/SHA256SUMS`](../output_apks/SHA256SUMS) 是已重建并包含 `ae7aef4` 的产物哈希：

| 文件 | 包名 | SHA-256 |
| --- | --- | --- |
| `rednote-9.48.1-renamed-control.apk` | `com.kirikira.rednote.fold` | `46c7c0203dfff70c4b12dcc0ead68a1155efe26dc98e2442e046d7b0c7ae9db8` |
| `rednote-9.48.1-fold-custom.apk` | `com.kirikira.rednote.fold` | `1e7b5f7abb45b7af92d8bee56d661e6ef09fc89fd3cc0cf0d841600b3b07669c` |

构建报告验证对照版仅改 `AndroidManifest.xml` 与 `classes17.dex`；布局版改这两项和 `classes4.dex`。独立 payload 审计确认原始 1,985 条目中其他条目哈希一致；编译 gate 检查通过，8 项单元测试通过。

原包名但重签的 B 组在非签名 payload 一致的审计下仍复现进程退出，说明改包名并非该退出的必要条件。C 与 D 同样退出，暂不支持 fold gates 是退出的必要原因。A/B 仍不能确定具体机制：重签会改变实际 signer 和签名元数据，不能从现象单独断言应用做了证书校验、APK 完整性校验或服务端拒绝。

## KVM 与 ARM Waydroid

API 35 x86_64 测试使用 Android Emulator 37.2.12、Google APIs system image 和可用 KVM。镜像提供 `libndk_translation.so` 并声明 ARM64 ABI，但这是 **x86_64 guest 中的 ARM native bridge**，不等同于原生 ARM Android 环境。

- 旧 run [37580918798](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37580918798) 验证 hosted runner 的 `/dev/kvm` 可用，并成功启动 API 35 emulator。它没有完成 APK 下载或安装。
- 旧 smoke run [37581654651](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37581654651) 的克隆安装曾因重复 custom permission 失败；该问题已在当前构建修复。该 run 的旧 APK 与哈希不代表现在的产物。
- [模块探测 run 37585019547](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37585019547) 已确认官方 extras 提供的 ARM/x86 Binder 模块可用。这验证了模块侧条件，不证明目标应用已在 Waydroid 中安装或启动。
- 原生 ARM Waydroid run [37601728448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601728448) 因 LXC 缺少 `XDG_RUNTIME_DIR/pulse/native` 挂载而失败，没有完成应用测试。
- 补齐 PulseAudio 后的第三轮 [37602265414](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37602265414) 已实际到达 Android user 0 ready；LXC 状态 `RUNNING`，地址 `192.168.240.112`。这次未测试 APK，是因为脚本过早将未知地址 `UNKNOWN` 拼成 `UNKNOWN:5555` 并超时，不是 Waydroid 容器未启动。
- IP 发现修复 commit `b56cbad` 的第四轮 [37603857949](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37603857949) 已取消。日志显示 Android ready 且地址为 `192.168.240.112`；首次 `adb connect` 明确报告 `failed to authenticate`，后续返回 already connected，但 `adb get-state` 未变为 `device`。该次运行未执行 `show-full-ui`，随后 LXC 进入 `FROZEN`。这是自建 Android 的 ADB 主机认证和窗口生命周期问题，未安装或启动 APK。
- [37605217096](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37605217096) 成功构建 native ARM QEMU fold APK，但 Android 初始化取消，APK 安装和应用测试跳过。后续四组对照 run [37611437295](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611437295)、[37611717935](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611717935)、[37611443776](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611443776)、[37611440851](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611440851) 已完成应用启动对照。

此前在本机用 TCG 软件模拟的 API 30/35 尝试有系统服务缺失或首次启动过慢的问题，不能代表上述 hosted KVM 结果，也不能作为当前应用测试结论。此前的 `INSTALL_FAILED_DUPLICATE_PERMISSION` 和克隆启动 NPE 均已修复；旧 NPE 记录不代表当前 APK。

## 登录与风控测试边界

最新原版 Waydroid 已实际提交用户授权手机号并进入验证码页，未检测到“环境不安全”；尚未提交 OTP 或确认登录。源于旧 helper 页面重启/标签不匹配以及 run 37613132905 的地区列表定位失败已修正；这些旧轮次均未输入号码。最新预览通过唯一 +86 行定位，验证区号后才接收一次加密手机号输入。

原版 stock 窗口 1080×1920 / density 420 欢迎按钮完整出现；源码确认 PHONE 行由本地无条件生成。此前 letterbox 小窗口只露出约 3px 属于窗口裁剪，不是服务端登录响应。原生 ARM HTTPS 探测的 Google `204`、REDnote `200`、edith `200` 只证明基础端点可达，不证明 app 登录 API 成功。

三个非原版变体在手机号提交前退出，当前没有它们的实际登录响应。原版到达验证码页也不等于最终登录成功；不把 helper timeout、进程 `SIGNALED` 6 或 HTTPS 连通性称为风控。
