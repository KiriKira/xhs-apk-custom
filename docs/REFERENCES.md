# References

## Foldable behavior

- OneLab XHS fold hook:
  https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldVideoHook.java
- OneLab fold layout policy:
  https://github.com/pigerzhu/OneLab/blob/main/app/src/main/java/io/github/pigerzhu/onelab/hook/applications/XhsFoldLayoutPolicy.java

## Patch / protection references

- Piko:
  https://github.com/crimera/piko
- Local Piko fork used during investigation:
  https://github.com/KiriKira/piko-custom
- Morphe Reddit signature spoof:
  https://github.com/MorpheApp/morphe-patches/blob/main/extensions/reddit/src/main/java/app/morphe/extension/reddit/patches/SpoofSignaturePatch.java
- Morphe installer-source spoof:
  https://github.com/MorpheApp/morphe-patches/blob/main/patches/src/main/kotlin/app/morphe/patches/all/misc/installer/ChangeInstallerSource.kt
- Piko Instagram signature-check handling commit:
  https://github.com/KiriKira/piko-custom/commit/76982744b7adcc8cac5470586af9d27bad9a01c6

## Historical XHS CI runs before repository split

- First successful full-rebuild experiment:
  https://github.com/KiriKira/twitter-apk-custom/actions/runs/35408383025
- Minimal-Dex + re-signed control experiment:
  https://github.com/KiriKira/twitter-apk-custom/actions/runs/35429591674
- Signature/integrity diagnostic run:
  https://github.com/KiriKira/twitter-apk-custom/actions/runs/35448633363

These links are preserved only as historical provenance. New XHS work belongs in this repository.
