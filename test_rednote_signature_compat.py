import hashlib
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

from pathlib import Path

from build_rednote import (
    compare_payload_entries,
    make_minimal_candidate,
    resolve_manifest_application_class,
)
from rednote_signature_compat import patch_application_startup


class StartupHookTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rednote-signature-hook-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        self.smali_path = self.temp_dir / "XhsApplication.smali"
        self.smali_path.write_text(
            ".class public Lcom/xingin/xhs/app/XhsApplication;\n"
            ".super Landroid/app/Application;\n\n"
            ".method public attachBaseContext(Landroid/content/Context;)V\n"
            "    .locals 2\n"
            "    invoke-super {p0, p1}, Landroid/app/Application;->attachBaseContext(Landroid/content/Context;)V\n"
            "    return-void\n"
            ".end method\n",
            encoding="utf-8",
        )

    def test_hook_is_inserted_after_registers_and_is_idempotent(self):
        self.assertTrue(patch_application_startup(self.smali_path))
        text = self.smali_path.read_text(encoding="utf-8")
        self.assertRegex(
            text,
            r"(?s)\.locals 2\n\s*\n\s*invoke-static \{\}, "
            r"Ldev/kiri/xhsspoof/SignatureSpoof;->install\(\)V",
        )
        self.assertLess(
            text.index("SignatureSpoof;->install()V"),
            text.index("invoke-super {p0, p1}"),
        )
        self.assertFalse(patch_application_startup(self.smali_path))
        self.assertEqual(text.count("SignatureSpoof;->install()V"), 1)


class SignatureCompatArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rednote-signature-archive-test-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(self.temp_dir, ignore_errors=True))
        self.baseline = self.temp_dir / "baseline.apk"
        self.rebuilt = self.temp_dir / "rebuilt.apk"
        self.candidate = self.temp_dir / "candidate.apk"
        self.helper = self.temp_dir / "helper.dex"
        self.helper.write_bytes(b"helper-dex-payload")

        with zipfile.ZipFile(self.baseline, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"original-manifest")
            archive.writestr("classes17.dex", b"original-touched-dex")
            archive.writestr("assets/kept.bin", b"unchanged-payload")
            archive.writestr("META-INF/BNDLTOOL.SF", b"old-signature")

        with zipfile.ZipFile(self.rebuilt, "w") as archive:
            archive.writestr("AndroidManifest.xml", b"rebuilt-manifest")
            archive.writestr("classes17.dex", b"rebuilt-touched-dex")

    def test_helper_dex_is_appended_stored_and_audited_as_the_only_new_payload(self):
        added = {"classes23.dex": self.helper}
        cleanup = make_minimal_candidate(
            self.baseline,
            self.rebuilt,
            {"AndroidManifest.xml", "classes17.dex"},
            self.candidate,
            added_entries=added,
        )
        self.assertEqual(cleanup["addedPayloadEntries"], ["classes23.dex"])
        with zipfile.ZipFile(self.candidate) as archive:
            self.assertEqual(archive.read("classes23.dex"), b"helper-dex-payload")
            self.assertEqual(archive.getinfo("classes23.dex").compress_type, zipfile.ZIP_STORED)

        audit = compare_payload_entries(
            self.baseline,
            self.candidate,
            {"AndroidManifest.xml", "classes17.dex"},
            added_entries={"classes23.dex"},
        )
        self.assertEqual(
            audit["addedPayloadEntries"],
            [
                {
                    "entry": "classes23.dex",
                    "sha256": hashlib.sha256(b"helper-dex-payload").hexdigest(),
                }
            ],
        )
        self.assertTrue(audit["allOtherPayloadHashesMatch"])

    def test_application_class_is_resolved_from_the_source_package(self):
        manifest = ET.fromstring(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android" '
            'package="com.xingin.xhs"><application android:name=".app.XhsApplication" /></manifest>'
        )
        self.assertEqual(
            resolve_manifest_application_class(manifest, "com.xingin.xhs"),
            "com.xingin.xhs.app.XhsApplication",
        )

    def test_unexpected_payload_entry_is_rejected(self):
        make_minimal_candidate(
            self.baseline,
            self.rebuilt,
            {"AndroidManifest.xml", "classes17.dex"},
            self.candidate,
            added_entries={"classes23.dex": self.helper},
        )
        with zipfile.ZipFile(self.candidate, "a") as archive:
            archive.writestr("classes24.dex", b"unexpected-dex")
        with self.assertRaisesRegex(Exception, "Payload entry set changed unexpectedly"):
            compare_payload_entries(
                self.baseline,
                self.candidate,
                {"AndroidManifest.xml", "classes17.dex"},
                added_entries={"classes23.dex"},
            )


if __name__ == "__main__":
    unittest.main()
