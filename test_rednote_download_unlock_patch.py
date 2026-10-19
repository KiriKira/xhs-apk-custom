from pathlib import Path
import tempfile
import unittest

from rednote_download_unlock_patch import ALLOWED_RETURN, DISABLED_FIELD_READ, patch_media_save_config


class DownloadUnlockPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "MediaSaveConfig.smali"
        self.source = (
            Path(__file__).parent
            / "tests/fixtures/rednote_9481_media_save_config.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_returns_false_without_touching_the_stored_field(self):
        audit = patch_media_save_config(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched, self.source.replace(DISABLED_FIELD_READ, ALLOWED_RETURN, 1))
        getter = patched.split(".method public final d()Z", 1)[1].split(".end method", 1)[0]
        self.assertNotIn(DISABLED_FIELD_READ, getter)
        self.assertIn("disableSaveMedia:Z", patched)
        self.assertTrue(audit["disabledFlagBypassed"])
        self.assertTrue(audit["storedFieldPreserved"])
        self.assertTrue(audit["parcelPreserved"])
        self.assertTrue(audit["serverPayloadUnchanged"])

    def test_rejects_changed_version_without_partial_write(self):
        changed = self.source.replace(".locals 1", ".locals 2")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_media_save_config(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_media_save_config(self.path)
        self.assertEqual(self.path.read_text(), self.source + "\n" + self.source)

    def test_rejects_second_patch_instead_of_duplicate_edits(self):
        patch_media_save_config(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_media_save_config(self.path)
        self.assertEqual(self.path.read_text(), first)


if __name__ == "__main__":
    unittest.main()
