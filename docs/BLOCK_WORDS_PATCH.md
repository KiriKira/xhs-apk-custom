# REDnote keyword blocking and the 小K书设置 page

Optional patch (`--block-words`) for the REDnote 9.48.1 / 9481803 `fold-compat` build. It adds a
manual blocklist for discovery-feed cards and a settings entry that edits that list.

## Why

`--hide-feed-ads` hides cards the server marks as ads (`is_ads` / a dedicated `AdsInfo` item). Cards
that promote something without that mark look the same as ordinary notes. The blocklist hides a card
when its visible text matches a word the user typed, so untagged promotional content can be removed
without a model or request change.

## Settings entry

`SettingActivityV2.onCreate` is patched with one call to
`Ldev/kiri/xhsads/SettingsHook;->install(Landroid/app/Activity;)V`, and
`SettingActivityV2.onWindowFocusChanged(Z)` with
`SettingsHook.ensure(Landroid/app/Activity;)V` so the row comes back after returning from the keyword
page or after the settings list is rebuilt. After the next layout the helper:

1. walks the activity view tree to the settings `RecyclerView` and takes its adapter when the adapter
   class is `com.drakeet.multitype.MultiTypeAdapter`;
2. registers `Ldev/kiri/xhsads/BlockBinder;` for a private `dev.kiri.xhsads.BlockEntry` item. The
   adapter's register/read/set methods are obfuscated in this build, so each one is located by
   signature (`(Class, binderSubtype)V`, `()List`, `(List)V`) instead of by name;
3. inserts the item immediately after the settings row whose title equals `关于小红书`
   (`setting_about`); when the list is still empty or the title is not there yet it retries up to
   eight times, 250 ms apart, before falling back to the last row;
4. writes the new list back with the adapter's own setter (which only swaps the backing list) and then
   calls `notifyDataSetChanged()`; a repeat run inside the same activity is idempotent because the item
   is detected by class.

Every step is wrapped in `try/catch (Throwable)`. If any assumption fails, the settings page opens
unchanged instead of crashing, and the keyword filter (which lives on its own path) is unaffected.

The row renders `小K书设置` with a subtitle showing the current keyword count; tapping it opens
`dev.kiri.xhsads.BlockWordsActivity`, declared by the builder as `android:exported="false"` with the
platform `Theme.Material.Light.DarkActionBar` theme. The page has one multi-line field (one word per
line, and `,`/`，`/`、`/`;` are also accepted), plus 清空 and 保存.

## Storage

`SharedPreferences` `kiri_xhs_block_words`, key `words` (single string). Parsing trims each entry,
drops empties and de-duplicates.

## Filtering

The keyword filter reuses the display hook installed by `--hide-feed-ads`. The inserted code runs after
the original bind and calls `Ldev/kiri/xhsads/FeedKeywordFilter;->matches(Landroid/view/View;)Z`; the
result is OR-ed with the ad flag before `FeedAdDisplay.apply`, so a keyword hit gets the same
`View.GONE` + zero-height state, and recycling restores the original visibility/height.

Matching operates on the text of the card's own `TextView`s, so it needs no obfuscated entity field
and behaves the same for every card type. Text is lower-cased for comparison; strings that look like
counters (digits plus `万/w/k/m/+`, e.g. `1.2万`) are ignored so numeric keywords do not match like
counts. Author names and the card body that the feed actually renders are included.

## Scope and limits

- Only cards bound by `FeedCustomMultiTypeAdapter` (discovery/home feed) are filtered. Search results,
  detail pages, messages and the follow feed are unchanged.
- Requests and payloads are untouched; no impression is forged and no server flag is rewritten.
- The settings row is a private item type, so it has no native settings action id and no server-side
  switch; it exists only in this build.
- The row is inserted at runtime, so it appears with the settings page and disappears with it; the
  values persist in `SharedPreferences` across restarts.

## Validation

`test_rednote_block_words_patch.py` covers the pinned `SettingActivityV2.onCreate` fixture (hook added
after the original body, changed input rejected without a partial write, duplicate method rejected),
the keyword hook insertion into the ad-display hook (order and single insertion), the manifest activity
declaration, and the constraint that the Java helper sources use only `android.jar` APIs (the binder
must therefore live in smali).

`build_rednote.py` additionally re-parses the produced APK: `classes19.dex` must contain the keyword
call before the display apply, and `classes15.dex` must contain `SettingsHook.install` inside
`onCreate` plus the two helper classes with the verified binder base. `tools/verify_rednote_release.py`
gates a release on `--expect-block-words`, the report's `keywordBlocking` section and the helper DEX
hash.

Live behavior in the feed and the settings row were not observed on a device as part of this patch;
the checks above are static plus helper-level.

## On-device diagnostics

The filter reports what it actually did, so a device report can be judged without logcat access:

- `BlockSettings.record()` shows a Toast for the first three bound cards of each process (`小K书诊断 #1：词 1 个`) and for the first three hits, then stays quiet.
- The `小K书设置` page prints `已保存 N 个屏蔽词`, `已检查卡片 X 张，命中 Y 张`, and the last card's visible text (first 300 characters).
- The card text is the card's own `TextView` text plus the `String` fields of the bound adapter item plus the root's content description; separators (space, `-`, `_`, `/`, `·`, ideographic space) are ignored on both sides of the comparison, and like/view counters such as `1.2万` never take part.

Zero checked cards means the bind hook never ran for that feed pipeline (see
`FEED_AD_DISPLAY_PATCH.md`: two feed implementations exist in 9.48.1), not that the keyword list is
empty; a non-zero count with no hit and a sample text that lacks the keyword means the text is not on
the card.

The page also saves on `onPause`, so a typed list is persisted even when `保存` is not tapped.
