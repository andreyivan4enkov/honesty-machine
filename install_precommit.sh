#!/bin/bash
# install_precommit.sh — installs a git pre-commit hook that BLOCKS commits
# containing BLOCK-severity findings (per honesty_patterns.json).
# Run once in the repository root:  bash install_precommit.sh
# An existing pre-commit hook is backed up to pre-commit.bak.<timestamp> and
# CHAINED (executed before the gate), not silently overwritten.
set -e
cd "$(dirname "$0")"
if [ ! -d .git ]; then
  echo "No .git in current directory — run this in the repository root."
  exit 1
fi
mkdir -p .git/hooks
if [ -f .git/hooks/pre-commit ]; then
  BAK=".git/hooks/pre-commit.bak.$(date +%s)"
  mv .git/hooks/pre-commit "$BAK"
  echo "Existing pre-commit hook backed up to $BAK (will be chained)."
fi
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/bash
# pre-commit: honesty gate v2.
# - audits STAGED content (git show :file), not the working tree
# - fail-closed: missing auditor or python blocks the commit
# - chains any previously installed pre-commit.bak.* hooks first
# - examples/ excluded (intentional demo fraud lives there)
ROOT=$(git rev-parse --show-toplevel) || exit 1
AUDIT="$ROOT/honest_audit.py"

for bak in "$ROOT/.git/hooks"/pre-commit.bak.*; do
  [ -e "$bak" ] || continue
  if [ -x "$bak" ]; then
    "$bak"
    [ $? -ne 0 ] && exit 1
  fi
done

if [ ! -f "$AUDIT" ]; then
  echo "[honesty] honest_audit.py not found — BLOCKING (fail-closed)."
  exit 1
fi
PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "[honesty] python3/python not found — BLOCKING (fail-closed)."
  exit 1
fi

TMP=$(mktemp -d 2>/dev/null || mktemp -d -t honesty-gate)
trap 'rm -rf "$TMP"' EXIT
LIST="$TMP/list.z"
: > "$LIST"
COUNT=0
# NUL-safe list; renames expanded to delete+add so edited renames are audited.
while IFS= read -r -d '' f; do
  case "$f" in examples/*|examples) continue;; esac
  mkdir -p "$TMP/$(dirname -- "$f")"
  if git show ":$f" > "$TMP/$f" 2>/dev/null; then
    printf '%s\0' "$f" >> "$LIST"
    COUNT=$((COUNT + 1))
  fi
done < <(git diff --cached --name-only -z --diff-filter=ACMR --no-renames)

if [ "$COUNT" -eq 0 ]; then
  exit 0
fi
echo "[honesty] auditing $COUNT staged file(s) (staged content, not worktree)"
cd "$TMP"
# auditor filters by configured extensions itself; xargs -0 keeps any filename safe
xargs -0 "$PY" "$AUDIT" < "$LIST"
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo ""
  echo "[honesty] COMMIT BLOCKED (exit $STATUS): fraud found, or config error (exit 2)."
  echo "[honesty] Remove the fraud, or justify a WARN-level exception in the commit message."
  exit 1
fi
echo "[honesty] no fraud, commit allowed."
exit 0
HOOK
chmod +x .git/hooks/pre-commit
echo "Done: .git/hooks/pre-commit installed. Every commit now passes the honesty gate."
