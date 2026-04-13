#!/usr/bin/env bash
# AlgoVoi pre-commit secret scanner
#
# Blocks commits that include likely secrets in ANY staged file (source,
# config, docs — does not matter). Triggered patterns are a combination of
# known AlgoVoi shapes and generic high-entropy / provider shapes.
#
# Install once per clone:
#   ln -sf ../../scripts/pre-commit-secret-scan.sh .git/hooks/pre-commit
#   chmod +x scripts/pre-commit-secret-scan.sh
#
# Skip this hook only with an EXPLICIT override (never by accident):
#   ALGOVOI_SKIP_SECRET_SCAN=1 git commit ...
#
# Exit codes:
#   0  no matches
#   1  match found — commit blocked

set -eu

if [[ "${ALGOVOI_SKIP_SECRET_SCAN:-0}" == "1" ]]; then
  echo "[pre-commit] ALGOVOI_SKIP_SECRET_SCAN=1 — skipping secret scan"
  exit 0
fi

# List of patterns to block. Each pattern is a grep -E regex.
# -----------------------------------------------------------------
# AlgoVoi-specific shapes:
#   algvk_[A-Za-z0-9_-]{30,}      → DB-managed admin key (algvk_ prefix,
#                                    from admin_key_service.py). MUST come
#                                    BEFORE the algv_ pattern so grep matches
#                                    the longer prefix first in alternation.
#   algv_[A-Za-z0-9_-]{30,}       → tenant API key plaintext
#   ak_[a-f0-9]{64}               → legacy static admin key in vm.env format
# Known tenant UUID (demo tenant — only allowed in the audit doc):
#   YOUR_TENANT_UUID_HERE
# HMAC secret shapes:
#   64 lowercase hex chars on a line with "SECRET" / "KEY" nearby
PATTERNS=(
  'algvk_[A-Za-z0-9_-]{20,}'
  'algv_[A-Za-z0-9_-]{30,}'
  'ak_[a-f0-9]{64}'
  'YOUR_TENANT_UUID_HERE'
  '***REDACTED_OLD_WEBHOOK_SECRET***'
)

# Files the scanner should NEVER look at (by path):
#  - audit docs are allowed to reference tenant UUIDs for historical context
#  - test files contain obviously-fake fixture tokens by design (strings like
#    "algvk_testtoken123" or "algvk_never_log_this_value"). They are not real
#    secrets, and blocking them would make the test suite impossible to edit.
#    Test authors are expected to not put real keys in tests (separate rule).
#  - this script and its config
EXCLUDE_PATTERNS=(
  '^docs/SECURITY_AUDIT_.*\.md$'
  '^tests/'
  '^.*/tests/'
  '^scripts/pre-commit-secret-scan\.sh$'
  '^\.gitignore$'
)

# Staged files (added/modified, no deletions).
STAGED=$(git diff --cached --name-only --diff-filter=AM)

if [[ -z "$STAGED" ]]; then
  exit 0
fi

FOUND=0

while IFS= read -r file; do
  [[ -z "$file" ]] && continue
  [[ ! -f "$file" ]] && continue

  # Skip excluded paths
  excluded=0
  for ex in "${EXCLUDE_PATTERNS[@]}"; do
    if [[ "$file" =~ $ex ]]; then
      excluded=1
      break
    fi
  done
  [[ "$excluded" == "1" ]] && continue

  # Run each pattern against the staged content (not the working-tree content).
  # `git show :FILE` prints exactly what will be committed.
  CONTENT=$(git show ":$file" 2>/dev/null || true)
  [[ -z "$CONTENT" ]] && continue

  for pat in "${PATTERNS[@]}"; do
    if echo "$CONTENT" | grep -E -q "$pat"; then
      MATCH_LINE=$(echo "$CONTENT" | grep -E -n "$pat" | head -1)
      echo "[pre-commit] BLOCKED: secret pattern '$pat' in $file"
      echo "             $MATCH_LINE"
      FOUND=1
    fi
  done
done <<< "$STAGED"

if [[ "$FOUND" == "1" ]]; then
  cat <<EOF

═══════════════════════════════════════════════════════════════════════
COMMIT BLOCKED — likely secret detected in staged files.

Remove the secret from the staged file. Do NOT work around this hook by
setting ALGOVOI_SKIP_SECRET_SCAN=1 unless you have explicitly verified
the match is a false positive (e.g. a test fixture).

If the secret has already been pushed anywhere, treat it as COMPROMISED
and rotate it on the backend before continuing.
═══════════════════════════════════════════════════════════════════════
EOF
  exit 1
fi

exit 0
