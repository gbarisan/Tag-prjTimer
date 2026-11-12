#!/bin/bash
# Double-click this file in Finder to start Taglog.
# It starts a small local server and opens Taglog in your web browser.
# Close this Terminal window (or press Ctrl-C) to stop it.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is needed. Install it from https://www.python.org/downloads/macos/"
  echo "or run:  xcode-select --install"
  read -r -p "Press Return to close."
  exit 1
fi
exec python3 -m taglog_web "$@"
