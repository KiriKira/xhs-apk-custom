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


if __name__ == "__main__":
    unittest.main()
