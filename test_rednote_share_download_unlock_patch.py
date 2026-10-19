from pathlib import Path
import tempfile
import unittest

from rednote_share_download_unlock_patch import (
    ORIGINAL_BODY,
    PATCHED_BODY,
    patch_share_panel_download,
)


class SharePanelDownloadPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "ShareInfoDetail$Operate.smali"
        self.source = (
            Path(__file__).parent
            / "tests/fixtures/rednote_9481_share_operate.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_returns_false_only_for_download_entry(self):
        audit = patch_share_panel_download(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched, self.source.replace(ORIGINAL_BODY, PATCHED_BODY, 1))
        self.assertIn('const-string v1, "download_all_image_new"', patched)
        self.assertIn("iget-boolean v0, p0, Lcom/xingin/entities/ShareInfoDetail$Operate;->disable:Z", patched)
        self.assertTrue(audit["downloadEntryEnabled"])
        self.assertTrue(audit["otherShareEntriesUnchanged"])
        self.assertTrue(audit["disableToastPreserved"])

    def test_rejects_changed_version_without_partial_write(self):
        changed = self.source.replace(".locals 1", ".locals 2")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_share_panel_download(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_share_panel_download(self.path)
        self.assertEqual(self.path.read_text(), self.source + "\n" + self.source)

    def test_rejects_second_patch_instead_of_duplicate_edits(self):
        patch_share_panel_download(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_share_panel_download(self.path)
        self.assertEqual(self.path.read_text(), first)


if __name__ == "__main__":
    unittest.main()
