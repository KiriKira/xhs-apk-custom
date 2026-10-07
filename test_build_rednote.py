import unittest
import xml.etree.ElementTree as ET

from pathlib import Path

from build_rednote import (
    ANDROID,
    BuildError,
    dex_name_for_smali,
    is_signature_metadata,
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
              <permission android:name="{OLD_PACKAGE}.permission.DEFINED"
                  android:permissionGroup="{OLD_PACKAGE}.permission.GROUP" />
              <application android:name=".App" android:backupAgent="BackupAgent">
                <activity android:name="MainActivity" android:parentActivityName=".Parent" />
                <activity-alias android:name=".Alias" android:targetActivity=".MainActivity" />
                <service android:name="{OLD_PACKAGE}.Service">
                  <intent-filter><action android:name="{OLD_PACKAGE}.ACTION_KEEP" /></intent-filter>
                </service>
                <provider android:name="FileProvider"
                    android:authorities="{OLD_PACKAGE}.files;legacy.sdk.authority"
                    android:permission="{OLD_PACKAGE}.permission.CUSTOM" />
              </application>
            </manifest>'''
        )

    def test_rebases_package_components_permissions_and_real_provider_authorities(self):
        old, changes, warnings = transform_manifest(self.root, NEW_PACKAGE)
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

        uses_permission = self.root.find("uses-permission")
        self.assertEqual(
            uses_permission.get(ANDROID + "name"), NEW_PACKAGE + ".permission.CUSTOM"
        )
        internet = list(self.root.findall("uses-permission"))[1]
        self.assertEqual(internet.get(ANDROID + "name"), "android.permission.INTERNET")
        definition = self.root.find("permission")
        self.assertEqual(
            definition.get(ANDROID + "name"), NEW_PACKAGE + ".permission.DEFINED"
        )
        self.assertEqual(
            definition.get(ANDROID + "permissionGroup"), NEW_PACKAGE + ".permission.GROUP"
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
        self.assertTrue(any("hard-coded content URIs" in warning for warning in warnings))
        self.assertTrue(any(item["field"] == "manifest.package" for item in changes))

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


if __name__ == "__main__":
    unittest.main()
