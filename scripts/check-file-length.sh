#!/bin/bash
# Check if files exceed maximum line limit

MAX_LINES=500
EXIT_CODE=0

for file in "$@"; do
  LINE_COUNT=$(wc -l < "$file")

  if [ "$LINE_COUNT" -gt "$MAX_LINES" ]; then
    echo "ERROR: $file has $LINE_COUNT lines, exceeding the limit of $MAX_LINES." >&2
    EXIT_CODE=1
  fi
done

exit $EXIT_CODE
