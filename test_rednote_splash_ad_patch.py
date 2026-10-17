from pathlib import Path
import tempfile
import unittest

from rednote_splash_ad_patch import AD_BRANCH, NO_AD_BRANCH, patch_splash_ad_dispatch


class SplashAdPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "uy.f.smali"
        self.source = (
            Path(__file__).parent
            / "tests/fixtures/rednote_9481_splash_dispatch.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_keeps_every_instruction_except_the_branch(self):
        audit = patch_splash_ad_dispatch(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched, self.source.replace(AD_BRANCH, NO_AD_BRANCH, 1))
        self.assertEqual(patched.count(NO_AD_BRANCH), 1)
        self.assertNotIn(AD_BRANCH, patched)
        self.assertTrue(audit["adBranchBypassed"])
        self.assertTrue(audit["adCallbackRetained"])
        self.assertTrue(audit["noAdCallbackRetained"])
        self.assertTrue(audit["requestsUnchanged"])

    def test_rejects_changed_version_without_partial_write(self):
        changed = self.source.replace(".locals 4", ".locals 5")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_splash_ad_dispatch(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            patch_splash_ad_dispatch(self.path)
        self.assertEqual(self.path.read_text(), self.source + "\n" + self.source)

    def test_rejects_second_patch_instead_of_duplicate_edits(self):
        patch_splash_ad_dispatch(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "differs"):
            patch_splash_ad_dispatch(self.path)
        self.assertEqual(self.path.read_text(), first)


if __name__ == "__main__":
    unittest.main()
