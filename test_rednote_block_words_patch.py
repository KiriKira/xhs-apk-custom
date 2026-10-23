"""Unit tests for the keyword-block patch (settings entry + feed keyword hook)."""

import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
import tempfile

from rednote_ad_patch import patch_feed_bind
import rednote_block_words_patch as module


class SettingsActivityPatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "SettingActivityV2.smali"
        self.source = (
            Path(__file__).parent / "tests/fixtures/rednote_9481_settings_oncreate.smali"
        ).read_text()
        self.path.write_text(self.source)

    def test_hook_is_added_after_the_original_oncreate_body(self):
        audit = module.patch_settings_activity(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched.count(module.SETTINGS_ACTIVITY_HOOK), 1)
        self.assertEqual(patched.count(module.FOCUS_ENSURE_HOOK), 1)
        stripped = patched.replace(module.SETTINGS_ACTIVITY_HOOK, "").replace(
            module.FOCUS_ENSURE_HOOK, ""
        )
        self.assertEqual(stripped, self.source)
        self.assertLess(
            patched.index(module.SETTINGS_ACTIVITY_LAUNCH),
            patched.index(module.SETTINGS_ACTIVITY_HOOK),
        )
        self.assertLess(
            patched.index(module.FOCUS_SUPER_CALL),
            patched.index(module.FOCUS_ENSURE_HOOK),
        )
        self.assertEqual(audit["originalMethodSha256"], module.EXPECTED_ONCREATE_SHA)
        self.assertEqual(audit["refreshMethodSha256"], module.EXPECTED_FOCUS_SHA)

    def test_rejects_a_different_oncreate_without_writing(self):
        changed = self.source.replace(".locals 3", ".locals 4")
        self.path.write_text(changed)
        with self.assertRaisesRegex(ValueError, "differs"):
            module.patch_settings_activity(self.path)
        self.assertEqual(self.path.read_text(), changed)

    def test_rejects_duplicate_method(self):
        self.path.write_text(self.source + "\n" + self.source)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            module.patch_settings_activity(self.path)


class FeedKeywordHookTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "FeedCustomMultiTypeAdapter.smali"
        self.path.write_text(
            (Path(__file__).parent / "tests/fixtures/rednote_9481_feed_bind.smali").read_text()
        )
        patch_feed_bind(self.path)

    def test_keyword_check_runs_before_the_display_apply(self):
        audit = module.patch_feed_keyword_filter(self.path)
        patched = self.path.read_text()
        self.assertEqual(patched.count("rednote_feed_keyword_done"), 2)
        self.assertEqual(patched.count("FeedKeywordFilter;->matches"), 1)
        self.assertLess(
            patched.index(":rednote_feed_ad_apply"),
            patched.index("FeedKeywordFilter;->matches"),
        )
        self.assertLess(
            patched.index(":rednote_feed_keyword_done"),
            patched.rindex("FeedAdDisplay;->apply"),
        )
        self.assertTrue(audit["sameDisplayStateAsAdPatch"])

    def test_rejects_second_insertion(self):
        module.patch_feed_keyword_filter(self.path)
        first = self.path.read_text()
        with self.assertRaisesRegex(ValueError, "already present"):
            module.patch_feed_keyword_filter(self.path)
        self.assertEqual(self.path.read_text(), first)

    def test_requires_the_ad_display_hook(self):
        self.path.write_text(
            (Path(__file__).parent / "tests/fixtures/rednote_9481_feed_bind.smali").read_text()
        )
        with self.assertRaisesRegex(ValueError, "display hook"):
            module.patch_feed_keyword_filter(self.path)


class ManifestActivityTests(unittest.TestCase):
    def test_declares_a_non_exported_activity(self):
        root = ET.fromstring(
            '<manifest xmlns:android="http://schemas.android.com/apk/res/android"'
            ' package="com.kirikira.rednote.fold"><application android:name=".App"/></manifest>'
        )
        audit = module.declare_block_words_activity(root)
        activity = root.find("./application/activity")
        self.assertIsNotNone(activity)
        namespace = "{http://schemas.android.com/apk/res/android}"
        self.assertEqual(activity.get(namespace + "name"), module.ACTIVITY_CLASS)
        self.assertEqual(activity.get(namespace + "exported"), "false")
        self.assertEqual(audit["activity"], module.ACTIVITY_CLASS)
        with self.assertRaisesRegex(ValueError, "already declared"):
            module.declare_block_words_activity(root)

    def test_requires_an_application_element(self):
        root = ET.fromstring('<manifest xmlns:android="http://schemas.android.com/apk/res/android"/>')
        with self.assertRaisesRegex(ValueError, "application"):
            module.declare_block_words_activity(root)


class SourceShapeTests(unittest.TestCase):
    def test_helper_sources_stay_inside_the_supported_api(self):
        # The helper dex is compiled against android.jar only, so no androidx type may
        # appear in the Java sources; the binder lives in smali for that reason.
        for name, body in module.JAVA_SOURCES.items():
            self.assertNotIn("import androidx", body, f"{name} must not import androidx")
        self.assertIn("Lba/d;", module.SMALI_CLASSES["BlockBinder.smali"])
        self.assertIn("RecyclerView$ViewHolder", module.SMALI_CLASSES["BlockViewHolder.smali"])


if __name__ == "__main__":
    unittest.main()
