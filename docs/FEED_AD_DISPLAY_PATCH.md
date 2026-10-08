# REDnote discovery-feed ad display patch

This optional experiment builds on the REDnote 9.48.1 / 9481803 `fold-compat` configuration, package `com.kirikira.rednote.fold`, with the same existing keystore. Enable it using `--hide-feed-ads`; it is disabled by default.

## Identified data and UI

The original source DEX maps `NoteItemBean.isAd` to JSON `is_ads`, and `adsInfo` to `ads_info`. `MediaBean` and `NativeMediaBean` copy this ad flag when converting from `NoteItemBean`. Brand content has a separate flag. An `adsInfo` value alone is insufficient to classify a normal note, as media models can initialize an empty AdsInfo object.

Discovery feed uses `FeedCustomMultiTypeAdapter.onBindViewHolder(ViewHolder,int,List)` in `classes19.dex`. Its superclass obtains the bound item from `MultiTypeAdapter.B0().get(position)` and invokes the actual card binder. Dedicated `AdsInfo` cards include `ImageAdsViewBinder`, `NativeVideoAdsViewBinder`, and another registered ad binder. Each holder's `itemView` is the entire card root.

## Change

The patch inserts two display-only hooks around the original superclass bind:

1. Restore the root's previous visibility and height if this helper hid it earlier.
2. Execute the original binding code, including its original presenter/image-loading calls.
3. Inspect the bound item: `NoteItemBean`, `MediaBean`, or `NativeMediaBean` must have `isAd=true`; a dedicated `AdsInfo` item also qualifies. Other item types retain their existing display state.
4. For an ad, set the root to `View.GONE` and set its layout height to zero. Save its original state in a weak map so recycled holders can bind ordinary cards with their correct new dimensions.

The patch retains feed items, response parsing, requests, and the original bind. It does not forge advertisement impressions. Actual visibility-based impression reporting can naturally change when a card is hidden. This experiment covers this discovery/home-feed adapter; search, detail pages, splash screens, and other ad surfaces are outside its scope.

## Layout after hiding

The source feed uses `ExploreStaggeredGridLayoutManager` and `ExploreDoubleRowStaggeredDiverDecoration`
(configured in `qkc.m0`). The layout manager measures an item's zero content height and places
later cards according to the remaining span heights. Hiding therefore collapses the original
card-sized area and later cards move up; it does not reserve the original card rectangle.

The adapter item remains in the data list. RecyclerView still measures its item-decoration insets
and margins even when the root is `GONE`, so a small grid separator can remain. Phone layouts use
a 5 dp divider; the usual ad root decoration has integer half-divider offsets above and below
(about 4 dp total), with the bottom offset increasing near the list end (about 7 dp total).
Pad layouts use an 8 dp divider. The exact residual offset depends on position and root type. The inspected ad
binders do not mark the roots full-span or set extra root margins.

These layout details follow the original APK's layout-manager, decoration and binder code.
The prior actual-Android helper checks below cover visibility, height and holder restoration;
they did not measure a live server-delivered advertisement in the full feed.

## Validation

`test_rednote_ad_patch.py` uses the original pinned bind method as a fixture. It verifies that all original code is retained, the bind is executed once between the two hooks, and a changed or duplicated method fails without partially applying the patch. The builder also inspects compiled `classes19.dex` for restore/bind/hide ordering and all four item predicates; all other merged payloads are audited.

The ARM Waydroid workflow's `fold-compat-hide-ads` variant loads the helper from the actual output APK and tests ad visibility/height, repeated hiding, holder restoration, ordinary cards that were already hidden, null layout parameters, and null views. A separate once-only phone flow ends at the SMS-code page; no OTP input is requested or submitted. A helper smoke test verifies the display state but does not itself establish that a live server-delivered ad was observed and hidden.

## 2026-10-08 test result (JST)

[Run 37652937937](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37652937937), source commit `6d80052227eb46d793dac9c091e318ee831cc3fd`, completed successfully on native ARM Waydroid. All eight actual-Android display checks passed. The patched APK installed, its signature compatibility helper was active, and one authorized +86 number was submitted. The limited report has `phone_entered=true`, `get_code_clicked=true`, `result_category=otp_screen`, `otp_input_visible=true`, `timeout=false`, and final `stage=complete`. The flow showed no unsafe-environment rejection. No OTP input was requested or submitted; SMS receipt and final authentication are not claimed.

[Tested APK artifact](https://github.com/KiriKira/xhs-apk-custom/actions/runs/37652937937/artifacts/11497292622) (one-day retention): APK SHA-256 `337dd853737eccfad2ead9e09e5f344ede6d6b028f10d01bb9d9ab188888a84f`.

The same APK is published permanently as [rednote-v9.48.1-2](https://github.com/KiriKira/xhs-apk-custom/releases/tag/rednote-v9.48.1-2). Its Android versionCode and versionName remain unchanged from [rednote-v9.48.1-1](https://github.com/KiriKira/xhs-apk-custom/releases/tag/rednote-v9.48.1-1), so the previous APK is a direct overlay rollback. See [versioning and rollback](REDNOTE_RELEASE.md#versioning-and-rollback).

The local rebuild also passed signature/alignment/payload/compiled-hook checks, with APK SHA-256 `2c08f3c2df5dbc3e49ecf662fd9ac81e38068dd131762dcfa12d499c38dbe60c`. ZIP bytes differ from the hosted build; it is a rebuild of the same source and patch configuration, not the exact APK installed by the hosted test. Both use package `com.kirikira.rednote.fold` and signer SHA-256 `637c226c67aec0cdbc6f49cd476d5247f999122606286273e16233a913a088b4`.
