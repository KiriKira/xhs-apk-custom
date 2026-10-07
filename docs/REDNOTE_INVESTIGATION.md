# REDnote 重打包调查（2026-10-07）

## 当前结论

主进程初始化兼容修复已在 commit [`ae7aef4`](https://github.com/KiriKira/xhs-apk-custom/commit/ae7aef4) 落盘，并已用于重建本地两种变体。最新 API 35 KVM smoke 中，原始包、换包名对照版和布局版均安装成功、进入隐私协议首屏，PID 分别为 4357、4732、5090；20 秒观察未检测到崩溃。此前 API 30 深度预览的修复后对照版能越过旧 NPE、同意隐私协议，随后出现 `SIGABRT` 和 `libndk_translation.so` 栈帧；该较早结果与最新 API 35 短时 smoke 是不同环境和观察阶段。三个变体都尚未进入手机号登录验证。

本轮没有输入手机号、请求短信验证码或完成登录，也没有观察到可供判断的登录风控提示。因此现有结果不能说明登录是否会触发“环境不安全”，更不能判断是账号、网络、虚拟环境还是 APK 改动导致。

## 输入来源与校验

Google Play 的 [REDnote 条目](https://play.google.com/store/apps/details?id=com.xingin.xhs&hl=en&gl=US)显示包名为 `com.xingin.xhs`。本次没有从 Play 安装或导出 APK；实际输入来自 [APKPure REDnote 下载页](https://apkpure.net/rednote-app/com.xingin.xhs/download)，不能称作已核验的 Google Play 导出包。

输入为 REDnote `9.48.1` / version code `9481803` 的 XAPK，含 base、`config.arm64_v8a`、`config.xxhdpi` 三个 APK。XAPK SHA-256：

```text
bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0
```

三个输入 APK 的签名均通过 `apksigner` 验证，应用签名证书 SHA-256 相同：`dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd`。输入的 SourceStamp 证书 SHA-256 为 `3257d599a49d2c961a471ca9843f59d341a405884583fc087df4237b733bbd6d`。这只记录输入文件校验；重打包 APK 使用自定义签名，不能宣称保留了官方签名或 SourceStamp。

## 当前 APK 与静态验证

当前 [`output_apks/SHA256SUMS`](../output_apks/SHA256SUMS) 已更新为包含 commit `ae7aef4` 主进程兼容修复的两种 APK 哈希。两个克隆变体均使用 `com.kirikira.rednote.fold`，比较时需先卸载前一个变体。

| 产物 | 变体 | SHA-256 |
| --- | --- | --- |
| `output_apks/rednote-9.48.1-renamed-control.apk` | 合并 XAPK、改包名，未做布局改动 | `46c7c0203dfff70c4b12dcc0ead68a1155efe26dc98e2442e046d7b0c7ae9db8` |
| `output_apks/rednote-9.48.1-fold-custom.apk` | 合并 XAPK、改包名，加两处布局 gate 改动 | `1e7b5f7abb45b7af92d8bee56d661e6ef09fc89fd3cc0cf0d841600b3b07669c` |

重复的 `{applicationId}.gcm.permission.C2D_MESSAGE` 已修复，主进程名检查也已更新为克隆包名；旧文档中的 duplicate-permission 安装失败和克隆 NPE 均为修复前问题，不代表当前 APK。

构建报告位于 `output_apks/rednote-9.48.1-control-build-report.json` 和 `output_apks/rednote-9.48.1-fold-build-report.json`。两个 APK 的签名与 zipalign 检查均通过；源 merge 基线 1,985 个原始条目除下述改动外哈希保持一致。对照版只重建 `classes17.dex`，布局版重建 `classes17.dex` 和 `classes4.dex`，其余 payload 哈希一致。编译后检查确认 `ddc.a.invoke` 使用新主进程名；布局版两个目标 gate 编译为 `const/4 v0, 1; return v0`。8 项单元测试通过。静态审计不代表登录兼容性。

## 运行证据与边界

| 变体 / 环境 | 已观察结果 | 登录状态 |
| --- | --- | --- |
| 未修改 APKPure 原始 XAPK，API 35 Google APIs x86_64 KVM smoke | 三个 split 安装成功，Activity 启动并到达隐私协议页；短时 smoke 未报崩溃。之后更深的预览在同意隐私协议并点登录后 native abort，栈中包含 `libndk_translation.so`。见 [run 37598983597](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37598983597)。 | 未显示手机号输入页；未输入手机号或请求短信。 |
| 未修改 APKPure 原始 XAPK，API 30 预览 | 到达隐私协议页；随后报告 native `SIGSEGV`。本地预览记录没有可用 native backtrace。 | 未输入手机号或请求短信。 |
| 换包名对照版旧 APK，API 35 | 修复前启动期发生 `XhsActivity.getResources()` 的 Java NPE，见 [run 37599034582](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37599034582)。这是已修复的旧问题。 | 未到登录页。 |
| 三个当前变体，API 35 Google APIs x86_64 KVM | [CI run 37601174448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601174448) 中，原始包、对照版和布局版均安装成功并显示隐私协议首屏；PID 4357 / 4732 / 5090，20 秒内均未检测到崩溃。 | 没有手机号表单输入；未请求短信。 |
| 主进程修复后的换包名对照版，API 30 | [run 37601175067](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601175067) 同意隐私后未再 NPE，随后以 native `SIGABRT` 退出，状态码 6，栈含多个 `libndk_translation.so` 帧。 | 未显示手机号表单；未输入手机号或请求短信。 |

此前克隆版 NPE 是启动兼容问题，不是服务器风控结果；`ddc/a` 中主进程名检查已由 `ae7aef4` 修复，最新对照版与布局版都能稳定显示隐私首屏 20 秒。较早 API 30 native abort 仍是待查问题。最新 smoke 仅验证隐私首屏，不等于主界面或登录可用。

API 35 x86_64 镜像声明 `x86_64,arm64-v8a` 并带 `libndk_translation.so`。原始 APK 的深度预览确实包含该 native bridge 的崩溃帧；这说明 native crash 与 ARM 翻译路径同时出现，但不能单凭栈帧认定翻译层就是根因。原始 APK 在 API 30 的 `SIGSEGV` 记录也不足以定位 native 根因。

已审阅的预览和 CI 记录均未输入手机号、请求短信验证码或完成登录。预览结果里的 `timeout` 是流程未到达目标状态，不代表服务器拒绝；没有手机号页面，也就不能判断登录风控提示是否出现。

## 后续状态

- 在 API 30/35 和原生 ARM Waydroid 继续检查新 APK 的启动稳定性；尚未验证登录页或手机号流程。
- 原生 ARM Waydroid run [37601728448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601728448) 曾因 PulseAudio socket 缺失导致 LXC mount 失败。第三轮 [37602265414](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37602265414) 后来已到达 Android user 0 ready、LXC `RUNNING` 且 IP `192.168.240.112`；该轮实际未安装 APK，因脚本过早接受 `UNKNOWN:5555` 并超时，不是容器未启动。
- 修复 IP 发现逻辑的 commit `b56cbad` 对应第四轮 [37603857949](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37603857949)，该轮已取消。日志显示 Android ready 且曾获得 `192.168.240.112`；首次 `adb connect` 明确报告 `failed to authenticate`，后续返回 already connected，但 `adb get-state` 未到达 `device`。运行期间没有 `show-full-ui` 活动，之后 LXC 进入 `FROZEN`。该轮没有 APK 安装或应用测试；需修复自建 Android 的调试认证和窗口生命周期。
- 原生 ARM 构建 run [37605217096](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37605217096) 成功构建 fold 变体，但使用旧连接脚本的 Android 初始化步骤已取消，APK 安装和应用测试均未执行。下一轮需明确启动 Waydroid UI 并验证 ADB 主机密钥信任及 `get-state=device` 后再继续；目前仍无原生 ARM APK 运行结果。模块探测 run [37585019547](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37585019547) 已验证官方 extras 下 ARM/x86 Binder 模块可用。
- 在获得稳定登录页之前，不对环境风控作结论。任何后续登录检查都应把 app crash、网络错误、验证码流程和明确的服务端安全提示分别记录。

## Morphe 普通克隆兼容性参考

核查的 Morphe 提交为 `1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2`。其 [Clone app patch](https://github.com/MorpheApp/morphe-patches/blob/1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2/patches/src/main/kotlin/app/morphe/patches/all/misc/clone/CloneAppPatch.kt) 明确警告克隆可能崩溃或功能异常，并处理 package name、custom permission 和 provider authorities；已知不兼容列表声明为非穷尽。Morphe [issue #2839](https://github.com/MorpheApp/morphe-patches/issues/2839) 记录了 YT Music 启用 Clone app 后 PoToken 设置项消失；[issue #528](https://github.com/MorpheApp/morphe-patches/issues/528) 记录 Reddit 改包后的登录问题。这些是逐应用兼容性示例，不能外推为 REDnote 的风控根因。

在所查 Morphe 源码和 issue、ReVanced patches issue 中，没有搜到 REDnote / 小红书专用 patch 或明确报告“environment is unsafe”。这只说明本次公开仓库检索范围；ReVanced 原仓库受 [GitHub DMCA 下架](https://github.com/github/dmca/blob/master/2026/03/2026-03-12-morpheapp.md)影响，不能据零搜索结果断言全网不存在相关记录。
