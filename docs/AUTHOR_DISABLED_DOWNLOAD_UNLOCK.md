# Author-disabled download unlock

## Problem

Some REDnote notes show a grey save button. Tapping it reports that the author
has disabled downloads and the media cannot be saved.

## Permission model

The server sends `disable_save` in the note's `media_save_config`. The client
parses it into `com.xingin.entities.MediaSaveConfig.disableSaveMedia`
(`classes12.dex`).

```
.field private disableSaveMedia:Z
    .annotation runtime Lxf/c;
        value = "disable_save"
    .end annotation
.end field
```

Every client-side save/download decision reads that field through the single
getter `MediaSaveConfig.d()Z`. A static scan of the 9.48.1 build finds ten
call sites, all of them permission gates:

- `AsyncImageGalleryController` and the classes18 gallery controllers set the
  image-gallery state from `d()`;
- `h59.u` / `h59.z` (long-press panel and its click lambda) and `p49.s`
  (presenter click) block the note-detail download action;
- `za9.b` (`DownloadController`) and `eb9.a` (`PaidDownload`) block their
  click paths;
- `sxb.b` blocks another download entry point.

`MediaSaveConfig` also has `disableWaterMark` and `disableCoverWeibo`, but
neither controls whether saving is allowed.

## Patch

`rednote_download_unlock_patch.py` replaces the getter body:

```
iget-boolean v0, p0, Lcom/xingin/entities/MediaSaveConfig;->disableSaveMedia:Z
```

with

```
const/4 v0, 0x0
```

The method hash pins the verified 9.48.1 decode, and the patch asserts exactly
one match. The stored field, the Parcel writer/creator, `equals`, `hashCode`,
`toString` and the server payload are untouched. All consumers of `d()` now
take their normal allowed branch, so the existing save button and click paths
behave exactly like an ordinary note.

## Verification

- Unit tests cover the exact replacement, a changed-version rejection, a
  duplicate-method rejection and a second-patch rejection.
- The local compile check assembles `classes12.dex` with APKEditor 1.4.9 and
  confirms the compiled getter is `const/4 v0, 0` followed by `return v0`.
- The release verifier re-runs that compiled-bytecode check on the published
  APK and requires `classes12.dex` in the modified-entry set.
- Device confirmation of an actually author-disabled note is still required;
  no such note was exercised in this repository's automated build.
