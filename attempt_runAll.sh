#!/usr/bin/env bash

set -euo pipefail

if [ $# -lt 3 ]; then
  echo "Usage: ./runAll.sh <input_folder/> <time_limit_seconds> <results.log>"
  exit 1
fi

INPUT_DIR="$1"
TIME_LIMIT="$2"
OUT_LOG="$3"

: > "$OUT_LOG"

shopt -s nullglob
FILES=("$INPUT_DIR"/*.cnf)

if [ ${#FILES[@]} -eq 0 ]; then
  echo "No .cnf files found in $INPUT_DIR"
  exit 1
fi


for f in "${FILES[@]}"; do
  # Prefer GNU timeout if available; otherwise run without it.
  if command -v timeout >/dev/null 2>&1; then
    set +e
    OUT=$(timeout "${TIME_LIMIT}" ./run.sh "$f")
    STATUS=$?
    set -e
    if [ $STATUS -eq 124 ] || [ $STATUS -eq 137 ]; then
      # TIMEOUT / KILLED: emit a placeholder line so the log stays aligned
      NAME=$(basename "$f")
      printf '{"Instance": "%s", "Time": "%.2f", "Result": "TIMEOUT"}\n' "$NAME" "$TIME_LIMIT" >> "$OUT_LOG"
      continue

    elif [ $STATUS -ne 0 ]; then
      NAME=$(basename "$f")
      printf '{"Instance": "%s", "Time": "%.2f", "Result": "ERROR"}\n' "$NAME" "$TIME_LIMIT" >> "$OUT_LOG"
      continue

    fi

  else
    OUT=$(./run.sh "$f")
  fi

  # Append only the last line (the required JSON)
  echo "$OUT" | tail -n 1 >> "$OUT_LOG"
done
