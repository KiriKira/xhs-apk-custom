# REDnote release

The REDnote build is independent of the domestic `build_xhs.py` workflow and release.

| | Domestic XHS | REDnote |
| --- | --- | --- |
| Package | `com.xingin.xhs` | `com.kirikira.rednote.fold` |
| Source versionCode | `9334801` | `9540804` (9.54.0) |
| APK asset | `xhs-fold8-custom.apk` | `rednote-fold-custom.apk` |
| Release tag | `v1.0.0` | `rednote-v9.54.0-*` (小K书 icon, ads hidden, splash ad skipped, author-disabled downloads unlocked, package compatibility, WeChat sharing); `rednote-v9.48.1-17` is the previous 9.48.1 line |
| Workflow | `build-xhs.yml` | `build-rednote.yml` |

Both outputs use the repository's existing `ks_pkcs12.keystore`, alias `jhc`. The actual APK signer SHA-256 is `637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4`, independently verified against the domestic v1.0.0 release APK.

## Source and patches

The source is APKPure's REDnote 9.54.0 ARM64 XAPK, not a direct Google Play download:

https://d.apkpure.net/b/XAPK/com.xingin.xhs?versionCode=9540804

Pinned XAPK SHA-256: `bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0`.
All three APK members are verified before merging. Their signing certificate SHA-256 is `dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd`; their verified Google source-stamp certificate is reported separately. This input certificate differs from the domestic source's certificate.

The build carries over the domestic configuration's two layout gates (`isHorizontalFolderDevice()` and `isPad()` return true), early Application signature compatibility helper, and `XINGIN` V1 signer entry name. The helper uses the REDnote source certificate and new package ID. Manifest components are fully qualified, while provider authorities and app-declared custom permissions are isolated for coexistence.

The application explicitly preserves `android:process="com.xingin.xhs"` and the original
`ddc.a` predicate. Other source main-process gates therefore continue to see their expected
label. The actual installed package and PackageManager identity remain `com.kirikira.rednote.fold`;
this is a single repackaged APK. Private component process names still follow the clone prefix.
The resource-table package name is changed to the installed package in its fixed name field;
numeric resource IDs and all bytes outside that field are checked unchanged. This configuration
is the default (`--keep-original-main-process`) and was used in the `-3` fix, for which the account
owner reports no recurrence of the previous card crash so far.

The signature helper changes Java package-signature queries inside the app process; Android still verifies the output APK against the existing repository signing key. No model/manufacturer, installer, region, or native/server attestation patch was added.

Release `rednote-v9.48.1-5` applies the 小K书 launcher icon from `assets/branding/xiaokshu.png`, keeps the discovery-feed ad display patch, and includes the package compatibility fix. The Android package, version metadata, and signer stay the same, so the build remains an in-place update for the existing REDnote clone.

The builder preserves the original DEX/native payloads during split merging. The fold/signature configuration rebuilds `classes17.dex` and `classes4.dex` and adds its helper DEX. `--hide-feed-ads` additionally patches `classes19.dex` and adds a display helper DEX. Manifest and resource-table changes are included in the payload audit. All other merged payload hashes are verified. The release workflow independently inspects the compiled startup hook, helper package/certificate, application process, original main-process predicate, resource package, both layout gates, and the ad-display hook when enabled, then verifies APK signatures and 16 KiB alignment.

The ad-display patch preserves the original card bind and requests, then hides cards marked as ads in the discovery feed. It restores a recycled card's dimensions before rebinding. See [scope and evidence](FEED_AD_DISPLAY_PATCH.md).

The splash-ad skip patch (`--skip-splash-ads`) changes one branch in the cold-start splash result dispatcher `uy.f.a(...)`: the ad callback path is replaced by an unconditional jump to the original no-ad path, so the home view is created without an ad. The request, payload download and telemetry are unchanged. See [scope and evidence](SPLASH_AD_SKIP_PATCH.md).

The author-disabled download patch (`--allow-disabled-downloads`) enables the existing save paths without changing the server payload: `MediaSaveConfig.d()` returns false, the `image_download` function switch reports enabled, and the share sheet's `download_all_image_new` entry reports enabled. Other switches and share entries keep the server flag. See [scope and evidence](AUTHOR_DISABLED_DOWNLOAD_UNLOCK.md).

## Observed login result

[ARM Waydroid test run 37636029064](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37636029064) tested the patched `fold-compat` configuration with package `com.kirikira.rednote.fold`. It reached the SMS verification page, and the account owner confirmed receipt of the SMS. That flow showed no unsafe-environment rejection. Final verification/login was not tested; the account owner requested stopping at this point. These observations apply to this test and do not establish that every device/account will pass final authentication.

[Ad-display test run 37652937937](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37652937937) passed eight actual-Android display/recycling checks and reached the SMS verification page with a newly authorized number. The account owner defined this page as the test endpoint. No OTP was requested or submitted. Release `rednote-v9.48.1-2` imports this exact tested APK, SHA-256 `337dd853737eccfad2ead9e09e5f344ede6d6b028f10d01bb9d9ab188888a84f`.

## Versioning and rollback

Android blocks a lower `versionCode` during ordinary installation. Each REDnote build line keeps the upstream `versionCode`/`versionName` of the base it was ported to (`9540804` / `9.54.0` for the current line); only the Release tags count patch revisions. The package ID and cryptographic signing identity remain identical across lines, so a 9.54.0 build upgrades in place over a 9.48.1 build without an uninstall, and rolling back means reinstalling an official or older REDnote APK with the same package.

- Stable revision with the 小K书 launcher icon, ad-display patch, splash-ad skip, author-disabled download unlock, package compatibility fix and WeChat sharing: `rednote-v9.48.1-9`.
- Previous stable build without the function-switch/share-entry unlock: `rednote-v9.48.1-8`.
- [Return to the fixed build with ads shown](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-3/rednote-fold-custom.apk).

Publishing checks package, versions and signer; a separate rollback VM is no longer a release gate,
as requested by the account owner. The existing domestic and previous REDnote releases and assets
are retained. The historical checks below remain evidence for their specific APKs.

[Release run 37696172646](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37696172646) passed all four installations and data-marker checks on ARM64 Android API 33. The permanent [rollback report](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-2/rollback-check.json) records the exact baseline/candidate hashes, versions and unchanged UID.

## Building and publishing

The [WeChat share identity configuration](WECHAT_SHARE_IDENTITY.md) is included
in stable release `rednote-v9.48.1-6` and enabled by default in production builds.
**微信分享需要同时安装官方国际版 REDnote（Google Play 版），与小K书共存。**
The account owner confirmed successful sharing with that configuration. The
manual `wechat_share_identity` input can disable it; `-5` remains available for
overlay rollback.

Run **Build and Release REDnote Fold Custom** manually. `publish: true` publishes after build validation; `publish: false` only builds. The `prerelease` input defaults to `true` to preserve the prior behavior; set it to `false` to publish a stable release. `hide_feed_ads` controls the discovery-feed display patch, `skip_splash_ads` controls the cold-start splash-ad skip, and publishing requires both to be enabled. Each build uses the pinned XAPK and current package-compatibility configuration. Choose a fresh `rednote-v9.48.1-<revision>` tag. Relevant main-branch changes build without publishing, and `rednote-v*` tag pushes publish as pre-releases.

The workflow publishes the APK, build report and `SHA256SUMS`. It refuses to replace an existing release's assets and always uses `--latest=false` to preserve the domestic release's Latest designation. No rollback VM, phone number, or SMS code is required by the production build or included in release assets.

## 9.54.0 port (versionCode 9540804)

The 9.54.0 port keeps every patch from the 9.48.1 line but had to relocate each anchor,
because obfuscated names and class-to-DEX layout changed between builds:

| Patch | 9.48.1 anchor | 9.54.0 anchor |
| --- | --- | --- |
| Fold layout gates | `DeviceInfoContainer` in `classes4.dex` | same class, now in `classes3.dex` |
| Feed ad display | `FeedCustomMultiTypeAdapter.onBindViewHolder`, item list `B0()` | same method, item list `A0()` |
| Splash ad skip | `uy.f.a(qe.o, …)` | `qz.f.a(we/o, …)`, no-ad marker `Lc00/f;` |
| Author-disabled download | `MediaSaveConfig.d()` | `MediaSaveConfig.b()` |
| Share-panel download | `ShareInfoDetail$Operate.b()` | `ShareInfoDetail$Operate.a()` |
| Image-download switch | `FunctionSwitch.b()` in `classes12.dex` | `FunctionSwitch.a()`, now in `classes13.dex` |
| Keyword-block settings | `SettingActivityV2.onCreate` via `Rd` | same method via `Vd`; binder base `Lha/d;` |
| WeChat share identity | `MMessageActV2.send` in `classes4.dex` | same method in `classes3.dex` (unchanged bytecode) |
| Signature compat hook | `XhsApplication` in `classes17.dex` | same class, now in `classes19.dex` |
| Main-process gate | `ddc/a.invoke()` comparing `ddc/b.b` | process-type enum assignment in an obfuscated helper |

The main-process gate is now located structurally (a method that both compares the
package literal through `Intrinsics` and stores a process-type value) instead of by
class name, and the release verifier asserts that no comparison was rebased onto the
clone package. The fold-layout claim is unchanged: 9.54.0 carries the same
`android_folder_device_list` allow-list and the same device model lists as 9.48.1, so
forcing `isHorizontalFolderDevice()` and `isPad()` remains necessary for
international/Japanese Z Fold8 units (`SM-F971B`/`SM-F976B` are absent from the list
while the mainland `SM-F9710`/`SM-F9760` are present).
