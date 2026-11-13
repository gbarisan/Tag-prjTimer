"""Reports (port of taglog_report.tcl and the project times window)."""

from __future__ import annotations

import csv
import datetime as dt
import io
import os
import threading
from typing import Dict, List, Optional, Tuple

from . import tagfile as tf
from .store import Store, entry_to_dict
from .timeutil import entry_duration, format_duration, parse_date, parse_datetime, parse_expected_time


def _entries(store: Store, d: dt.date) -> List[tf.Entry]:
    return [e for e in store.read_log(d)[1:] if tf.has_item(e, "StartTime")]


def _dur(e: tf.Entry) -> int:
    return entry_duration(tf.entry_val(e, "StartTime"), tf.entry_val(e, "EndTime"))


def is_overtime(e: tf.Entry) -> bool:
    """Entries whose Rate is "Overtime" (the value the original offers)."""
    return tf.entry_val(e, "Rate").strip().lower() == "overtime"


def money(weighted_secs: float, hourly_rate: float) -> float:
    """Amount for a number of 'rate-weighted' seconds (overtime seconds count
    multiplier times)."""
    return round(weighted_secs / 3600.0 * hourly_rate, 2)


# ---------------------------------------------------------------------------
# Today's project times (doShowProjects / fillpreventries)
# ---------------------------------------------------------------------------

# Per-day totals by project, cached by file path and modification time so
# that the all-time totals on the Today page stay fast with years of logs.
_DAY_TOTALS_CACHE: Dict[str, Tuple[int, int, Dict[str, int]]] = {}
_CACHE_LOCK = threading.Lock()


def day_totals_by_project(store: Store, d: dt.date) -> Dict[str, int]:
    path = store.log_path(d)
    try:
        st = os.stat(path)
    except OSError:
        return {}
    key = (st.st_mtime_ns, st.st_size)
    with _CACHE_LOCK:
        hit = _DAY_TOTALS_CACHE.get(path)
        if hit and hit[:2] == key:
            return hit[2]
    totals: Dict[str, int] = {}
    for e in _entries(store, d):
        p = tf.entry_val(e, "Project") or "unknown"
        totals[p] = totals.get(p, 0) + _dur(e)
    with _CACHE_LOCK:
        _DAY_TOTALS_CACHE[path] = (key[0], key[1], totals)
    return totals


def project_totals_to_date(store: Store, projects: List[str], until: dt.date) -> Dict[str, int]:
    """All time logged on each project from its StartDate (if any) to `until`."""
    pmap = store.project_map()
    starts = {p: parse_date(str(pmap.get(p, {}).get("start") or "")) for p in projects}
    out = {p: 0 for p in projects}
    for d in store.log_files_between(None, until):
        day = day_totals_by_project(store, d)
        for p in projects:
            if p in day and (starts[p] is None or d >= starts[p]):
                out[p] += day[p]
    return out


def day_project_times(store: Store, d: dt.date, current_project: str = "",
                      current_elapsed: int = 0) -> Dict[str, object]:
    """Project times window: today's time, all-time total, expected and
    remaining time for active projects and for projects booked today."""
    pmap = store.project_map()
    times: Dict[str, int] = {}
    for name in store.open_project_names():
        if pmap.get(name, {}).get("active"):
            times[name] = 0
    for p, secs in day_totals_by_project(store, d).items():
        times[p] = times.get(p, 0) + secs
    if current_elapsed:
        p = current_project or "unknown"
        times[p] = times.get(p, 0) + current_elapsed
    total = sum(times.values())
    nonbreaks = sum(v for k, v in times.items() if not pmap.get(k, {}).get("breaks"))
    to_date = project_totals_to_date(store, [p for p in times if p != "unknown"], d)
    rows = []
    for k, v in sorted(times.items(), key=lambda kv: kv[0].lower()):
        info = pmap.get(k, {})
        booked = to_date.get(k, 0) + (current_elapsed if (current_project or "unknown") == k else 0)
        row = {"project": k, "seconds": v, "breaks": bool(info.get("breaks")),
               "total_booked": booked if k != "unknown" else None}
        if k != "unknown" and not info.get("breaks"):
            row.update(_budget(booked, str(info.get("expected_time", "") or "")))
        else:
            row.update({"expected_seconds": None, "remaining": None, "over_budget": False,
                        "expected_unreadable": False})
        rows.append(row)
    return {"rows": rows, "total": total, "total_nonbreaks": nonbreaks}


# ---------------------------------------------------------------------------
# Weekly time bookings by project (showTimeBookings)
# ---------------------------------------------------------------------------

def monday_of(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=d.weekday())


def time_bookings(store: Store, start: dt.date, weeks: int = 1, spread: str = "byweek",
                  book_by: str = "code", hourly_rate: float = 0.0,
                  overtime_multiplier: float = 1.5) -> Dict[str, object]:
    """Weekly time bookings.

    spread: 'off' | 'byweek' | 'byday' - how time on Overheads projects is
    redistributed over the other (non-break, non-immutable) projects.
    book_by: 'code' | 'name' | 'both' - how projects are labelled.
    hourly_rate: if > 0, amounts are added. Entries with Rate "Overtime" cost
    hourly_rate * overtime_multiplier; Breaks projects cost nothing. Spread
    overheads carry their cost (and overtime) with them in the same proportion
    as their time.
    """
    pmap = store.project_map()

    def flag(p: str, f: str) -> bool:
        return bool(pmap.get(p, {}).get(f))

    def label(p: str) -> str:
        code = str(pmap.get(p, {}).get("code") or "")
        if book_by == "name" or not code:
            return p
        if book_by == "both":
            return f"{code} ({p})"
        return code

    start = monday_of(start)
    out_weeks = []
    for w in range(max(1, min(int(weeks), 53))):
        wstart = start + dt.timedelta(days=7 * w)
        days = [wstart + dt.timedelta(days=i) for i in range(7)]
        booked: List[str] = []
        immutable_keys = set()
        projtimes: Dict[str, List[int]] = {}
        daytotal = [0] * 7
        dayoverheads = [0] * 7
        dayimmutable = [0] * 7
        nonbreaks = breaks = overheads = immutable = 0
        warnings = []
        per_day_proj: List[Dict[str, int]] = [dict() for _ in range(7)]
        # overtime seconds and rate-weighted seconds, per project and for overheads
        ot: Dict[str, float] = {}
        wsec: Dict[str, float] = {}
        day_oh_ot = [0.0] * 7
        day_oh_w = [0.0] * 7
        ot_total = 0
        w_total = 0.0

        for i, d in enumerate(days):
            if not store.read_log(d):
                if d.weekday() < 5 and d <= dt.date.today():
                    warnings.append(f"No log file for {d.isoformat()}")
                continue
            for e in _entries(store, d):
                p = tf.entry_val(e, "Project") or "unknown"
                dur = _dur(e)
                otime = dur if is_overtime(e) else 0
                weighted = dur + otime * (overtime_multiplier - 1)
                if flag(p, "breaks"):
                    breaks += dur
                    continue
                ot_total += otime
                w_total += weighted
                if spread != "off" and flag(p, "overheads"):
                    daytotal[i] += dur
                    nonbreaks += dur
                    overheads += dur
                    dayoverheads[i] += dur
                    day_oh_ot[i] += otime
                    day_oh_w[i] += weighted
                else:
                    key = label(p)
                    if key not in projtimes:
                        booked.append(key)
                        projtimes[key] = [0] * 7
                        ot[key] = 0.0
                        wsec[key] = 0.0
                    projtimes[key][i] += dur
                    ot[key] += otime
                    wsec[key] += weighted
                    per_day_proj[i][key] = per_day_proj[i].get(key, 0) + dur
                    daytotal[i] += dur
                    nonbreaks += dur
                    if flag(p, "immutable"):
                        immutable += dur
                        dayimmutable[i] += dur
                        immutable_keys.add(key)

        spreadable = [k for k in booked if k not in immutable_keys]
        if spread == "byweek":
            base = sum(sum(projtimes[k]) for k in spreadable)
            if base > 0:
                for k in spreadable:
                    frac = sum(projtimes[k]) / base
                    for i in range(7):
                        if dayoverheads[i]:
                            projtimes[k][i] += int(round(dayoverheads[i] * frac))
                            ot[k] += day_oh_ot[i] * frac
                            wsec[k] += day_oh_w[i] * frac
        elif spread == "byday":
            for i in range(7):
                if not dayoverheads[i]:
                    continue
                base = sum(v for k, v in per_day_proj[i].items() if k in spreadable)
                if base <= 0:
                    continue
                for k, v in per_day_proj[i].items():
                    if k in spreadable:
                        projtimes[k][i] += int(round(dayoverheads[i] * v / base))
                        ot[k] += day_oh_ot[i] * v / base
                        wsec[k] += day_oh_w[i] * v / base

        rows = [{"project": k, "days": projtimes[k], "total": sum(projtimes[k]),
                 "overtime": int(round(ot[k])),
                 "amount": money(wsec[k], hourly_rate) if hourly_rate else None}
                for k in booked]
        out_weeks.append({
            "start": wstart.isoformat(),
            "iso_week": wstart.isocalendar()[1],
            "days": [d.isoformat() for d in days],
            "rows": rows,
            "day_totals": daytotal,
            "nonbreaks_total": nonbreaks,
            "breaks_total": breaks,
            "overheads_total": overheads if spread != "off" else 0,
            "unspread_overheads": sum(dayoverheads) if not booked else 0,
            "overtime_total": ot_total,
            "amount_total": money(w_total, hourly_rate) if hourly_rate else None,
            "warnings": warnings,
        })
    return {"weeks": out_weeks, "spread": spread, "book_by": book_by,
            "rates": {"hourly": hourly_rate, "overtime_multiplier": overtime_multiplier}
            if hourly_rate else None}


def time_bookings_csv(report: Dict[str, object], fmt: str = "hours",
                      hours_per_day: float = 7.58, currency: str = "") -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    priced = bool(report.get("rates"))
    amount_head = f"Amount ({currency})" if currency else "Amount"

    def f(v):
        return format_duration(v, fmt, hours_per_day)

    def a(v):
        return "" if v is None else f"{v:.2f}"
    for week in report["weeks"]:  # type: ignore[index]
        days = [dt.date.fromisoformat(x) for x in week["days"]]
        extra_head = ["Overtime", amount_head] if priced else []
        w.writerow(["Project", "Total"] + [d.strftime("%a %d/%m") for d in days] + extra_head)
        for row in week["rows"]:
            extra = [f(row["overtime"]), a(row["amount"])] if priced else []
            w.writerow([row["project"], f(row["total"])] + [f(v) for v in row["days"]] + extra)
        extra = [f(week["overtime_total"]), a(week["amount_total"])] if priced else []
        w.writerow(["Total (non breaks)", f(week["nonbreaks_total"])] +
                   [f(v) for v in week["day_totals"]] + extra)
        w.writerow(["Breaks total", f(week["breaks_total"])])
        w.writerow([])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Time by activity (doTimeByActivityOK)
# ---------------------------------------------------------------------------

def time_by_activity(store: Store, start: Optional[dt.date], end: Optional[dt.date],
                     project: str = "") -> Dict[str, object]:
    acts: Dict[str, int] = {}
    total = 0
    for d in store.log_files_between(start, end):
        for e in _entries(store, d):
            if project and tf.entry_val(e, "Project") != project:
                continue
            a = tf.entry_val(e, "Activity") or "unknown"
            dur = _dur(e)
            acts[a] = acts.get(a, 0) + dur
            total += dur
    rows = [{"activity": k, "seconds": v} for k, v in sorted(acts.items(), key=lambda kv: -kv[1])]
    return {"rows": rows, "total": total}


# ---------------------------------------------------------------------------
# Total time for a project (doTotalTimeForProjectOK)
# ---------------------------------------------------------------------------

def project_total(store: Store, project: str, start: Optional[dt.date],
                  end: Optional[dt.date], hourly_rate: float = 0.0,
                  overtime_multiplier: float = 1.5) -> Dict[str, object]:
    files = store.log_files_between(start, end)
    total = 0
    overtime = 0
    days = []
    acts: Dict[str, int] = {}
    for d in files:
        found = False
        for e in _entries(store, d):
            if tf.entry_val(e, "Project") != project:
                continue
            dur = _dur(e)
            total += dur
            if is_overtime(e):
                overtime += dur
            a = tf.entry_val(e, "Activity") or "unknown"
            acts[a] = acts.get(a, 0) + dur
            found = True
        if found:
            days.append(d)
    p = store.project_map().get(project, {})
    amount = None
    if hourly_rate:
        weighted = 0 if p.get("breaks") else total + overtime * (overtime_multiplier - 1)
        amount = money(weighted, hourly_rate)
    return {
        "project": project,
        "total": total,
        "overtime": overtime,
        "amount": amount,
        "breaks": bool(p.get("breaks")),
        "files_examined": len(files),
        "days_with_entries": len(days),
        "first_date": days[0].isoformat() if days else "",
        "last_date": days[-1].isoformat() if days else "",
        "activities": [{"activity": k, "seconds": v}
                       for k, v in sorted(acts.items(), key=lambda kv: -kv[1])],
        "expected_time": p.get("expected_time", ""),
        **_budget(total, str(p.get("expected_time", "") or "")),
    }


def _budget(actual: int, expected_text: str) -> Dict[str, object]:
    """Expected time vs actual: remaining seconds (negative when over)."""
    expected = parse_expected_time(expected_text)
    if expected is None:
        return {"expected_seconds": None, "remaining": None, "over_budget": False,
                "expected_unreadable": bool(expected_text.strip())}
    return {"expected_seconds": expected, "remaining": expected - actual,
            "over_budget": actual > expected, "expected_unreadable": False}


# ---------------------------------------------------------------------------
# Interruptions report (doInterruptionsReportOK)
# ---------------------------------------------------------------------------

def interruptions(store: Store, start: Optional[dt.date], end: Optional[dt.date]) -> Dict[str, object]:
    total = 0
    peak = 0
    peak_day = ""
    files = store.log_files_between(start, end)
    for d in files:
        n = sum(1 for e in store.read_log(d)[1:]
                if tf.entry_val(e, "Stack-info").startswith("!"))
        total += n
        if n > peak:
            peak, peak_day = n, d.isoformat()
    days = len(files)
    return {"total": total, "days": days,
            "average": round(total / days, 2) if days else 0,
            "peak": peak, "peak_day": peak_day}


# ---------------------------------------------------------------------------
# Project progress report (doProjectReportOK)
# ---------------------------------------------------------------------------

def _in_range(value: str, start: Optional[dt.date], end: Optional[dt.date]) -> bool:
    d = parse_datetime(value)
    if d is None:
        return False
    if start and d.date() < start:
        return False
    if end and d.date() > end:
        return False
    return True


def project_progress(store: Store, project: str, start: Optional[dt.date],
                     end: Optional[dt.date]) -> Dict[str, object]:
    actions = [e for e in store.actions() if not project or tf.entry_val(e, "Project") == project]
    today = dt.date.today()
    cutoff = min(end, today) if end else today

    def row(e, a, b):
        return {"id": tf.entry_val(e, "Id"), "title": tf.entry_val(e, "Title"),
                "expected": tf.entry_val(e, a), "actual": tf.entry_val(e, b),
                "status": tf.entry_val(e, "Status")}

    completed = [row(e, "Expected-completed-date", "Completed-date") for e in actions
                 if _in_range(tf.entry_val(e, "Completed-date"), start, end)]
    started = [row(e, "Expected-start-date", "Active-date") for e in actions
               if _in_range(tf.entry_val(e, "Active-date"), start, end)]
    slipped = []
    for e in actions:
        if tf.entry_val(e, "Status") in ("Completed", "Aborted"):
            continue
        due = parse_date(tf.entry_val(e, "Expected-completed-date"))
        if due and due < cutoff:
            slipped.append(row(e, "Expected-completed-date", "Original-expected-completed-date"))
    active = [row(e, "Expected-completed-date", "Active-date") for e in actions
              if tf.entry_val(e, "Status") == "Active"]
    return {"project": project, "start": start.isoformat() if start else "",
            "end": end.isoformat() if end else "", "completed": completed,
            "started": started, "slipped": slipped, "active": active}


# ---------------------------------------------------------------------------
# Active actions review (doActiveActionsReview)
# ---------------------------------------------------------------------------

def active_actions_review(store: Store) -> Dict[str, object]:
    actives = [e for e in store.actions() if tf.entry_val(e, "Status") == "Active"]
    ids = {tf.entry_val(e, "Id") for e in actives}
    earliest = None
    for e in actives:
        d = parse_date(tf.entry_val(e, "Active-date") or tf.entry_val(e, "Date"))
        if d and (earliest is None or d < earliest):
            earliest = d
    spent: Dict[str, int] = {i: 0 for i in ids}
    if actives:
        for d in store.log_files_between(earliest, None):
            for e in _entries(store, d):
                a = tf.entry_val(e, "Action")
                if a in spent:
                    spent[a] += _dur(e)
    rows = []
    from .timeutil import parse_hms
    for e in actives:
        aid = tf.entry_val(e, "Id")
        exp_t = tf.entry_val(e, "Expected-time")
        exp_d = tf.entry_val(e, "Expected-completed-date")
        due = parse_datetime(exp_d)
        rows.append({
            "id": aid, "title": tf.entry_val(e, "Title"), "project": tf.entry_val(e, "Project"),
            "spent": spent.get(aid, 0), "expected_time": exp_t,
            "expected_completed": exp_d,
            "over_time": bool(exp_t) and spent.get(aid, 0) > parse_hms(exp_t),
            "overdue": bool(due) and due < dt.datetime.now(),
        })
    try:
        rows.sort(key=lambda r: int(tf.entry_val(store.get_action(r["id"]) or [], "Priority") or 50))
    except ValueError:
        pass
    return {"rows": rows}


# ---------------------------------------------------------------------------
# Log search (logSelect / fillLogWin)
# ---------------------------------------------------------------------------

def search_logs(store: Store, start: Optional[dt.date], end: Optional[dt.date],
                project: str = "", text: str = "", activity: str = "", contact: str = "",
                action: str = "") -> List[Dict[str, object]]:
    out = []
    for d in store.log_files_between(start, end):
        log = store.read_log(d)
        if not log:
            continue
        rows = []
        for idx, e in enumerate(log[1:], start=1):
            if project and tf.entry_val(e, "Project") != project:
                continue
            if activity and tf.entry_val(e, "Activity") != activity:
                continue
            if contact and tf.entry_val(e, "Contact") != contact:
                continue
            if action and tf.entry_val(e, "Action") != action:
                continue
            if text and text.lower() not in tf.entry_val(e, "Description").lower():
                continue
            r = entry_to_dict(e)
            r["_index"] = idx
            r["_duration"] = _dur(e)
            rows.append(r)
        summary = tf.entry_val(log[0], "Summary")
        if rows or (summary and not (project or text or activity or contact or action)):
            out.append({"date": d.isoformat(), "summary": summary, "entries": rows})
    return out
