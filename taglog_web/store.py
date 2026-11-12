"""Access to taglog's data files in the data directory (default ~/diary).

Layout (identical to the Tcl/Tk taglog):

    <rootdir>/log<YYYY>/<MM><DD>.tag    one log file per day
    <rootdir>/log<YYYY>/<MM>.tag        month summary
    <rootdir>/log<YYYY>/yearsumm<YYYY>.tag  year summary
    <rootdir>/projects.tag              projects
    <rootdir>/actions.tag               actions (to-do items)
    <rootdir>/contacts.tag              contacts
    <rootdir>/activities                one activity name per line

Files are re-read on every operation (nothing is cached), and every
modification is written straight back to disk atomically.
"""

from __future__ import annotations

import datetime as dt
import glob
import os
import re
import threading
from typing import Dict, List, Optional, Tuple

from . import tagfile as tf
from .prefs import Prefs
from .tagfile import Entry
from .timeutil import entry_duration, parse_datetime, weekday_name

# Order of fields in a log entry (getlogentry in the taglog script)
LOG_FIELDS = ["Id", "StartTime", "EndTime", "Project", "Rate", "Contact", "Action",
              "ActionTitle", "Activity", "Stack-info", "Description"]

# Order of fields in an action (getact_input_fields in taglog_action.tcl)
ACTION_FIELDS = ["Id", "Title", "Project", "Date", "Priority", "Status", "Period",
                 "Expected-cost", "Expected-time", "Expected-start-date",
                 "Expected-completed-date", "Precursor", "Active-after", "Subtask-of",
                 "Next-action", "Abort-action", "Email-status-to", "Delegated-to",
                 "Difficulty"]
ACTION_TEXT_FIELDS = ["Description", "Deliverable", "Reason", "Summary"]

VALID_STATES = ["Unclaimed", "Pending", "Active", "Blocked", "Delegated", "Completed",
                "Aborted", "Periodic"]

PROJECT_FLAGS = ["Overheads", "Breaks", "Active", "Immutable"]


class StoreError(Exception):
    pass


def entry_to_dict(entry: Entry) -> Dict[str, str]:
    """Convert an entry to a dict (first value wins for repeated names)."""
    d: Dict[str, str] = {}
    for item in entry:
        if item[0] == "End":
            continue
        d.setdefault(item[0], item[1])
    return d


class Store:
    def __init__(self, prefs: Prefs):
        self.prefs = prefs
        self.lock = threading.RLock()

    # ------------------------------------------------------------------
    # paths
    # ------------------------------------------------------------------
    @property
    def rootdir(self) -> str:
        return self.prefs.rootdir

    def log_path(self, d: dt.date) -> str:
        return os.path.join(self.rootdir, f"log{d.year}", f"{d.month:02d}{d.day:02d}.tag")

    def month_summary_path(self, year: int, month: int) -> str:
        return os.path.join(self.rootdir, f"log{year}", f"{month:02d}.tag")

    def year_summary_path(self, year: int) -> str:
        return os.path.join(self.rootdir, f"log{year}", f"yearsumm{year}.tag")

    # ------------------------------------------------------------------
    # log files
    # ------------------------------------------------------------------
    @staticmethod
    def new_log_header(d: dt.date) -> Entry:
        return [("Tag-worklog-version", "1.0", None), ("Date", d.isoformat(), None),
                ("WeekDay", weekday_name(d), None), tf.END]

    def read_log(self, d: dt.date) -> List[Entry]:
        """Entries of a day's log; element 0 is the header. [] if no file."""
        return tf.read_file(self.log_path(d))

    def ensure_log(self, d: dt.date) -> List[Entry]:
        with self.lock:
            entries = self.read_log(d)
            if not entries:
                entries = [self.new_log_header(d)]
                tf.write_file(self.log_path(d), entries)
            return entries

    def append_log_entry(self, d: dt.date, entry: Entry) -> None:
        with self.lock:
            entries = self.ensure_log(d)
            entries.append(tf.ensure_end(entry))
            tf.write_file(self.log_path(d), entries)

    def replace_log_entry(self, d: dt.date, index: int, entry: Optional[Entry]) -> None:
        """Replace (or delete when entry is None) log entry `index` (1-based)."""
        with self.lock:
            entries = self.read_log(d)
            if index < 1 or index >= len(entries):
                raise StoreError("No such log entry")
            if entry is None:
                del entries[index]
            else:
                entries[index] = tf.ensure_end(entry)
            tf.write_file(self.log_path(d), entries)

    def update_log_header(self, d: dt.date, name: str, value: str,
                          endlabel: Optional[str] = None) -> None:
        with self.lock:
            entries = self.ensure_log(d)
            header = entries[0]
            if value == "" and endlabel is None:
                tf.remove_item(header, name)
            else:
                tf.set_or_replace(header, name, value, endlabel)
            entries[0] = header
            tf.write_file(self.log_path(d), entries)

    def set_last_entry_end(self, d: dt.date, end: str) -> bool:
        """Port of doadjstartOK's 'adjust previous end time'."""
        with self.lock:
            entries = self.read_log(d)
            if len(entries) < 2:
                return False
            last = entries[-1]
            if not tf.has_item(last, "EndTime"):
                return False
            tf.set_or_replace(last, "EndTime", end)
            tf.write_file(self.log_path(d), entries)
            return True

    def log_dates(self) -> List[dt.date]:
        """All dates that have a log file, sorted."""
        out = []
        for path in glob.glob(os.path.join(glob.escape(self.rootdir), "log*", "[0-9]*.tag")):
            year_dir = os.path.basename(os.path.dirname(path))
            m_year = re.fullmatch(r"log(\d+)", year_dir)
            m_day = re.fullmatch(r"(\d\d)(\d\d)\.tag", os.path.basename(path))
            if not (m_year and m_day):
                continue
            try:
                out.append(dt.date(int(m_year.group(1)), int(m_day.group(1)), int(m_day.group(2))))
            except ValueError:
                continue
        return sorted(out)

    def log_files_between(self, start: Optional[dt.date], end: Optional[dt.date]) -> List[dt.date]:
        """Port of dateRangeToLogfileList: existing log dates in [start, end]."""
        start = start or dt.date(2000, 1, 1)
        end = end or dt.date.today()
        return [d for d in self.log_dates() if start <= d <= end]

    def read_summary(self, path: str) -> str:
        entries = tf.read_file(path)
        if len(entries) < 2:
            return ""
        return tf.entry_val(entries[1], "Description")

    def write_summary(self, path: str, text: str) -> None:
        """Port of doMonthSummaryOK / doYearSummaryOK."""
        with self.lock:
            hdr: Entry = [("Tag-worklog-version", "1.0", None), tf.END]
            body: Entry = []
            tf.tag_append(body, "Description", text.strip(), "END_D")
            body.append(tf.END)
            tf.write_file(path, [hdr, body])

    # ------------------------------------------------------------------
    # projects
    # ------------------------------------------------------------------
    def read_projects(self) -> List[Entry]:
        entries = tf.read_file(self.prefs.projects_file)
        if not entries:
            entries = [[("Tag-accountproj-version", "1.0", None), tf.END]]
        return entries

    def write_projects(self, entries: List[Entry]) -> None:
        tf.write_file(self.prefs.projects_file, entries)

    @staticmethod
    def project_to_dict(entry: Entry) -> Dict[str, object]:
        flags = tf.entry_vals(entry, "Flags")
        flagset = set()
        for f in flags:
            # Tcl uses "string match -nocase *Flag*" via -contains
            for name in PROJECT_FLAGS:
                if name.lower() in f.lower():
                    flagset.add(name)
        end = tf.entry_val(entry, "EndDate")
        closed = bool(end) and end <= dt.date.today().isoformat()
        return {
            "name": tf.entry_val(entry, "Name"),
            "code": tf.entry_val(entry, "Code"),
            "start": tf.entry_val(entry, "StartDate"),
            "end": end,
            "expected_time": tf.entry_val(entry, "ExpectedTime"),
            "next_action_id": tf.entry_val(entry, "NextActionId"),
            "overheads": "Overheads" in flagset,
            "breaks": "Breaks" in flagset,
            "active": "Active" in flagset,
            "immutable": "Immutable" in flagset,
            "closed": closed,
        }

    def projects(self) -> List[Dict[str, object]]:
        return [self.project_to_dict(e) for e in self.read_projects()[1:]
                if tf.entry_val(e, "Name")]

    def project_map(self) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        for p in self.projects():
            out.setdefault(str(p["name"]), p)
        return out

    def open_project_names(self) -> List[str]:
        """Port of taglog_getList proj: open active projects first, then others."""
        ps = [p for p in self.projects() if not p["closed"]]
        return [str(p["name"]) for p in ps if p["active"]] + \
               [str(p["name"]) for p in ps if not p["active"]]

    def save_project(self, data: Dict[str, object], original_name: Optional[str] = None) -> None:
        """Add (original_name None) or edit a project."""
        name = str(data.get("name") or "").strip()
        if not name:
            raise StoreError("Project name is required")
        with self.lock:
            entries = self.read_projects()
            idx = None
            for i, e in enumerate(entries[1:], start=1):
                if tf.entry_val(e, "Name") == (original_name if original_name is not None else name):
                    idx = i
                    break
            if original_name is None:
                if idx is not None:
                    raise StoreError(f"Project '{name}' already exists")
                # Port of addProjectOK
                e: Entry = []
                tf.tag_append(e, "Name", name)
                tf.tag_append(e, "NextActionId", "1")
                tf.tag_append(e, "Code", str(data.get("code") or ""))
                tf.tag_append(e, "StartDate", str(data.get("start") or ""))
                tf.tag_append(e, "EndDate", str(data.get("end") or ""))
                tf.tag_append(e, "ExpectedTime", str(data.get("expected_time") or ""))
                for flag in PROJECT_FLAGS:
                    if data.get(flag.lower()):
                        tf.tag_append(e, "Flags", flag)
                e.append(tf.END)
                entries.append(e)
            else:
                if idx is None:
                    raise StoreError(f"No project named '{original_name}'")
                if name != original_name and any(
                        tf.entry_val(x, "Name") == name for x in entries[1:]):
                    raise StoreError(f"Project '{name}' already exists")
                # Port of inputProjectOK / doEditProjectsOK
                e = entries[idx]
                tf.set_or_replace(e, "Name", name)
                for flag in PROJECT_FLAGS:
                    tf.set_or_replace_flag(e, "Flags", flag, bool(data.get(flag.lower())))
                for key, field in (("code", "Code"), ("start", "StartDate"),
                                   ("end", "EndDate"), ("expected_time", "ExpectedTime")):
                    if key in data:
                        tf.set_or_replace(e, field, str(data.get(key) or ""))
                entries[idx] = e
            self.write_projects(entries)

    def delete_project(self, name: str) -> None:
        with self.lock:
            entries = self.read_projects()
            new = [entries[0]] + [e for e in entries[1:] if tf.entry_val(e, "Name") != name]
            if len(new) == len(entries):
                raise StoreError(f"No project named '{name}'")
            self.write_projects(new)

    def next_project_action_index(self, name: str) -> Optional[int]:
        """Port of incprojactindex."""
        with self.lock:
            entries = self.read_projects()
            for i, e in enumerate(entries):
                if tf.entry_val(e, "Name") == name:
                    try:
                        t = int(tf.entry_val(e, "NextActionId") or 0)
                    except ValueError:
                        t = 0
                    t += 1
                    tf.set_or_replace(e, "NextActionId", str(t))
                    entries[i] = e
                    self.write_projects(entries)
                    return t
        return None

    # ------------------------------------------------------------------
    # actions
    # ------------------------------------------------------------------
    def read_actions(self) -> List[Entry]:
        entries = tf.read_file(self.prefs.actions_file)
        if not entries:
            entries = [[("Tag-action-version", "1.0", None), tf.END]]
        return entries

    def write_actions(self, entries: List[Entry]) -> None:
        tf.write_file(self.prefs.actions_file, entries)

    def find_action(self, entries: List[Entry], action_id: str) -> int:
        for i, e in enumerate(entries):
            if i > 0 and tf.entry_val(e, "Id") == action_id:
                return i
        return -1

    def actions(self) -> List[Entry]:
        return self.read_actions()[1:]

    def get_action(self, action_id: str) -> Optional[Entry]:
        entries = self.read_actions()
        i = self.find_action(entries, action_id)
        return entries[i] if i >= 0 else None

    def active_actions(self) -> List[Dict[str, str]]:
        """Port of getactiveactions: Active actions sorted by priority."""
        out = []
        for e in self.actions():
            if tf.entry_val(e, "Status") == "Active":
                try:
                    pr = int(tf.entry_val(e, "Priority") or 50)
                except ValueError:
                    pr = 50
                out.append({"id": tf.entry_val(e, "Id"), "title": tf.entry_val(e, "Title"),
                            "project": tf.entry_val(e, "Project"), "priority": pr,
                            "subtask_of": tf.entry_val(e, "Subtask-of")})
        out.sort(key=lambda a: a["priority"])
        return out

    def _auto_action_id(self, project: str, now: dt.datetime) -> str:
        """Port of setupAutoId."""
        if project:
            seq = self.next_project_action_index(project)
            if seq is not None:
                return f"{project.replace(' ', '_')}.{seq}"
        return "taglog." + now.strftime("%Y%m%d%H%M%S")

    @staticmethod
    def build_action(fields: Dict[str, str], extra: Optional[List[Tuple[str, str, Optional[str]]]] = None) -> Entry:
        """Port of getact_input_fields (+ extra fields kept on edit)."""
        e: Entry = []
        for name in ACTION_FIELDS:
            tf.tag_append(e, name, (fields.get(name) or "").strip())
        for name in ACTION_TEXT_FIELDS:
            tf.tag_append(e, name, (fields.get(name) or "").strip(), "END_D")
        for item in extra or []:
            e.append(item)
        e.append(tf.END)
        return e

    def create_action(self, fields: Dict[str, str], now: Optional[dt.datetime] = None) -> Entry:
        """Port of actionInputOK / writeaction."""
        now = now or dt.datetime.now()
        fields = {k: str(v) for k, v in fields.items() if v is not None}
        if not fields.get("Title", "").strip():
            raise StoreError("An action needs a title")
        with self.lock:
            entries = self.read_actions()
            if not fields.get("Id") or fields.get("Id") == "*Auto*":
                base = self._auto_action_id(fields.get("Project", ""), now)
                fields["Id"] = base
                n = 1
                while self.find_action(entries, fields["Id"]) >= 0:
                    n += 1
                    fields["Id"] = f"{base}-{n}"
            if self.find_action(entries, fields["Id"]) >= 0:
                raise StoreError(f"An action with Id '{fields['Id']}' already exists")
            fields.setdefault("Date", now.strftime("%Y-%m-%d %H:%M"))
            fields.setdefault("Priority", "50")
            fields.setdefault("Status", "Pending")
            if fields.get("Active-after") and fields.get("Status") != "Delegated":
                fields["Status"] = "Blocked"
            action = self.build_action(fields)
            entries.append(action)
            if fields.get("Subtask-of"):
                self._add_subtask(entries, fields["Subtask-of"], fields["Id"])
            self.write_actions(entries)
            return action

    @staticmethod
    def _add_subtask(entries: List[Entry], parent_id: str, sub_id: str) -> None:
        """Port of Update_subtasks for a single subtask."""
        for i, e in enumerate(entries):
            if i > 0 and tf.entry_val(e, "Id") == parent_id:
                subs = tf.entry_val(e, "Subtasks")
                if sub_id in subs.split(","):
                    return
                subs = sub_id if not subs else f"{subs},{sub_id}"
                tf.set_or_replace(e, "Subtasks", subs)
                entries[i] = e
                return

    def edit_action(self, action_id: str, fields: Dict[str, str]) -> Entry:
        """Port of actionEditOK: standard fields rebuilt, other fields kept."""
        with self.lock:
            entries = self.read_actions()
            i = self.find_action(entries, action_id)
            if i < 0:
                raise StoreError(f"No action '{action_id}'")
            old = entries[i]
            known = set(ACTION_FIELDS) | set(ACTION_TEXT_FIELDS) | {"End"}
            extra = [item for item in old if item[0] not in known]
            new_fields = {k: str(v) for k, v in fields.items() if v is not None}
            new_fields["Id"] = action_id
            for name in ACTION_FIELDS + ACTION_TEXT_FIELDS:
                if name not in new_fields:
                    new_fields[name] = tf.entry_val(old, name)
            if new_fields.get("Subtask-of") and \
                    new_fields["Subtask-of"] != tf.entry_val(old, "Subtask-of"):
                self._add_subtask(entries, new_fields["Subtask-of"], action_id)
            action = self.build_action(new_fields, extra)
            entries[i] = action
            self.write_actions(entries)
            return action

    def change_action_state(self, action_id: str, new_state: str, note: str = "",
                            now: Optional[dt.datetime] = None) -> Dict[str, object]:
        """Port of actNewState. Returns {'next_action': id-or-''}."""
        if new_state not in VALID_STATES:
            raise StoreError(f"Invalid state {new_state}")
        now = now or dt.datetime.now()
        result: Dict[str, object] = {"next_action": ""}
        with self.lock:
            entries = self.read_actions()
            i = self.find_action(entries, action_id)
            if i < 0:
                raise StoreError(f"No action '{action_id}'")
            e = entries[i]
            tf.set_or_replace(e, "Status", new_state)
            # The original always inserts a new <State>-date item before End
            tf.ensure_end(e)
            e.insert(len(e) - 1, (f"{new_state}-date", now.strftime("%Y-%m-%d %H:%M"), None))
            if note.strip():
                e.insert(len(e) - 1, (f"{new_state}-note", note.strip(), "END_D"))
            entries[i] = e
            if new_state == "Completed":
                nxt = tf.entry_val(e, "Next-action")
                if nxt:
                    j = self.find_action(entries, nxt)
                    if j >= 0:
                        ne = entries[j]
                        tf.set_or_replace(ne, "Status", "Active")
                        tf.ensure_end(ne)
                        ne.insert(len(ne) - 1, ("Active-date", now.strftime("%Y-%m-%d %H:%M"), None))
                        entries[j] = ne
                        result["next_action"] = nxt
            self.write_actions(entries)
        return result

    def revise_action(self, action_id: str, expected_date: str, expected_time: str,
                      summary: str = "", today: Optional[dt.date] = None) -> bool:
        """Port of doReviseAction."""
        today = today or dt.date.today()
        with self.lock:
            entries = self.read_actions()
            i = self.find_action(entries, action_id)
            if i < 0:
                raise StoreError(f"No action '{action_id}'")
            e = entries[i]
            revised = False
            if expected_date and expected_date != tf.entry_val(e, "Expected-completed-date"):
                if not tf.entry_val(e, "Original-expected-completed-date"):
                    tf.set_or_replace(e, "Original-expected-completed-date",
                                      tf.entry_val(e, "Expected-completed-date"))
                tf.set_or_replace(e, "Expected-completed-date", expected_date)
                revised = True
            if expected_time and expected_time != tf.entry_val(e, "Expected-time"):
                if not tf.entry_val(e, "Original-expected-time"):
                    tf.set_or_replace(e, "Original-expected-time", tf.entry_val(e, "Expected-time"))
                tf.set_or_replace(e, "Expected-time", expected_time)
                revised = True
            if summary.strip():
                tf.set_or_replace(e, "Summary", summary.strip(), "END_D")
                revised = True
            if revised:
                tf.set_or_replace(e, "Revised-date", today.isoformat())
                entries[i] = e
                self.write_actions(entries)
            return revised

    def due_time_blocked(self, now: Optional[dt.datetime] = None) -> List[Dict[str, str]]:
        """Blocked/Delegated actions whose Active-after time has passed."""
        now = now or dt.datetime.now()
        out = []
        for e in self.actions():
            if tf.entry_val(e, "Status") in ("Blocked", "Delegated"):
                aa = parse_datetime(tf.entry_val(e, "Active-after"))
                if aa and aa <= now:
                    out.append({"id": tf.entry_val(e, "Id"), "title": tf.entry_val(e, "Title"),
                                "status": tf.entry_val(e, "Status"),
                                "active_after": tf.entry_val(e, "Active-after"),
                                "description": tf.entry_val(e, "Description")})
        return out

    # ------------------------------------------------------------------
    # contacts (read-only in this version)
    # ------------------------------------------------------------------
    def contact_ids(self) -> List[str]:
        return [tf.entry_val(e, "Id") for e in tf.read_file(self.prefs.contacts_file)[1:]
                if tf.entry_val(e, "Id")]

    # ------------------------------------------------------------------
    # history of an action (port of displayAnActionHistory)
    # ------------------------------------------------------------------
    def action_history(self, action_id: str, since: Optional[dt.date] = None) -> Dict[str, object]:
        rows = []
        total = 0
        for d in self.log_files_between(since, None):
            for e in self.read_log(d)[1:]:
                if tf.entry_val(e, "Action") == action_id:
                    dur = entry_duration(tf.entry_val(e, "StartTime"), tf.entry_val(e, "EndTime"))
                    total += dur
                    rows.append({"date": d.isoformat(), "start": tf.entry_val(e, "StartTime"),
                                 "end": tf.entry_val(e, "EndTime"), "duration": dur,
                                 "activity": tf.entry_val(e, "Activity"),
                                 "description": tf.entry_val(e, "Description")})
        return {"entries": rows, "total": total}
