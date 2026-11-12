"""Tests for the tag file format, including cross-checks against the
original Tcl implementation (tests/fixtures/tag.tcl, copied unmodified from
the taglog distribution). The Tcl tests are skipped if tclsh is missing."""

import os
import shutil
import subprocess
import tempfile
import unittest

from taglog_web import tagfile as tf

HERE = os.path.dirname(os.path.abspath(__file__))
TAG_TCL = os.path.join(HERE, "fixtures", "tag.tcl")
TCLSH = shutil.which("tclsh")

SAMPLE = [
    [("Tag-worklog-version", "1.0", None), ("Date", "2026-11-12", None),
     ("WeekDay", "Thursday", None),
     ("Summary", "A good day\nwith two lines", "END_S"), tf.END],
    [("Id", "20261112093000", None), ("StartTime", "9:00:00", None),
     ("EndTime", "9:30:00", None), ("Project", "Big project", None),
     ("Activity", "email", None),
     ("Description", "Line one\n  indented: with colon\n\nlast line", "END_D"), tf.END],
    [("Id", "x", None), ("StartTime", "9:30:00", None), ("EndTime", "10:00:00", None),
     ("Description", "unicode – café ✓", "END_D"), tf.END],
]


def run_tcl(script: str) -> str:
    res = subprocess.run([TCLSH], input=script, capture_output=True, text=True,
                         encoding="utf-8", check=True)
    return res.stdout


TCL_DUMP = r"""
source {%s}
encoding system utf-8
fconfigure stdout -encoding utf-8
foreach e [tag readfile {%s}] {
  foreach item $e {
    puts -nonewline "[lindex $item 0]\x1f[lindex $item 1]\x1f[lindex $item 2]\x1e"
  }
  puts -nonewline "\x1d"
}
"""


def tcl_parse(path: str):
    out = run_tcl(TCL_DUMP % (TAG_TCL, path))
    entries = []
    for chunk in out.split("\x1d")[:-1]:
        entry = []
        for it in chunk.split("\x1e")[:-1]:
            name, value, label = it.split("\x1f")
            entry.append((name, value, label or None))
        entries.append(entry)
    return entries


class TestParse(unittest.TestCase):
    def test_round_trip(self):
        text = tf.serialize(SAMPLE)
        self.assertEqual(tf.parse(text), SAMPLE)
        self.assertEqual(tf.serialize(tf.parse(text)), text)

    def test_format_details(self):
        text = tf.serialize([[("A", "1", None), tf.END]])
        self.assertEqual(text, "A: 1\nEnd: \n")
        text = tf.serialize([[("D", "x\ny", "END_D"), tf.END]])
        self.assertEqual(text, "D:: END_D\nx\ny\nEND_D\nEnd: \n")

    def test_lenient_input(self):
        # No space after colon, CRLF line ends, blank lines between entries,
        # missing newline at the end of the file.
        text = "A:1\r\nEnd:\r\n\r\nB: 2\nD:: END_D\nhello\nEND_D"
        e = tf.parse(text)
        self.assertEqual(e[0], [("A", "1", None), ("End", "", None)])
        self.assertEqual(e[1], [("B", "2", None), ("D", "hello", "END_D")])

    def test_empty(self):
        self.assertEqual(tf.parse(""), [])
        self.assertEqual(tf.parse("\n\n  \n"), [])

    def test_helpers(self):
        e = [("Name", "P", None), ("Flags", "Active", None), tf.END]
        tf.set_or_replace(e, "Code", "C1")
        self.assertEqual(e[-2], ("Code", "C1", None))
        tf.set_or_replace_flag(e, "Flags", "Breaks", True)
        tf.set_or_replace_flag(e, "Flags", "Active", False)
        self.assertEqual(tf.entry_vals(e, "Flags"), ["Breaks"])
        self.assertEqual(e[-1], tf.END)
        self.assertTrue(tf.match_cond(e, ("Flags", "-contains", "break")))
        self.assertTrue(tf.match_cond([("P", "40", None)], ("P", "<=", "50")))
        self.assertFalse(tf.match_cond([("P", "60", None)], ("P", "<=", "50")))


@unittest.skipUnless(TCLSH, "tclsh not installed")
class TestTclCompatibility(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir)

    def test_tcl_reads_python_output(self):
        path = os.path.join(self.dir, "a.tag")
        tf.write_file(path, SAMPLE)
        self.assertEqual(tcl_parse(path), SAMPLE)

    def test_tcl_rewrite_is_byte_identical(self):
        a = os.path.join(self.dir, "a.tag")
        b = os.path.join(self.dir, "b.tag")
        tf.write_file(a, SAMPLE)
        run_tcl("source {%s}\nencoding system utf-8\ntag writefile {%s} [tag readfile {%s}]\n"
                % (TAG_TCL, b, a))
        with open(a, "rb") as fa, open(b, "rb") as fb:
            self.assertEqual(fa.read(), fb.read())

    def test_python_reads_tcl_output(self):
        path = os.path.join(self.dir, "t.tag")
        run_tcl(r"""
source {%s}
encoding system utf-8
set e1 [list [list Tag-action-version 1.0] [list End]]
set e2 [list [list Id A.1] [list Title "Do it"] [list Description "x\ny: z" END_D] [list Status Active] [list End]]
tag writefile {%s} [list $e1 $e2]
""" % (TAG_TCL, path))
        e = tf.read_file(path)
        self.assertEqual(e[1], [("Id", "A.1", None), ("Title", "Do it", None),
                                ("Description", "x\ny: z", "END_D"),
                                ("Status", "Active", None), tf.END])
        self.assertEqual(e[0][-1], tf.END)

    def test_original_sample_file(self):
        path = os.path.join(HERE, "fixtures", "test.tag")
        self.assertEqual(tf.read_file(path), tcl_parse(path))


if __name__ == "__main__":
    unittest.main()
