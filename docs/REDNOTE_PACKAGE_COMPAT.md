# REDnote 改包兼容排查

本次针对已发布的 `rednote-v9.48.1-1` 原文件排查登录后冷启动问题。
APK SHA-256：`776a835279b476bd0314dc77488fc43f03244869f2fed48aa8ee0e4d9e930773`。
此文件不包含账号、手机号、验证码或登录凭据。

## 原项目的打包方式

国内版 `build_xhs.py` 将修改的 DEX 回填原 APK，并注入签名查询 helper 后重签。
它保留 `com.xingin.xhs` 安装包名。该 helper 改变应用进程内的
`PackageInfo` / `SigningInfo` 查询结果；实际 APK 仍由项目 keystore 签名。
它没有把完整原 APK 放入另一个容器。

REDnote 构建合并 XAPK 分包后，将实际 Manifest 包名改为
`com.kirikira.rednote.fold`，并隔离自有权限和 Provider authority。
Java 类名保留原命名空间，这与 Android 安装包名、进程名是不同概念。
默认主进程名随安装包名变化；不会因为 DEX 类名未变就保留原进程名。

## Morphe YouTube 的参考

已核对 Morphe patches v1.46.0，commit
`1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2`，以及其 patcher 1.14.0。

- [Clone app](https://github.com/MorpheApp/morphe-patches/blob/1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2/patches/src/main/kotlin/app/morphe/patches/all/misc/clone/CloneAppPatch.kt) 修改实际 Manifest 包名和自有权限、Provider 等资源，采用常规 APK 重打包。
- [YouTube GmsCore support](https://github.com/MorpheApp/morphe-patches/blob/1bcd0bcedf1238e71b0bd8815da2c10df7ef5bd2/patches/src/main/kotlin/app/morphe/patches/shared/misc/gms/GmsCoreSupportPatch.kt) 更新特定权限、服务、authority、content URI 和目标方法，并用 metadata 向 GmsCore 声明原 Google 包名与签名。
- 部分业务接口仍要求原包名，例如 GNP 注册路径，因此补丁会在该调用处保留原值。这不是全局包名替换，也不是将所有内部 API 的身份固定成原版。
- [资源重命名处理器](https://github.com/MorpheApp/morphe-patcher/blob/5eacde46237f2fe657eb9bfbe90d2528d248a336/src/main/kotlin/app/morphe/patcher/resource/processor/PackageRenamingProcessor.kt) 处理特定资源引用，不会自动修正 DEX 中的进程判断。

YouTube 的 GmsCore 专用逻辑不能直接移植到 REDnote。可借鉴的是按用途明确区分
安装身份、进程判断、组件地址与服务端业务标识，再用方法指纹限定每个修改位置。

## 在上一版成品中确认的遗漏

已读取发布 APK 的 `classes17.dex`，确认 `ddc.a.invoke()` 使用新包名，
`XhsApplication.isMainProcess()` 仍比较旧包名 `com.xingin.xhs`。
后者的结果写入全局主进程标记 `psb.f.j`。
源码中另有 `wcc.i.o()`、`wcc.i.f()`、`wcc.p.e()`、`wcc.q0.i()` 等旧包名判断，
涉及账户和启动任务、Provider proxy、native 库路径初始化。

这是已确认的内部不一致；卡片崩溃的具体原因仍需登录后的崩溃栈来确定。
此次测试保持上一版 APK 不变，不把未验证的启动补丁加入发布包。

资源表检查也确认 `resources.arsc` 的包名仍为 `com.xingin.xhs`，与 Manifest 新包名
不同。AOSP 的动态资源查找按资源包名匹配，使用 `Context.getPackageName()` 作为
查找包名的部分调用可能取不到 ID。已找到的商店 Tab 动效、播客错误视图和评论图标
路径有跳过或固定 ID 的降级处理，尚不足以把全局首页/卡片故障归因于资源表。
目标 Android 运行时的动态查找结果也尚未实测。

若实验性地设置 `application android:process="com.xingin.xhs"`，可让主进程名保持
原字符串，但必须同时恢复 `ddc` 中的旧进程名比较。该办法只保留进程名，
不会恢复原包的 UID、数据目录、权限、Provider 或 PackageManager 身份。
参考 [Android process 属性](https://developer.android.com/guide/topics/manifest/application-element#proc)。
