#!/usr/bin/env bash
set -euo pipefail

skill_name="git-session-orchestrator"
required_paths=(
  "SKILL.md"
  "agents/openai.yaml"
  "references/git-ops-playbook.md"
  "scripts/session_monitor.py"
  "scripts/git_coordination.py"
  "scripts/heartbeat_monitor.py"
)

bold=""
reset=""
blue=""
green=""
yellow=""
red=""

log_header() {
  printf "%s%s%s\n" "${bold}" "git-session-orchestrator installer" "${reset}"
}

log_step() {
  printf "%s[%s]%s %s\n" "${blue}" "$1" "${reset}" "$2"
}

log_ok() {
  printf "%sOK%s %s\n" "${green}" "${reset}" "$1"
}

log_warn() {
  printf "%sWARN%s %s\n" "${yellow}" "${reset}" "$1"
}

log_err() {
  printf "%sERROR%s %s\n" "${red}" "${reset}" "$1" >&2
}

usage() {
  cat <<'EOF'
Usage: ./install.sh [--force] [--dry-run] [--path <dir>] [--no-color] [--print-path] [--help]

Options:
  --force, -f      Replace an existing install without prompting.
  --dry-run, -n    Print planned actions without modifying files.
  --path <dir>     Install root (default: ~/.codex/skills).
  --no-color       Disable ANSI colors.
  --print-path     Print destination path and exit.
  --help, -h       Show this help text.
EOF
}

confirm_replace() {
  local answer=""
  read -r -p "Existing install found. Replace it? [y/N] " answer || true
  case "${answer}" in
    y|Y|yes|YES)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

force=0
dry_run=0
no_color=0
print_path=0
dest_root="${HOME}/.codex/skills"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force|-f)
      force=1
      ;;
    --dry-run|-n)
      dry_run=1
      ;;
    --path)
      if [[ $# -lt 2 ]]; then
        log_err "Missing value for --path"
        usage
        exit 2
      fi
      dest_root="$2"
      shift
      ;;
    --path=*)
      dest_root="${1#*=}"
      ;;
    --no-color)
      no_color=1
      ;;
    --print-path)
      print_path=1
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      log_err "Unknown argument: $1"
      usage
      exit 2
      ;;
  esac
  shift
done

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
src="${script_dir}/${skill_name}"

case "${dest_root}" in
  "~")
    dest_root="${HOME}"
    ;;
  "~/"*)
    dest_root="${HOME}/${dest_root#~/}"
    ;;
esac

dest="${dest_root}/${skill_name}"

if [[ "${print_path}" -eq 1 ]]; then
  printf "%s\n" "${dest}"
  exit 0
fi

if [[ "${no_color}" -eq 0 ]] && [[ -t 1 ]] && command -v tput >/dev/null 2>&1; then
  if [[ "$(tput colors 2>/dev/null || echo 0)" -ge 8 ]]; then
    bold="$(tput bold)"
    reset="$(tput sgr0)"
    blue="$(tput setaf 4)"
    green="$(tput setaf 2)"
    yellow="$(tput setaf 3)"
    red="$(tput setaf 1)"
  fi
fi

log_header
log_step "1/5" "Validating source bundle"
printf "  source: %s\n" "${src}"
printf "  destination: %s\n" "${dest}"

if [[ ! -d "${src}" ]]; then
  log_err "Missing skill folder: ${src}"
  exit 1
fi

if [[ -e "${dest}" ]] && [[ "${force}" -eq 0 ]]; then
  if [[ "${dry_run}" -eq 1 ]]; then
    log_warn "Existing install detected; dry-run will show replacement steps."
  elif [[ -t 0 ]]; then
    if ! confirm_replace; then
      log_warn "Install cancelled."
      exit 0
    fi
  else
    log_err "Destination exists and prompt is unavailable. Re-run with --force."
    exit 1
  fi
fi

log_step "2/5" "Preparing destination"
if [[ "${dry_run}" -eq 1 ]]; then
  printf "  mkdir -p %q\n" "${dest_root}"
else
  mkdir -p "${dest_root}"
fi

log_step "3/5" "Removing previous install (if present)"
if [[ "${dry_run}" -eq 1 ]]; then
  printf "  rm -rf %q\n" "${dest}"
else
  rm -rf "${dest}"
fi

log_step "4/5" "Copying skill files"
if [[ "${dry_run}" -eq 1 ]]; then
  if command -v rsync >/dev/null 2>&1; then
    printf "  rsync -a %q %q\n" "${src}/" "${dest}/"
  else
    printf "  cp -R %q %q\n" "${src}" "${dest}"
  fi
else
  if command -v rsync >/dev/null 2>&1; then
    rsync -a "${src}/" "${dest}/"
  else
    cp -R "${src}" "${dest}"
  fi
fi

log_step "5/5" "Verifying install"
if [[ "${dry_run}" -eq 1 ]]; then
  printf "  verification skipped in dry-run mode\n"
  log_ok "Dry run complete."
  exit 0
fi

missing=0
for rel in "${required_paths[@]}"; do
  if [[ ! -e "${dest}/${rel}" ]]; then
    log_err "Missing expected file: ${dest}/${rel}"
    missing=1
  fi
done

if [[ "${missing}" -ne 0 ]]; then
  exit 1
fi

log_ok "Installed ${skill_name} to ${dest}"
printf "Next: ls %q\n" "${dest}"
