# Taglog (web edition)

A modern, browser-based port of [taglog](https://github.com/JohnLines/taglog) by John Lines, an
electronic workbook that combines **logging time to projects** with **keeping a diary of what you
actually did**. The original is a Tcl/Tk desktop program; this version runs a small local server
(Python standard library only, no installs) and shows the interface in your web browser.

It reads and writes **the same data files** as the original (`~/.taglog` and `~/diary/...`), so you
can switch to it without converting anything, and switch back.

## Running it on a Mac

You need Python 3.8 or newer. Check by opening Terminal and running `python3 --version`.
If macOS offers to install the "command line developer tools", accept; that provides `python3`.
Alternatively, install Python from <https://www.python.org/downloads/macos/>.

**Easiest:** double-click `Taglog.command` in Finder. A Terminal window opens, then Taglog opens in
your browser at <http://127.0.0.1:8765/>. Keep the Terminal window open while you use Taglog; close it
(or press Ctrl-C) to stop.

> The first time, macOS may refuse to open a file downloaded from the internet. Right-click
> `Taglog.command` → **Open** → **Open**. If it says the file is not executable, run
> `chmod +x Taglog.command` in Terminal from the folder.

**From Terminal:**

```bash
cd path/to/taglog-web
python3 -m taglog_web
```

Options: `--port 8800`, `--no-browser`, `-c /path/to/prefs` (use another preferences file, like the
original's `-c`).

Tip: in Safari or Chrome you can add the page to the Dock ("File → Add to Dock" in Safari, or
"Install page as app" in Chrome) so it behaves like a separate app.

## What it does

| Area | Features |
|---|---|
| **Today** | Running timer for the current entry; project, activity, action, contact, rate and description (autosaved). **Next** logs the entry and starts a new one (▾ to pick the next activity). Pause/Resume. Interrupt (!), Push (+) and Pop (−) stack for interruptions. Adjust start time (optionally moving the previous entry's end). Complete/abort the current action. Today's entries (click to edit/delete), day summary, project times today (click a project to switch), "today's actions" notes. |
| **Log & search** | Browse any day; edit entries; day summaries; search by date range, project, activity, contact and text; month and year summaries. |
| **Actions** | Filter by status/project/priority/text; create and edit actions with all the original fields; state changes with notes (recorded as `<State>-date` / `<State>-note`); next-action activation on completion; subtasks; time logged per action; time-blocked actions become due after their *Active after* time. |
| **Projects** | Add, edit, delete; booking code, start/end dates, expected time; Active, Breaks, Overheads and Immutable flags. |
| **Reports** | Weekly time bookings by project (overheads spread by week or by day; label by code or name; hh:mm, decimal hours or decimal days; CSV download); time by activity; total time for a project; project progress; active actions review (revise expected time and date); interruptions. |
| **Settings** | Data directory, date and time format, hours per day, overhead spreading, number of "today" actions, activities list. These are saved to `~/.taglog` in the original's format. |

Keyboard: **⌘/Ctrl + Enter** = Next.

## Compatibility with the original taglog

* Day logs `~/diary/logYYYY/MMDD.tag`, month/year summaries, `projects.tag`, `actions.tag`,
  `contacts.tag` and `activities` use exactly the original tag format. The parser is a direct port
  of `tag.tcl`. The test suite checks it against the original `tag.tcl` in both directions,
  byte for byte.
* `~/.taglog` is read without running Tcl: top-level `set name value` lines are understood, and
  anything else (procs, `[command]` substitutions) is ignored and reported under Settings. When
  you save settings, only the changed `set` lines are rewritten; everything else, including
  your own lines below the "automatically saved" marker, is kept.
* The current, unfinished entry is stored in `~/diary/.taglog-web-state.json`, so closing the
  browser or restarting does not lose it. The original ignores this file.
* **Don't run the original and this version at the same time.** The original keeps data in memory
  and would overwrite changes made here (and vice versa).

## Not included yet

These parts of the original were left for a later version: sending e-mail (SMTP) for actions and
reports (the *Email-status-to* field is stored but no mail is sent), contacts management and vCard
import (existing contacts are offered in lists), periodic actions and their reminder window,
archiving old actions/projects, updating projects from a URL, German/French/Dutch translations,
the built-in help pages, and "start procs".

## Deliberate differences from the original

* Weekly bookings: you choose the Monday the report starts on; ISO week numbers are shown. The
  original's week numbering could pick different weeks depending on the weekday of 1 January.
* Weekly bookings label projects by booking code by default, as the original does, but fall back to
  the project name when a project has no code.
* The "byday" overhead spreading, which is disabled in the original, works here.
* Entries with a missing end time, or an end before the start, count as zero time rather than negative.
* Decimal-hour figures are rounded from total seconds, so they can differ by 0.01 from the original.
* Project progress report: "slipped" lists unfinished actions past their expected completion date.
  The original repeated the "started" list there. The end date of the range is honoured.
* Midnight: if the app is running at midnight, the entry is split at 23:59:59 / 0:00:00 like the
  original. If it was not running (the Mac was off), the open entry is closed at the last time the
  app was seen running.
* IDs are generated with zero-padded times (e.g. `20261112090503`) and are made unique if two are
  created in the same second.

## Security

The server listens only on `127.0.0.1`. API requests must carry a custom header and a localhost
`Host`, which stops other web pages in your browser from reading or changing your diary.

## Development

```bash
python3 -m unittest discover -s tests -v
```

The Tcl cross-check tests run when `tclsh` is installed (`brew install tcl-tk`) and are skipped
otherwise. `tests/fixtures/tag.tcl` is an unmodified copy of the original's `src/tag.tcl`.

## License

GNU General Public License v3, as for the original taglog. See `LICENSE`.
Original program © John Lines; this port is a derivative work.
