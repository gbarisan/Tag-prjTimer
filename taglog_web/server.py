"""Local HTTP server: JSON API + static single-page UI.

Listens on 127.0.0.1 only. API requests must carry the header
``X-Taglog: 1`` and a localhost Host header, which stops other web sites
open in your browser from sending requests to it.
"""

from __future__ import annotations

import datetime as dt
import json
import mimetypes
import os
import re
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urlparse

from . import __version__
from . import reports
from . import tagfile as tf
from .help import HelpLibrary
from .prefs import Prefs
from .session import Session
from .store import ACTION_FIELDS, ACTION_TEXT_FIELDS, LOG_FIELDS, VALID_STATES, Store, StoreError, entry_to_dict
from .timeutil import parse_date

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _date(value: Optional[str], default: Optional[dt.date] = None) -> Optional[dt.date]:
    if not value:
        return default
    d = parse_date(value)
    if d is None:
        raise ApiError(f"Bad date '{value}' (use YYYY-MM-DD)")
    return d


class App:
    def __init__(self, prefs_path: Optional[str] = None):
        self.prefs = Prefs(prefs_path)
        self.store = Store(self.prefs)
        self.session = Session(self.store)
        self.help = HelpLibrary()
        self.routes: List[Tuple[str, re.Pattern, Callable]] = []
        self._register()

    # ------------------------------------------------------------------
    def route(self, method: str, pattern: str):
        def deco(fn):
            self.routes.append((method, re.compile("^" + pattern + "$"), fn))
            return fn
        return deco

    def dispatch(self, method: str, path: str, query: Dict[str, str], body: Dict) -> object:
        for m, rx, fn in self.routes:
            if m != method:
                continue
            match = rx.match(path)
            if match:
                args = [unquote(a) for a in match.groups()]
                return fn(*args, q=query, b=body)
        raise ApiError("Not found", 404)

    # ------------------------------------------------------------------
    def today_payload(self) -> Dict[str, object]:
        self.session.tick()
        snap = self.session.snapshot()
        d = self.session.date
        log = self.store.read_log(d)
        entries = []
        for idx, e in enumerate(log[1:], start=1):
            r = entry_to_dict(e)
            r["_index"] = idx
            r["_duration"] = reports._dur(e)
            entries.append(r)
        header = log[0] if log else []
        n = self.prefs.num_today_actions
        return {
            "version": __version__,
            "session": snap,
            "date": d.isoformat(),
            "entries": entries,
            "summary": tf.entry_val(header, "Summary"),
            "today_actions": [tf.entry_val(header, f"Action-title.{i}") for i in range(1, n + 1)],
            "project_times": reports.day_project_times(
                self.store, d, str(snap.get("project") or ""), int(snap.get("elapsed") or 0)),
            "projects": self.store.open_project_names(),
            "activities": self.prefs.activities,
            "contacts": self.store.contact_ids(),
            "active_actions": self.store.active_actions(),
            "due_blocked": self.store.due_time_blocked(),
            "prefs": self.prefs.to_dict(),
        }

    # ------------------------------------------------------------------
    def _register(self) -> None:
        r = self.route
        S, st = self.session, self.store

        @r("GET", "/api/today")
        def get_today(q, b):
            return self.today_payload()

        @r("POST", "/api/session")
        def post_session(q, b):
            S.update(b)
            return {"ok": True}

        @r("POST", "/api/next")
        def post_next(q, b):
            S.update(b.get("fields") or {})
            S.next(b.get("activity") or "", b.get("project") or None)
            return self.today_payload()

        @r("POST", "/api/pause")
        def post_pause(q, b):
            S.update(b.get("fields") or {})
            S.pause()
            return self.today_payload()

        @r("POST", "/api/resume")
        def post_resume(q, b):
            S.resume()
            return self.today_payload()

        @r("POST", "/api/stack/push")
        def post_push(q, b):
            S.update(b.get("fields") or {})
            S.push(b.get("kind") or "+")
            return self.today_payload()

        @r("POST", "/api/stack/pop")
        def post_pop(q, b):
            S.update(b.get("fields") or {})
            S.pop()
            return self.today_payload()

        @r("POST", "/api/adjust-start")
        def post_adjust(q, b):
            try:
                S.adjust_start(str(b.get("start") or ""), bool(b.get("adjust_prev")))
            except ValueError as e:
                raise ApiError(str(e))
            return self.today_payload()

        @r("POST", "/api/current-action")
        def post_current_action(q, b):
            try:
                S.set_current_action(str(b.get("id") or ""))
            except ValueError as e:
                raise ApiError(str(e))
            return self.today_payload()

        @r("POST", "/api/current-action/(complete|abort)")
        def post_finish_current(which, q, b):
            S.update(b.get("fields") or {})
            S.finish_current_action("Completed" if which == "complete" else "Aborted")
            return self.today_payload()

        @r("POST", "/api/today-actions")
        def post_today_actions(q, b):
            titles = b.get("titles") or []
            for i, t in enumerate(titles, start=1):
                st.update_log_header(S.date, f"Action-title.{i}", str(t or ""))
            return {"ok": True}

        # -- logs ---------------------------------------------------------
        @r("GET", "/api/log-dates")
        def get_log_dates(q, b):
            return {"dates": [d.isoformat() for d in st.log_dates()]}

        @r("GET", "/api/log/(\\d{4}-\\d{2}-\\d{2})")
        def get_log(date, q, b):
            d = _date(date)
            log = st.read_log(d)
            rows = []
            for idx, e in enumerate(log[1:], start=1):
                x = entry_to_dict(e)
                x["_index"] = idx
                x["_duration"] = reports._dur(e)
                rows.append(x)
            return {"date": d.isoformat(), "exists": bool(log),
                    "summary": tf.entry_val(log[0], "Summary") if log else "",
                    "entries": rows}

        @r("PUT", "/api/log/(\\d{4}-\\d{2}-\\d{2})/(\\d+)")
        def put_log_entry(date, idx, q, b):
            d = _date(date)
            log = st.read_log(d)
            i = int(idx)
            if i < 1 or i >= len(log):
                raise ApiError("No such entry", 404)
            old = log[i]
            # Port of dologedit: rebuild the known fields, keep any others.
            e: tf.Entry = []
            for name in LOG_FIELDS:
                val = b.get(name, tf.entry_val(old, name))
                tf.tag_append(e, name, str(val or "").strip() if name != "Description" else str(val or "").strip(),
                              "END_D" if name == "Description" else None)
            for item in old:
                if item[0] not in LOG_FIELDS and item[0] != "End":
                    e.append(item)
            e.append(tf.END)
            st.replace_log_entry(d, i, e)
            return get_log(date, q=q, b=b)

        @r("DELETE", "/api/log/(\\d{4}-\\d{2}-\\d{2})/(\\d+)")
        def delete_log_entry(date, idx, q, b):
            d = _date(date)
            try:
                st.replace_log_entry(d, int(idx), None)
            except StoreError as e:
                raise ApiError(str(e), 404)
            return get_log(date, q=q, b=b)

        @r("POST", "/api/log/(\\d{4}-\\d{2}-\\d{2})/summary")
        def post_day_summary(date, q, b):
            d = _date(date)
            text = str(b.get("text") or "").strip()
            st.update_log_header(d, "Summary", text, "END_S" if text else None)
            return {"ok": True}

        @r("GET", "/api/summary/(\\d{4})(?:-(\\d{2}))?")
        def get_summary(year, month, q, b):
            y = int(year)
            path = st.month_summary_path(y, int(month)) if month else st.year_summary_path(y)
            return {"text": st.read_summary(path), "exists": os.path.isfile(path)}

        @r("POST", "/api/summary/(\\d{4})(?:-(\\d{2}))?")
        def post_summary(year, month, q, b):
            y = int(year)
            if month and not 1 <= int(month) <= 12:
                raise ApiError("Bad month")
            path = st.month_summary_path(y, int(month)) if month else st.year_summary_path(y)
            st.write_summary(path, str(b.get("text") or ""))
            return {"ok": True}

        @r("GET", "/api/search")
        def get_search(q, b):
            return {"days": reports.search_logs(
                st, _date(q.get("from")), _date(q.get("to")), q.get("project", ""),
                q.get("text", ""), q.get("activity", ""), q.get("contact", ""),
                q.get("action", ""))}

        # -- projects -----------------------------------------------------
        @r("GET", "/api/projects")
        def get_projects(q, b):
            return {"projects": st.projects()}

        @r("POST", "/api/projects")
        def post_project(q, b):
            try:
                st.save_project(b)
            except StoreError as e:
                raise ApiError(str(e))
            return {"projects": st.projects()}

        @r("PUT", "/api/projects/(.+)")
        def put_project(name, q, b):
            try:
                st.save_project(b, original_name=name)
            except StoreError as e:
                raise ApiError(str(e))
            return {"projects": st.projects()}

        @r("DELETE", "/api/projects/(.+)")
        def delete_project(name, q, b):
            try:
                st.delete_project(name)
            except StoreError as e:
                raise ApiError(str(e))
            return {"projects": st.projects()}

        # -- actions ------------------------------------------------------
        def action_dict(e: tf.Entry) -> Dict[str, object]:
            d = entry_to_dict(e)
            d["_items"] = [[i[0], i[1]] for i in e if i[0] != "End"]
            return d

        @r("GET", "/api/actions")
        def get_actions(q, b):
            acts = st.actions()
            statuses = [s for s in (q.get("status") or "").split(",") if s]
            out = []
            for e in acts:
                if statuses and tf.entry_val(e, "Status") not in statuses:
                    continue
                if q.get("project") and tf.entry_val(e, "Project") != q["project"]:
                    continue
                if q.get("maxpriority"):
                    try:
                        if int(tf.entry_val(e, "Priority") or 50) > int(q["maxpriority"]):
                            continue
                    except ValueError:
                        pass
                if q.get("text"):
                    t = q["text"].lower()
                    if t not in tf.entry_val(e, "Title").lower() and \
                            t not in tf.entry_val(e, "Description").lower() and \
                            t not in tf.entry_val(e, "Id").lower():
                        continue
                out.append(action_dict(e))
            if q.get("sort") == "priority":
                def pkey(a):
                    try:
                        return int(a.get("Priority") or 50)
                    except ValueError:
                        return 50
                out.sort(key=pkey)
            return {"actions": out, "states": VALID_STATES,
                    "fields": ACTION_FIELDS, "text_fields": ACTION_TEXT_FIELDS}

        @r("GET", "/api/actions/(.+)/history")
        def get_action_history(aid, q, b):
            a = st.get_action(aid)
            if a is None:
                raise ApiError("No such action", 404)
            since = parse_date(tf.entry_val(a, "Date"))
            return st.action_history(aid, since)

        @r("GET", "/api/actions/(.+)")
        def get_action(aid, q, b):
            a = st.get_action(aid)
            if a is None:
                raise ApiError("No such action", 404)
            return {"action": action_dict(a)}

        @r("POST", "/api/actions")
        def post_action(q, b):
            try:
                a = st.create_action(b)
            except StoreError as e:
                raise ApiError(str(e))
            return {"action": action_dict(a)}

        @r("POST", "/api/actions/(.+)/state")
        def post_action_state(aid, q, b):
            try:
                res = st.change_action_state(aid, str(b.get("state") or ""), str(b.get("note") or ""))
            except StoreError as e:
                raise ApiError(str(e))
            return res

        @r("POST", "/api/actions/(.+)/revise")
        def post_action_revise(aid, q, b):
            try:
                changed = st.revise_action(aid, str(b.get("expected_date") or ""),
                                           str(b.get("expected_time") or ""),
                                           str(b.get("summary") or ""))
            except StoreError as e:
                raise ApiError(str(e))
            return {"revised": changed}

        @r("PUT", "/api/actions/(.+)")
        def put_action(aid, q, b):
            try:
                a = st.edit_action(aid, b)
            except StoreError as e:
                raise ApiError(str(e))
            return {"action": action_dict(a)}

        # -- reports ------------------------------------------------------
        @r("GET", "/api/reports/timebook")
        def get_timebook(q, b):
            default_start = reports.monday_of(dt.date.today())
            if self.prefs.start_last_week:
                default_start -= dt.timedelta(days=7)
            start = _date(q.get("start"), default_start)
            try:
                weeks = int(q.get("weeks") or 1)
            except ValueError:
                raise ApiError("weeks must be a number")
            rep = reports.time_bookings(st, start, weeks,
                                        q.get("spread") or self.prefs.spread_overheads,
                                        q.get("book_by") or self.prefs.book_by,
                                        self.prefs.hourly_rate, self.prefs.overtime_multiplier)
            rep["currency"] = self.prefs.currency
            return rep

        @r("GET", "/api/reports/activity")
        def get_rep_activity(q, b):
            return reports.time_by_activity(st, _date(q.get("from")), _date(q.get("to")),
                                            q.get("project", ""))

        @r("GET", "/api/reports/project-total")
        def get_rep_project_total(q, b):
            p = q.get("project") or ""
            if not p:
                raise ApiError("Choose a project")
            proj = st.project_map().get(p, {})
            rep = reports.project_total(st, p, _date(q.get("from") or str(proj.get("start") or "")),
                                        _date(q.get("to") or str(proj.get("end") or "")),
                                        self.prefs.hourly_rate, self.prefs.overtime_multiplier)
            rep["currency"] = self.prefs.currency
            return rep

        @r("GET", "/api/reports/gantt")
        def get_rep_gantt(q, b):
            p = q.get("project") or ""
            if not p:
                raise ApiError("Choose a project")
            return reports.gantt(st, p, q.get("aborted") == "1")

        @r("GET", "/api/reports/interruptions")
        def get_rep_interruptions(q, b):
            return reports.interruptions(st, _date(q.get("from")), _date(q.get("to")))

        @r("GET", "/api/reports/progress")
        def get_rep_progress(q, b):
            return reports.project_progress(st, q.get("project", ""), _date(q.get("from")),
                                            _date(q.get("to")))

        @r("GET", "/api/reports/review")
        def get_rep_review(q, b):
            return reports.active_actions_review(st)

        # -- help ---------------------------------------------------------
        @r("GET", "/api/help")
        def get_help_index(q, b):
            lang = q.get("lang") or self.prefs.language
            out = self.help.index(lang)
            if q.get("q"):
                out["matches"] = self.help.search(q["q"], lang)
            return out

        @r("GET", "/api/help/([A-Za-z0-9_.-]+)")
        def get_help_topic(tid, q, b):
            return self.help.topic(tid, q.get("lang") or self.prefs.language, __version__)

        # -- prefs --------------------------------------------------------
        @r("GET", "/api/prefs")
        def get_prefs(q, b):
            return self.prefs.to_dict()

        @r("POST", "/api/prefs")
        def post_prefs(q, b):
            old_root = self.prefs.rootdir
            acts = b.get("activities")
            try:
                self.prefs.save(b.get("values") or {}, acts if isinstance(acts, list) else None)
            except (ValueError, OSError) as e:
                raise ApiError(str(e))
            if self.prefs.rootdir != old_root:
                self.session.reload_for_new_rootdir()
            return self.prefs.to_dict()

    # ------------------------------------------------------------------
    def timebook_csv(self, q: Dict[str, str]) -> str:
        rep = self.dispatch("GET", "/api/reports/timebook", q, {})
        return reports.time_bookings_csv(rep, q.get("format") or self.prefs.duration_format,
                                         self.prefs.hours_per_day, self.prefs.currency)


ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]"}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "taglog-web/" + __version__

        def log_message(self, fmt, *args):  # quieter console
            if os.environ.get("TAGLOG_WEB_DEBUG"):
                super().log_message(fmt, *args)

        # -- helpers --------------------------------------------------
        def _send(self, status: int, body: bytes, ctype: str, extra: Optional[Dict[str, str]] = None):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, status: int, obj: object):
            self._send(status, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].lower()
            return host in ALLOWED_HOSTS

        def _static(self, path: str):
            if path in ("", "/"):
                path = "/index.html"
            full = os.path.normpath(os.path.join(STATIC_DIR, path.lstrip("/")))
            if not full.startswith(STATIC_DIR + os.sep) or not os.path.isfile(full):
                self._send(404, b"Not found", "text/plain")
                return
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                data = f.read()
            self._send(200, data, ctype, {
                "Content-Security-Policy":
                    "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                    "frame-ancestors 'none'"})

        def _handle(self, method: str):
            if not self._host_ok():
                self._send(403, b"Forbidden host", "text/plain")
                return
            url = urlparse(self.path)
            query = {k: v[-1] for k, v in parse_qs(url.query).items()}
            if not url.path.startswith("/api/") and url.path != "/export/timebook.csv":
                if method in ("GET", "HEAD"):
                    self._static(url.path)
                else:
                    self._send(405, b"Method not allowed", "text/plain")
                return
            if url.path == "/export/timebook.csv":
                try:
                    data = app.timebook_csv(query).encode("utf-8")
                except ApiError as e:
                    self._send(e.status, str(e).encode(), "text/plain; charset=utf-8")
                    return
                self._send(200, data, "text/csv; charset=utf-8",
                           {"Content-Disposition": 'attachment; filename="time-bookings.csv"'})
                return
            if self.headers.get("X-Taglog") != "1":
                self._json(403, {"error": "Missing X-Taglog header"})
                return
            body: Dict = {}
            length = int(self.headers.get("Content-Length") or 0)
            if length:
                if length > 5_000_000:
                    self._json(413, {"error": "Request too large"})
                    return
                try:
                    body = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(body, dict):
                        raise ValueError
                except ValueError:
                    self._json(400, {"error": "Body must be a JSON object"})
                    return
            try:
                with app.store.lock:
                    result = app.dispatch(method, url.path, query, body)
                self._json(200, result)
            except ApiError as e:
                self._json(e.status, {"error": str(e)})
            except StoreError as e:
                self._json(400, {"error": str(e)})
            except Exception as e:  # pragma: no cover - unexpected
                traceback.print_exc()
                self._json(500, {"error": f"{type(e).__name__}: {e}"})

        def do_GET(self):
            self._handle("GET")

        def do_HEAD(self):
            self._handle("GET")

        def do_POST(self):
            self._handle("POST")

        def do_PUT(self):
            self._handle("PUT")

        def do_DELETE(self):
            self._handle("DELETE")

    return Handler


def start_ticker(app: App, interval: float = 30.0) -> threading.Thread:
    """Background thread that handles midnight roll-over (minuteTimer)."""
    stop = threading.Event()

    def loop():
        while not stop.wait(interval):
            try:
                app.session.tick()
            except Exception:  # pragma: no cover
                traceback.print_exc()

    t = threading.Thread(target=loop, name="taglog-ticker", daemon=True)
    t.stop = stop  # type: ignore[attr-defined]
    t.start()
    return t


def serve(port: int = 8765, prefs_path: Optional[str] = None, open_browser: bool = True) -> None:
    app = App(prefs_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    start_ticker(app)
    print(f"taglog-web {__version__}")
    print(f"Data directory: {app.prefs.rootdir}")
    for w in app.prefs.warnings:
        print(f"  note: {w}")
    print(f"Open {url}  (press Ctrl-C to stop)")
    if open_browser:
        import webbrowser
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping. Your current entry is saved and will be restored next time.")
    finally:
        app.session.save()
        httpd.server_close()
