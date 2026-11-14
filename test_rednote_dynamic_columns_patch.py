from pathlib import Path
import tempfile
import unittest

from rednote_dynamic_columns_patch import (
    BAND_DP,
    EXPECTED_METHOD_SHA,
    band_counts,
    patch_dynamic_columns,
)


class DynamicColumnsPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "n.smali"
        self.source = (
            Path(__file__).parent
            / "tests/fixtures/rednote_9540_dynamic_columns.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_default_table_gives_three_or_four_outer_and_five_inner(self):
        audit = patch_dynamic_columns(self.path)
        self.assertEqual(audit["outerScreenColumns"], [2, 3, 4])
        self.assertEqual(audit["innerScreenColumns"], [3, 4, 5])
        self.assertEqual(audit["patchedBands"]["SMALL"], [2, 3, 4])
        self.assertEqual(audit["patchedBands"]["BIG"], [3, 4, 5])
        # Cover screens keep a single column.
        self.assertEqual(audit["patchedBands"]["TINNY"], [1, 1, 1])
        self.assertEqual(audit["originalMethodSha256"], EXPECTED_METHOD_SHA)

    def test_rewrite_keeps_every_band_threshold_and_returns_each_count(self):
        patch_dynamic_columns(self.path)
        patched = self.path.read_text()
        for dp in BAND_DP:
            self.assertIn(f"const/16 v2, 0x{dp:x}", patched)
        # Every column count in the table must have a return site.
        for value in (1, 2, 3, 4, 5):
            self.assertIn(f"const/4 v0, 0x{value:x}", patched)
        self.assertEqual(patched.count("return v0"), 16)
        # The pinch state is read back through a(), never the obfuscated table.
        self.assertIn("invoke-virtual {p0}, Let/n;->a()I", patched)
        self.assertNotIn("Let/n$e;->a:[I", patched)

    def test_original_string_building_is_gone(self):
        patch_dynamic_columns(self.path)
        patched = self.path.read_text()
        self.assertNotIn("DynamicColumnFitWidth", patched)
        self.assertNotIn("StringBuilder", patched)

    def test_custom_maxima(self):
        audit = patch_dynamic_columns(self.path, outer_max=3, inner_max=4)
        self.assertEqual(audit["outerScreenColumns"], [2, 2, 3])
        self.assertEqual(audit["innerScreenColumns"], [2, 3, 4])

    def test_rejects_changed_method_without_partial_write(self):
        changed = self.source.replace(".locals 5", ".locals 6")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs from the verified"):
            patch_dynamic_columns(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "Expected exactly one"):
            patch_dynamic_columns(self.path)

    def test_rejects_inverted_maxima(self):
        with self.assertRaisesRegex(ValueError, "at least"):
            band_counts(5, 4)
        with self.assertRaisesRegex(ValueError, "outer_max"):
            band_counts(9, 9)


if __name__ == "__main__":
    unittest.main()
