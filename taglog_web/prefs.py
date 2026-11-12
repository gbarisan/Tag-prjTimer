"""Read and write taglog's preferences file (~/.taglog).

The original program `source`s ~/.taglog as Tcl code. We do not run Tcl;
instead we parse top-level ``set name value`` commands, which is what
taglog's own "Preferences" dialog writes (see savePrefs in taglog_init.tcl).
Anything else in the file (procs, command substitutions, ...) is ignored and
reported in ``Prefs.warnings``.

When saving, only the ``set`` lines for changed settings are rewritten; all
other lines, and everything below the
"# above this line is automatically saved" marker, are preserved verbatim, so
the original Tcl/Tk taglog keeps working with the same file.
"""

from __future__ import annotations

import os
import re
from typing import Dict, List, Optional, Tuple

HEADER = "# Preferences for taglog"
MARKER = "# above this line is automatically saved - put your changes below here -"
MARKER_PREFIX = "# above this line is automatically saved"

# Defaults from initialise in taglog_init.tcl
DEFAULT_ACTIVITIES = [
    "phone-in", "phone-out", "meeting", "meeting-preparation", "meeting-review",
    "email", "reading", "programming", "writing", "thinking", "service-break",
    "informal-discussion",
]

DEFAULTS: Dict[str, object] = {
    "rootdir": "~/diary",
    "actionsfilename": "",
    "projectsfilename": "",
    "contactsfilename": "",
    "activitiesfilename": "",
    "dateformat_view": "YYYY-MM-DD",
    "currentTimeFormat": "%d:%02d:%02d",
    "showtime_hours_per_day": "7.58",
    "showtime_spreadoverheads": "byweek",
    "showtime_format": "1",
    "showtime_bookbycode": "0",
    "timebook_startlastweek": "1",
    "num_today_actions": "3",
    "language": "en",
    "id_prefix": "",
}

# Settings the web UI is allowed to change.
EDITABLE = [
    "rootdir", "activitiesfilename", "dateformat_view", "currentTimeFormat",
    "showtime_hours_per_day", "showtime_spreadoverheads",
    "timebook_startlastweek", "num_today_actions",
]


class TclParseError(Exception):
    pass


# ---------------------------------------------------------------------------
# Minimal Tcl word parser
# ---------------------------------------------------------------------------

class _Unsupported(Exception):
    """Raised when a word needs command substitution or unknown variables."""


_BACKSLASH = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\", '"': '"', "$": "$",
              "[": "[", "]": "]", "{": "{", "}": "}", " ": " ", ";": ";"}


def _subst(text: str, variables: Dict[str, object]) -> str:
    """Backslash and $variable substitution; '[' raises _Unsupported."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "\n":
                out.append(" ")
                i += 2
                while i < n and text[i] in " \t":
                    i += 1
                continue
            out.append(_BACKSLASH.get(nxt, nxt))
            i += 2
            continue
        if c == "[":
            raise _Unsupported("command substitution")
        if c == "$":
            m = re.match(r"\$(?:\{([^}]*)\}|([A-Za-z0-9_]+(?:::[A-Za-z0-9_]+)*)(\([^)]*\))?)", text[i:])
            if not m or (m.group(1) is None and m.group(2) is None):
                out.append("$")
                i += 1
                continue
            if m.group(3):
                raise _Unsupported("array variable")
            name = m.group(1) if m.group(1) is not None else m.group(2)
            if name not in variables:
                raise _Unsupported(f"unknown variable {name}")
            val = variables[name]
            out.append(" ".join(val) if isinstance(val, list) else str(val))
            i += len(m.group(0))
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _parse_commands(script: str) -> List[Tuple[List[Tuple[str, str]], int, int]]:
    """Split a Tcl script into commands.

    Returns a list of (words, start, end) where each word is
    (kind, raw_text) with kind in {'brace', 'quote', 'bare'} and start/end
    are character offsets of the command in the script.
    """
    cmds = []
    i = 0
    n = len(script)
    while i < n:
        # Skip whitespace and command separators
        while i < n and script[i] in " \t\r\n;":
            i += 1
        if i >= n:
            break
        if script[i] == "#":
            while i < n and script[i] != "\n":
                if script[i] == "\\" and i + 1 < n:
                    i += 1
                i += 1
            continue
        start = i
        words: List[Tuple[str, str]] = []
        while i < n and script[i] not in "\n;":
            c = script[i]
            if c in " \t\r":
                i += 1
                continue
            if c == "\\" and i + 1 < n and script[i + 1] == "\n":
                i += 2
                continue
            if c == "{":
                depth = 1
                j = i + 1
                while j < n and depth:
                    if script[j] == "\\":
                        j += 2
                        continue
                    if script[j] == "{":
                        depth += 1
                    elif script[j] == "}":
                        depth -= 1
                    j += 1
                if depth:
                    raise TclParseError("unbalanced braces")
                words.append(("brace", script[i + 1:j - 1]))
                i = j
            elif c == '"':
                j = i + 1
                while j < n and script[j] != '"':
                    if script[j] == "\\":
                        j += 1
                    elif script[j] == "[":
                        j = _skip_brackets(script, j)
                        continue
                    j += 1
                if j >= n:
                    raise TclParseError("unbalanced quotes")
                words.append(("quote", script[i + 1:j]))
                i = j + 1
            else:
                j = i
                while j < n and script[j] not in " \t\r\n;":
                    if script[j] == "\\":
                        j += 1
                    elif script[j] == "[":
                        j = _skip_brackets(script, j)
                        continue
                    j += 1
                words.append(("bare", script[i:j]))
                i = j
        cmds.append((words, start, i))
    return cmds


def _skip_brackets(script: str, j: int) -> int:
    depth = 0
    n = len(script)
    while j < n:
        c = script[j]
        if c == "\\":
            j += 2
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return j + 1
        j += 1
    raise TclParseError("unbalanced brackets")


def tcl_list(text: str) -> List[str]:
    """Split a Tcl list string into elements (no substitution)."""
    out: List[str] = []
    for kind, raw in _parse_commands(text.replace("\n", " "))[0][0] if text.strip() else []:
        out.append(raw if kind == "brace" else _subst(raw, {}))
    return out


def _word_value(kind: str, raw: str, variables: Dict[str, object]) -> str:
    if kind == "brace":
        return raw
    return _subst(raw, variables)


def tcl_quote(value: str) -> str:
    """Quote a value for a `set` line so Tcl reads it back unchanged."""
    if value == "":
        return '""'
    if re.fullmatch(r"[A-Za-z0-9_./:%~+,@=-]+", value):
        return value
    escaped = (value.replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$")
               .replace("[", "\\[").replace("]", "\\]").replace("\n", "\\n"))
    return f'"{escaped}"'


def expand_path(path: str) -> str:
    """Expand a leading ~ the way Tcl's file commands do."""
    if not path:
        return path
    return os.path.expanduser(path)


# ---------------------------------------------------------------------------
# Prefs
# ---------------------------------------------------------------------------

class Prefs:
    def __init__(self, prefs_path: Optional[str] = None, system_path: str = "/etc/taglog.conf"):
        self.prefs_path = prefs_path or os.path.expanduser("~/.taglog")
        self.system_path = system_path
        self.values: Dict[str, object] = dict(DEFAULTS)
        self.warnings: List[str] = []
        self.activities: List[str] = list(DEFAULT_ACTIVITIES)
        self.load()

    # -- loading ----------------------------------------------------------
    def load(self) -> None:
        self.values = dict(DEFAULTS)
        self.warnings = []
        self._activities_set_in_prefs = False
        for path in (self.system_path, self.prefs_path):
            if path and os.path.isfile(path):
                self._load_file(path)
        self._load_activities()

    def _load_file(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError as e:
            self.warnings.append(f"Could not read {path}: {e}")
            return
        try:
            cmds = _parse_commands(text)
        except TclParseError as e:
            self.warnings.append(f"{path}: could not parse ({e}); using defaults")
            return
        for words, _s, _e in cmds:
            if not words:
                continue
            if words[0] != ("bare", "set") or len(words) != 3:
                cmdname = words[0][1]
                if cmdname not in ("set",):
                    self.warnings.append(f"{os.path.basename(path)}: ignored Tcl command '{cmdname}'")
                continue
            name_kind, name = words[1]
            if name_kind != "bare" or not re.fullmatch(r"[A-Za-z0-9_]+", name):
                continue  # arrays such as smtpv(...) are not needed
            try:
                value = _word_value(*words[2], self.values)
            except _Unsupported as e:
                self.warnings.append(f"{os.path.basename(path)}: could not evaluate 'set {name}' ({e})")
                continue
            if name == "activities":
                try:
                    self.values["activities"] = tcl_list(value)
                    self._activities_set_in_prefs = True
                except TclParseError:
                    pass
                continue
            self.values[name] = value

    def _load_activities(self) -> None:
        fn = self.activities_file
        acts: Optional[List[str]] = None
        if fn and os.path.isfile(fn):
            try:
                with open(fn, "r", encoding="utf-8", errors="replace") as f:
                    acts = [a.strip() for a in f.read().split("\n")]
                acts = [a for a in acts if a]
            except OSError:
                acts = None
        if acts is None:
            v = self.values.get("activities")
            acts = list(v) if isinstance(v, list) else list(DEFAULT_ACTIVITIES)
        self.activities = acts

    # -- accessors --------------------------------------------------------
    def get(self, name: str, default: object = "") -> object:
        return self.values.get(name, default)

    def _path(self, name: str, fallback: str) -> str:
        v = str(self.values.get(name) or "")
        return expand_path(v) if v else os.path.join(self.rootdir, fallback)

    @property
    def rootdir(self) -> str:
        return expand_path(str(self.values.get("rootdir") or "~/diary"))

    @property
    def actions_file(self) -> str:
        return self._path("actionsfilename", "actions.tag")

    @property
    def projects_file(self) -> str:
        return self._path("projectsfilename", "projects.tag")

    @property
    def contacts_file(self) -> str:
        return self._path("contactsfilename", "contacts.tag")

    @property
    def activities_file(self) -> str:
        return self._path("activitiesfilename", "activities")

    @property
    def time_format(self) -> str:
        return str(self.values.get("currentTimeFormat") or "%d:%02d:%02d")

    @property
    def date_format(self) -> str:
        return str(self.values.get("dateformat_view") or "YYYY-MM-DD")

    @property
    def hours_per_day(self) -> float:
        try:
            v = float(str(self.values.get("showtime_hours_per_day")))
            return v if 0 < v < 24 else 7.58
        except ValueError:
            return 7.58

    @property
    def num_today_actions(self) -> int:
        try:
            v = int(str(self.values.get("num_today_actions")))
            return v if 0 <= v <= 20 else 3
        except ValueError:
            return 3

    @property
    def spread_overheads(self) -> str:
        v = str(self.values.get("showtime_spreadoverheads") or "byweek")
        if v == "0":
            return "off"
        if v == "1":
            return "byweek"
        return v if v in ("off", "byweek", "byday") else "byweek"

    @property
    def start_last_week(self) -> bool:
        return str(self.values.get("timebook_startlastweek", "1")) != "0"

    @property
    def book_by(self) -> str:
        v = str(self.values.get("showtime_bookbycode", "0"))
        return {"0": "code", "1": "name", "2": "both"}.get(v, "code")

    @property
    def duration_format(self) -> str:
        v = str(self.values.get("showtime_format", "1"))
        return {"0": "hhmm", "1": "hours", "2": "days"}.get(v, "hours")

    def to_dict(self) -> Dict[str, object]:
        return {
            "prefs_path": self.prefs_path,
            "prefs_exists": os.path.isfile(self.prefs_path),
            "rootdir": str(self.values.get("rootdir") or "~/diary"),
            "rootdir_expanded": self.rootdir,
            "activitiesfilename": str(self.values.get("activitiesfilename") or ""),
            "activities_file": self.activities_file,
            "dateformat_view": self.date_format,
            "currentTimeFormat": self.time_format,
            "showtime_hours_per_day": str(self.values.get("showtime_hours_per_day")),
            "showtime_spreadoverheads": self.spread_overheads,
            "timebook_startlastweek": "1" if self.start_last_week else "0",
            "num_today_actions": str(self.num_today_actions),
            "book_by": self.book_by,
            "duration_format": self.duration_format,
            "activities": self.activities,
            "files": {
                "actions": self.actions_file,
                "projects": self.projects_file,
                "contacts": self.contacts_file,
            },
            "warnings": self.warnings,
        }

    # -- saving -----------------------------------------------------------
    def save(self, changes: Dict[str, str], activities: Optional[List[str]] = None) -> None:
        """Persist changed settings to the prefs file (and activities file)."""
        changes = {k: str(v) for k, v in changes.items() if k in EDITABLE}
        if changes.get("currentTimeFormat") not in (None, "%d:%02d:%02d", "%d:%02d"):
            raise ValueError("Time format must be %d:%02d:%02d or %d:%02d")
        if changes.get("dateformat_view") not in (None, "YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY"):
            raise ValueError("Unknown date format")
        if changes.get("showtime_spreadoverheads") not in (None, "off", "byweek", "byday"):
            raise ValueError("Unknown overhead spreading mode")
        if "showtime_hours_per_day" in changes:
            hpd = float(changes["showtime_hours_per_day"])
            if not 0 < hpd < 24:
                raise ValueError("Hours per day must be between 0 and 24")
        if "num_today_actions" in changes:
            nta = int(changes["num_today_actions"])
            if not 0 <= nta <= 20:
                raise ValueError("Number of today actions must be 0-20")
        if "dateformat_view" in changes:
            changes["dateformat_tcl"] = {
                "DD/MM/YYYY": "%d/%m/%Y", "MM/DD/YYYY": "%m/%d/%Y"}.get(
                changes["dateformat_view"], "%Y-%m-%d")

        changed = {k: v for k, v in changes.items() if str(self.values.get(k, "")) != v}
        if changed:
            self._write_prefs(changed)
            self.values.update(changed)
        if activities is not None:
            acts = [a.strip() for a in activities if a.strip()]
            fn = self.activities_file
            os.makedirs(os.path.dirname(fn) or ".", exist_ok=True)
            with open(fn, "w", encoding="utf-8") as f:
                f.write("\n".join(acts) + "\n")
        self._load_activities()

    def _write_prefs(self, changed: Dict[str, str]) -> None:
        path = self.prefs_path
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8", errors="surrogateescape") as f:
                text = f.read()
        else:
            text = f"{HEADER}\n{MARKER}\n"
        lines = text.split("\n")
        marker_idx = next((i for i, l in enumerate(lines) if l.startswith(MARKER_PREFIX)), None)
        if marker_idx is None:
            # No marker: treat the whole existing file as "user section".
            auto, rest = [HEADER], [MARKER] + lines
        else:
            auto, rest = lines[:marker_idx], lines[marker_idx:]
        remaining = dict(changed)
        new_auto = []
        for line in auto:
            m = re.match(r"^\s*set\s+([A-Za-z0-9_]+)\s", line)
            if m and m.group(1) in remaining:
                name = m.group(1)
                new_auto.append(f"set {name} {tcl_quote(remaining.pop(name))}")
            else:
                new_auto.append(line)
        for name, value in remaining.items():
            new_auto.append(f"set {name} {tcl_quote(value)}")
        out = "\n".join(new_auto + rest)
        if not out.endswith("\n"):
            out += "\n"
        tmp = path + ".tmp-taglog-web"
        with open(tmp, "w", encoding="utf-8", errors="surrogateescape") as f:
            f.write(out)
        os.replace(tmp, path)
