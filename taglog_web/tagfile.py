"""Reader/writer for taglog "tag" files.

This is a faithful port of the parser and writer in the original
``tag.tcl`` (procs ``tag__readitem``, ``tag__readentry``, ``tag readfile``
and ``tag writefile``) so that files written by this program can be read by
the original Tcl/Tk taglog and vice versa.

File format summary::

    Name: single line value
    Name:: END_D
    multi-line value
    END_D
    End:

An *entry* is a list of *items* terminated by an ``End`` item. An item is a
``(name, value, endlabel)`` tuple; ``endlabel`` is ``None`` for single-line
items.
"""

from __future__ import annotations

import os
import tempfile
from typing import Iterable, List, Optional, Tuple

Item = Tuple[str, str, Optional[str]]
Entry = List[Item]

END: Item = ("End", "", None)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _read_item(buf: str, i: int) -> Tuple[Optional[Item], int]:
    """Port of tag__readitem. Returns (item or None, new index)."""
    n = len(buf)
    while i < n and buf[i].isspace():
        i += 1
    start = i
    while i < n and buf[i] != ":":
        i += 1
    name = buf[start:i]
    i += 1

    if i < n and buf[i] == ":":
        # Multi-line item: "Name:: ENDLABEL\n ... \nENDLABEL\n"
        i += 1
        start = i
        while i < n and buf[i] != "\n":
            i += 1
        endlabel = buf[start:i].strip()
        value_start = i + 1
        rest_pos = buf.find(endlabel + "\n", i)
        if rest_pos == -1:
            # Tolerate a file whose final end label has no trailing newline.
            if endlabel and buf.endswith(endlabel) and len(buf) - len(endlabel) >= i:
                rest_pos = len(buf) - len(endlabel)
            else:
                value = buf[value_start:]
                return (name, value, endlabel), n
        # Tcl: value = [string range $tagbuf $start [expr $i-2]]
        value = buf[value_start:max(value_start, rest_pos - 1)]
        i = rest_pos + len(endlabel)
        return (name, value, endlabel), i

    # Single-line item
    if i < n and buf[i] == " ":
        i += 1
    start = i
    while i < n and buf[i] != "\n":
        i += 1
    value = buf[start:i]
    if value.endswith("\r"):
        value = value[:-1]
    if name == "" and value == "":
        return None, i
    return (name, value, None), i


def _read_entry(buf: str, i: int) -> Tuple[Entry, int]:
    """Port of tag__readentry."""
    entry: Entry = []
    while True:
        item, i = _read_item(buf, i)
        if item is None:
            break
        entry.append(item)
        if item[0] == "End":
            break
    return entry, i


def parse(text: str) -> List[Entry]:
    """Parse the contents of a tag file into a list of entries."""
    result: List[Entry] = []
    i = 0
    n = len(text)
    while i < n:
        entry, i = _read_entry(text, i)
        if entry or not result:
            # The Tcl code always keeps the first (header) entry.
            result.append(entry)
    if result == [[]]:
        return []
    return result


def read_file(path: str) -> List[Entry]:
    """Read a tag file. Returns [] if it does not exist or is unreadable."""
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return []
    return parse(data.decode("utf-8", errors="surrogateescape"))


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def serialize_entry(entry: Iterable[Item]) -> str:
    out = []
    for item in entry:
        name, value = item[0], item[1]
        endlabel = item[2] if len(item) > 2 else None
        if endlabel:
            out.append(f"{name}:: {endlabel}\n{value}\n{endlabel}\n")
        else:
            out.append(f"{name}: {value}\n")
    return "".join(out)


def serialize(entries: Iterable[Iterable[Item]]) -> str:
    return "".join(serialize_entry(e) for e in entries)


def write_file(path: str, entries: Iterable[Iterable[Item]]) -> None:
    """Write entries atomically (temp file + rename)."""
    text = serialize(entries)
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".taglog-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(text.encode("utf-8", errors="surrogateescape"))
        try:
            st = os.stat(path)
            os.chmod(tmp, st.st_mode & 0o7777)
        except OSError:
            pass
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


# ---------------------------------------------------------------------------
# Entry helpers (ports of tag_entryVal, tagappend, tag setorreplace, ...)
# ---------------------------------------------------------------------------

def entry_val(entry: Optional[Entry], name: str) -> str:
    """First value of the named item, or ''."""
    if not entry:
        return ""
    for item in entry:
        if item[0] == name:
            return item[1]
    return ""


def entry_vals(entry: Entry, name: str) -> List[str]:
    return [item[1] for item in entry if item[0] == name]


def has_item(entry: Entry, name: str) -> bool:
    return any(item[0] == name for item in entry)


def tag_append(entry: Entry, name: str, value: Optional[str], endlabel: Optional[str] = None) -> Entry:
    """Port of tagappend: append only if value is non-empty."""
    if value is None or value == "":
        return entry
    entry.append((name, value, endlabel))
    return entry


def _insert_before_end(entry: Entry, item: Item) -> None:
    # Tcl: linsert $entry [expr [llength $entry]-1] $newitem
    pos = max(len(entry) - 1, 0)
    if entry and entry[-1][0] != "End":
        pos = len(entry)
    entry.insert(pos, item)


def set_or_replace(entry: Entry, name: str, value: str, endlabel: Optional[str] = None) -> Entry:
    """Port of 'tag setorreplace'."""
    new_item: Item = (name, value, endlabel)
    for idx, item in enumerate(entry):
        if item[0] == name:
            entry[idx] = new_item
            return entry
    _insert_before_end(entry, new_item)
    return entry


def remove_item(entry: Entry, name: str) -> Entry:
    entry[:] = [item for item in entry if item[0] != name]
    return entry


def set_or_replace_flag(entry: Entry, name: str, flag: str, on: bool) -> Entry:
    """Port of 'tag setorreplaceflags'."""
    for idx, item in enumerate(entry):
        if item[0] == name and item[1] == flag:
            if not on:
                del entry[idx]
            return entry
    if on:
        _insert_before_end(entry, (name, flag, None))
    return entry


def ensure_end(entry: Entry) -> Entry:
    if not entry or entry[-1][0] != "End":
        entry.append(END)
    return entry


# ---------------------------------------------------------------------------
# Selection (port of tag matchcond / matchall / extract)
# ---------------------------------------------------------------------------

def _num(v: str) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def match_cond(entry: Entry, test: tuple) -> bool:
    label, op = test[0], test[1]
    for item in entry:
        name, value = item[0], item[1]
        if name != label:
            continue
        if op == "==":
            if value == test[2]:
                return True
        elif op == "!=":
            if value != test[2]:
                return True
        elif op == "<=":
            a, b = _num(value), _num(test[2])
            if a is not None and b is not None:
                if a <= b:
                    return True
            elif value <= test[2]:
                return True
        elif op == "-in":
            if value in test[2]:
                return True
        elif op == "-contains":
            if str(test[2]).lower() in value.lower():
                return True
        elif op == "-exists":
            return True
        elif op in ("-later", "-earlier"):
            from .timeutil import parse_datetime
            a = parse_datetime(value)
            b = parse_datetime(test[2])
            if a is None or b is None:
                continue
            if op == "-later" and a > b:
                return True
            if op == "-earlier" and a < b:
                return True
        else:
            raise ValueError(f"Invalid operator {op}")
    return False


def match_all(entry: Entry, tests: Iterable[tuple]) -> bool:
    return all(match_cond(entry, t) for t in tests)


def extract(entries: Iterable[Entry], tests: Iterable[tuple]) -> List[Entry]:
    tests = list(tests)
    return [e for e in entries if match_all(e, tests)]
