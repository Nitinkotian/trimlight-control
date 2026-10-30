#!/bin/bash
# Double-click to start the Trimlight app on a Mac. Close this window (or press Ctrl+C) to stop it.
cd "$(dirname "$0")" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. See README.md > Install Python."
  read -r -p "Press Return to close."
  exit 1
fi
python3 webapp.py "$@"
status=$?
if [ $status -ne 0 ]; then read -r -p "The app stopped with an error. Press Return to close."; fi
exit $status
