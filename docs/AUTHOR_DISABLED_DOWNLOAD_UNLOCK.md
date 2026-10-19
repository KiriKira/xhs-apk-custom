# Author-disabled download unlock

## Problem

Some REDnote notes show a grey save button. Tapping it reports that the author
has disabled downloads and the media cannot be saved. The message is not a
client string: it comes from the server's `disableToast` for the share entry.

Two separate server models gate saving:

1. `com.xingin.entities.MediaSaveConfig.disableSaveMedia` (serialized
   `disable_save`) in `classes12.dex`, read through the single getter
   `MediaSaveConfig.d()Z`. This flag drives the note-detail/image-gallery save
   state and the paid-download click gates.
2. `com.xingin.entities.ShareInfoDetail$Operate.disable` and `disableToast` in
   `classes12.dex`. The share sheet's save entry has type
   `download_all_image_new`; `ShareUserView` renders it at 50% alpha when
   `Operate.b()Z` is true and the click handler shows `disableToast` instead of
   saving.

## Patch

`rednote_download_unlock_patch.py` replaces the `MediaSaveConfig` getter body:

```
iget-boolean v0, p0, Lcom/xingin/entities/MediaSaveConfig;->disableSaveMedia:Z
```

with

```
const/4 v0, 0x0
```

`rednote_share_download_unlock_patch.py` replaces the share-entry getter with a
type check:

```
iget-object v0, ...->type
const-string v1, "download_all_image_new"
invoke-virtual {v1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
...
if-eqz v0, :cond_0
const/4 v0, 0x0
return v0
:cond_0
iget-boolean v0, ...->disable
return v0
```

Only the image-download share entry reports enabled; every other share action
keeps the server's disable value. The stored fields, Parcel representation,
`disableToast`, `equals`, `hashCode`, `toString` and the server payload are
untouched. Both patches pin the verified 9.48.1 method hash and assert exactly
one match.

## Verification

- Unit tests cover the exact replacements, changed-version rejection,
  duplicate-method rejection and second-patch rejection.
- A local compile check assembles `classes12.dex` with APKEditor 1.4.9 and
  confirms `MediaSaveConfig.d()` is `const/4 v0, 0` + `return v0` and that the
  share getter keeps the `download_all_image_new` check, the false return and
  the original `disable` fallback.
- The release verifier re-runs both compiled-bytecode checks on the published
  APK and requires `classes12.dex` in the modified-entry set.
- Device confirmation on an actually author-disabled note is still required;
  no such note was exercised in this repository's automated build.
