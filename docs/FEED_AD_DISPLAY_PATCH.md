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

The patch retains feed items, response parsing, requests, and the original bind. It does not forge advertisement impressions. Actual visibility-based impression reporting can naturally change when a card is hidden. This experiment covers this discovery/home-feed adapter; search, detail pages, splash screens, and other ad surfaces are outside its scope. Item decorations may still leave some spacing between collapsed cards.

## Validation

`test_rednote_ad_patch.py` uses the original pinned bind method as a fixture. It verifies that all original code is retained, the bind is executed once between the two hooks, and a changed or duplicated method fails without partially applying the patch. The builder also inspects compiled `classes19.dex` for restore/bind/hide ordering and all four item predicates; all other merged payloads are audited.

The ARM Waydroid workflow's `fold-compat-hide-ads` variant loads the helper from the actual output APK and tests ad visibility/height, repeated hiding, holder restoration, ordinary cards that were already hidden, null layout parameters, and null views. A separate once-only phone flow ends at the SMS-code page; no OTP input is requested or submitted. A helper smoke test verifies the display state but does not itself establish that a live server-delivered ad was observed and hidden.
