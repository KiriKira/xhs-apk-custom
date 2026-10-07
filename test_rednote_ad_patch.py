from pathlib import Path
import tempfile
import unittest

from rednote_ad_patch import HIDE, RESTORE, SUPER_BIND, patch_feed_bind


class FeedAdPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "FeedCustomMultiTypeAdapter.smali"
        self.source = (Path(__file__).parent / "tests/fixtures/rednote_9481_feed_bind.smali").read_text()
        self.path.write_text(self.source)

    def test_keeps_all_original_binding_code_and_registers(self):
        audit = patch_feed_bind(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched.replace(RESTORE, "").replace(HIDE, ""), self.source)
        self.assertEqual(patched.count(SUPER_BIND), 1)
        self.assertEqual(patched.count("    .locals 4\n"), 1)
        self.assertLess(patched.index(RESTORE), patched.index(SUPER_BIND))
        self.assertLess(patched.index(SUPER_BIND), patched.index(HIDE))
        self.assertTrue(audit["originalBindPreserved"])

    def test_rejects_changed_version_without_partial_write(self):
        changed = self.source.replace(".locals 4", ".locals 5")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_feed_bind(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_feed_bind(self.path)

    def test_rejects_second_patch_instead_of_duplicate_hooks(self):
        patch_feed_bind(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_feed_bind(self.path)
        self.assertEqual(self.path.read_text(), first)


if __name__ == "__main__":
    unittest.main()
