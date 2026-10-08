# WeChat share identity compatibility

`rednote-v9.48.1-6` was promoted to a stable release after the account owner
confirmed successful WeChat sharing with the official international REDnote
installed alongside 小K书. It builds on `rednote-v9.48.1-5` and retains the same installed package
`com.kirikira.rednote.fold`, signing key, Android versionCode `9481803`, versionName
`9.48.1`, launcher icon, ad display patch and package compatibility configuration.

The optional `--wechat-share-official-package` patch changes the declared sender
package to `com.xingin.xhs` only in `MMessageActV2.send` when the target is
`com.tencent.mm` and the request's `_wxapi_command_type` is 2 (`SendMessageToWX`).
The original `_mmessage_appPackage` write and checksum call use that same value.
The source media, AppID, token acquisition, registration, calling UID, callbacks
and non-share requests are retained. `Context.getPackageName()` and Android's
package/signature information are not changed globally.

**微信分享需要同时安装官方国际版 REDnote（Google Play 版），与小K书共存。**
[Official international REDnote](https://play.google.com/store/apps/details?id=com.xingin.xhs)
uses package `com.xingin.xhs`. The successful real-device result applies to this
coinstalled configuration; it does not establish every receiver-side check.
Sharing callbacks may return to the official app.

The source-method fingerprint, share-only guard, package/checksum ordering and
compiled instructions are checked during building. The successful share result
comes from the account owner's real-device test. The production workflow enables
this configuration by default and supports publishing stable releases; the
manual `wechat_share_identity` input can disable it.

To return to the stable configuration, overlay-install
[the -5 APK](https://github.com/KiriKira/xhs-apk-custom/releases/download/rednote-v9.48.1-5/rednote-fold-custom.apk).
The package, signer and Android versions remain the same. This release does not
run another rollback VM or SMS flow.
