#!/usr/bin/env bash
# Fail if HermesCube git tree contains operator pollution or live memory artifacts.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

fail=0

echo "check_isolation: scanning $ROOT"

# Tracked live memory / learning surfaces
if git ls-files | grep -E '\.(cube)$|memory\.cube|engram_net\.json|yield_gradient\.json|journey\.jsonl$' >/dev/null; then
  echo "FAIL: tracked memory/learning data files present"
  git ls-files | grep -E '\.(cube)$|memory\.cube|engram_net\.json|yield_gradient\.json|journey\.jsonl$' || true
  fail=1
fi

# Absolute operator paths / personal hosts in tracked non-binary files
# (allow this script and docs that mention the pattern as forbidden)
hits=$(git grep -nE '/home/ilo|/home/pablothethinker|\.ilo/brain|parallax\.local' -- \
  ':(exclude)scripts/check_isolation.sh' \
  ':(exclude)CONTRIBUTING.md' \
  ':(exclude)**/*.png' \
  ':(exclude)**/*.jpg' \
  2>/dev/null || true)
if [[ -n "${hits}" ]]; then
  echo "FAIL: operator absolute paths in tracked files:"
  echo "$hits"
  fail=1
fi

# Secrets-ish
if git grep -nE 'sk-[a-zA-Z0-9]{10,}|api_key\s*=\s*['\''\"][^'\''\"]{8,}' -- \
  ':(exclude)**/*.md' 2>/dev/null | head -5 | grep -q .; then
  echo "FAIL: possible secrets in tracked code"
  fail=1
fi

if [[ "$fail" -ne 0 ]]; then
  echo "check_isolation: FAILED"
  exit 1
fi
echo "check_isolation: OK"
