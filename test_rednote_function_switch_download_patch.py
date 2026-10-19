from pathlib import Path
import tempfile
import unittest

from rednote_function_switch_download_patch import (
    ORIGINAL_BODY,
    PATCHED_BODY,
    patch_image_download_switch,
)


class ImageDownloadSwitchPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "FunctionSwitch.smali"
        self.source = (
            Path(__file__).parent
            / "tests/fixtures/rednote_9481_function_switch.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_enables_only_image_download(self):
        audit = patch_image_download_switch(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched, self.source.replace(ORIGINAL_BODY, PATCHED_BODY, 1))
        self.assertIn('const-string v1, "image_download"', patched)
        self.assertIn("iget-boolean v0, p0, Lcom/xingin/entities/notedetail/FunctionSwitch;->enable:Z", patched)
        self.assertTrue(audit["imageDownloadEnabled"])
        self.assertTrue(audit["otherFunctionSwitchesUnchanged"])

    def test_rejects_changed_version_without_partial_write(self):
        changed = self.source.replace(".locals 1", ".locals 2")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_image_download_switch(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_image_download_switch(self.path)
        self.assertEqual(self.path.read_text(), self.source + "\n" + self.source)

    def test_rejects_second_patch_instead_of_duplicate_edits(self):
        patch_image_download_switch(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_image_download_switch(self.path)
        self.assertEqual(self.path.read_text(), first)


if __name__ == "__main__":
    unittest.main()
