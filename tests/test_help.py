"""Tests for the help system (port of taglog_help.tcl)."""

import os
import re
import unittest

from taglog_web import tagfile as tf
from taglog_web.help import HELP_DIR, HelpLibrary

STATIC = os.path.join(os.path.dirname(HELP_DIR), "static")


class TestHelp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.h = HelpLibrary()

    def test_languages(self):
        langs = {l["code"]: l["topics"] for l in self.h.languages()}
        self.assertGreater(langs["en"], 120)
        self.assertGreater(langs["de"], 120)
        for code in ("es", "fr", "it", "nl"):
            self.assertIn(code, langs)

    def test_web_topic_overrides_original(self):
        t = self.h.topic("introduction", "en")
        self.assertTrue(t["adapted"])
        self.assertIn("Today page", t["text"])
        self.assertNotIn("File/Exit", t["text"])

    def test_original_topic(self):
        t = self.h.topic("hint_activity_pre_meeting", "en")
        self.assertFalse(t["adapted"])
        self.assertIn("Meetings can be a great waste of time", t["text"])

    def test_translation_and_fallback(self):
        de = self.h.topic("actinput_status", "de")
        self.assertEqual(de["lang"], "de")
        self.assertTrue(de["translated"])
        # German original of a topic rewritten in English is flagged
        self.assertTrue(self.h.topic("introduction", "de")["describes_original_ui"])
        fr = self.h.topic("actinput_status", "fr")
        self.assertEqual(fr["lang"], "en")
        self.assertFalse(fr["translated"])
        # a topic that only exists in the web overlay
        self.assertEqual(self.h.topic("stack", "de")["lang"], "en")

    def test_latin1_file(self):
        it = self.h.topic("prefs_language", "it")
        self.assertEqual(it["lang"], "it")
        self.assertNotIn("�", it["text"])
        self.assertIn("linguaggio", it["text"])

    def test_version_substitution_and_unknown(self):
        self.assertIn("version 9.9", self.h.topic("About", "en", "9.9")["text"])
        u = self.h.topic("no_such_topic", "en")
        self.assertFalse(u["found"])
        self.assertEqual(u["text"], "There is no help for this item.")

    def test_search(self):
        self.assertIn("endbutton", self.h.search("overtime rate"))
        self.assertEqual(self.h.search(""), [])

    def test_overlay_ids_exist_or_are_new(self):
        overlay = tf.read_file(os.path.join(HELP_DIR, "taglog_help_web_en.tag"))
        ids = [tf.entry_val(e, "Id") for e in overlay[1:]]
        self.assertEqual(len(ids), len(set(ids)))
        for e in overlay[1:]:
            self.assertTrue(tf.entry_val(e, "Title"), tf.entry_val(e, "Id"))
            self.assertTrue(tf.entry_val(e, "Description"), tf.entry_val(e, "Id"))

    def test_ui_references_existing_topics(self):
        ids = set(self.h.all_ids())
        with open(os.path.join(STATIC, "index.html"), encoding="utf-8") as f:
            html = f.read()
        with open(os.path.join(STATIC, "app.js"), encoding="utf-8") as f:
            js = f.read()
        refs = set(re.findall(r'data-help="([^"]+)"', html))
        # help: "x" and help: isNew ? "a" : "b" in openDialog calls
        for m in re.finditer(r'help: ((?:isNew \? )?"[A-Za-z_]+"(?: : "[A-Za-z_]+")?)', js):
            refs |= set(re.findall(r'"([A-Za-z_]+)"', m.group(1)))
        # the "?" key's per-page topics and the project dialog's field topics
        view_topics = js.split("const viewTopic = {")[1].split("}")[0]
        refs |= set(re.findall(r': "([A-Za-z_]+)"', view_topics))
        refs |= {"project_expectedtime", "ep_enddate"}
        missing = sorted(r for r in refs if r not in ids)
        self.assertEqual(missing, [], f"UI refers to help topics that do not exist: {missing}")
        self.assertGreater(len(refs), 30)


if __name__ == "__main__":
    unittest.main()
