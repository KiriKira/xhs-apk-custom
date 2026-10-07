# xhs-apk-custom

Custom Xiaohongshu (小红书) Android build for foldable-device layout behavior.

The active build now targets one device-tested configuration only.

## Current release configuration

Package: `com.xingin.xhs`

Base APK:

- versionCode from the source URL: `9334801`
- base SHA-256: `04ee354d9e76ada81eb27283a1c8998c06892e8e6f22c117320046e2acb49411`

The production APK applies:

- Java `PackageInfo` / `SigningInfo` signature spoof using the official XHS signing certificate;
- v1 signer entry name `XINGIN`;
- `DeviceInfoContainer.isHorizontalFolderDevice() -> true`;
- `DeviceInfoContainer.isPad() -> true`.

This is the configuration that passed device testing for startup/login and the desired foldable layout behavior.

No `Build.MODEL`, `Build.MANUFACTURER`, or region spoofing is used.

## Output

The only production artifact is:

`xhs-fold8-custom.apk`

Latest stable release: https://github.com/KiriKira/xhs-apk-custom/releases/tag/v1.0.0

`.github/workflows/build-xhs.yml` builds and verifies that APK on relevant `main` changes or manual dispatch.

The persistent test signing key is kept in `ks_pkcs12.keystore` so future custom builds retain the same signing identity. It is a public test key and must not be treated as a secret.

## Implementation

- `build_xhs.py` — production builder.
- `signature_spoof_experiment.py` / `xhs_build_ci.py` — shared implementation and historical investigation helpers.
- `docs/INVESTIGATION.md` — experiment history.
- `docs/SIGNATURE_PROTECTION.md` — signature/integrity notes.
- `docs/REFERENCES.md` — source references.

## REDnote diagnostic build

`build_rednote.py` is an independent builder for a locally supplied APK or complete
XAPK set. It verifies the expected input SHA-256 and APK member signatures, merges
XAPK splits when needed, changes the applicationId for a separate install, and
optionally applies the two existing layout gates. It does not inject the production
signature-spoof helper. Original production builds remain on `build_xhs.py`.

The downloaded diagnostic input is APKPure REDnote 9.48.1 / 9481803, ARM64. Google
Play also uses `com.xingin.xhs`; a matching package name alone does not establish
that two distribution channels deliver identical files. See
[the investigation](docs/REDNOTE_INVESTIGATION.md) and
[runtime prerequisites and test matrix](docs/REDNOTE_RUNTIME.md). Hosted API 35
KVM tests installed all three variants and reached the privacy screen without a
crash during a 20-second observation. Deeper x86 previews encountered native
crashes before the phone form; native ARM64 Waydroid testing is ongoing. No phone
number, SMS request, OTP submission or login has been tested yet. See the
[runtime evidence](docs/ANDROID_VM_TEST.md) for the limits of these results.

With Java 21, APKEditor in `bins/apkeditor.jar`, Python 3.10+, and Android build-tools
(`aapt2`, `zipalign`, `apksigner`) available, build the diagnostic layout variant:

```sh
export KEYSTORE_PASSWORD=123456789 # Repository's public test key only.
python build_rednote.py \
  --input /path/to/rednote-9.48.1-9481803-arm64.xapk \
  --sha256 bbc6e888f0084336418ea07e05bda4723d8b01a36879fe054d050deec0a5c8b0 \
  --source https://apkpure.net/rednote-app/com.xingin.xhs/download \
  --application-id com.kirikira.rednote.fold \
  --fold-layout \
  --output output_apks/rednote-9.48.1-fold-custom.apk \
  --report output_apks/rednote-9.48.1-fold-build-report.json
```

Omit `--fold-layout` to create the renamed control. Use the SHA-256 of your actual
input when testing another file. The JSON report records member certificates,
merge provenance, manifest changes, touched DEX files, output signature and
payload hash verification. A successful build verifies packaging; device startup,
layout and login remain separate checks.

## Key findings

A plain re-signed control APK crashed at startup. A Java-level `PackageInfo` / `SigningInfo` signature spoof made the re-signed app launch, and the tested `XINGIN` signer-name variant also supported login.

The final layout build additionally forces both the horizontal-fold and Pad gates.

## References

- OneLab XHS fold hook:
  https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldVideoHook.java
- OneLab fold layout policy:
  https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldLayoutPolicy.java
- Morphe Reddit signature spoof reference:
  https://github.com/MorpheApp/morphe-patches/blob/main/extensions/reddit/src/main/java/app/morphe/extension/reddit/patches/SpoofSignaturePatch.java
