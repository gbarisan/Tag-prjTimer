"""Behavioural tests: prefs, session (Next/Pause/stack/midnight), actions,
projects and reports, using a temporary data directory and a fake clock."""

import datetime as dt
import os
import shutil
import tempfile
import unittest

from taglog_web import reports
from taglog_web import tagfile as tf
from taglog_web.prefs import Prefs
from taglog_web.session import Session
from taglog_web.store import Store


class FakeClock:
    def __init__(self, t: dt.datetime):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, **kw):
        self.t += dt.timedelta(**kw)


PREFS_TEXT = """# Preferences for taglog
set language en
set showtime_hours_per_day 7.5
set docdir "/usr/share/doc/taglog"
set libsdir "/usr/share/taglog"
set rootdir "%s"
set showtime_spreadoverheads byweek
set timebook_startlastweek 1
set dateformat_view DD/MM/YYYY
set dateformat_tcl %%d/%%m/%%Y
set currentTimeFormat %%d:%%02d:%%02d
set num_today_actions 3
set history_win_depth 15
set current_win_depth 15
set id_prefix ""
set start_procs {  }
set exit_procs
set projects_url ""
set activitiesfilename "$rootdir/activities"
# above this line is automatically saved - put your changes below here -
set showtime_bookbycode 1
proc my_custom_proc {} { puts hi }
"""


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "diary")
        self.prefs_path = os.path.join(self.tmp, ".taglog")
        with open(self.prefs_path, "w") as f:
            f.write(PREFS_TEXT % self.root)
        self.prefs = Prefs(self.prefs_path, system_path=os.path.join(self.tmp, "none"))
        self.store = Store(self.prefs)
        self.clock = FakeClock(dt.datetime(2026, 11, 10, 9, 0, 0))  # a Tuesday
        self.session = Session(self.store, clock=self.clock)

    def tearDown(self):
        shutil.rmtree(self.tmp)


class TestPrefs(Base):
    def test_parse(self):
        p = self.prefs
        self.assertEqual(p.rootdir, self.root)
        self.assertEqual(p.date_format, "DD/MM/YYYY")
        self.assertEqual(p.time_format, "%d:%02d:%02d")
        self.assertEqual(p.hours_per_day, 7.5)
        self.assertEqual(p.activities_file, os.path.join(self.root, "activities"))
        self.assertEqual(p.book_by, "name")  # set below the marker
        self.assertTrue(any("my_custom_proc" in w or "proc" in w for w in p.warnings))

    def test_save_preserves_other_lines(self):
        self.prefs.save({"dateformat_view": "YYYY-MM-DD", "num_today_actions": "2"},
                        activities=["meeting", "email", "coding"])
        with open(self.prefs_path) as f:
            text = f.read()
        self.assertIn("set dateformat_view YYYY-MM-DD\n", text)
        self.assertIn("set dateformat_tcl %Y-%m-%d\n", text)
        self.assertIn("set num_today_actions 2\n", text)
        self.assertIn('set docdir "/usr/share/doc/taglog"\n', text)
        self.assertIn("proc my_custom_proc {} { puts hi }", text)
        # the user section stays below the marker
        self.assertLess(text.index("set num_today_actions 2"), text.index("# above this line"))
        self.assertLess(text.index("# above this line"), text.index("set showtime_bookbycode 1"))
        p2 = Prefs(self.prefs_path, system_path="/nonexistent")
        self.assertEqual(p2.date_format, "YYYY-MM-DD")
        self.assertEqual(p2.activities, ["meeting", "email", "coding"])

    def test_missing_prefs_file(self):
        p = Prefs(os.path.join(self.tmp, "nope"), system_path="/nonexistent")
        self.assertEqual(p.rootdir, os.path.expanduser("~/diary"))
        self.assertIn("meeting", p.activities)


class TestSession(Base):
    def log(self, d=None):
        return self.store.read_log(d or dt.date(2026, 11, 10))

    def test_next_writes_entry(self):
        self.session.update({"project": "P1", "activity": "email", "description": "hello\nworld"})
        self.clock.advance(minutes=30)
        self.session.next("meeting")
        log = self.log()
        self.assertEqual(tf.entry_val(log[0], "WeekDay"), "Tuesday")
        e = log[1]
        self.assertEqual(tf.entry_val(e, "StartTime"), "9:00:00")
        self.assertEqual(tf.entry_val(e, "EndTime"), "9:30:00")
        self.assertEqual(tf.entry_val(e, "Project"), "P1")
        self.assertEqual(tf.entry_val(e, "Description"), "hello\nworld")
        s = self.session.state
        self.assertEqual(s["start"], "9:30:00")
        self.assertEqual(s["activity"], "meeting")
        self.assertEqual(s["project"], "P1")  # project is kept
        self.assertEqual(s["description"], "")

    def test_pause_resume(self):
        self.clock.advance(minutes=10)
        self.session.pause()
        self.assertFalse(self.session.state["running"])
        self.clock.advance(minutes=50)
        self.session.resume()
        self.assertEqual(self.session.state["start"], "10:00:00")
        self.assertEqual(len(self.log()), 2)

    def test_interrupt_stack(self):
        self.session.update({"project": "Main"})
        self.clock.advance(minutes=20)
        self.session.push("!")
        self.session.update({"project": "Phone", "description": "call"})
        self.clock.advance(minutes=5)
        self.session.pop()
        self.assertEqual(self.session.state["project"], "Main")
        self.assertEqual(self.session.state["stack_info"], "")
        log = self.log()
        self.assertTrue(tf.entry_val(log[2], "Stack-info").startswith("! "))
        self.assertEqual(tf.entry_val(log[2], "Stack-info")[2:], tf.entry_val(log[1], "Id"))
        r = reports.interruptions(self.store, None, dt.date(2026, 11, 30))
        self.assertEqual(r["total"], 1)

    def test_midnight_while_running(self):
        self.clock.t = dt.datetime(2026, 11, 10, 23, 50)
        self.session.resume()
        self.clock.t = dt.datetime(2026, 11, 10, 23, 59, 40)
        self.session.tick()  # the server ticks every 30 seconds
        self.clock.t = dt.datetime(2026, 11, 11, 0, 0, 10)
        self.session.tick()
        old = self.log(dt.date(2026, 11, 10))
        self.assertEqual(tf.entry_val(old[-1], "EndTime"), "23:59:59")
        self.assertEqual(self.session.state["start"], "0:00:00")
        self.assertEqual(self.session.state["date"], "2026-11-11")

    def test_restart_after_days(self):
        self.session.update({"description": "unfinished"})
        self.clock.advance(hours=2)
        self.session.tick()  # last seen 11:00
        # Server not running for two days; a new Session object loads the state
        self.clock.t = dt.datetime(2026, 11, 12, 8, 0)
        s2 = Session(self.store, clock=self.clock)
        old = self.log(dt.date(2026, 11, 10))
        self.assertEqual(tf.entry_val(old[-1], "EndTime"), "11:00:00")
        self.assertEqual(tf.entry_val(old[-1], "Description"), "unfinished")
        self.assertEqual(s2.state["start"], "8:00:00")

    def test_adjust_start(self):
        self.clock.advance(minutes=30)
        self.session.next("")
        self.session.adjust_start("9:20:00", True)
        self.assertEqual(tf.entry_val(self.log()[-1], "EndTime"), "9:20:00")
        self.assertEqual(self.session.state["start"], "9:20:00")
        with self.assertRaises(ValueError):
            self.session.adjust_start("soon", False)


class TestActionsProjects(Base):
    def test_project_and_action_ids(self):
        self.store.save_project({"name": "Big Job", "code": "BJ", "active": True})
        a = self.store.create_action({"Title": "First", "Project": "Big Job"})
        # incprojactindex: NextActionId starts at 1 and is incremented first
        self.assertEqual(tf.entry_val(a, "Id"), "Big_Job.2")
        b = self.store.create_action({"Title": "No project"}, now=dt.datetime(2026, 1, 2, 3, 4, 5))
        self.assertEqual(tf.entry_val(b, "Id"), "taglog.20260102030405")
        c = self.store.create_action({"Title": "Later", "Active-after": "2026-12-01"})
        self.assertEqual(tf.entry_val(c, "Status"), "Blocked")

    def test_edit_keeps_extra_fields(self):
        a = self.store.create_action({"Title": "T", "Status": "Active"})
        aid = tf.entry_val(a, "Id")
        self.store.change_action_state(aid, "Pending", "waiting for X")
        e = self.store.edit_action(aid, {"Title": "T2"})
        self.assertEqual(tf.entry_val(e, "Title"), "T2")
        self.assertEqual(tf.entry_val(e, "Pending-note"), "waiting for X")
        self.assertTrue(tf.entry_val(e, "Pending-date"))
        self.assertEqual(e[-1], tf.END)

    def test_next_action_activation_via_session(self):
        a1 = self.store.create_action({"Title": "Step 1", "Status": "Active"})
        a2 = self.store.create_action({"Title": "Step 2", "Status": "Pending"})
        id1, id2 = tf.entry_val(a1, "Id"), tf.entry_val(a2, "Id")
        self.store.edit_action(id1, {"Next-action": id2})
        self.session.set_current_action(id1)
        self.clock.advance(minutes=15)
        self.session.finish_current_action("Completed")
        self.assertEqual(tf.entry_val(self.store.get_action(id1), "Status"), "Completed")
        self.assertEqual(tf.entry_val(self.store.get_action(id2), "Status"), "Active")
        self.assertEqual(self.session.state["action"], id2)
        log = self.store.read_log(dt.date(2026, 11, 10))
        self.assertEqual(tf.entry_val(log[-1], "Action"), id1)
        hist = self.store.action_history(id1)
        self.assertEqual(hist["total"], 15 * 60)

    def test_revise(self):
        a = self.store.create_action({"Title": "T", "Expected-time": "1:00",
                                      "Expected-completed-date": "2026-11-20"})
        aid = tf.entry_val(a, "Id")
        self.assertTrue(self.store.revise_action(aid, "2026-11-25", "2:00", today=dt.date(2026, 11, 12)))
        e = self.store.get_action(aid)
        self.assertEqual(tf.entry_val(e, "Original-expected-time"), "1:00")
        self.assertEqual(tf.entry_val(e, "Original-expected-completed-date"), "2026-11-20")
        self.assertEqual(tf.entry_val(e, "Revised-date"), "2026-11-12")

    def test_subtasks(self):
        self.store.create_action({"Title": "Parent", "Id": "P.1"})
        self.store.create_action({"Title": "Child", "Id": "P.2", "Subtask-of": "P.1"})
        self.store.create_action({"Title": "Child2", "Id": "P.3", "Subtask-of": "P.1"})
        self.assertEqual(tf.entry_val(self.store.get_action("P.1"), "Subtasks"), "P.2,P.3")

    def test_project_flags_edit(self):
        self.store.save_project({"name": "X", "active": True, "breaks": True})
        self.store.save_project({"name": "X", "active": False, "overheads": True}, original_name="X")
        p = self.store.project_map()["X"]
        self.assertFalse(p["active"])
        self.assertFalse(p["breaks"])
        self.assertTrue(p["overheads"])


class TestReports(Base):
    def add(self, d, start, end, project, activity=""):
        e = []
        tf.tag_append(e, "Id", "1")
        tf.tag_append(e, "StartTime", start)
        tf.tag_append(e, "EndTime", end)
        tf.tag_append(e, "Project", project)
        tf.tag_append(e, "Activity", activity)
        e.append(tf.END)
        self.store.append_log_entry(d, e)

    def test_time_bookings_byweek(self):
        st = self.store
        st.save_project({"name": "A", "code": "CA"})
        st.save_project({"name": "B", "code": "CB"})
        st.save_project({"name": "Admin", "overheads": True})
        st.save_project({"name": "Lunch", "breaks": True})
        mon = dt.date(2026, 11, 9)
        self.add(mon, "9:00", "12:00", "A")          # 3h
        self.add(mon, "12:00", "13:00", "Lunch")     # break
        self.add(mon, "13:00", "14:00", "B")         # 1h
        self.add(mon, "14:00", "16:00", "Admin")     # 2h overhead
        r = reports.time_bookings(st, mon, 1, "byweek", "code")["weeks"][0]
        rows = {x["project"]: x for x in r["rows"]}
        self.assertEqual(set(rows), {"CA", "CB"})
        self.assertEqual(rows["CA"]["total"], 3 * 3600 + int(round(7200 * 0.75)))
        self.assertEqual(rows["CB"]["total"], 1 * 3600 + int(round(7200 * 0.25)))
        self.assertEqual(r["nonbreaks_total"], 6 * 3600)
        self.assertEqual(r["breaks_total"], 3600)
        r2 = reports.time_bookings(st, mon, 1, "off", "name")["weeks"][0]
        self.assertEqual({x["project"] for x in r2["rows"]}, {"A", "B", "Admin"})
        csv = reports.time_bookings_csv({"weeks": [r]}, "hhmm")
        self.assertIn("CA,04:30", csv)

    def test_activity_and_project_total(self):
        d = dt.date(2026, 11, 9)
        self.add(d, "9:00:00", "9:45:00", "A", "email")
        self.add(d, "9:45:00", "10:00:00", "B", "email")
        self.add(d, "10:00:00", "11:00:00", "A", "meeting")
        r = reports.time_by_activity(self.store, d, d)
        self.assertEqual({x["activity"]: x["seconds"] for x in r["rows"]},
                         {"email": 3600, "meeting": 3600})
        t = reports.project_total(self.store, "A", d, d)
        self.assertEqual(t["total"], 105 * 60)
        self.assertEqual(t["days_with_entries"], 1)

    def test_project_budget(self):
        from taglog_web.timeutil import parse_expected_time
        self.assertEqual(parse_expected_time("40"), 40 * 3600)
        self.assertEqual(parse_expected_time("2,5"), 9000)
        self.assertEqual(parse_expected_time("1:30"), 5400)
        self.assertIsNone(parse_expected_time("soon"))
        d = dt.date(2026, 11, 9)
        self.store.save_project({"name": "A", "expected_time": "2:00"})
        self.store.save_project({"name": "B", "expected_time": "lots"})
        self.add(d, "9:00", "10:30", "A")
        t = reports.project_total(self.store, "A", d, d)
        self.assertEqual((t["expected_seconds"], t["remaining"], t["over_budget"]), (7200, 1800, False))
        self.add(d, "11:00", "12:00", "A")
        t = reports.project_total(self.store, "A", d, d)
        self.assertEqual((t["remaining"], t["over_budget"]), (-1800, True))
        t = reports.project_total(self.store, "B", d, d)
        self.assertIsNone(t["expected_seconds"])
        self.assertTrue(t["expected_unreadable"])
        self.assertFalse(t["over_budget"])

    def test_search(self):
        d = dt.date(2026, 11, 9)
        self.add(d, "9:00", "10:00", "A", "email")
        self.store.update_log_header(d, "Summary", "summary text", "END_S")
        res = reports.search_logs(self.store, d, d, project="A")
        self.assertEqual(len(res[0]["entries"]), 1)
        self.assertEqual(res[0]["summary"], "summary text")
        self.assertEqual(reports.search_logs(self.store, d, d, project="Z"), [])


if __name__ == "__main__":
    unittest.main()
