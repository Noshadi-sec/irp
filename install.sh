#!/bin/bash
{
# Truncation guard: this brace group opens on line 2 and closes on the last
# line, so bash reads the whole file before running anything. A download cut
# off before the final `}` is a syntax error at EOF, and nothing runs.
set -euo pipefail

PACKAGE="irp-agents"
REPOSITORY="Noshadi-sec/irp"
version_pattern='[0-9]+\.[0-9]+\.[0-9]+((a|b|rc)[0-9]+)?'
version="${IRP_VERSION:-}"
dry_run=false
start_setup=true
verbose=false

fail() {
  printf 'IRP installation failed: %s\n' "$1" >&2
  exit 1
}

usage() {
  cat <<'USAGE'
Usage: install.sh [--version VERSION] [--dry-run] [--no-setup] [--verbose]

Installs the IRP CLI with `uv tool install`, then starts `irp setup`
when a terminal is available. Pass --no-setup to run `irp setup` later.
This installer needs uv and never installs it, Python, or anything else.
USAGE
}

main() {
  while (($# > 0)); do
    case "$1" in
      --version)
        (($# >= 2)) || fail "--version requires a value."
        version="$2"
        shift 2
        ;;
      --dry-run) dry_run=true; shift ;;
      --no-setup|--no-prompt) start_setup=false; shift ;;
      --verbose) verbose=true; shift ;;
      --help|-h) usage; exit 0 ;;
      *) fail "unknown option: $1" ;;
    esac
  done

  if [ "$verbose" = true ]; then
    set -x
  fi

  platform="$(uname -s)"
  [ "$platform" = "Darwin" ] || [ "$platform" = "Linux" ] || fail "IRP supports macOS and Linux."
  command -v curl >/dev/null 2>&1 || fail "curl is required. Install curl, then rerun this installer."
  command -v uv >/dev/null 2>&1 || fail "uv is required. Install it from https://docs.astral.sh/uv/getting-started/installation/ and rerun this installer."

  if [ -n "$version" ]; then
    [[ "$version" =~ ^${version_pattern}$ ]] || fail "version must be an exact release such as 0.1.0."
  else
    release_json="$(curl -fsSL --proto '=https' --tlsv1.2 --retry 3 -H 'Accept: application/vnd.github+json' "https://api.github.com/repos/$REPOSITORY/releases/latest")" \
      || fail "the latest release could not be resolved. Check network access or pass --version VERSION."
    tag="$(printf '%s' "$release_json" | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -n 1)"
    [[ "$tag" =~ ^${PACKAGE}-(${version_pattern})$ ]] || fail "the latest release tag was invalid. Retry later or pass --version VERSION."
    version="${BASH_REMATCH[1]}"
  fi

  bin_dir="$(uv tool dir --bin 2>/dev/null)" || fail "uv could not report its tool directory. Check your uv installation."
  install_bin="$bin_dir/irp"

  printf 'IRP install plan\n'
  printf '  Version: %s\n' "$version"
  printf '  Command: uv tool install --force %s==%s\n' "$PACKAGE" "$version"
  printf '  Binary:  %s\n' "$install_bin"
  printf '  Setup:   %s\n' "$([ "$start_setup" = true ] && printf 'start when a terminal is available' || printf 'skipped')"

  if [ "$dry_run" = true ]; then
    printf 'Dry run complete; no changes made.\n'
    exit 0
  fi

  uv tool install --force "$PACKAGE==$version" || fail "uv could not install IRP. Check network access to PyPI, then retry."
  [ -x "$install_bin" ] || fail "uv finished without installing the irp command at $install_bin."
  installed_version="$("$install_bin" --version 2>/dev/null | tr -d '[:space:]')" || fail "the installed version could not be read."
  [ "$installed_version" = "$version" ] || fail "installed version $installed_version does not match $version."

  printf 'IRP %s is installed.\n' "$version"
  case ":$PATH:" in
    *":$bin_dir:"*) ;;
    *) printf 'Add %s to your PATH (or run `uv tool update-shell`).\n' "$bin_dir" ;;
  esac
  if [ "$start_setup" = true ] && [ -r /dev/tty ] && [ -w /dev/tty ] && [ -t 1 ] && [ -t 2 ]; then
    printf 'Starting IRP setup...\n'
    "$install_bin" setup </dev/tty >/dev/tty
  else
    printf 'Run %s setup to connect your agents.\n' "$install_bin"
  fi
}

main "$@"
exit $?
}
