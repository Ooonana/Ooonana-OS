# Qt portal live-palette candidate

Unpublished native Qt6.11.1 plugin fix. Not installed in WSL or published repo.
Final ISO must wait for package/provenance integration and release validation.

Qt's portal bridge receives live color preference, but its fallback base theme
can retain a cached palette. One added cache invalidation, before the existing
theme-change event, lets held-open widgets repaint. No stylesheet, app restart,
terminal-profile rewrite, privileged helper or polling loop.

Vendor input files are pinned individually in source-pins.json. Patcher refuses
changed/extra/linked inputs; all other vendor code remains unchanged. CMake
requires exact6.11.1 public/private headers. Builder uses a read-only task-owned
musl build cache and private overlay, records dependencies/input/binary hashes,
and disables networking for compilation. It never updates host/Ooonana WSL.
Existing output refuses overwrite. Reusing a previous task-owned compiler upper
is opt-in via OOONANA_QT_BUILD_REUSE, not an installed-system operation.

QA helper only accepts a hashed candidate against the pinned original plugin
hash, then binds it read-only inside disposable root. Never ABI-mix versions.
Tests cover actual portal change signals, held Chromium/Qt paint, unchanged
window state, retained browser address draft and unchanged terminal profile.

Remaining: unsigned native package/provenance/closure integration; other Qt
plugins/apps, Firefox, installed/mixed-DPI sessions. Custom app palettes and
terminal color profiles stay user-owned. No whole-desktop completion claim.

References: [Qt6.11 portal implementation](https://raw.githubusercontent.com/qt/qtbase/v6.11.1/src/plugins/platformthemes/xdgdesktopportal/qxdgdesktopportaltheme.cpp),
[Qt platform palette cache](https://github.com/qt/qtbase/blob/6.11/src/gui/kernel/qplatformtheme.cpp),
[Settings portal contract](https://raw.githubusercontent.com/flatpak/xdg-desktop-portal/main/data/org.freedesktop.portal.Settings.xml).
