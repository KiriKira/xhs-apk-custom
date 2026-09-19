# Signature / integrity protection notes

This file records relevant implementation patterns found while investigating why a re-signed XHS control APK crashes at startup.

Nothing in this document should be read as evidence that XHS uses a particular mechanism until it is observed in the target APK.

## Morphe: Reddit signature spoof

Morphe's Reddit patch contains a useful general pattern for applications that query their own certificate through Android's Java package APIs.

Reference:
https://github.com/MorpheApp/morphe-patches/blob/main/extensions/reddit/src/main/java/app/morphe/extension/reddit/patches/SpoofSignaturePatch.java

The implementation replaces values exposed through `PackageInfo`:

- legacy `PackageInfo.signatures`;
- Android 9+ `SigningInfo.getApkContentsSigners()`.

It does this early in application startup by replacing `PackageInfo.CREATOR`, then clears PackageManager/Parcel caches so later queries observe the substituted certificate.

Important limitation: this does **not** change the certificate Android itself used to install the APK. It only affects compatible in-process Java queries.

Therefore it is useful as a diagnostic test: if a Java-level spoof makes a re-signed control launch, the protection path can be narrowed substantially.

## Morphe: installer-source spoof

Morphe also has a generic `Change installer source` patch that makes an app appear to come from a selected store such as Google Play, Galaxy Store, or Xiaomi GetApps.

Reference:
https://github.com/MorpheApp/morphe-patches/blob/main/patches/src/main/kotlin/app/morphe/patches/all/misc/installer/ChangeInstallerSource.kt

Installer-source spoofing should be tested independently from certificate spoofing so the cause remains identifiable.

## Piko / X protected APK experience

Piko documents that newer protected X APKs historically needed a ripped APK or a compatibility shim. Its compatibility check looks for a protected application startup shape rather than pretending the problem is a generic signing comparison.

Current Piko README:
https://github.com/crimera/piko

This is relevant as an engineering lesson: a successful Android APK signature verification does not imply the application will accept a modified or re-signed package.

## Piko Instagram signature-related patch

Piko also contains a targeted Instagram change described as handling a signature check when sharing/opening links.

Commit:
https://github.com/KiriKira/piko-custom/commit/76982744b7adcc8cac5470586af9d27bad9a01c6

That patch is very specific to Instagram's URI trust logic and should not be copied blindly into XHS. Its useful lesson is to locate the actual check and patch the narrow decision point when possible.

## XHS test strategy

Because the re-signed control already crashes, the recommended order is:

1. reproduce with control;
2. identify whether startup reaches Java application code;
3. test Java package-signature spoof only;
4. test installer-source spoof separately;
5. inspect native checks if Java spoof does not help;
6. reintroduce `isHorizontalFolderDevice()` only after the clean control launches.

This keeps each experiment attributable and avoids hiding the real failure behind multiple simultaneous bypasses.
