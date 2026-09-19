# Investigation log

## Scope

Target package: `com.xingin.xhs`.

The original issue is that XHS presents a different home layout on a mainland-China Galaxy Z Fold8 than on an international/Japanese Fold8. The mainland device exposes the denser foldable layout and supports pinch-based layout adjustment.

This document records what has actually been tested. Hypotheses are kept separate from confirmed observations.

## 1. Foldable-layout lead

The OneLab project contains an XHS foldable hook. For the home-feed option it hooks:

`com.xingin.adaptation.device.DeviceInfoContainer.isHorizontalFolderDevice()`

and forces the result to `true`.

OneLab separately treats video-detail layout as a different set of gates, including `isPad()` and several `DetailFeedAbTestHelper` methods.

This is strong evidence that XHS already contains a built-in foldable path and that `isHorizontalFolderDevice()` participates in selecting it. It does **not** by itself prove how the official mainland build decides that the physical device qualifies.

## 2. First static patch

The first CI implementation:

1. downloaded the base APK;
2. decoded it with APKEditor;
3. found `DeviceInfoContainer.smali`;
4. replaced `isHorizontalFolderDevice()Z` with an unconditional `true`;
5. rebuilt and re-signed the APK.

CI confirmed the target method was found in `classes15.dex` and patched.

The resulting APK installed but crashed immediately at launch.

Historical successful build:
https://github.com/KiriKira/twitter-apk-custom/actions/runs/35408383025

## 3. Minimal-DEX experiment

Because the first build reconstructed the entire APK, the build was changed so APKEditor was used only to rebuild the touched DEX. The output APK otherwise kept the original manifest, resources, native libraries, assets, and untouched DEX files.

A second output was added:

`xhs-resigned-control.apk`

This control did **not** contain the foldable code modification. It used the original APK payload with the old signing metadata removed and was signed with the experimental key.

Historical build:
https://github.com/KiriKira/twitter-apk-custom/actions/runs/35429591674

## 4. Confirmed result: re-signing alone is enough to reproduce the crash

The re-signed control APK also crashes immediately on launch.

This is the most important result so far.

It means:

- the `isHorizontalFolderDevice()` modification is **not required** to reproduce the crash;
- full APK resource rebuilding is **not required** to reproduce the crash;
- investigation should focus first on behavior that changes when the APK signing identity changes.

This does **not** yet prove which protection mechanism is responsible. Possible categories include Java-side package-signature checks, installer/source checks, native certificate/integrity checks, APK/Dex hashing, or a protection framework.

## 5. Diagnostics prepared

The last diagnostic workflow in the old repository searched the decoded APK for references to:

- `PackageManager` / `getPackageInfo`;
- `GET_SIGNATURES` / `GET_SIGNING_CERTIFICATES`;
- `SigningInfo` / `getApkContentsSigners`;
- `hasSigningCertificate`;
- signature/certificate/integrity/tamper/installer strings;
- native `.so` candidates.

Historical diagnostic run:
https://github.com/KiriKira/twitter-apk-custom/actions/runs/35448633363

No bypass should be added until the exact failure path is narrowed down further.

## Next investigation stage

The next stage should be controlled A/B testing, not additional foldable-layout changes.

Candidate experiments:

1. Java-level signature spoof while leaving the foldable code untouched.
2. Installer-source spoof as a separate variable.
3. Capture Java crash information where possible.
4. If Java spoofing does not change behavior, inspect native libraries and early startup paths for certificate/integrity checks.
5. Only after a clean re-signed control can launch should the foldable gate patch be reintroduced.

## Base APK recorded in CI

- package: `com.xingin.xhs`
- versionCode from download URL: `9334801`
- SHA-256: `04ee354d9e76ada81eb27283a1c8998c06892e8e6f22c117320046e2acb49411`
