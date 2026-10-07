# Android Emulator 运行与 APK 安装记录

日期：2026-10-07

## 环境与启动方式

使用 Android Emulator 37.2.12（build 16428233）和 Android 11 / API 30 Google APIs x86_64 system image rev 16。AVD 名称为 `rednote-api30`，配置位于 `/workspace/android-sdk/avds/rednote-api30.avd`；guest 分配 2 个 vCPU、2048 MiB RAM，屏幕为 720×1280。ADB serial 为 `emulator-5554`。

本环境没有可用 KVM：在 Docker privileged 探测中仍未发现 `/dev/kvm`，CPU 未暴露 `vmx` 或 `svm` 标志；`emulator -accel-check` 报告 CPU 不支持 vmx 或 svm。因此这个 AVD 使用 QEMU TCG 软件模拟，不能描述为 KVM 加速。

重启同一 AVD 的命令：

```sh
export ANDROID_SDK_ROOT=/workspace/android-sdk
export PATH="$ANDROID_SDK_ROOT/platform-tools:$ANDROID_SDK_ROOT/emulator:$PATH"
ANDROID_I_WANT_MY_TCG=yes "$ANDROID_SDK_ROOT/emulator/emulator" \
  -avd rednote-api30 -accel off -no-window -no-audio -no-boot-anim \
  -gpu swiftshader -no-snapshot
```

Emulator 37.2.12 使用 `-gpu swiftshader`。这里不使用旧的 `swiftshader_indirect` 参数。`ANDROID_I_WANT_MY_TCG=yes` 是在关闭加速、改用 TCG 时所需的显式环境变量。TCG 模式官方标注为很慢；关闭窗口、音频和快照不会消除 CPU 模拟成本。

等待 Android 完成启动后再安装应用。ADB 显示 `device` 只说明 ADB 已连接，不能代替 `sys.boot_completed=1`：

```sh
adb -s emulator-5554 get-state
adb -s emulator-5554 shell getprop sys.boot_completed
```

API 30 的后续观察：首次启动中 `system_server` PID 534 退出，随后出现新 PID 1285；SystemUI 和 PermissionController 记录 `DeadSystemException`。截图显示 `System UI isn't responding`。虽然稍后 `sys.boot_completed` 报告 `1`，再次检查时 `package` 与 `activity` 服务均不存在，因此不能把这个属性单独视为可测试的系统。

原始三个 split 的 `adb install-multiple` 已实际尝试，返回 `Failure calling service package: Broken pipe (32)`；没有确认安装成功，未启动 REDnote。保存的启动日志可证实 PackageManager 初始化约 91 秒、Watchdog `WAITED_HALF` 及长时间线程竞争，但缺少系统退出时刻的直接根因日志，不能写成已证实的 Watchdog kill、应用崩溃或风控拒绝。

随后已停止 API 30，改为启动 Android 15 / API 35 Google APIs x86_64 rev 9。官方归档 SHA-1 `0103e6dab21290c4b9d16550a3ce99476f884eef` 校验通过，镜像 build.prop 声明 `x86_64,arm64-v8a`、`libndk_translation.so`。新 AVD 为 `rednote-api35`，ADB serial `emulator-5556`，命令行分配 1 vCPU、3072 MiB RAM；仍使用 `-accel off`，不是 KVM。最终运行状态在后文补记。

## ARM64 ABI 检查

启动中的 API 30 x86_64 Google APIs 镜像已经报告以下 ABI：

```text
x86_64,x86,arm64-v8a,armeabi-v7a,armeabi
```

`ro.dalvik.vm.native.bridge` 为 `libndk_translation.so`，且 `/system/lib64/libndk_translation.so` 文件存在。这表明 system image 声明 ARM64 ABI 并带有 ARM native bridge；它尚不能替代目标 APK 的实际安装、进程启动及 ARM64 `.so` 加载检查。

启动就绪后，可复核：

```sh
adb -s emulator-5554 shell getprop ro.product.cpu.abilist
adb -s emulator-5554 shell getprop ro.product.cpu.abilist64
adb -s emulator-5554 shell getprop ro.dalvik.vm.native.bridge
adb -s emulator-5554 shell ls -l /system/lib64/libndk_translation.so
```

## 三个 APK 变体

源文件来自 APKPure 分发的 REDnote 9.48.1 XAPK，不是从 Google Play 直接导出的安装包。原始 XAPK 拆出的三个 APK 为 base、ARM64 split 和 xxhdpi split；合并构建的两个输出 APK 使用相同克隆包名，所以比较它们时应先卸载前一个。

| 变体 | 文件 | 安装包名 | 安装方式 |
|---|---|---|---|
| 原始 APKPure XAPK 分包 | `/workspace/rednote-input/verify/com.xingin.xhs.apk`、`config.arm64_v8a.apk`、`config.xxhdpi.apk` | `com.xingin.xhs` | `adb install-multiple`，三个分包一起安装 |
| 换包名对照版 | `/workspace/xhs-apk-custom/output_apks/rednote-9.48.1-renamed-control.apk` | `com.kirikira.rednote.fold` | 单 APK 安装 |
| 折叠布局补丁版 | `/workspace/xhs-apk-custom/output_apks/rednote-9.48.1-fold-custom.apk` | `com.kirikira.rednote.fold` | 单 APK 安装 |

以下命令用于在 AVD 启动完成后依次安装并尝试启动各变体。它们是复现步骤，不表示这些安装或 UI 启动已经执行成功。原始应用与克隆版包名不同；两个克隆版包名相同，切换克隆版时先卸载，避免保留前一个变体的数据：

```sh
ADB=/workspace/android-sdk/platform-tools/adb
SERIAL=emulator-5554

# 1. 原始 APKPure XAPK 的 base 与两个 split
"$ADB" -s "$SERIAL" install-multiple -r \
  /workspace/rednote-input/verify/com.xingin.xhs.apk \
  /workspace/rednote-input/verify/config.arm64_v8a.apk \
  /workspace/rednote-input/verify/config.xxhdpi.apk
"$ADB" -s "$SERIAL" shell monkey -p com.xingin.xhs 1

# 2. 仅改包名的对照版
"$ADB" -s "$SERIAL" uninstall com.kirikira.rednote.fold
"$ADB" -s "$SERIAL" install \
  /workspace/xhs-apk-custom/output_apks/rednote-9.48.1-renamed-control.apk
"$ADB" -s "$SERIAL" shell monkey -p com.kirikira.rednote.fold 1

# 3. 布局补丁版
"$ADB" -s "$SERIAL" uninstall com.kirikira.rednote.fold
"$ADB" -s "$SERIAL" install \
  /workspace/xhs-apk-custom/output_apks/rednote-9.48.1-fold-custom.apk
"$ADB" -s "$SERIAL" shell monkey -p com.kirikira.rednote.fold 1
```

如果克隆版的 `uninstall` 提示包尚未安装，可在首次安装时跳过该行。切换回原始变体前，也应先确认原始包是否已安装；若需要干净比较，可先卸载 `com.xingin.xhs` 再重新执行 `install-multiple`。安装成功后可用 `adb -s emulator-5554 shell pm path <package>` 确认 Package Manager 已登记 APK。

## 当前测试边界

本记录确认了 Emulator/AVD 配置、ADB 连接、API 30 镜像的 ARM64 ABI 声明及 native bridge 文件存在。记录撰写时系统仍未完成首次启动，因此尚无这三个 APK 的安装、应用进程启动、界面显示或登录结果。未输入或记录手机号、短信验证码或账号凭据；未修改系统属性或设备标识以隐藏模拟器。TCG 环境的应用运行表现也不能代表真实 ARM64 设备的性能或服务端处理结果。

## GitHub Actions KVM 对照

用户进一步授权在免费的 GitHub Actions runner 上测试。新增 `.github/workflows/rednote-kvm-test.yml`，仅使用公开仓库的标准 `ubuntu-24.04` runner，不使用 larger runner、不上传 artifact、不存储 cache。独立分支 `codex/rednote-kvm-test` 的 push 触发测试，不改动生产构建 workflow。

该流程要求真实存在的 `/dev/kvm`，调用 Emulator `-accel-check`，并使用 `-accel on` 启动 Android 15 Google APIs x86_64 镜像。构建先于虚拟机启动，避免二者同时占用 JVM/Android 内存。输入 XAPK 和 APKEditor 都固定 SHA-256，重新构建换包名对照及布局版本后，由 `tools/rednote_emulator_smoke.py` 依次卸载、安装、启动三个变体。

本轮自动化仅收集无账号状态的截图、UI XML、安装/启动状态和简短崩溃摘要，输出到 job 日志；没有加入手机号或登录凭据。该结果必须等实际 job 完成后核对，不能从 workflow 文件推断安装或运行成功。Google APIs 镜像也不等于通过 Play Store 安装的真实设备环境。
