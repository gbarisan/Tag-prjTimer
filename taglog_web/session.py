"""The "current entry" being timed (main window state of the Tcl program).

In the original program this state lives in global variables and is lost
when you Quit. Here it is also saved to ``<rootdir>/.taglog-web-state.json``
after every change so that a browser reload or a restart of the server does
not lose the description you are typing. That file is ignored by the
original Tcl/Tk taglog.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import re
from typing import Callable, Dict, List, Optional

from . import tagfile as tf
from .store import Store
from .timeutil import parse_hms, tcl_format

STATE_FILE = ".taglog-web-state.json"

EDITABLE_FIELDS = ("start", "project", "activity", "action", "action_title",
                   "contact", "rate", "description")


class Session:
    def __init__(self, store: Store, clock: Callable[[], dt.datetime] = dt.datetime.now):
        self.store = store
        self.clock = clock
        # Share the store's re-entrant lock so the background ticker and the
        # request handlers can never take two locks in opposite orders.
        self.lock = store.lock
        self.state: Dict[str, object] = {}
        self._load()

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    @property
    def path(self) -> str:
        return os.path.join(self.store.rootdir, STATE_FILE)

    def _fresh(self, now: dt.datetime) -> Dict[str, object]:
        return {
            "date": now.date().isoformat(),
            "start": self._fmt(now),
            "project": "", "activity": "", "action": "", "action_title": "",
            "contact": "", "rate": "", "description": "",
            "stack_info": "", "stack": [], "running": True,
            "last_seen": now.timestamp(),
        }

    def _load(self) -> None:
        now = self.clock()
        state = self._fresh(now)
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                for k in state:
                    if k in saved:
                        state[k] = saved[k]
        except (OSError, ValueError):
            pass
        self.state = state
        self.tick()

    def save(self) -> None:
        with self.lock:
            os.makedirs(self.store.rootdir, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=1)
            os.replace(tmp, self.path)

    def reload_for_new_rootdir(self) -> None:
        with self.lock:
            self._load()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _fmt(self, t: dt.datetime) -> str:
        return tcl_format(self.store.prefs.time_format, t.hour, t.minute, t.second)

    @property
    def date(self) -> dt.date:
        return dt.date.fromisoformat(str(self.state["date"]))

    def snapshot(self) -> Dict[str, object]:
        with self.lock:
            s = dict(self.state)
            s["stack_depth"] = len(self.state.get("stack") or [])
            now = self.clock()
            s["now"] = self._fmt(now)
            if s.get("running"):
                s["elapsed"] = max(0, parse_hms(self._fmt(now)) - parse_hms(str(s["start"])))
            else:
                s["elapsed"] = 0
            return s

    def update(self, fields: Dict[str, object]) -> None:
        with self.lock:
            for k in EDITABLE_FIELDS:
                if k in fields and fields[k] is not None:
                    self.state[k] = str(fields[k])
            self.save()

    def _build_entry(self, end: str, now: dt.datetime) -> tf.Entry:
        """Port of getlogentry."""
        s = self.state
        e: tf.Entry = []
        tf.tag_append(e, "Id", now.strftime("%Y%m%d%H%M%S"))
        tf.tag_append(e, "StartTime", str(s["start"]))
        tf.tag_append(e, "EndTime", end)
        tf.tag_append(e, "Project", str(s["project"]))
        tf.tag_append(e, "Rate", str(s["rate"]))
        tf.tag_append(e, "Contact", str(s["contact"]))
        tf.tag_append(e, "Action", str(s["action"]))
        tf.tag_append(e, "ActionTitle", str(s["action_title"]))
        tf.tag_append(e, "Activity", str(s["activity"]))
        tf.tag_append(e, "Stack-info", str(s["stack_info"]))
        tf.tag_append(e, "Description", str(s["description"]).strip(), "END_D")
        e.append(tf.END)
        return e

    def _write_current(self, end: str, now: dt.datetime) -> str:
        """Port of writelog: append the current entry to its day's log."""
        entry = self._build_entry(end, now)
        self.store.append_log_entry(self.date, entry)
        return tf.entry_val(entry, "Id")

    # ------------------------------------------------------------------
    # main window operations
    # ------------------------------------------------------------------
    def next(self, activity: Optional[str] = "", project: Optional[str] = None) -> str:
        """Port of donext: finish the current entry and start a new one."""
        with self.lock:
            self.tick()
            now = self.clock()
            end = self._fmt(now)
            log_id = ""
            if self.state.get("running"):
                log_id = self._write_current(end, now)
            s = self.state
            s["description"] = ""
            s["action"] = ""
            s["action_title"] = ""
            s["contact"] = ""
            si = str(s.get("stack_info") or "")
            if si.startswith("!"):
                s["stack_info"] = "+" + si[1:]
            s["start"] = end
            s["running"] = True
            s["activity"] = activity or ""
            if project:
                s["project"] = project
            self.save()
            return log_id

    def pause(self) -> None:
        """Port of dopause."""
        with self.lock:
            self.tick()
            if not self.state.get("running"):
                return
            now = self.clock()
            self._write_current(self._fmt(now), now)
            self.state["description"] = ""
            self.state["start"] = "pause"
            self.state["running"] = False
            self.save()

    def resume(self) -> None:
        """Port of doresume."""
        with self.lock:
            now = self.clock()
            self.state["date"] = now.date().isoformat()
            self.state["start"] = self._fmt(now)
            self.state["running"] = True
            self.state["last_seen"] = now.timestamp()
            self.save()

    def set_current_action(self, action_id: str) -> None:
        """Port of setcurrentAction."""
        with self.lock:
            if not action_id:
                self.state["action"] = ""
                self.state["action_title"] = ""
            else:
                a = self.store.get_action(action_id)
                if a is None:
                    raise ValueError(f"No action '{action_id}'")
                self.state["action"] = action_id
                self.state["action_title"] = tf.entry_val(a, "Title")
                self.state["project"] = tf.entry_val(a, "Project")
            self.save()

    def finish_current_action(self, new_state: str) -> Dict[str, object]:
        """Port of actCompleteCurrent / actAbortCurrent."""
        with self.lock:
            action_id = str(self.state.get("action") or "")
            if not action_id:
                return {"next_action": ""}
            self.next("")
            result = self.store.change_action_state(action_id, new_state, now=self.clock())
            nxt = str(result.get("next_action") or "")
            if nxt:
                self.set_current_action(nxt)
            return result

    def push(self, kind: str) -> None:
        """Port of stack_push: kind '!' = interruption, '+' = push."""
        if kind not in ("!", "+"):
            raise ValueError("kind must be ! or +")
        with self.lock:
            frame = {"project": self.state["project"], "action_title": self.state["action_title"],
                     "action": self.state["action"]}
            log_id = self.next("")
            frame["log_id"] = log_id
            stack: List[Dict[str, object]] = list(self.state.get("stack") or [])
            stack.append(frame)
            self.state["stack"] = stack
            self.state["stack_info"] = f"{kind} {log_id}"
            self.save()

    def pop(self) -> None:
        """Port of stack_pop."""
        with self.lock:
            stack = list(self.state.get("stack") or [])
            if not stack:
                return
            self.next("")
            frame = stack.pop()
            self.state["project"] = frame.get("project", "")
            self.state["action_title"] = frame.get("action_title", "")
            self.state["action"] = frame.get("action", "")
            self.state["stack_info"] = f"- {frame.get('log_id', '')}" if stack else ""
            self.state["stack"] = stack
            self.save()

    def adjust_start(self, new_start: str, adjust_prev_end: bool) -> None:
        """Port of doadjstartOK."""
        new_start = new_start.strip()
        if not re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", new_start):
            raise ValueError("Start time must look like H:MM or H:MM:SS")
        with self.lock:
            if not self.state.get("running"):
                raise ValueError("Taglog is paused; press Resume first")
            now = self.clock()
            if self.date == now.date() and parse_hms(new_start) > parse_hms(self._fmt(now)):
                raise ValueError(f"{new_start} is in the future")
            if adjust_prev_end:
                log = self.store.read_log(self.date)
                if len(log) > 1:
                    prev_start = tf.entry_val(log[-1], "StartTime")
                    if prev_start and parse_hms(new_start) < parse_hms(prev_start):
                        raise ValueError(
                            f"{new_start} is before the previous entry started ({prev_start}). "
                            "Edit or delete the previous entry first, or don't change its end time.")
                self.store.set_last_entry_end(self.date, new_start)
            self.state["start"] = new_start
            self.save()

    # ------------------------------------------------------------------
    # midnight handling (port of handleMidnight, made restart-safe)
    # ------------------------------------------------------------------
    def tick(self) -> None:
        """Call regularly. Rolls the entry over to a new day when needed.

        If the server was running at midnight the entry is closed at
        23:59:59 and a new one starts at 0:00:00, as the original did. If the
        server was not running (e.g. the Mac was off), the entry is closed at
        the last time the server was seen, and a new entry starts now.
        """
        with self.lock:
            now = self.clock()
            try:
                entry_date = self.date
            except (ValueError, KeyError):
                self.state["date"] = now.date().isoformat()
                entry_date = now.date()
            if entry_date < now.date():
                last_seen = dt.datetime.fromtimestamp(float(self.state.get("last_seen") or 0))
                alive_at_midnight = last_seen.date() >= now.date() - dt.timedelta(days=1) and \
                    (now - last_seen) < dt.timedelta(minutes=10)
                if self.state.get("running"):
                    if alive_at_midnight and entry_date == now.date() - dt.timedelta(days=1):
                        end = tcl_format(self.store.prefs.time_format, 23, 59, 59)
                        new_start = tcl_format(self.store.prefs.time_format, 0, 0, 0)
                    else:
                        if last_seen.date() == entry_date:
                            end = self._fmt(last_seen)
                        else:
                            end = tcl_format(self.store.prefs.time_format, 23, 59, 59)
                        new_start = self._fmt(now)
                    # Close the entry in the old day's file
                    self._write_current(end, now)
                    s = self.state
                    s["description"] = ""
                    s["action"] = ""
                    s["action_title"] = ""
                    s["contact"] = ""
                    s["start"] = new_start
                self.state["date"] = now.date().isoformat()
            self.state["last_seen"] = now.timestamp()
            self.save()
