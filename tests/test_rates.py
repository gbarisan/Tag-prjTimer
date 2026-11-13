"""Hourly rate / overtime multiplier: settings, costs in reports, and
compatibility with the original taglog's savePrefs."""

import datetime as dt
import os
import shutil
import subprocess
import tempfile
import unittest

from taglog_web import reports
from taglog_web import tagfile as tf
from taglog_web.prefs import MARKER_PREFIX, Prefs
from taglog_web.store import Store

HERE = os.path.dirname(os.path.abspath(__file__))
TCLSH = shutil.which("tclsh")

PREFS = """# Preferences for taglog
set language en
set rootdir "%s"
set num_today_actions 3
# above this line is automatically saved - put your changes below here -
set my_own_setting 42
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "diary")
        self.path = os.path.join(self.tmp, ".taglog")
        with open(self.path, "w") as f:
            f.write(PREFS % self.root)
        self.prefs = Prefs(self.path, system_path="/nonexistent")
        self.store = Store(self.prefs)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def text(self):
        with open(self.path) as f:
            return f.read()


class TestRatePrefs(Base):
    def test_defaults(self):
        self.assertEqual(self.prefs.hourly_rate, 0.0)
        self.assertEqual(self.prefs.overtime_multiplier, 1.5)
        self.assertEqual(self.prefs.currency, "")

    def test_saved_below_marker(self):
        self.prefs.save({"hourly_rate": "45,50", "overtime_multiplier": "2", "rate_currency": "€"})
        text = self.text()
        marker = text.index(MARKER_PREFIX)
        for line in ("set hourly_rate 45.5", "set overtime_multiplier 2", 'set rate_currency "€"'):
            self.assertIn(line + "\n", text)
            self.assertGreater(text.index(line), marker)
        self.assertIn("set my_own_setting 42", text)
        p2 = Prefs(self.path, system_path="/nonexistent")
        self.assertEqual((p2.hourly_rate, p2.overtime_multiplier, p2.currency), (45.5, 2.0, "€"))
        # changing again replaces in place, no duplicates
        p2.save({"hourly_rate": "50"})
        self.assertEqual(self.text().count("set hourly_rate"), 1)
        self.assertIn("set hourly_rate 50\n", self.text())

    def test_existing_line_below_marker_is_replaced(self):
        with open(self.path, "a") as f:
            f.write("set num_today_actions 1\n")
        p = Prefs(self.path, system_path="/nonexistent")
        self.assertEqual(p.num_today_actions, 1)
        p.save({"num_today_actions": "2"})
        self.assertEqual(Prefs(self.path, system_path="/nonexistent").num_today_actions, 2)

    def test_validation(self):
        for bad in ({"hourly_rate": "abc"}, {"hourly_rate": "-5"},
                    {"overtime_multiplier": "0"}, {"overtime_multiplier": "11"},
                    {"rate_currency": "TOO LONG CURRENCY"}):
            with self.assertRaises(ValueError, msg=bad):
                self.prefs.save(bad)
        self.prefs.save({"hourly_rate": ""})
        self.assertEqual(self.prefs.hourly_rate, 0.0)

    @unittest.skipUnless(TCLSH, "tclsh not installed")
    def test_original_savePrefs_keeps_rates(self):
        self.prefs.save({"hourly_rate": "40", "overtime_multiplier": "1.5", "rate_currency": "$"})
        script = r"""
proc mc { m } { return $m }
source {%s}
set prefsfile {%s}
source $prefsfile
foreach v { docdir libsdir showtime_hours_per_day showtime_spreadoverheads timebook_startlastweek
            dateformat_view dateformat_tcl currentTimeFormat history_win_depth current_win_depth
            id_prefix start_procs exit_procs projects_url activitiesfilename } {
  if { ! [info exists $v] } { set $v "" }
}
set num_today_actions 5
savePrefs
""" % (os.path.join(HERE, "fixtures", "taglog_init.tcl"), self.path)
        subprocess.run([TCLSH], input=script, text=True, check=True, capture_output=True)
        p = Prefs(self.path, system_path="/nonexistent")
        self.assertEqual(p.num_today_actions, 5)       # written by the original
        self.assertEqual(p.hourly_rate, 40.0)          # kept by the original
        self.assertEqual(p.currency, "$")
        self.assertIn("set my_own_setting 42", self.text())


class TestRateReports(Base):
    def add(self, d, start, end, project, rate=""):
        e = []
        tf.tag_append(e, "Id", "1")
        tf.tag_append(e, "StartTime", start)
        tf.tag_append(e, "EndTime", end)
        tf.tag_append(e, "Project", project)
        tf.tag_append(e, "Rate", rate)
        e.append(tf.END)
        self.store.append_log_entry(d, e)

    def setUp(self):
        super().setUp()
        st = self.store
        st.save_project({"name": "A", "code": "CA"})
        st.save_project({"name": "B", "code": "CB"})
        st.save_project({"name": "Admin", "overheads": True})
        st.save_project({"name": "Lunch", "breaks": True})
        self.mon = mon = dt.date(2026, 11, 9)
        self.add(mon, "9:00", "12:00", "A")                  # 3h normal
        self.add(mon, "12:00", "13:00", "Lunch")             # break: free
        self.add(mon, "13:00", "14:00", "B")                 # 1h normal
        self.add(mon, "18:00", "20:00", "A", "Overtime")     # 2h overtime
        self.add(mon + dt.timedelta(days=1), "9:00", "11:00", "Admin")  # 2h overhead

    def test_no_rate_no_amounts(self):
        w = reports.time_bookings(self.store, self.mon, 1, "off", "name")["weeks"][0]
        self.assertIsNone(w["amount_total"])
        self.assertTrue(all(r["amount"] is None for r in w["rows"]))

    def test_amounts_without_spread(self):
        r = reports.time_bookings(self.store, self.mon, 1, "off", "name", 40.0, 1.5)
        w = r["weeks"][0]
        rows = {x["project"]: x for x in w["rows"]}
        self.assertEqual(rows["A"]["amount"], 3 * 40 + 2 * 60)   # 240
        self.assertEqual(rows["A"]["overtime"], 2 * 3600)
        self.assertEqual(rows["B"]["amount"], 40)
        self.assertEqual(rows["Admin"]["amount"], 80)
        self.assertEqual(w["amount_total"], 360)
        self.assertEqual(w["overtime_total"], 2 * 3600)
        csv = reports.time_bookings_csv(r, "hhmm", currency="€")
        self.assertIn("Amount (€)", csv)
        self.assertIn("A,05:00", csv)
        self.assertIn(",02:00,240.00", csv)

    def test_amounts_with_spread_byweek(self):
        w = reports.time_bookings(self.store, self.mon, 1, "byweek", "name", 40.0, 1.5)["weeks"][0]
        rows = {x["project"]: x for x in w["rows"]}
        # A has 5h of 6h project time -> 5/6 of the 80 overhead amount
        self.assertAlmostEqual(rows["A"]["amount"], 240 + 80 * 5 / 6, places=2)
        self.assertAlmostEqual(rows["B"]["amount"], 40 + 80 / 6, places=2)
        self.assertEqual(w["amount_total"], 360)

    def test_project_total(self):
        t = reports.project_total(self.store, "A", self.mon, self.mon, 40.0, 1.5)
        self.assertEqual(t["amount"], 240)
        self.assertEqual(t["overtime"], 2 * 3600)
        self.assertEqual(reports.project_total(self.store, "Lunch", self.mon, self.mon, 40.0)["amount"], 0)
        self.assertIsNone(reports.project_total(self.store, "A", self.mon, self.mon)["amount"])


if __name__ == "__main__":
    unittest.main()
