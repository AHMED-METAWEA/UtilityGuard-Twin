#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/ug-contract-drift.XXXXXX")"
trap 'rm -rf -- "$tmp"' EXIT
node "$root/scripts/gen_types.mjs" "$tmp"

# Recursive diff also catches missing counterparts and extra committed files.
if diff -rq -- "$root/frontend/src/generated" "$tmp"; then
    echo 'Contract types are up to date.'
else
    echo 'Contract type drift detected in the files listed above. Fix: make gen-types' >&2
    exit 1
fi
