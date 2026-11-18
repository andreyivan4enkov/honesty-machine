#!/bin/bash
# install_precommit.sh — installs a git pre-commit hook that BLOCKS commits
# containing BLOCK-severity findings (per honesty_patterns.json).
# Run once in the repository root:  bash install_precommit.sh
set -e
cd "$(dirname "$0")"
if [ ! -d .git ]; then
  echo "No .git in current directory — run this in the repository root."
  exit 1
fi
mkdir -p .git/hooks
cat > .git/hooks/pre-commit <<'HOOK'
#!/bin/bash
# pre-commit: honesty gate. Blocks the commit on BLOCK-severity findings.
ROOT=$(git rev-parse --show-toplevel)
AUDIT="$ROOT/honest_audit.py"
if [ ! -f "$AUDIT" ]; then
  echo "[honesty] honest_audit.py not found — skipping check."
  exit 0
fi
# NOTE: examples/ contains intentional fraud for testing the gate itself —
# it is excluded here. Do NOT put real project code under examples/.
FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -Ei '\.(py|c|cc|cpp|mm|m|glsl|comp|metal|swift)$' | grep -v '^examples/' || true)
if [ -z "$FILES" ]; then
  exit 0
fi
echo "[honesty] auditing: $FILES"
cd "$ROOT"
python3 "$AUDIT" $FILES
STATUS=$?
if [ $STATUS -ne 0 ]; then
  echo ""
  echo "[honesty] COMMIT BLOCKED: BLOCK-severity findings present."
  echo "[honesty] Remove the fraud, or justify a WARN-level exception in the commit message."
  exit 1
fi
echo "[honesty] no fraud, commit allowed."
exit 0
HOOK
chmod +x .git/hooks/pre-commit
echo "Done: .git/hooks/pre-commit installed. Every commit now passes the honesty gate."
