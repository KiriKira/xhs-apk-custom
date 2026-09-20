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
