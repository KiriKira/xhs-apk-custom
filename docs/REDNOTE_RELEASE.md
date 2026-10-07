# REDnote release

The REDnote build is independent of the domestic `build_xhs.py` workflow and release.

| | Domestic XHS | REDnote |
| --- | --- | --- |
| Package | `com.xingin.xhs` | `com.kirikira.rednote.fold` |
| Source versionCode | `9334801` | `9481803` (9.48.1) |
| APK asset | `xhs-fold8-custom.apk` | `rednote-fold-custom.apk` |
| Release tag | `v1.0.0` | `rednote-v9.48.1-2` (ads hidden); `rednote-v9.48.1-1` (rollback) |
| Workflow | `build-xhs.yml` | `build-rednote.yml` |

Both outputs use the repository's existing `ks_pkcs12.keystore`, alias `jhc`. The actual APK signer SHA-256 is `637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4`, independently verified against the domestic v1.0.0 release APK.

## Source and patches

The source is APKPure's REDnote 9.48.1 ARM64 XAPK, not a direct Google Play download:

https://d.apkpure.net/b/XAPK/com.xingin.xhs?versionCode=9481803&nc=arm64-v8a&sv=21

Pinned XAPK SHA-256: `bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0`.
All three APK members are verified before merging. Their signing certificate SHA-256 is `dbf2ddfe68dc6c3d7bdbd1c70aae13993f50fa99b51d6f0c668a284ee9e6fdcd`; their verified Google source-stamp certificate is reported separately. This input certificate differs from the domestic source's certificate.

The build carries over the domestic configuration's two layout gates (`isHorizontalFolderDevice()` and `isPad()` return true), early Application signature compatibility helper, and `XINGIN` V1 signer entry name. The helper uses the REDnote source certificate and new package ID. The new package also requires adapting the hard-coded main-process predicate in `ddc.a.invoke()`, fully qualifying manifest components, and isolating provider authorities and app-declared custom permissions for coexistence.

The signature helper changes Java package-signature queries inside the app process; Android still verifies the output APK against the existing repository signing key. No model/manufacturer, installer, region, or native/server attestation patch was added.

The builder preserves the original DEX/native payloads during split merging. The fold/signature configuration rebuilds `classes17.dex` and `classes4.dex` and adds its helper DEX. `--hide-feed-ads` additionally patches `classes19.dex` and adds a display helper DEX. All other merged payload hashes are verified. The release workflow independently inspects the compiled startup hook, helper package/certificate, main-process predicate, both layout gates, and the ad-display hook when enabled, then verifies APK signatures and 16 KiB alignment.

The ad-display patch preserves the original card bind and requests, then hides cards marked as ads in the discovery feed. It restores a recycled card's dimensions before rebinding. See [scope and evidence](FEED_AD_DISPLAY_PATCH.md).

## Observed login result

[ARM Waydroid test run 37636029064](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37636029064) tested the patched `fold-compat` configuration with package `com.kirikira.rednote.fold`. It reached the SMS verification page, and the account owner confirmed receipt of the SMS. That flow showed no unsafe-environment rejection. Final verification/login was not tested; the account owner requested stopping at this point. These observations apply to this test and do not establish that every device/account will pass final authentication.

[Ad-display test run 37652937937](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37652937937) passed eight actual-Android display/recycling checks and reached the SMS verification page with a newly authorized number. The account owner defined this page as the test endpoint. No OTP was requested or submitted. Release `rednote-v9.48.1-2` imports this exact tested APK, SHA-256 `337dd853737eccfad2ead9e09e5f344ede6d6b028f10d01bb9d9ab188888a84f`.

## Versioning and rollback

Android blocks a lower `versionCode` during ordinary installation. Both REDnote revisions deliberately keep `versionCode=9481803` and `versionName=9.48.1`; only the Release tags count patch revisions. The package ID and cryptographic signing identity also remain identical. This allows direct replacement in either direction instead of uninstalling the app.

- [Install the ad-display patch](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-2/rednote-fold-custom.apk).
- [Install the previous behavior to roll back](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-1/rednote-fold-custom.apk).

The publishing workflow installs the previous APK, places a synthetic marker in its empty test app data, then installs the ad APK, the previous APK, and the ad APK again with `adb install -r`. Every replacement must succeed with unchanged package versions/signers and the marker retained. This test uses an empty VM and never reads a real account's data or sends SMS. The existing domestic and previous REDnote releases and their assets are retained.

[Release run 37696172646](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37696172646) passed all four installations and data-marker checks on ARM64 Android API 33. The permanent [rollback report](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-2/rollback-check.json) records the exact baseline/candidate hashes, versions and unchanged UID.

## Building and publishing

Run **Build and Release REDnote Fold Custom** manually. `publish: true` creates a new REDnote release after validation and the overlay/rollback check; `publish: false` only builds. `hide_feed_ads` controls the optional display patch. `source_test_run` imports the pinned, successful ad-display test artifact from run `37652937937` rather than rebuilding it. For this pinned source, choose a fresh `rednote-v9.48.1-<revision>` tag. Relevant main-branch changes build without publishing, and `rednote-v*` tag pushes publish.

The workflow publishes the APK, build report, `rollback-check.json` and `SHA256SUMS`. Imported test builds also attach the limited SMS-screen result and ad-display smoke evidence. It refuses to replace an existing release's assets and uses `--latest=false` to preserve the domestic release's Latest designation. No phone number or SMS code is needed by the production build or included in release assets.
