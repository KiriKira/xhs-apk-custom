import unittest
import xml.etree.ElementTree as ET
import shutil
import tempfile
import zipfile

from pathlib import Path

from build_rednote import (
    ANDROID,
    BuildError,
    dex_name_for_smali,
    is_signature_metadata,
    make_selected_dex_decode_input,
    patch_main_process_package_gate,
    parse_args,
    prepare_selective_dex_rebuild,
    reject_split_manifest,
    transform_manifest,
)


OLD_PACKAGE = "com.xingin.xhs"
NEW_PACKAGE = "com.kirikira.rednote.fold"


class ManifestTransformTests(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(
            f'''<manifest xmlns:android="http://schemas.android.com/apk/res/android"
                package="{OLD_PACKAGE}">
              <queries>
                <provider android:authorities="com.android.calendar" />
              </queries>
              <uses-permission android:name="{OLD_PACKAGE}.permission.CUSTOM" />
              <uses-permission android:name="android.permission.INTERNET" />
              <uses-permission android:name="{OLD_PACKAGE}.manual.dump" />
              <uses-permission android:name="{{applicationId}}.gcm.permission.C2D_MESSAGE" />
              <uses-permission android:name="vendor.sdk.permission.OWNED" />
              <uses-permission android:name="com.google.android.gms.permission.AD_ID" />
              <permission android:name="{OLD_PACKAGE}.permission.CUSTOM" />
              <permission android:name="{OLD_PACKAGE}.permission.DEFINED"
                  android:permissionGroup="{OLD_PACKAGE}.permission.GROUP" />
              <permission-group android:name="{OLD_PACKAGE}.permission.GROUP" />
              <permission android:name="{{applicationId}}.gcm.permission.C2D_MESSAGE" />
              <permission android:name="vendor.sdk.permission.OWNED" />
              <application android:name=".App" android:backupAgent="BackupAgent">
                <activity android:name="MainActivity" android:parentActivityName=".Parent" />
                <activity-alias android:name=".Alias" android:targetActivity=".MainActivity" />
                <service android:name="{OLD_PACKAGE}.Service"
                    android:permission="{OLD_PACKAGE}.permission.CUSTOM">
                  <intent-filter><action android:name="{OLD_PACKAGE}.ACTION_KEEP" /></intent-filter>
                </service>
                <provider android:name="FileProvider"
                    android:authorities="{OLD_PACKAGE}.files;legacy.sdk.authority"
                    android:permission="{OLD_PACKAGE}.permission.CUSTOM"
                    android:readPermission="{{applicationId}}.gcm.permission.C2D_MESSAGE"
                    android:writePermission="vendor.sdk.permission.OWNED" />
                <receiver android:name=".SdkReceiver"
                    android:permission="{OLD_PACKAGE}.qmethod.permission.pandoraex" />
              </application>
            </manifest>'''
        )

    def test_rebases_package_components_permissions_and_real_provider_authorities(self):
        old, changes, warnings, permission_audit = transform_manifest(
            self.root, NEW_PACKAGE
        )
        self.assertEqual(old, OLD_PACKAGE)
        self.assertEqual(self.root.get("package"), NEW_PACKAGE)

        application = self.root.find("application")
        self.assertIsNotNone(application)
        self.assertEqual(application.get(ANDROID + "name"), OLD_PACKAGE + ".App")
        self.assertEqual(application.get(ANDROID + "backupAgent"), OLD_PACKAGE + ".BackupAgent")
        activity = application.find("activity")
        self.assertEqual(activity.get(ANDROID + "name"), OLD_PACKAGE + ".MainActivity")
        self.assertEqual(activity.get(ANDROID + "parentActivityName"), OLD_PACKAGE + ".Parent")
        alias = application.find("activity-alias")
        self.assertEqual(alias.get(ANDROID + "name"), OLD_PACKAGE + ".Alias")
        self.assertEqual(alias.get(ANDROID + "targetActivity"), OLD_PACKAGE + ".MainActivity")
        service = application.find("service")
        self.assertEqual(service.get(ANDROID + "name"), OLD_PACKAGE + ".Service")
        self.assertEqual(
            service.find("intent-filter/action").get(ANDROID + "name"),
            OLD_PACKAGE + ".ACTION_KEEP",
        )

        uses_permissions = {
            item.get(ANDROID + "name") for item in self.root.findall("uses-permission")
        }
        self.assertIn(NEW_PACKAGE + ".permission.CUSTOM", uses_permissions)
        self.assertIn("android.permission.INTERNET", uses_permissions)
        self.assertIn(OLD_PACKAGE + ".manual.dump", uses_permissions)
        self.assertIn(
            NEW_PACKAGE + ".gcm.permission.C2D_MESSAGE", uses_permissions
        )
        self.assertIn(
            NEW_PACKAGE + ".clone.vendor.sdk.permission.OWNED", uses_permissions
        )
        self.assertIn("com.google.android.gms.permission.AD_ID", uses_permissions)
        definition = next(
            item
            for item in self.root.findall("permission")
            if item.get(ANDROID + "name") == NEW_PACKAGE + ".permission.DEFINED"
        )
        self.assertEqual(
            definition.get(ANDROID + "name"), NEW_PACKAGE + ".permission.DEFINED"
        )
        self.assertEqual(
            definition.get(ANDROID + "permissionGroup"), NEW_PACKAGE + ".permission.GROUP"
        )
        declared_group = self.root.find("permission-group")
        self.assertEqual(
            declared_group.get(ANDROID + "name"), NEW_PACKAGE + ".permission.GROUP"
        )
        self.assertTrue(
            any(
                item.get(ANDROID + "name")
                == NEW_PACKAGE + ".gcm.permission.C2D_MESSAGE"
                for item in self.root.findall("permission")
            )
        )

        query_provider = self.root.find("queries/provider")
        self.assertEqual(query_provider.get(ANDROID + "authorities"), "com.android.calendar")
        real_provider = application.find("provider")
        self.assertEqual(
            real_provider.get(ANDROID + "authorities"),
            NEW_PACKAGE + ".files;" + NEW_PACKAGE + ".clone.legacy.sdk.authority",
        )
        self.assertEqual(
            real_provider.get(ANDROID + "permission"), NEW_PACKAGE + ".permission.CUSTOM"
        )
        self.assertEqual(
            real_provider.get(ANDROID + "readPermission"),
            NEW_PACKAGE + ".gcm.permission.C2D_MESSAGE",
        )
        self.assertEqual(
            real_provider.get(ANDROID + "writePermission"),
            NEW_PACKAGE + ".clone.vendor.sdk.permission.OWNED",
        )
        service = application.find("service")
        self.assertEqual(
            service.get(ANDROID + "permission"), NEW_PACKAGE + ".permission.CUSTOM"
        )
        sdk_receiver = application.find("receiver")
        self.assertEqual(
            sdk_receiver.get(ANDROID + "permission"),
            OLD_PACKAGE + ".qmethod.permission.pandoraex",
        )
        self.assertTrue(any("hard-coded content URIs" in warning for warning in warnings))
        self.assertTrue(any(item["field"] == "manifest.package" for item in changes))
        self.assertTrue(
            any("without a matching app declaration were preserved" in warning for warning in warnings)
        )
        audit_by_source = {
            item["sourceName"]: item
            for item in permission_audit["clonedDeclarations"]
        }
        self.assertEqual(
            audit_by_source["{applicationId}.gcm.permission.C2D_MESSAGE"]["cloneName"],
            NEW_PACKAGE + ".gcm.permission.C2D_MESSAGE",
        )
        placeholder_refs = audit_by_source[
            "{applicationId}.gcm.permission.C2D_MESSAGE"
        ]["updatedReferences"]
        self.assertEqual(
            {(item["element"], item["attribute"]) for item in placeholder_refs},
            {
                ("uses-permission", "android:name"),
                (
                    f"provider[android:name={OLD_PACKAGE}.FileProvider]",
                    "android:readPermission",
                ),
            },
        )
        self.assertIn(
            {
                "element": "uses-permission",
                "attribute": "android:name",
                "value": OLD_PACKAGE + ".manual.dump",
            },
            permission_audit["unmodifiedPackageScopedReferences"],
        )

    def test_split_and_required_split_manifests_are_rejected(self):
        for xml in (
            f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{OLD_PACKAGE}" split="config.arm64_v8a"/>',
            f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{OLD_PACKAGE}" android:requiredSplitTypes="base__abi"/>',
            f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{OLD_PACKAGE}"><uses-split android:name="feature"/></manifest>',
        ):
            with self.subTest(xml=xml):
                with self.assertRaises(BuildError):
                    reject_split_manifest(ET.fromstring(xml), "fixture APK")

    def test_apkeditor_internal_smali_paths_map_to_the_source_dex(self):
        decoded = Path("/tmp/decode")
        self.assertEqual(
            dex_name_for_smali(
                decoded,
                decoded / "smali" / "classes" / "com" / "example" / "Target.smali",
            ),
            "classes.dex",
        )
        self.assertEqual(
            dex_name_for_smali(
                decoded,
                decoded / "smali" / "classes15" / "com" / "example" / "Target.smali",
            ),
            "classes15.dex",
        )
        self.assertEqual(
            dex_name_for_smali(
                decoded,
                decoded / "smali_classes2" / "com" / "example" / "Target.smali",
            ),
            "classes2.dex",
        )

    def test_signature_cleanup_preserves_nested_jar_manifest(self):
        self.assertTrue(is_signature_metadata("META-INF/MANIFEST.MF"))
        self.assertTrue(is_signature_metadata("META-INF/BNDLTOOL.RSA"))
        self.assertTrue(is_signature_metadata("stamp-cert-sha256"))
        self.assertFalse(is_signature_metadata("META-INF/versions/9/OSGI-INF/MANIFEST.MF"))
        self.assertFalse(is_signature_metadata("META-INF/services/com.example.Factory"))


class MainProcessPackageGateTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(__import__("tempfile").mkdtemp(prefix="rednote-smali-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        self.smali_path = self.temp_dir / "smali" / "classes17" / "ddc" / "a.smali"
        self.smali_path.parent.mkdir(parents=True)
        self.smali_path.write_text(
            '''.class public final synthetic Lddc/a;
.super Ljava/lang/Object;

.method public final invoke()Ljava/lang/Object;
    .locals 2
    sget-object v0, Lddc/b;->b:Ljava/lang/String;
    const-string v1, "com.xingin.xhs"
    invoke-static {v0, v1}, Lkotlin/jvm/internal/Intrinsics;->areEqual(Ljava/lang/Object;Ljava/lang/Object;)Z
    move-result v0
    return-object v0
.end method

.method public unrelated()V
    .locals 1
    const-string v0, "com.xingin.xhs"
    return-void
.end method
''',
            encoding="utf-8",
        )

    def test_rebases_only_the_unique_main_process_predicate(self):
        audit = patch_main_process_package_gate(
            self.smali_path, OLD_PACKAGE, NEW_PACKAGE
        )
        text = self.smali_path.read_text(encoding="utf-8")
        self.assertIn(f'const-string v1, "{NEW_PACKAGE}"', text)
        self.assertIn('const-string v0, "com.xingin.xhs"', text)
        self.assertEqual(
            audit,
            {
                "class": "ddc.a",
                "method": "invoke()Ljava/lang/Object;",
                "sourceProcessName": OLD_PACKAGE,
                "cloneProcessName": NEW_PACKAGE,
            },
        )

    def test_rejects_a_duplicated_main_process_predicate(self):
        text = self.smali_path.read_text(encoding="utf-8")
        method_body = '''
    sget-object v0, Lddc/b;->b:Ljava/lang/String;
    const-string v1, "com.xingin.xhs"
    invoke-static {v0, v1}, Lkotlin/jvm/internal/Intrinsics;->areEqual(Ljava/lang/Object;Ljava/lang/Object;)Z
'''
        text = text.replace(".end method", method_body + ".end method", 1)
        self.smali_path.write_text(text, encoding="utf-8")
        with self.assertRaises(BuildError):
            patch_main_process_package_gate(self.smali_path, OLD_PACKAGE, NEW_PACKAGE)


class SelectiveDexRebuildTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rednote-dex-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.decoded = self.temp_dir / "decoded"
        self.smali_root = self.decoded / "smali"
        for dirname in ("classes", "classes2", "classes4", "classes17"):
            (self.smali_root / dirname).mkdir(parents=True)
            (self.smali_root / dirname / "Example.smali").write_text(".class Example\n")
        self.baseline = self.temp_dir / "baseline.apk"
        self.dex_payloads = {
            "classes.dex": b"dex-main-original",
            "classes2.dex": b"dex-2-original",
            "classes4.dex": b"dex-4-original",
            "classes17.dex": b"dex-17-original",
        }
        with zipfile.ZipFile(self.baseline, "w") as archive:
            for name, data in self.dex_payloads.items():
                archive.writestr(name, data)

    def test_only_touched_dex_remains_smali_and_other_dexes_are_raw_passthrough(self):
        audit = prepare_selective_dex_rebuild(
            self.decoded, self.baseline, {"classes4.dex", "classes17.dex"}
        )
        self.assertEqual(audit["rebuiltDexEntries"], ["classes17.dex", "classes4.dex"])
        self.assertEqual(audit["passthroughDexEntries"], ["classes.dex", "classes2.dex"])
        self.assertEqual(
            sorted(path.name for path in self.smali_root.iterdir()),
            ["classes17", "classes4"],
        )
        self.assertEqual(
            sorted(path.name for path in (self.decoded / "dex").iterdir()),
            ["classes.dex", "classes2.dex"],
        )
        with zipfile.ZipFile(self.baseline) as source:
            for name in audit["passthroughDexEntries"]:
                self.assertEqual(
                    (self.decoded / "dex" / name).read_bytes(), source.read(name)
                )

    def test_rejects_a_selected_dex_without_a_smali_directory(self):
        with self.assertRaises(BuildError):
            prepare_selective_dex_rebuild(
                self.decoded, self.baseline, {"classes3.dex"}
            )


class SelectiveDexDecodeInputTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rednote-decode-input-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))
        self.baseline = self.temp_dir / "baseline.apk"
        self.filtered = self.temp_dir / "filtered.apk"
        with zipfile.ZipFile(self.baseline, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"manifest")
            archive.writestr("resources.arsc", b"resources")
            archive.writestr("assets/asset.bin", b"asset")
            archive.writestr("lib/arm64-v8a/libsample.so", b"native")
            archive.writestr("classes.dex", b"dex-primary")
            archive.writestr("classes4.dex", b"dex-fold")
            archive.writestr("classes17.dex", b"dex-app-and-process-gate")

    def test_filtered_input_keeps_non_dex_payload_and_original_dex_names(self):
        audit = make_selected_dex_decode_input(
            self.baseline,
            self.filtered,
            {"classes4.dex", "classes17.dex"},
        )
        self.assertEqual(audit["sourceDexEntries"], ["classes.dex", "classes17.dex", "classes4.dex"])
        self.assertEqual(audit["selectedDexEntries"], ["classes17.dex", "classes4.dex"])
        self.assertEqual(audit["excludedDexEntries"], ["classes.dex"])
        self.assertTrue(audit["selectedDexEntryNamesPreserved"])

        with zipfile.ZipFile(self.baseline) as source, zipfile.ZipFile(self.filtered) as filtered:
            self.assertEqual(
                set(filtered.namelist()),
                {
                    "AndroidManifest.xml",
                    "resources.arsc",
                    "assets/asset.bin",
                    "lib/arm64-v8a/libsample.so",
                    "classes4.dex",
                    "classes17.dex",
                },
            )
            self.assertEqual(filtered.read("classes4.dex"), source.read("classes4.dex"))
            self.assertEqual(filtered.read("classes17.dex"), source.read("classes17.dex"))
            for name in ("AndroidManifest.xml", "resources.arsc", "assets/asset.bin", "lib/arm64-v8a/libsample.so"):
                self.assertEqual(filtered.read(name), source.read(name))

        decoded = self.temp_dir / "decoded"
        for dex_stem in ("classes4", "classes17"):
            (decoded / "smali" / dex_stem).mkdir(parents=True)
        rebuild_audit = prepare_selective_dex_rebuild(
            decoded,
            self.baseline,
            {"classes4.dex", "classes17.dex"},
        )
        self.assertEqual(rebuild_audit["passthroughDexEntries"], ["classes.dex"])
        self.assertEqual((decoded / "dex" / "classes.dex").read_bytes(), b"dex-primary")

    def test_missing_selected_dex_is_rejected_and_repeated_flag_parses(self):
        with self.assertRaisesRegex(BuildError, "Selected DEX entries are missing"):
            make_selected_dex_decode_input(
                self.baseline,
                self.filtered,
                {"classes18.dex"},
            )

        args = parse_args(
            [
                "--input",
                "source.xapk",
                "--sha256",
                "0" * 64,
                "--source",
                "pinned workflow fixture",
                "--decode-dex",
                "classes17.dex",
                "--decode-dex",
                "classes4.dex",
            ]
        )
        self.assertEqual(args.decode_dex, ["classes17.dex", "classes4.dex"])


if __name__ == "__main__":
    unittest.main()
