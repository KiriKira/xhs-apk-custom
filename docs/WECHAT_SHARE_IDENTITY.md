# WeChat share identity experiment

`rednote-v9.48.1-6` is a Pre-release experiment based on the stable 小K书 build
`rednote-v9.48.1-5`. It retains the same installed package
`com.kirikira.rednote.fold`, signing key, Android versionCode `9481803`, versionName
`9.48.1`, launcher icon, ad display patch and package compatibility configuration.

The optional `--wechat-share-official-package` patch changes the declared sender
package to `com.xingin.xhs` only in `MMessageActV2.send` when the target is
`com.tencent.mm` and the request's `_wxapi_command_type` is 2 (`SendMessageToWX`).
The original `_mmessage_appPackage` write and checksum call use that same value.
The source media, AppID, token acquisition, registration, calling UID, callbacks
and non-share requests are retained. `Context.getPackageName()` and Android's
package/signature information are not changed globally.

The hypothesis is that WeChat may query the signature of the package declared in
the request. Testing therefore requires a coinstalled official `com.xingin.xhs`
app whose certificate matches the WeChat AppID registration. Whether WeChat
instead rejects the real caller/token identity is unverified. A successful share
could return its callback to the official app.

The source-method fingerprint, share-only guard, package/checksum ordering and
compiled instructions are checked during building. No successful WeChat share is
claimed by those checks. The production workflow defaults this experiment off
and refuses to publish it as a stable release.

To return to the stable configuration, overlay-install
[the -5 APK](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-5/rednote-fold-custom.apk).
The package, signer and Android versions remain the same. This release does not
run another rollback VM or SMS flow.
