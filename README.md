# xhs-apk-custom

Experimental Xiaohongshu (小红书) Android patching workspace focused on foldable-device layout behavior.

This repository was split out of `KiriKira/twitter-apk-custom` so XHS reverse-engineering, build history, signing, and CI stay independent from the Twitter/Piko project.

## Goal

The original target is the China XHS package `com.xingin.xhs` on a Galaxy Z Fold8 sold outside mainland China. The observed mainland-device build exposes a denser foldable home layout (including four-column behavior) while the international device does not.

OneLab provides the strongest current lead: its XHS foldable hook forces
`com.xingin.adaptation.device.DeviceInfoContainer.isHorizontalFolderDevice()`
to return true for the home-feed foldable path. Optional video-layout hooks also force `isPad()` and several DetailFeed feature gates.

## Current state

**Do not treat the current APK outputs as working releases.**

The important finding so far is that a **re-signed control APK also crashes at launch**, even when the foldable method is not patched. That means the foldable patch is not required to reproduce the crash. The remaining blocker is likely related to XHS signature / integrity / installer-origin protection, but the exact check has not yet been identified.

See [docs/INVESTIGATION.md](docs/INVESTIGATION.md) for the experiment history and [docs/SIGNATURE_PROTECTION.md](docs/SIGNATURE_PROTECTION.md) for candidate protection mechanisms and reference implementations.

## Current base APK

- Package: `com.xingin.xhs`
- Version code supplied by the Coolapk URL: `9334801`
- Base APK SHA-256 observed in CI: `04ee354d9e76ada81eb27283a1c8998c06892e8e6f22c117320046e2acb49411`

The direct download URL is kept in the workflow input/default for reproducibility.

## Build layout

- `xhs_build_ci.py` — current experimental patch/build script.
- `download_bins.py` — downloads APKEditor.
- `.github/workflows/build-xhs.yml` — manual CI entry point.
- `docs/` — investigation notes and references.
- `ks_pkcs12.keystore` — persistent **test signing key**, migrated from the previous builder so future experimental APKs keep the same signing identity.

The committed key is intentionally only a test key. Because this repository is public, it must not be treated as a secret or used for security-sensitive distribution.

## CI

The workflow is manual-only for now. This is intentional: current builds are diagnostic experiments and should not run automatically on every commit.

It currently produces:

- `xhs-fold8-custom-minimal.apk` — replaces only the touched DEX after patching.
- `xhs-resigned-control.apk` — no foldable code change; official payload is re-signed with the persistent test key.

The control APK is currently known to crash on launch.

## References

- OneLab XHS fold hook: https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldVideoHook.java
- OneLab fold layout policy: https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldLayoutPolicy.java
- Morphe Reddit signature spoof reference: https://github.com/MorpheApp/morphe-patches/blob/main/extensions/reddit/src/main/java/app/morphe/extension/reddit/patches/SpoofSignaturePatch.java
