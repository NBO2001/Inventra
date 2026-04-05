#!/bin/bash
# Ralph Wiggum - Long-running AI agent loop
# Usage: ./ralph.sh [--tool codex] [max_iterations]

set -euo pipefail

# Parse arguments
TOOL="codex"
MAX_ITERATIONS=10

while [[ $# -gt 0 ]]; do
  case $1 in
    --tool)
      TOOL="$2"
      shift 2
      ;;
    --tool=*)
      TOOL="${1#*=}"
      shift
      ;;
    *)
      # Assume it's max_iterations if it's a number
      if [[ "$1" =~ ^[0-9]+$ ]]; then
        MAX_ITERATIONS="$1"
      fi
      shift
      ;;
  esac
done

# Validate tool choice
if [[ "$TOOL" != "codex" ]]; then
  echo "Error: Invalid tool '$TOOL'. Must be 'codex'."
  exit 1
fi
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PRD_FILE="$SCRIPT_DIR/prd.json"
PROGRESS_FILE="$SCRIPT_DIR/progress.txt"
ARCHIVE_DIR="$SCRIPT_DIR/archive"
LAST_BRANCH_FILE="$SCRIPT_DIR/.last-branch"
LAST_PRD_SNAPSHOT="$SCRIPT_DIR/.last-prd.json"

for dependency in codex jq; do
  if ! command -v "$dependency" >/dev/null 2>&1; then
    echo "Error: Missing required dependency '$dependency'."
    exit 1
  fi
done

# Archive previous run if branch changed
if [ -f "$PRD_FILE" ] && [ -f "$LAST_BRANCH_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  LAST_BRANCH=$(cat "$LAST_BRANCH_FILE" 2>/dev/null || echo "")
  
  if [ -n "$CURRENT_BRANCH" ] && [ -n "$LAST_BRANCH" ] && [ "$CURRENT_BRANCH" != "$LAST_BRANCH" ]; then
    # Archive the previous run
    DATE=$(date +%Y-%m-%d)
    # Strip "ralph/" prefix from branch name for folder
    FOLDER_NAME=$(echo "$LAST_BRANCH" | sed 's|^ralph/||')
    ARCHIVE_FOLDER="$ARCHIVE_DIR/$DATE-$FOLDER_NAME"
    
    echo "Archiving previous run: $LAST_BRANCH"
    mkdir -p "$ARCHIVE_FOLDER"
    if [ -f "$LAST_PRD_SNAPSHOT" ]; then
      cp "$LAST_PRD_SNAPSHOT" "$ARCHIVE_FOLDER/prd.json"
    elif [ -f "$PRD_FILE" ]; then
      cp "$PRD_FILE" "$ARCHIVE_FOLDER/"
    fi
    [ -f "$PROGRESS_FILE" ] && cp "$PROGRESS_FILE" "$ARCHIVE_FOLDER/"
    echo "   Archived to: $ARCHIVE_FOLDER"
    
    # Reset progress file for new run
    echo "# Ralph Progress Log" > "$PROGRESS_FILE"
    echo "Started: $(date)" >> "$PROGRESS_FILE"
    echo "---" >> "$PROGRESS_FILE"
  fi
fi

# Track current branch
if [ -f "$PRD_FILE" ]; then
  CURRENT_BRANCH=$(jq -r '.branchName // empty' "$PRD_FILE" 2>/dev/null || echo "")
  if [ -n "$CURRENT_BRANCH" ]; then
    echo "$CURRENT_BRANCH" > "$LAST_BRANCH_FILE"
  fi
  cp "$PRD_FILE" "$LAST_PRD_SNAPSHOT"
fi

# Initialize progress file if it doesn't exist
if [ ! -f "$PROGRESS_FILE" ]; then
  echo "# Ralph Progress Log" > "$PROGRESS_FILE"
  echo "Started: $(date)" >> "$PROGRESS_FILE"
  echo "---" >> "$PROGRESS_FILE"
fi

echo "Starting Ralph - Tool: $TOOL - Max iterations: $MAX_ITERATIONS"

for i in $(seq 1 $MAX_ITERATIONS); do
  echo ""
  echo "==============================================================="
  echo "  Ralph Iteration $i of $MAX_ITERATIONS ($TOOL)"
  echo "==============================================================="

  LAST_MESSAGE_FILE=$(mktemp)

  set +e
  OUTPUT=$(codex exec --yolo -C "$SCRIPT_DIR" --output-last-message "$LAST_MESSAGE_FILE" "Continue working on the current Ralph task using the repository context and stop only when everything is complete. Respond with <promise>COMPLETE</promise> when finished." 2>&1 | tee /dev/stderr)
  CODEX_EXIT=$?
  set -e

  if [[ $CODEX_EXIT -ne 0 ]]; then
    echo "Codex exited with status $CODEX_EXIT. Continuing..."
    rm -f "$LAST_MESSAGE_FILE"
    sleep 2
    continue
  fi
  
  # Check for completion signal only in the final assistant message.
  if [[ -f "$LAST_MESSAGE_FILE" ]] && grep -q "<promise>COMPLETE</promise>" "$LAST_MESSAGE_FILE"; then
    echo ""
    echo "Ralph completed all tasks!"
    echo "Completed at iteration $i of $MAX_ITERATIONS"
    rm -f "$LAST_MESSAGE_FILE"
    exit 0
  fi

  rm -f "$LAST_MESSAGE_FILE"
  
  echo "Iteration $i complete. Continuing..."
  sleep 2
done

echo ""
echo "Ralph reached max iterations ($MAX_ITERATIONS) without completing all tasks."
echo "Check $PROGRESS_FILE for status."
exit 1
