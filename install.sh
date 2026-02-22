#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
src="${script_dir}/git-session-orchestrator"
dest="${HOME}/.codex/skills/git-session-orchestrator"

if [[ ! -d "${src}" ]]; then
  echo "Missing skill folder: ${src}" >&2
  exit 1
fi

mkdir -p "${HOME}/.codex/skills"
rm -rf "${dest}"
cp -R "${src}" "${dest}"

echo "Installed git-session-orchestrator to ${dest}"
