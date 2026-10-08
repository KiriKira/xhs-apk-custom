from pathlib import Path
import tempfile
import unittest

from rednote_wechat_share_patch import (
    APP_PACKAGE_EXTRA_CALL,
    CHECKSUM_CALL,
    CONTEXT_PACKAGE_CALL,
    OFFICIAL_PACKAGE,
    PATCH_MARKER,
    _guard,
    patch_send_share_identity,
)


FIXTURE = Path(__file__).parent / "tests/fixtures/rednote_mmessage_send.smali"


class WeChatShareIdentityPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "MMessageActV2.smali"
        self.source = FIXTURE.read_text()
        self.path.write_text(self.source)

    def test_only_adds_command2_wechat_guard_and_preserves_original_identity_path(self):
        audit = patch_send_share_identity(self.path, OFFICIAL_PACKAGE)
        patched = self.path.read_text()

        self.assertEqual(patched.replace("\n" + _guard(OFFICIAL_PACKAGE), ""), self.source)
        self.assertEqual(patched.count(PATCH_MARKER), 1)
        self.assertIn(CONTEXT_PACKAGE_CALL, patched)
        self.assertIn('const-string v5, "_wxapi_command_type"', patched)
        self.assertIn("    const/4 v5, 0x2", patched)
        self.assertIn('const-string v5, "com.tencent.mm"', patched)
        self.assertIn(APP_PACKAGE_EXTRA_CALL, patched)
        self.assertIn(CHECKSUM_CALL, patched)
        self.assertEqual(audit["strategy"], "experiment")
        self.assertEqual(audit["realPackage"], "com.kirikira.rednote.fold")
        self.assertEqual(audit["claimedPackage"], OFFICIAL_PACKAGE)
        self.assertTrue(audit["shareOnlyGuard"])
        self.assertTrue(audit["contextPackageRetained"])
        self.assertTrue(audit["packageExtraAndChecksumUseClaim"])
        self.assertEqual(audit["methodScopedCounts"]["commandTypeGuard"], 1)

    def test_rejects_changed_method_without_partial_write(self):
        changed = self.source.replace(".locals 7", ".locals 8", 1)
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_send_share_identity(self.path, OFFICIAL_PACKAGE)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method_without_partial_write(self):
        duplicate = self.source + "\n" + self.source
        self.path.write_text(duplicate)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_send_share_identity(self.path, OFFICIAL_PACKAGE)
        self.assertEqual(self.path.read_text(), duplicate)

    def test_rejects_second_application_without_duplicate_guard(self):
        patch_send_share_identity(self.path, OFFICIAL_PACKAGE)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "already patched"):
            patch_send_share_identity(self.path, OFFICIAL_PACKAGE)
        self.assertEqual(self.path.read_text(), first)

    def test_rejects_invalid_claimed_package_without_mutation(self):
        with self.assertRaisesRegex(ValueError, "dotted Android package"):
            patch_send_share_identity(self.path, "com")
        self.assertEqual(self.path.read_text(), self.source)


if __name__ == "__main__":
    unittest.main()
