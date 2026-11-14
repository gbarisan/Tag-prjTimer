"""Help topics (port of taglog_help.tcl).

The original help files ``taglog_help_<lang>.tag`` are shipped unchanged in
``taglog_web/help/``. ``taglog_help_web_<lang>.tag`` holds topics rewritten
for this version (the originals describe the Tcl/Tk windows); a topic there
replaces the original topic with the same Id.

Lookup order for a topic in language L:
  web_L, original L, web_en, original en, then the UNKNOWN topic.
"""

from __future__ import annotations

import os
import re
import threading
from typing import Dict, List, Tuple

from . import tagfile as tf

HELP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "help")

# Language names as offered by the original preferences dialog
LANGUAGE_NAMES = {
    "en": "English", "de": "Deutsch", "es": "Español", "fr": "Français",
    "el": "Ελληνικά", "it": "Italiano", "nl": "Nederlands",
}

# Topics about features of the original that this version does not have
# (yet). They are listed separately in the help browser.
NOT_IN_THIS_VERSION_PREFIXES = (
    "addcontact", "contact", "cview_", "viewc", "smtp_", "actmail", "mailtb",
    "led_", "add_old_log", "alwin_", "lvsa_", "archiveproject", "archproj",
    "project_update", "editprefs_projects_url", "editprefs_start_procs",
    "editprefs_history_win_depth", "editprefs_current_win_depth",
    "editprefs_id_prefix", "prefs_docdir", "prefs_libsdir", "actsel_filename",
    "actsel_showfields", "actsel_id", "actsel_title", "timebook_year",
    "timebook_weekno", "timebook_numweeks",
)

# Explicit titles for topics whose Id is not self-explanatory.
TITLES = {
    "About": "About Taglog", "UNKNOWN": "Unknown topic", "introduction": "Introduction",
    "file": "Days, logs and pausing", "actions": "Actions", "projects": "Projects",
    "reports": "Reports", "contacts": "Contacts", "actinput": "Entering an action",
    "actsel": "Choosing which actions to show", "actreminder": "Today's actions",
    "addproject": "Adding a project", "editproject": "Editing projects",
    "viewproject": "Project times today", "adjstart": "Adjusting the start time",
    "logedit": "Editing log entries", "logsel": "Searching the log",
    "summarybox": "Day summary", "endbutton": "Current action buttons",
    "editprefs": "Settings", "timebooksel": "Weekly bookings report",
    "timebooksel_spreadoverheads": "Spreading overheads",
    "timebooksel_timeformat": "Report time format", "project_expectedtime":
    "Project expected time", "ep_enddate": "Project end date", "hint_help": "About the hints",
    "hint_activity_pre_meeting": "Hint: preparing for a meeting",
    "hint_problem_actions_overrun": "Hint: actions overrun",
    "hint_problem_interruptions": "Hint: interruptions", "stack": "Interrupt, Push and Pop",
    "contactview": "Viewing contacts", "viewc": "Viewing contacts",
    "add_old_log": "Adding an old log", "alwin_project": "Old log window: project",
    "lvsa_dirname": "Saving the log view", "archiveproject": "Archiving projects",
    "logedit_actiontitle": "Log entry field: action title",
    "actinput_expected_completed_date": "Action field: expected completed date",
    "actmail_message": "Mailing an action: message", "actmail_to": "Mailing an action: to",
}

PREFIX_TITLES = [
    ("actinput_", "Action field: "), ("addcontact_", "Contact field: "),
    ("cview_", "Contact view: "), ("logedit_", "Log entry field: "), ("logsel_", "Searching the log: "),
    ("actsel_", "Selecting actions: "), ("editprefs_", "Setting: "),
    ("prefs_", "Setting: "), ("smtp_", "Email setting: "), ("led_", "Log editor: "),
    ("timebook_", "Weekly bookings: "), ("hint_", "Hint: "),
]

GROUPS = [
    ("start", "Getting started"), ("today", "Today page"), ("log", "Log & search"),
    ("actions", "Actions"), ("projects", "Projects"), ("reports", "Reports"),
    ("settings", "Settings"), ("hints", "Hints"), ("other", "Other"),
    ("missing", "Features not in this version"),
]

_GROUP_OF = {
    "About": "start", "introduction": "start", "file": "start",
    "adjstart": "today", "endbutton": "today", "stack": "today", "viewproject": "today",
    "actreminder": "today", "summarybox": "today",
    "logedit": "log", "logsel": "log",
    "actions": "actions", "actinput": "actions",
    "projects": "projects", "addproject": "projects", "editproject": "projects",
    "project_expectedtime": "projects", "ep_enddate": "projects",
    "reports": "reports", "gantt": "reports", "editprefs": "settings",
}


def _humanize(s: str) -> str:
    s = s.replace("_", " ").replace("-", " ").strip()
    return s[:1].upper() + s[1:]


def topic_title(tid: str, explicit: str = "") -> str:
    if explicit:
        return explicit
    if tid in TITLES:
        return TITLES[tid]
    for prefix, label in PREFIX_TITLES:
        if tid.startswith(prefix):
            return label + _humanize(tid[len(prefix):]).lower()
    return _humanize(tid)


def topic_group(tid: str) -> str:
    if tid.startswith(NOT_IN_THIS_VERSION_PREFIXES) or tid in ("contacts", "contactview"):
        return "missing"
    if tid in _GROUP_OF:
        return _GROUP_OF[tid]
    if tid.startswith(("actinput_", "actsel")):
        return "actions"
    if tid.startswith(("logedit_", "logsel_")):
        return "log"
    if tid.startswith(("timebook", "activeActions")):
        return "reports"
    if tid.startswith(("prefs_", "editprefs_")):
        return "settings"
    if tid.startswith("hint_"):
        return "hints"
    return "other"


def _read_help_file(path: str) -> List[tf.Entry]:
    """Help files are UTF-8, except some older translations in Latin-1."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    return tf.parse(text)


class HelpLibrary:
    def __init__(self, directory: str = HELP_DIR):
        self.directory = directory
        self._cache: Dict[str, Tuple[float, Dict[str, Dict[str, str]]]] = {}
        self._lock = threading.Lock()

    def _file(self, name: str) -> Dict[str, Dict[str, str]]:
        path = os.path.join(self.directory, f"taglog_help_{name}.tag")
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return {}
        with self._lock:
            cached = self._cache.get(name)
            if cached and cached[0] == mtime:
                return cached[1]
            topics: Dict[str, Dict[str, str]] = {}
            for e in _read_help_file(path)[1:]:
                tid = tf.entry_val(e, "Id")
                if tid and tid not in topics:
                    topics[tid] = {"text": tf.entry_val(e, "Description"),
                                   "title": tf.entry_val(e, "Title")}
            self._cache[name] = (mtime, topics)
            return topics

    def languages(self) -> List[Dict[str, object]]:
        out = []
        for fn in sorted(os.listdir(self.directory)):
            m = re.fullmatch(r"taglog_help_([a-z]{2})\.tag", fn)
            if m:
                code = m.group(1)
                out.append({"code": code, "name": LANGUAGE_NAMES.get(code, code),
                            "topics": len([t for t in self._file(code) if t != "UNKNOWN"])})
        out.sort(key=lambda x: (x["code"] != "en", -int(x["topics"]), x["code"]))
        return out

    def _sources(self, lang: str) -> List[Tuple[str, str, bool]]:
        """(file name, language, adapted) in lookup order."""
        order = [(f"web_{lang}", lang, True), (lang, lang, False)]
        if lang != "en":
            order += [("web_en", "en", True), ("en", "en", False)]
        return order

    def all_ids(self) -> List[str]:
        ids = set(self._file("en")) | set(self._file("web_en"))
        ids.discard("UNKNOWN")
        return sorted(ids, key=str.lower)

    def topic(self, tid: str, lang: str = "en", version: str = "") -> Dict[str, object]:
        lang = lang if re.fullmatch(r"[a-z]{2}", lang or "") else "en"
        adapted_ids = set(self._file("web_en"))
        for name, used_lang, adapted in self._sources(lang):
            t = self._file(name).get(tid)
            if t is None:
                continue
            text = t["text"]
            if version:
                text = text.replace("$1", version)
            title_src = t["title"] or self._file("web_en").get(tid, {}).get("title", "")
            return {
                "id": tid, "found": True, "title": topic_title(tid, title_src),
                "text": text, "lang": used_lang, "requested_lang": lang,
                "translated": used_lang == lang,
                "adapted": adapted,
                # an original (non-adapted) text for a topic that was rewritten
                # in English describes the old Tcl/Tk windows
                "describes_original_ui": (not adapted) and tid in adapted_ids,
                "group": topic_group(tid),
            }
        # The original UNKNOWN topic asks readers to e-mail translations to
        # the original author, which does not fit a missing topic here.
        text = "There is no help for this item."
        return {"id": tid, "found": False, "title": topic_title(tid), "text": text,
                "lang": lang, "requested_lang": lang, "translated": True, "adapted": False,
                "describes_original_ui": False, "group": topic_group(tid)}

    def index(self, lang: str = "en") -> Dict[str, object]:
        lang = lang if re.fullmatch(r"[a-z]{2}", lang or "") else "en"
        own = set(self._file(lang)) | set(self._file(f"web_{lang}"))
        topics = []
        for tid in self.all_ids():
            title = (self._file(f"web_{lang}").get(tid, {}).get("title") or
                     self._file("web_en").get(tid, {}).get("title") or "")
            topics.append({"id": tid, "title": topic_title(tid, title), "group": topic_group(tid),
                           "translated": tid in own})
        return {"languages": self.languages(), "lang": lang,
                "groups": [{"id": g, "name": n} for g, n in GROUPS], "topics": topics}

    def search(self, query: str, lang: str = "en") -> List[str]:
        """Ids of topics whose title or text contains all the query words."""
        words = [w for w in query.lower().split() if w]
        if not words:
            return []
        out = []
        for tid in self.all_ids():
            t = self.topic(tid, lang)
            hay = f"{t['title']}\n{t['text']}\n{tid}".lower()
            if all(w in hay for w in words):
                out.append(tid)
        return out
