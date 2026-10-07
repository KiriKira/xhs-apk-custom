# REDnote 重打包调查（2026-10-07）

## 当前结论

主进程初始化兼容修复已在 commit [`ae7aef4`](https://github.com/KiriKira/xhs-apk-custom/commit/ae7aef4) 落盘，并已用于重建本地两种变体。此前 API 35 KVM smoke 中，原始包、换包名对照版和布局版均安装成功并进入隐私协议首屏，20 秒观察未检测到崩溃；这只能说明当时 x86_64 smoke 的首屏稳定性。

原生 ARM Waydroid 的最新四组对照显示：原版 REDnote 在隐私流程后到达手机号登录表单且进程健康；原包名但仅重签的三 split 对照、换包名 control、fold 变体都在隐私操作后以 `SIGNALED` / status 6 退出。重签原包名对照的非签名 payload hashes 与官方 split 一致，因此新包名不是复现退出的必要条件；control 与 fold 同样退出，fold gate 也不是必要条件。这使签名/签名元数据或 APK 完整性相关启动差异成为候选，但目前没有 native backtrace 或 abort message，不能确认签名校验，更不能称为服务端风控。

最新原版测试 [run 37614160907](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37614160907) 已确认 +86、实际输入用户授权的手机号、点击 Next 并进入验证码输入页；`phone_entered=true`、`get_code_clicked=true`、`otp_input_visible=true`，结果为 `otp_screen`，未检测到“环境不安全”提示。当前等待用户提供短信验证码，尚未提交 OTP 或确认最终登录成功。这排除了“该环境中原版也一律在请求验证码前拒绝登录”的说法；并不证明后续验证一定成功。此前 helper 返回 welcome 或 country selector 未解决的轮次均没有输入号码或请求短信，不能当作服务器拒绝。

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
| 原版 APKPure split，原生 ARM Waydroid | [run 37611437295](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611437295)：隐私流程后到达手机号登录表单，PID 4077 仍健康。标准窗口为 1080×1920、密度 420；欢迎页按钮完整显示。 | 仅显示表单；phone helper 超时，`phone_entered=false`、`get_code=false`。未输入号码或请求短信。 |
| 原版 APKPure split，原生 ARM Waydroid，最新实际手机号提交 | [run 37614160907](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37614160907)：PID 4031 健康，+86 表单确认；复用现有表单并只点击一次 Next。 | 实际输入授权手机号并进入验证码页，未检测到环境不安全；等待用户验证码，尚未确认最终登录。 |
| 原包名、原始三 split 仅重签名，原生 ARM Waydroid | [run 37611717935](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611717935)：非签名 payload hash 审计一致；同意隐私后进程以 `SIGNALED` / status 6 退出。未取得 native frames 或 abort message。 | 未输入号码或请求短信。 |
| 改包名 control、原生 ARM Waydroid | [run 37611443776](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611443776)：隐私操作后以 `SIGNALED` / status 6 退出；未取得 native frames 或 abort message。 | 未输入号码或请求短信。 |
| 改包名 fold、原生 ARM Waydroid | [run 37611440851](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611440851)：与 control 一样退出，未取得 native frames 或 abort message。 | 未输入号码或请求短信。 |

原包名重签组与两个克隆组在原生 ARM 中均发生同类退出，说明包名改写不是该退出的必要条件；control 与 fold 结果相同，也不支持 fold gate 为必要原因。当前仍无法区分实际 signer、SourceStamp/签名元数据、APK 完整性检查或其他启动差异。`SIGNALED` / status 6 只表明信号退出，缺少 native frames 和 abort message 时不应给出根因。

此前 API 30/35 x86_64 结果仍应单独看待：部分深度预览的栈含 `libndk_translation.so`，但原生 ARM 的重签组也退出，因此 native bridge 不是目前这些结果的必要解释。原版 stock 窗口 1080×1920 / density 420 时欢迎按钮完整显示；PHONE 48dp 行在旧的小 letterbox 窗口中只露出约 3px，而静态源码确认该行是本地无条件构造。这是窗口裁剪/布局表现，不是服务端响应或登录验证。

原生 ARM 网络探测得到 Google `204`、REDnote `200`、edith `200`，只证明这些 HTTPS 端点可达，不证明应用登录 API 或认证流程成功。phone helper 的 timeout 是 UI 索引/标签失配，不代表服务器拒绝。

## 后续状态

- 已保存四组启动对照与 APK 哈希。最新原版实际提交手机号后进入验证码页，等待用户验证码；后三组未到手机号提交阶段。
- 原生 ARM Waydroid run [37601728448](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37601728448) 曾因 PulseAudio socket 缺失导致 LXC mount 失败。第三轮 [37602265414](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37602265414) 后来已到达 Android user 0 ready、LXC `RUNNING` 且 IP `192.168.240.112`；该轮实际未安装 APK，因脚本过早接受 `UNKNOWN:5555` 并超时，不是容器未启动。
- 修复 IP 发现逻辑的 commit `b56cbad` 对应第四轮 [37603857949](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37603857949)，该轮已取消。日志显示 Android ready 且曾获得 `192.168.240.112`；首次 `adb connect` 明确报告 `failed to authenticate`，后续返回 already connected，但 `adb get-state` 未到达 `device`。运行期间没有 `show-full-ui` 活动，之后 LXC 进入 `FROZEN`。该轮没有 APK 安装或应用测试；需修复自建 Android 的调试认证和窗口生命周期。
- 原生 ARM 后续 run [37611437295](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611437295)、[37611717935](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611717935)、[37611443776](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611443776)、[37611440851](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37611440851) 已完成上述四组对照；除原版外，其余三组在隐私操作后退出。模块探测 run [37585019547](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37585019547) 已验证官方 extras 下 ARM/x86 Binder 模块可用。
- 最新原版出现验证码输入页，尚无最终登录结果；未检测到安全提示。早先 run 37613132905 在地区列表停止，PID 4501 健康且未输入号码；后续已改为唯一 +86 行定位。仅按明确页面状态记录，不把 helper timeout、进程退出或 HTTPS 连通性当作服务器风控结论。

## Morphe 普通克隆兼容性参考

核查的 Morphe 提交为 `1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2`。其 [Clone app patch](https://github.com/MorpheApp/morphe-patches/blob/1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2/patches/src/main/kotlin/app/morphe/patches/all/misc/clone/CloneAppPatch.kt) 明确警告克隆可能崩溃或功能异常，并处理 package name、custom permission 和 provider authorities；已知不兼容列表声明为非穷尽。Morphe [issue #2839](https://github.com/MorpheApp/morphe-patches/issues/2839) 记录了 YT Music 启用 Clone app 后 PoToken 设置项消失；[issue #528](https://github.com/MorpheApp/morphe-patches/issues/528) 记录 Reddit 改包后的登录问题。这些是逐应用兼容性示例，不能外推为 REDnote 的风控根因。

原项目 `signature_spoof_experiment.py` 的兼容 helper 钩住应用进程中的 `PackageInfo.CREATOR`，并替换兼容 Java 查询可见的 `PackageInfo.signatures` / `SigningInfo` 值。其目标包名硬编码为 `com.xingin.xhs`；它不会改变 Android 实际安装 signer，也不能代表 native 校验或 REDnote 克隆包。Morphe 的 [Reddit signature patch](https://github.com/MorpheApp/morphe-patches/blob/main/extensions/reddit/src/main/java/app/morphe/extension/reddit/patches/SpoofSignaturePatch.java) 是同类进程内 Java 查询兼容示例，不能视为 native 或服务端检查的证据。详见本仓库 [signature/integrity notes](SIGNATURE_PROTECTION.md)。

在所查 Morphe 源码和 issue、ReVanced patches issue 中，没有搜到 REDnote / 小红书专用 patch 或明确报告“environment is unsafe”。这只说明本次公开仓库检索范围；ReVanced 原仓库受 [GitHub DMCA 下架](https://github.com/github/dmca/blob/master/2026/03/2026-03-12-morpheapp.md)影响，不能据零搜索结果断言全网不存在相关记录。
