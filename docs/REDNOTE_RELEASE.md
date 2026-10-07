# REDnote release

The REDnote build is independent of the domestic `build_xhs.py` workflow and release.

| | Domestic XHS | REDnote |
| --- | --- | --- |
| Package | `com.xingin.xhs` | `com.kirikira.rednote.fold` |
| Source versionCode | `9334801` | `9481803` (9.48.1) |
| APK asset | `xhs-fold8-custom.apk` | `rednote-fold-custom.apk` |
| Release tag | `v1.0.0` | `rednote-v9.48.1-1` |
| Workflow | `build-xhs.yml` | `build-rednote.yml` |

Both outputs use the repository's existing `ks_pkcs12.keystore`, alias `jhc`. The actual APK signer SHA-256 is `637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4`, independently verified against the domestic v1.0.0 release APK.

## Source and patches

The source is APKPure's REDnote 9.48.1 ARM64 XAPK, not a direct Google Play download:

https://d.apkpure.net/b/XAPK/com.xingin.xhs?versionCode=9481803&nc=arm64-v8a&sv=21

Pinned XAPK SHA-256: `bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0`.
All three APK members are verified before merging. Their signing certificate SHA-256 is `dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd`; their verified Google source-stamp certificate is reported separately. This input certificate differs from the domestic source's certificate.

The build carries over the domestic configuration's two layout gates (`isHorizontalFolderDevice()` and `isPad()` return true), early Application signature compatibility helper, and `XINGIN` V1 signer entry name. The helper uses the REDnote source certificate and new package ID. The new package also requires adapting the hard-coded main-process predicate in `ddc.a.invoke()`, fully qualifying manifest components, and isolating provider authorities and app-declared custom permissions for coexistence.

The signature helper changes Java package-signature queries inside the app process; Android still verifies the output APK against the existing repository signing key. No model/manufacturer, installer, region, or native/server attestation patch was added.

The builder preserves the original DEX/native payloads during split merging. It rebuilds only `classes17.dex` and `classes4.dex`, adds the helper DEX, and verifies all other merged payload hashes. The release workflow independently inspects the compiled startup hook, helper package/certificate, main-process predicate and both layout gates, then verifies APK signatures and 16 KiB alignment.

## Observed login result

[ARM Waydroid test run 37636029064](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37636029064) tested the patched `fold-compat` configuration with package `com.kirikira.rednote.fold`. It reached the SMS verification page, and the account owner confirmed receipt of the SMS. That flow showed no unsafe-environment rejection. Final verification/login was not tested; the account owner requested stopping at this point. These observations apply to this test and do not establish that every device/account will pass final authentication.

## Building and publishing

Run **Build and Release REDnote Fold Custom** manually. `publish: true` creates a new REDnote release after the build passes; `publish: false` only builds. Choose a fresh `rednote-v<major>.<minor>.<patch>-<build>` tag for a subsequent release. Relevant main-branch changes build without publishing, and `rednote-v*` tag pushes publish.

The workflow publishes the APK, build report and `SHA256SUMS`. It refuses to replace an existing release's assets and uses `--latest=false` to preserve the domestic release's Latest designation. No phone number or SMS code is needed by the production build or included in release assets.
