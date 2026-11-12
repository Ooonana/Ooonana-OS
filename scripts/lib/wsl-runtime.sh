# Ooonana WSL runtime guards. Embedded in the local adapter, not ISO payload.
# Optional prefix is for owned offline fixtures; live launch always uses /run.
ooonana_wsl_runtime_parent_safe() (
  wsl_parent="$1"; wsl_owner="$2"
  [ ! -L "$wsl_parent" ] && [ -d "$wsl_parent" ] || exit 1
  [ "$(stat -c %u "$wsl_parent")" = "$wsl_owner" ] || exit 1
  wsl_mode="$(stat -c %a "$wsl_parent")"
  case "$wsl_mode" in ''|*[!0-7]*) exit 1 ;; esac
  [ "$((0$wsl_mode & 0022))" = 0 ] && [ "$((0$wsl_mode & 0001))" = 1 ]
)

ooonana_wsl_runtime_ready() (
  wsl_uid="$1"; wsl_prefix="${2:-}"
  case "$wsl_uid" in ''|*[!0-9]*) exit 1 ;; esac
  wsl_owner=0
  if [ -n "$wsl_prefix" ]; then
    case "$wsl_prefix" in /*) ;; *) exit 1 ;; esac
    [ ! -L "$wsl_prefix" ] && [ -d "$wsl_prefix" ] || exit 1
    wsl_owner="$(id -u)"
  fi
  for wsl_parent in "$wsl_prefix/run" "$wsl_prefix/run/user"; do
    ooonana_wsl_runtime_parent_safe "$wsl_parent" "$wsl_owner" || exit 1
  done
  wsl_directory="$wsl_prefix/run/user/$wsl_uid"
  [ ! -L "$wsl_directory" ] && [ -d "$wsl_directory" ] || exit 1
  [ "$(stat -c %u "$wsl_directory")" = "$wsl_uid" ] &&
    [ "$(stat -c %a "$wsl_directory")" = 700 ]
)

ooonana_wsl_prepare_runtime() (
  wsl_uid="$1"; wsl_gid="$2"; wsl_prefix="${3:-}"
  case "$wsl_uid" in ''|*[!0-9]*) exit 1 ;; esac
  case "$wsl_gid" in ''|*[!0-9]*) exit 1 ;; esac
  wsl_owner=0
  if [ -n "$wsl_prefix" ]; then
    case "$wsl_prefix" in /*) ;; *) exit 1 ;; esac
    [ ! -L "$wsl_prefix" ] && [ -d "$wsl_prefix" ] || exit 1
    wsl_owner="$(id -u)"
  else
    [ "$(id -u)" = 0 ] || { echo 'WSL runtime preparation needs root' >&2; exit 1; }
  fi
  for wsl_parent in "$wsl_prefix/run" "$wsl_prefix/run/user"; do
    if [ ! -e "$wsl_parent" ] && [ ! -L "$wsl_parent" ]; then
      mkdir -m 0755 "$wsl_parent" || exit 1
    fi
    ooonana_wsl_runtime_parent_safe "$wsl_parent" "$wsl_owner" || {
      echo 'WSL runtime: unsafe parent retained' >&2; exit 1;
    }
  done
  wsl_directory="$wsl_prefix/run/user/$wsl_uid"
  [ ! -L "$wsl_directory" ] || { echo 'WSL runtime: linked directory retained' >&2; exit 1; }
  if [ ! -e "$wsl_directory" ]; then
    (umask 077; mkdir "$wsl_directory") || exit 1
    chown "$wsl_uid:$wsl_gid" "$wsl_directory" || exit 1
  else
    [ -d "$wsl_directory" ] && [ "$(stat -c %u "$wsl_directory")" = "$wsl_uid" ] || {
      echo 'WSL runtime: unexpected owner/type retained' >&2; exit 1;
    }
  fi
  chmod 0700 "$wsl_directory"
  ooonana_wsl_runtime_ready "$wsl_uid" "$wsl_prefix"
)
