# REDnote cold-start splash-ad skip patch

This optional patch builds on the REDnote 9.48.1 / 9481803 `fold-compat` configuration and keeps the existing feed-ad display patch unchanged. Enable it with `--skip-splash-ads`; it is disabled by default in the builder and enabled by default in the release workflow.

## Identified flow

`SplashV2Controller.P1()` (classes19.dex) runs the cold-start decision. After the login gates it waits for the splash-ad result object (`uy.f`, classes4.dex) and dispatches it through `uy.f.a(qe.o, onAd, onNoAd)`:

- `qe.o.c()` true → `onAd(ad)` → the controller preloads the ad, calls `duc.m.w0(ad)` to build the home `IndexView` with the ad attached, then `SplashV2Controller.S1(ad)`.
- `qe.o.c()` false → `onNoAd(0)` → `S1(null)` and `duc.m.x0(..., null, ...)` → `duc.m.w0(null)` builds the home view without an ad.

Static search over the pinned APK finds exactly one caller of `uy.f.a(...)` (`SplashV2Controller`), one ad-injection caller of `duc.m.w0(SplashAd)` (`duc.l`, the result callback), and no other `SplashAd` handoff into the index view. The dispatch therefore covers the native, red, brandmax and dynamic splash formats handled by this controller.

## Change

The patch replaces the single conditional branch in `uy.f.a(...)` with an unconditional jump to the original no-ad block:

```
-    if-eqz v0, :cond_0
+    goto :cond_0
```

Every other instruction, both result callbacks and the surrounding startup logic stay byte-for-byte identical. The ad request, payload download, telemetry and result parsing still run; only the display decision changes.

## Validation

- `test_rednote_splash_ad_patch.py` pins the exact decoded method text (SHA-256 `00b0227c…`) and verifies that a changed version, a duplicate method, or a second patch fails without writing.
- The builder inspects the compiled `classes4.dex`: the `qe.o.c()` call is followed by `move-result` and an unconditional `goto`, no conditional branch remains, both `Function1.invoke` callbacks are retained, and the jump target is the original no-ad marker load (`gz.f`).
- `tools/verify_rednote_release.py` requires `splashAdDisplay.enabled` for the release variant, checks `touchedDexEntry == classes4.dex`, and re-runs the compiled check.

No live server-delivered splash ad was observed in a device test. The claim is limited to the static dispatch path and the compiled instruction layout above.
