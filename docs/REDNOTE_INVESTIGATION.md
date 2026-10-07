# REDnote 重打包调查（2026-10-07）

## 已确认与未确认

Google Play 的 [rednote 条目](https://play.google.com/store/apps/details?id=com.xingin.xhs&hl=en&gl=US) 使用 `com.xingin.xhs`。这与原项目的中国版包名相同，但不足以证明两个渠道的代码、配置、版本和签名相同。官网 [下载页](https://www.rednote.com/download) 提供商店跳转；本次未通过 Google Play 安装或导出应用。

用户授权自行寻找第三方下载来源。本次获取 [APKPure 的 REDnote 下载](https://apkpure.net/rednote-app/com.xingin.xhs/download)，版本 `9.48.1` / `9481803`，是包含 base、`config.arm64_v8a`、`config.xxhdpi` 的 XAPK。来源应称为 **APKPure 分发包**，不能直接称为已核验的 Google Play 导出包。原 XAPK SHA-256：

```text
bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0
```

原文件保存在 `/workspace/rednote-input/`，不提交到 Git。每个分包的实际签名、ABI、文件哈希和下载来源记录在该目录的 `provenance.json`；构建报告另外记录合并、重签名、包名及布局改动。

Android build-tools 35.0.0 的 `apksigner` 核验 base APK：v1/v2/v3 签名通过，`Verified for SourceStamp: true`。三个分包的应用签名证书 SHA-256 均为 `dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd`。base 的 SourceStamp 证书显示 `O=Google Inc.`，SHA-256 为 `3257d599a49d2c961a471ca9843f59d341a405884583fc087df4237b733bbd6d`。这是可核查的签名和分发印章证据；本次下载链仍然是 APKPure，且没有与相同版本的设备端 Play 导出文件逐字节比较。

目前 **没有安装或登录测试结果**。当前容器没有 KVM 设备和 Android Binder 内核支持，无法运行请求的 KVM＋Waydroid 环境。这个输入又包含 ARM64 本地库，而工作区 CPU 是 x86_64；即使换到支持 Waydroid 的 x86_64 主机，也还需核对 ABI 兼容性。详细事实与测试步骤见 [REDNOTE_RUNTIME.md](REDNOTE_RUNTIME.md)。不能据此判断官方版或所有补丁版是否都会出现“环境不安全”。

## 本次构建结果

两份单体 APK 都已生成，版本为 `9.48.1` / `9481803`，新包名都是 `com.kirikira.rednote.fold`，使用仓库公开测试密钥重新签名。两者需要在干净应用数据下顺序测试，不能以相同包名同时安装。

| 产物 | 内容 | SHA-256 |
| --- | --- | --- |
| `output_apks/rednote-9.48.1-renamed-control.apk` | XAPK 合并、换包名，保留原 DEX | `9ee8510edd291cf98dce3dfbe4c29b9b7cbcce6ff4d7c74b01e5eaf85483294e` |
| `output_apks/rednote-9.48.1-fold-custom.apk` | 相同改包流程，加两处布局 gate 补丁 | `63f739db77a7660f29e577f775a5033d46a6ff1afca9ce567f52cb7de97ba453` |

两份 APK 的签名和 16 KiB native-library ZIP 对齐核验均通过。独立比较原分包的 1,985 个 DEX、native、assets、ServiceLoader 条目：对照包全部保留；布局包只有 `classes4.dex` 改变。直接解析最终布局包的 DEX 确认两个目标方法的指令均为 `const/4 v0, 1; return v0`。相对合并基线的完整 payload 审计还确认除 manifest 和目标 DEX 外没有其他内容改动。

源码的 4 项单元测试和合成 APK 的完整构建验证通过。第一次真实构建的 internal DEX 解码器在容器 8 GiB 内存上限触发 OOM；改为 `jf` 并限制解码/重建 JVM heap 为 4 GiB 后，真实构建成功。最终入口记录 merge 前后 DEX/native 哈希、工具参数和输入来源。

这些结果只证明打包和静态改动通过验证，**未验证启动、布局显示或登录**。新入口未注入生产脚本的签名伪装 helper；不能宣称获得了生产脚本既有的启动/登录兼容性。provider/content URI、自定义权限、回调及应用自检的运行行为仍需实际设备验证。

## 原构建的局限

- `xhs_build_ci.download_apk()` 把输入缓存在固定的 `.base_apk_xhs/xhs-base.apk`，文件存在就返回；直接改 URL 可能仍用旧 APK。
- `build_xhs.py` 仅替换 DEX 并保留原 manifest，没有 applicationId 改写能力；原签名 helper 也写死了 `com.xingin.xhs`。
- 当前生产构建包含 Java 签名伪装及两处布局 gate 改动；不能把它与“仅布局修改”视作相同实验。
- Play/第三方分包不能只抽出 base APK 就当作完整输入；本地库和部分资源在 splits 中。

独立入口 `build_rednote.py` 与生产构建分开，记录明确的输入 SHA-256 和来源，改写 manifest 并可选添加两处折叠屏布局改动。该入口不注入签名伪装，也不伪装设备、安装来源或认证结果。合并 XAPK、改包名和重签名后的产物属于自定义变体，必须独立测试启动和登录兼容性。

## Morphe 可参考的普通兼容性工作

核查的 Morphe 仓库提交为 `1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2`。在本次检查的 `patches` 和 `extensions` 中未发现 `xingin`、`rednote` 或 `xiaohongshu` 专用补丁；这只是该提交的搜索结果，不能代表所有第三方项目。

它的 [Clone app 补丁](https://github.com/MorpheApp/morphe-patches/blob/1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2/patches/src/main/kotlin/app/morphe/patches/all/misc/clone/CloneAppPatch.kt) 除了修改 package，还处理 provider authorities 和自定义 permission，且明确说明克隆可能导致崩溃或其他异常。这些是并装兼容性的参考，不是 REDnote 风控的实测证据。应用内部硬编码的 content URI、回调、SDK 配置和资源包关系仍可能需要逐项适配。

可继续做的工作是：核验官方分发物、在真实 ARM64 Android 设备上建立未修改基线、分开比较 split 侧载/合并重签/换包名/布局补丁，并记录提示原文和脱敏崩溃堆栈。若官方未修改版本也报同样提示，再通过官方支持渠道排查账号、网络或设备支持；若只在自定义版本出现，优先检查构建和组件兼容性。没有对照证据前，不应把原因写成确定结论。
