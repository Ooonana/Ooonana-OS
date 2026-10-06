#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

out="$(bash "$ROOT/scripts/build-android-package-repo.sh" \
  --dry-run \
  --out-dir /tmp/ooonana-android-aarch64-test)"

printf '%s\n' "$out" | grep -F 'arch: aarch64' >/dev/null
printf '%s\n' "$out" | grep -F 'alpine: 3.23' >/dev/null
printf '%s\n' "$out" | grep -F 'v3.23/main/aarch64' >/dev/null
printf '%s\n' "$out" | grep -F 'v3.23/community/aarch64' >/dev/null

for pkg in git openssh-client-default tmux nano jq ripgrep fd tree zip unzip make gcc g++ cmake ninja-build nodejs npm sqlite; do
  grep -Fx "$pkg" "$ROOT/configs/packages/android-aarch64.list" >/dev/null
done

for forbidden in \
  ooonana-core ooonana-kernel openvino-chat wine wine-compat \
  bunanachat devicechat \
  xfce4 lxqt-desktop openbox mate-desktop-environment plasma-desktop plasma-mobile phosh; do
  ! grep -Fx "$forbidden" "$ROOT/configs/packages/android-aarch64.list" >/dev/null
done

grep -F -- '--arch "$ARCH"' "$ROOT/scripts/build-android-package-repo.sh" >/dev/null
grep -F 'publish-repo-generation.py --source android-repo-staging --target public/aarch64' "$ROOT/.gitlab-ci.yml" >/dev/null
grep -F 'android_repo_url="${repo_url%/}/aarch64"' "$ROOT/.gitlab-ci.yml" >/dev/null
grep -F -- '--sign-key' "$ROOT/scripts/build-android-package-repo.sh" >/dev/null
grep -F 'repository-20261002.pub' "$ROOT/scripts/build-android-package-repo.sh" >/dev/null
grep -F 'public key does not match bundled Ooonana trusted key' "$ROOT/scripts/build-android-package-repo.sh" >/dev/null

! grep -F 'desktop-manager' "$ROOT/scripts/build-android-package-repo.sh" >/dev/null

echo OOONANA_ANDROID_AARCH64_REPO_TEST=PASS
