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

    def patched(self) -> str:
        patch_dynamic_columns(self.path)
        return self.path.read_text()

    def test_python_table_mirrors_the_helper(self):
        """band_counts must agree with ColumnSettings.resolve in the Java helper."""
        table = band_counts(4, 5)
        self.assertEqual(table["TINNY"], (1, 1, 1))
        self.assertEqual(table["SMALL"], (2, 3, 4))
        self.assertEqual(table["MIDDLE"], (2, 3, 4))
        self.assertEqual(table["BIG"], (3, 4, 5))
        self.assertEqual(table["LAGE"], (3, 4, 5))

    def test_stock_band_detection_is_kept_verbatim(self):
        """The whole width detection must survive; only the table lookup changes.

        Regenerating the detection is what broke the earlier revisions, so the
        head of the method is compared byte for byte.
        """
        patched = self.patched()
        original_head = self.source[: self.source.index("    :goto_0")]
        patched_head = patched[: patched.index("    :goto_0")]
        self.assertEqual(original_head, patched_head)
        for dp in BAND_DP:
            self.assertIn(f"0x{dp:x}", patched_head)

    def test_tail_delegates_to_the_runtime_helper(self):
        patched = self.patched()
        tail = patched[patched.index("    :goto_0"):]
        self.assertIn("Ldev/kiri/xhsads/ColumnSettings;->spanFor(II)I", tail)
        self.assertIn("Ljava/lang/Enum;->ordinal()I", tail)
        self.assertIn("invoke-virtual {p0}, Let/n;->a()I", tail)

    def test_entry_method_seeds_the_helper_context(self):
        patched = self.patched()
        self.assertIn(
            "invoke-static {p1}, Ldev/kiri/xhsads/ColumnSettings;->"
            "remember(Landroid/content/Context;)V",
            patched,
        )

    def test_reports_the_original_hash(self):
        audit = patch_dynamic_columns(self.path)
        self.assertEqual(audit["originalMethodSha256"], EXPECTED_METHOD_SHA)
        self.assertTrue(audit["bandDetectionPreserved"])
        self.assertEqual(audit["outerMaxColumns"], 4)
        self.assertEqual(audit["innerMaxColumns"], 5)

    def test_rejects_changed_method_without_partial_write(self):
        changed = self.source.replace(".locals 5", ".locals 6")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs from the verified"):
            patch_dynamic_columns(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_inverted_maxima(self):
        with self.assertRaisesRegex(ValueError, "between 2 and 9"):
            band_counts(10, 5)
        with self.assertRaisesRegex(ValueError, "between 2 and 9"):
            band_counts(4, 0)

    def test_custom_maxima_reach_the_report(self):
        audit = patch_dynamic_columns(self.path, outer_max=3, inner_max=6)
        self.assertEqual(audit["outerScreenColumns"], [2, 3, 3])
        self.assertEqual(audit["innerScreenColumns"], [4, 5, 6])
        self.assertEqual(audit["outerMaxColumns"], 3)
        self.assertEqual(audit["innerMaxColumns"], 6)


if __name__ == "__main__":
    unittest.main()
