# Current work - 2026-10-20

## October 20 Spotlight selection and default app fit

Real preferred-wrapper checks found Geany opening902×623 on640×600, clipping
menus/titlebar. Nemo's default height also overlapped panel/dock clearance.
Newly mapped floating Geany/Nemo frames now fit usable output only when needed;
already-fitting defaults and later user resize/move stay untouched. Native apps,
dialogs, tiled/fullscreen/hidden windows and reused/closed IDs are excluded.
No blanket font scaling or forced new desktop-wide app size.

Actual Files launch instead opened Wi-Fi: delayed search reset selected row,
and `profiles` outranked exact `Files`. Filtering/ranking/selection now finish
immediately; exact/prefix app names rank before description matches. Empty
query preserves catalog order; Unicode/no-match behavior stays.

Four real GTK/i3 wrapper cases pass terminal, Geany palette, Nemo Home, focus,
window bounds and later user geometry. Final Impeccable review caught missing
QA scaling application; corrected launcher/shared-content fixtures now record
actual192DPI/200% parent text and pass compact dark/desktop light cases. External
app/whole-desktop scaling is not inferred. Normal defaults stay100%. Both CIs
pass; signed generation `26407e012bd145c98b543d03621a7d563e6eb2e947c19e9517086687c2e8ca31`
published and installed in Ooonana WSL. Full signed checksums, separate runtime/
core transactions, verification/health and UID1000 imports/i3 checks pass.
Installed launcher/window-controls/dock bytes match source. Adapter/default
metadata refreshed without GUI restart; OpenVINO/boot config retained.
Whole-OS review remains active. Next requested: unify third-party titlebar
button size/placement with native controls, with fresh Impeccable review.
[Evidence](ui-whole-os-review.md#batch-31-preferred-launchers-search-selection-and-default-app-fit).

## October 19 flat dock, app groups and saved pins

Flat opaque dock now keeps pinned apps left and unpinned running apps right,
with section divider. Pin/Unpin never closes windows. Hold-drag reorders within
either section; explicit Pin/Unpin changes section. Keyboard Move left/right
also works. Atomic per-user `dock.json` saves app IDs/order only, never window
titles/PIDs/history. Failed saves retain old layout and expose recovery text.
Closed pins remain launchable; compact More apps retains overflow idle pins.
Direct grouped window rows/actions restore exactly one session; native dialogs
follow actual parent, different native apps and Firefox/Chromium stay distinct.
Top panel no longer has window controls/title/list; Task View stays.

Four real GTK/i3 dark/light normal100% and200% text-stress cases pass actual
Pin/Unpin, held mouse drag, rejected cross-section drop, reload, closed-pin
relaunch, minimize/restore, readonly failure/retry and keyboard window actions.
Actual320px overflow/hidden-pin options, edge tooltips, both panel sizes/themes
and2× device-scale controls also pass. Default60px dock/32px icons and global
100% scale remain. Native/rootfs/package-factory/panel-session regressions pass.
Runtime source `5a39c8c` passes both CIs and is signed/published as generation
`26bb8cf5f3ff10af9a104ac78886f32fe3f4fad280dd7644a7a956345be87942`.
Ooonana WSL core/runtime, adapter and default metadata refreshed; all1302
checksums, signatures, package/file/health checks and UID1000 import/i3 checks
pass. Installed UI bytes match source. No GUI restart or ISO build. OpenVINO,
boot config, history and prior generations retained.15 inactive private test
overlays removed (41340KiB logical); captures/logs stay. Windows duplicate-stage
cleanup blocked, not retried. Broader UI ledger stays open.
[Evidence and limits](ui-whole-os-review.md#batch-30-flat-dock-app-groups-and-persistent-pins).

## October 19 Qt scaling, pickers and desktop Home defaults

Actual Qt-only100%/200% probes pass both themes: six Preferences pages, font
chooser, image select/cancel/reopen, keyboard scrolling, exact pending path,
post-picker bounds and outer Cancel. GTK portal stays at desktop100%; this is
not physical mixed-DPI evidence or a new default. A real session defect was
reproduced: BusyBox user handoff preserved `/`/launch cwd despite correct HOME.
Desktop session now enters Home before bus/app startup, or refuses with clear
error if unavailable. Actual source prefix runs as UID1000 in Qt QA; picker
now opens Home. Explicit terminal workdir remains. Native/rootfs/WSL/package
regressions and final Qt matrix pass. Runtime source `f8402a7` passes both CIs;
signed generation `0c5889376f3bf6a88291ed60e5a7f80d6cb79ce33e31977d0010767d12ecc895`
is published and installed in Ooonana WSL. All1302 checksums, package transactions,
file verification, health hooks and installed UID1000 Home startup pass. Default
metadata/WSL adapter refreshed without GUI restart; OpenVINO/WSL config retained.
[Evidence and limits](ui-whole-os-review.md#batch-29-scaled-qt-pickers-and-session-home-defaults).

Follow-up dock direction is implemented/tested above; Home checkpoint below
does not yet contain those later changes. Whole UI ledger stays open.

Cleanup:45 inactive private QA overlays removed after exact-path, no-process,
no-symlink and all-process mount checks (434204KiB logical, regenerable). Captures,
logs, Firefox QA homes, source caches, history, checkpoints and ISO assets retained.
Receipt: `/var/tmp/ooonana-cleanup-20261019.KfO0FPGs`. Windows cleanup was rejected
before execution:22 bytecode files (~961kB) and completed duplicate F publication
stage remain. No retry/workaround used; no C:/F: deletion occurred. Logical ext4
reclaim does not imply immediate Windows free-space gain or VHD compaction.

## October 19 Task View and actual media integration

Panel numbers replaced by one compact overlapping-window Task View icon.
Existing window chooser now includes desktop switching/creation and exact
minimized-session restore; `Mod+Ctrl+Tab` opens it, existing workspace keys stay.
Real small-screen captures exposed clipped chooser height/unreadable inherited
colors; bounded rows and explicit child colors repair those defects, with
Paper/Graphite preference support. Actual private MPD/null-output checks also
found/fixed empty-tag parsing, Korean metadata encoding and Music growing back
over the panel. Parser-facing command locale stays unchanged. Real Dunst's
unchanged five-second timer recovers after service loss/restart and DND changes,
without a click/focus refresh. Runtime source `5395853` passes both CIs; signed
generation `ea616da2e3aa29602afdc8d26e21bbf4b418ae2ec8452cd020908155ac43f2d1`
is published and installed in Ooonana WSL. Core/runtime verification and health
hooks pass; installed UI/helper/i3 bytes match source. Default metadata/adapter
refreshed without GUI/WSL restart. Broader review stays active. No audible sound,
models or release ISO. [Checkpoint and GUI command](ui-whole-os-review.md#published-checkpoint-after-batch-28).

## October 19 Spotlight publication and native refresh

Runtime source `d499391` passes both CIs; signed generation is
`967ddd097a907cc4bb4075280c470198dc90dd8a45561a4c8bb2b4df217bac56`.
Pinned signature, all1302 checksums, clean300-source-file manifest and
654-package/612-node closure verified. Native core/runtime dry-run, reinstall,
verify and health hooks pass; both installed i3 configs match source and UID1000
`i3 -C` passes. Default metadata and local adapter refreshed without GUI/WSL
restart. OpenVINO metadata, WSL boot config, history and prior generations retained.
No user i3 overrides were present/changed. Actual WSLg input remains a separate
manual check; no release ISO, models or audio operation.
[Checkpoint and GUI command](ui-whole-os-review.md#published-checkpoint-after-batch-27).

## October 19 managed Spotlight and real app handoff

Actual i3 exposed a760px rule overriding Spotlight's display-aware GTK size;
640px screens clipped left controls atx=-60. Removed only forced resize, keeping
floating/border/centering and native defaults. Four dark/light,640/1280px cases
now pass actual desktop-entry discovery, X11 Return, real XTerm/native
Settings processes, launch dismissal, focus handoff and owned-window close.
Compact frame is586×442 within640×600. Current Settings source/wrappers are
read-only-bound in private QA; no mock launch success. Native/branding/rootfs/
package-factory regressions pass; publication/native refresh completed above.
[Evidence and remaining gates](ui-whole-os-review.md#batch-27-managed-spotlight-and-real-app-handoff).

## October 19 device-scale publication and native refresh

Runtime source `32a900a` passes GitHub/GitLab CI and is signed/published as
generation `32e04e40a81312cc13e732ab853d282c876b7192f743866e0137793de92cc73d`.
All1302 checksums, signature/trust pin, clean300-source-file manifest and
654-package/612-node closure verified. Native core/runtime dry-run, reinstall,
verification and health hooks pass; installed dock/controls bytes match source.
Default metadata and local WSL adapter refreshed without GUI/WSL restart;
OpenVINO metadata, boot config and history preserved. UID1000 imports/functions
pass; noninteractive WSLg emitted a seat warning, so actual WSLg input remains
unverified. No release ISO, audio or model operation. Whole-OS review stays
active. [Checkpoint](ui-whole-os-review.md#published-checkpoint-after-batch-26).

## October 19 actual device-scale alignment

Real `GDK_SCALE=2` exposed third-party controls displaced/doubled beyond their
i3 titlebar and logical/device mixing in fullscreen overlap. GTK placement,
CSS/icon budgets and i3 hit testing now use the appropriate coordinate units.
Four dark/light, normal-font 1×/2× cases pass real Minimize/Close clicks,
titlebar bounds and fullscreen restoration. Default typography stays unchanged;
2× is an isolated test, not a new default. Pure scale/negative-origin/remap
guards run in both CIs. Native/rootfs source regressions pass; broader
package-factory, shared native controls and actual2× dock-edge regressions also
pass both themes. Signed publication/native refresh are completed above.
[Evidence and limits](ui-whole-os-review.md#batch-26-device-scale-coordinate-alignment).

## October 19 dock publication and native WSL refresh

Source `519de7d` passes both CIs; signed candidate generation is
`10514cb56d6b0ae8d73edd5465a2caa323e3e6c1564fb0232c20f0bd50841d6d`.
Clean 300-source-file manifest, pinned signature, all1302 checksums and
654-package/612-node closure verified. Native core/runtime dry-run, reinstall,
verify and health hooks pass; installed dock bytes match source, UID1000 import
passes. Default source metadata and local WSL adapter refreshed, without
restarting GUI/WSL. History, prior generations, boot config and OpenVINO metadata
retained. Two completed QA overlays removed (5512KiB logical); captures/logs stay.
No Windows compaction/free-space claim, models, audio or ISO build. Broader UI
review, actual scaling/session/display/manual gates remain open.
[Checkpoint](ui-whole-os-review.md#published-checkpoint-after-batch-25).

## October 19 dock edge/fullscreen review

Real edge probes found dock covering fullscreen content. Existing i3 tree events
now hide it only for visible fullscreen containers covering its monitor, and
restore it without focus theft. Inactive workspaces, hidden tabs, scratchpad and
other outputs do not incorrectly hide it; global fullscreen is handled. No new
polling, resizing or idle-auto-hide policy. Eight dark/light variants pass real
tooltips, four-corner menus, centering, 44px targets and fullscreen/workspace
restoration: 640×600 normal/200%, 1024×768 normal, 320px dock-only stress.
Pure guards plus native/rootfs/package and both-theme multi-session/action/
keyboard regressions pass. Signed publication/WSL refresh are completed above.
[Evidence and limits](ui-whole-os-review.md#batch-25-dock-edges-and-fullscreen).

## October 18 administration/dialog publication and WSL refresh

Source `2ff2506` passes both CIs; signed candidate generation is
`49c469cb08b65e99ca9056edee0882a848449f96a291a9bbb0f87d60b094e2eb`.
All 1302 checksums, pinned signature, clean 300-file source manifest and
654-package/612-node closure verified. Native core/runtime dry-run, reinstall,
verification and health checks pass; installed shared UI/askpass bytes match
source, UID1000 imports pass. Default metadata and local adapter refreshed,
without restarting GUI/WSL. OpenVINO metadata, boot config and history preserved.
No ISO, audio or model operation. Broader review, including dock edges and
installed-session/physical/manual gates, remains active.
[Checkpoint and evidence](ui-whole-os-review.md#published-checkpoint-after-batch-24).

## October 18 administration and actual Settings storage review

Real password prompt lacked an accessible field name; added Account password
without changing its size. Six private dark/light, compact/desktop/200% checks
cover Escape, close, Enter, blank rejection and secret-pipe-only output. Actual
sudo/askpass cancellation now reaches Packages/Health, restores controls and
supports retry; private policy permits only harmless `/bin/true`, no package
transaction or real credentials. Actual Settings 0600 writes, reopen, read-only
failure rollback and retry also pass six variants. That path exposed scaled
short error dialogs crossing screen edges; shared dialogs now use GTK-compatible
font metrics and existing scrollable diagnostics when text would be too tall.
Signed publication/WSL refresh are completed above; broader review stays
active. [Evidence and remaining limits](ui-whole-os-review.md#batch-24-administration-and-settings-storage).

## October 18 notification publication and native refresh

Runtime source `9aa2ac7` passes GitHub/GitLab CI and is signed/published as
generation `ad33c627306829f0d3b6eba287a71215d86fb9d8440645a90fbd3106bab5c4e3`.
All 1302 checksums, signature/trust pin, clean 300-source-file manifest and
654-package/612-node closure verified. Native core/runtime dry-run, reinstall,
verify and health checks pass after full verification; installed notification
files match source and UID1000 imports pass. Default metadata resolves the new
snapshot; WSL adapter refreshed without restart. History, previous generations,
OpenVINO metadata and boot configuration retained. No ISO, sound or models.
[Publication evidence and remaining gates](ui-whole-os-review.md#published-checkpoint-after-batch-23).

## October 18 notification reading and storage recovery

Actual private Dunst/GTK lifecycle checks reproduced lost keyboard focus and
reading position after new arrivals, plus saved rows disappearing when read-state
writes failed. Center now restores semantic focus/reading position after GTK
allocation, keeps readable live/archive history on storage failures and presents
persistent save/remove errors with retry recovery. No text/control enlargement.
Four normal100% dark/light, 640×600/1024×768 checks pass, including explicit
service restart refresh, DND reset, reused notification IDs and clear-all.
Only owned private history is used; sound is suppressed in QA, not production.
Signed publication and native WSL refresh are completed above; broader review
remains active. [Evidence and limits](ui-whole-os-review.md#batch-23-notification-reading-and-storage-recovery).

## October 18 multilingual panel publication and WSL refresh

Runtime source `55c25b0` passes both CIs and is signed/published as generation
`0d8e862e06fa7e8bc068fea77308ed4119a78af728e034a4953f32b1ce5b800d`.
Clean 300-source-file manifest, all 1302 checksums, signature/trust pin and
654-package/612-node closure verified. Prior generation unchanged. Native WSL
snapshot reuses 643 immutable archives; core/runtime dry-run, reinstall, verify
and health checks pass after full verification. Installed window-list/supervisor
match source and Polybar config matches signed archive. UID1000 imports/checks
all responsive budgets. Default cloud metadata updated, 654 packages/two sources.
Canonical local adapter refreshed without GUI/WSL restart. OpenVINO metadata,
boot configuration, history/models/keys and rollback checkpoints retained.
No ISO, sound or physical device operation. Broader review remains active.
[Publication evidence and limits](ui-whole-os-review.md#published-checkpoint-after-batch-22).

## October 18 Qt picker and multilingual panel details

Real Qt font/image pickers pass 640×600/1024×768, dark/light: focused floating
dialogs, correct settings parent, bounds, Escape, reopen, exact owned-image path
and outer Cancel retention. No Qt restyling or user-profile changes needed.
Panel review then found missing Korean/CJK glyphs despite installed fonts, clipped
right controls at 760px and silent AI drift at middle-width thresholds. Added
shipped Noto fallback, responsive Wi-Fi budgets, compact 760–999px status priority
and tighter gaps below 1280px. Font sizes and opaque Graphite identity unchanged.
Actual accent-pixel centering guards now catch drift that Polybar logs missed.
Wide-label/100%/999+ sample checks cover 640/760/900/1000/1024/1100/1280px in both
app appearances; native/rootfs/package-factory checks pass. Four completed owned
Qt overlays removed; captures/logs/history retained. README desktop capture is
current. Signed candidate/installed WSL refresh is completed above.
[Evidence and remaining work](ui-whole-os-review.md#batch-22-qt-pickers-and-wide-label-panel-details).

## October 18 Qt placement publication and installed refresh

Runtime source `5c48b59` passes both CIs and is signed/published as generation
`5a66c5817a8a9fd0672c86378b18daf876b61ecef0a12fa504ab6a19e485b4c9`.
Clean 300-source-file manifest, 654 packages/612 dependency nodes, all 1302
checksums and signature/trust pin verified. Previous generation manifest stays
unchanged. Native WSL snapshot reuses 643 immutable archives; full verification
precedes separate core/runtime dry-runs, reinstall, file verification and health
checks. Installed window-controls hash exactly matches source; OpenVINO metadata
unchanged. Default cloud source now resolves new native snapshot, 654 packages
from two sources. Canonical local adapter refreshed without GUI/WSL restart;
installed guards also recreate transient `/run/user/1000` mode0700 correctly.
Four final QA overlays removed, in addition to 17 earlier; captures/logs/history
retained. No compaction/free-space claim, models, sound or ISO operation.
[Publication evidence and remaining gates](ui-whole-os-review.md#published-checkpoint-after-batches-20-21).

## October 18 Qt settings placement and full category review

Actual 640×600 QTerminal Preferences reproduced y=-13, clipping its titlebar.
An i3 map-centering rule alone did not fix Qt's later positioning; removed that
ineffective attempt. Existing window-controls service now corrects only newly
observed off-output QTerminal dialogs, once after settling. Native sizes/styles
stay unchanged. Changed geometry, hidden/closed/fullscreen/oversized windows and
service-start existing windows are left alone; no repeated positioning policy.
Pure guards plus real six-page dark/light review, bounds/Cancel, later user moves
and minimize/restore/fullscreen/move/exit pass 640×600 and 1024×768. Native UI,
rootfs and package-factory regressions pass. Publication/installed WSL refresh
is completed above; WSL-local runtime fix below is also live.
[Evidence and scope](ui-whole-os-review.md#batch-21-qt-settings-placement-and-categories).

## October 18 local WSL document-runtime correction

Local desktop adapter now uses canonical `/run/user/UID`, prepared through its
existing privileged socket setup. No boot command, daemon, broad environment
preservation or ISO-payload change added. Parent/type/owner/mode guards refuse
unsafe paths; existing same-owner contents survive permission correction.
Switching from the home runtime resets inherited bus address/marker only.
Root Ubuntu and nonroot Ooonana BusyBox fixtures, exact generated runtime
selection and full WSL-distro regressions pass. Adapter installed in Ooonana;
actual runtime is UID/GID1000, mode0700. Packaged launcher and `/etc/wsl.conf`
hashes unchanged. No GUI/WSL restart, sound, model or ISO operation. Actual
installed Firefox/WSLg interaction still needs its separate session check.
[Scope and evidence](ui-whole-os-review.md#batch-20-local-wsl-document-runtime).

## October 18 Qt publication and Firefox first-run follow-up

Qt source `f30dc7c` passes both CIs and is now signed/published as generation
`4245766927382e2806c6891ee027acd37d6e2761e4331ed3458a2b7946797454`.
Exact clean source manifest (299 files), all 1302 checksums, signature/trust pin,
654 packages/612 dependency nodes and prior-generation immutability pass.
Native Ooonana WSL core/runtime dry-runs, reinstalls, verification/health hooks,
exact helper/palette hashes and UID1000 GTK/CSS/default-font/query checks pass.
Default metadata points to the new native snapshot; adapter refreshed without
GUI/WSL restart. Existing OpenVINO metadata unchanged; no models/audio/ISO work.

Firefox QA now visibly expands first-run diagnostics, unchecks its opt-in and
accepts Terms only in the human-authorized disposable profile, on an isolated
network. Home-based runtime reproduced a selected-file permission error.
Canonical `/run/user/1000` resolves it; earlier apparent failures then proved to
be a QA assumption about private-window titles. Untraced real picker open/cancel,
exact portal URL plus rendered-content clipboard read and native window actions
now pass. Full redraw mirrors the existing WSL adaptation; no browser sandbox
disabled or broad access granted. Installed nested WSL runtime correction was
the next fix at this checkpoint; Batch 20 above records its implementation.

F: staging duplicate is verified against retained generation but cleanup was
blocked by execution policy; retained, with exact manual command in the ledger.
[Publication, first-run evidence and limits](ui-whole-os-review.md#published-checkpoint-after-batch-19).

## October 18 Qt appearance and removable-storage interruption

Real cached Qt6/QTerminal review found light menus/dialogs in dark mode and a
500px single tab. Theme application now bridges the selected appearance to
GSettings/Settings portal and selects Qt's existing portal plugin only when no
custom platform theme is set. No global Qt stylesheet or scale override added.
New terminal profiles use opaque Graphite/Paper, 11pt monospace, small margin,
hidden single-tab strip and natural multi-tab widths. Existing Qt preferences
and linked configurations stay untouched. Both 1024×768 appearances and actual
minimize/restore/fullscreen/move/exit-cancel/confirm pass on private Xvfb with
the existing WSL full-redraw adaptation. Thirteen preference/palette tests and
native/rootfs/package-factory regressions pass, including exact palette bytes
in built rootfs and core archive. No sound, models or release ISO operation.

Firefox rerun reuses the existing disposable QA Flatpak installation, with no
download/network or user-profile access. Real UID1000 renderer sandbox remains
active; first-run Terms still intercepts Open, so picker is not certified.
Windows detects the Realtek card reader but no SD disk/F: drive. No formatting,
repair or media writes attempted. New source is not yet signed/published to F:
or installed into Ooonana WSL; previous verified generation remains historical
checkpoint, not confirmation that the missing card is healthy.
[Qt captures, precise evidence and remaining work](ui-whole-os-review.md#batch-19-qt-appearance-and-first-run-proportions).

## October 18 installed branding and console diagnostics

Installed GRUB now shares live branding, stages its target font under Ooonana's
own filename and preserves existing custom boot font. Compact audio labels fit;
missing assets keep console/serial fallback. Actual private EFI main/submenus
and fallback at 640×480/1280×800 pass; kernel args/default/timeout unchanged.
Console status no longer overwrites consecutive warning lines. Normal desktop
console ordering allows existing pulse; serial/ambiguous/motion-off remain plain.
No new waits/workers; shutdown error feedback stops before recovery message.
Writer/native/backend/rootfs/ISO-fixture/initramfs regressions pass. Source
`9930c08` and both CIs pass. Signed 654-package generation
`1a0c0a9b91244d6e105e2c0aeeec8468240903218f4f112d529a9d8ae8284ba6`
and native Ooonana WSL refresh verified: signature, all 1302 checksums, clean
manifest, health hooks, exact installed hashes, user GTK/query and default cloud
cache. Adapter refreshed without restart. Redundant package copy removed after
658 matching hashes (784,431 bytes); history retained. Whole-OS review remains
active. No real install, sound, model, power or release ISO operation.
[Evidence](ui-whole-os-review.md#batch-17-consistent-installed-boot-branding).

## October 18 installer publication and minimal GRUB

Installer/presentation source `8066066` passed both CIs and is published as signed
654-package generation `5eaba3fa8900ea4c10ee9a21b9f932df80d8a44828d025ffe2f536eb2ef53ec8`.
All 1302 checksums, trust pins, source manifest and prior-generation immutability
verified. Native Ooonana WSL runtime/core dry-runs, transactions, health hooks,
exact helper hashes, user GTK/CSS/query and default metadata refresh pass. Adapter
refreshed without restart. Temporary package copy removed after all 658 files
matched retained generation (779,948 bytes); history/models/keys/ISO remain.
New real EFI review found invisible minimal-GRUB entries; explicit readable
colors/key hints now pass both 640×480 and 1280×800 role-pixel checks. Installed
text fallback is readable; branded installed menu remains a separate improvement.
No larger defaults: desktop stays 100%/10pt. No audio, model or ISO operation.
[Evidence and remaining work](ui-whole-os-review.md#published-checkpoint-after-batches-14-15).

## October 18 terminal installer follow-up

Private shell/PTY baseline reproduced password trimming/extra newline, reboot
on closed input/unknown text and force/poweroff fallback. Hidden entry now
preserves exact spaces/backslashes, reports EOF failure and restores original
terminal state, including interruption. Completion accepts explicit Enter/reboot
through orderly `bunana --restart` only; EOF, stay and unknown input do not reboot.
Failure remains visible. Removed pretend completed phase counters before work;
waiting text points to actual log. Seven isolated shell/PTY regressions and
full native/rootfs checks pass; no real installer or power command executed.
Source/candidate publication is verified above. Whole-OS review
and live/device gates remain open. Default text stays 100%/10pt.

## October 17 installer and preference follow-up

Installer form/review now fit actual 200% font metrics on 640×600, with readable
scrolling disk details, compact labels and explicit default Cancel. Default UI
remains 100%/10pt; 200% captures are stress tests only. Keyboard checks preserve
all 16 semantic fields, including password spaces and `|`; malformed form output
cannot shift targets. Theme apply retains user font/DPI/icon/unknown settings
and bridges reduced motion to GTK/XSettings. Eight private-file regressions,
full native/rootfs/backend checks and both-theme actual YAD fixtures pass.
No real installation, disk enumeration, audio, model or ISO work. Signed
candidate/installed WSL refresh for this follow-up is verified above.
[Evidence and remaining gates](ui-whole-os-review.md#batch-14-installer-fit-and-retained-presentation-preferences).

## October 17 Setup form and review follow-up

Reproduced 200% form/review overflow, invalid-field focus loss and stale review
approval dispatch after parent close. Setup now scrolls its welcome with the
form, stacks wide labels, wraps swap text and uses a bounded scrollable review.
Review includes manual routing/repository/password-presence choices, never
password contents. Inline validation focuses the field, preserves secrets and
checks IPv4/prefix/gateway/DNS and repository input. Pending/reentrant/closed
approval is refused; failure feedback remains visible and warns changes may be
partial. Existing CLI/backend authority and password transport are unchanged.
Private GTK/i3 checks pass both themes, 100/200%, including keyboard focus,
review Back/parent-close, draft retention, duplicate actions and reduced motion.
Prior content/dialog regression and full native source suite pass. Source
`a57c0cb` is on both remotes; GitHub/GitLab checks pass. Signed generation
`6515c1e66d0770af57ddc3544ba2446d91a4492108cbb4d73d7fc4412fc4bf80`
and native Ooonana WSL refresh verified, including pinned key, signature, 1302
checksums, health hooks, installed module hashes, UID1000 GTK/CSS and default
cloud metadata. Scratch stage/payload removed; history/checkpoints stay. Adapter
refreshed without restart. Computer Use still fails kernel-assets initialization
with error 3, so live Windows/WSLg gates remain open. Installer interaction review
continues. [Evidence](ui-whole-os-review.md#published-checkpoint-after-batch-13).

## October 17 Sound, Brightness and Music details

Startup waits for verified state rather than allowing guessed writes. Audio
reads and changes the selected output by identity; route/list failures remain
visible, preserve drafts and offer Refresh/retry. Unknown volume/mute stays
unknown. Brightness accepts only a verified display-backlight device, binds
writes to that device and does not guess 75% when hardware is absent. Music
polling cannot re-enable pending actions or overwrite an uncommitted volume.
Failures remain inline; closed callbacks and duplicate actions are refused.

Controls use compact content-fit actions, labelled sliders/device selectors,
bounded full-value tooltips and scrollable, keyboard-accessible content. Private
GTK/i3 checks pass dark/light, 100/200% text; all 25 native catalog pages pass
both appearances at 640×600. Full native/backend source regression passes.
No real route/mute/brightness/playback change or sound test ran. Source `9d02988`
is pushed to both remotes and both CI checks pass. Signed 654-package generation
`8cc58fc2caf8b8b7fd600bfe8925fa9fa4d5fadd2116bd315374953a9b61a2b3`
is published locally; previous generation is unchanged. Native Ooonana WSL
refresh verified after a successful startup retry: signature, 1302 checksums,
package health, installed hashes, UID1000 GTK/CSS, nonroot query and default
metadata source. Adapter refreshed; no forced restart.
Eight redundant staging copies, six transfer archives and five bytecode files
removed, including final publication stage. History/models/keys/ISO checkpoints
stay. Review resumed with both-theme 1024px panel and scoped-session regression,
all passing silent fixtures. [Evidence and limits](ui-whole-os-review.md#published-checkpoint-and-cleanup-after-batch-12).

## October 17 wireless details and lifecycle

Wi-Fi/Bluetooth now reject overlapping actions and closed-window callbacks;
selection changes cannot hide pending progress. Indeterminate feedback runs only
while busy and respects reduced motion. Service/controller state gates actions,
with Repair recovery retained. Reset and Bluetooth Remove default to Cancel,
remain parent-owned and cannot dispatch after parent close.

Wi-Fi advanced forms preserve secrets and show inline IPv4/gateway/DNS/proxy
errors with visible field focus. Certificates use bounded native local pickers;
scaled forms stack labels. Bluetooth secondary actions move under Device actions.
Scrollable wireless content, text-aware CSD reserves and one-time initial
placement correction prevent small-screen overflow, without fighting later drag.
Private GTK/i3 checks pass both themes, normal and 200% text; prior wireless,
shared-dialog and scaled Settings regressions pass. Backend/native source tests
pass. Source `617dabe` is on both remotes; GitHub/GitLab checks passed. Signed
654-package generation `6bf47130fc3e1fa0d5ac5dc10445d1f11dfaf4fdb24735e3a9014320ecf2076a`
and native Ooonana WSL core/runtime refresh verified: pinned keys, signature,
1302 checksums, clean source manifest, health hooks, installed hashes, actual GTK
imports/styles and nonroot query. Default metadata cache refreshed to the new
cloud snapshot. Older generations/checkpoints retained; adapter refreshed without
restart. Smaller headings included. No physical radio, audio, OpenVINO/model or
ISO action. [Evidence](ui-whole-os-review.md#published-checkpoint-after-batch-11).

## October 16 smaller-heading refinement

Shared native page headings change 16→14pt, hero headings 20→18pt and launcher
search 14→12pt, with proportional search padding. Body stays 10pt; card titles,
window controls, user DPI and Korean text remain unchanged. Impeccable's role
hierarchy, ui-styling's shared tokens and ui-ux-pro-max's consistent type scale
guide this narrow refinement, not a theme/framework replacement.
Private actual GTK density/type checks pass dark/light at 100/200%; compact
Task Manager interaction regression passes both themes. Included in October 17
signed candidate/installed WSL checkpoint above. No ISO built.
[Evidence](ui-whole-os-review.md#smaller-heading-refinement).

## October 16 Task Manager and window interaction follow-up

Task Manager gains compact navigation, bounded/copyable sensor values, filtered
counts, full-detail row tooltips/Ctrl+C, text-aware numeric widths and stable
row/scroll refresh. Missing counters clear stale graphs. End task defaults to
Cancel, retains confirmed identity and closes with parent. Actual private
GTK/i3 checks include 200% text and owned-process termination regression.

Window review found missing workspace keys and invalid bare move/resize mouse
commands. All number/select/move/cycle keys added; broken overrides removed.
Both-theme real native/XTerm pointer, tiling/tab/stack, focus, fullscreen,
exact-session restore and close checks pass with private compositor, without
i3 command-error bars. Branding test corrected rather than preserving bad code.
Source `b6f186f` is pushed to both remotes and both CI checks pass. Signed
654-package candidate and Ooonana WSL core/runtime update verified, including
1302 checksums, health hooks and installed source hashes. No ISO built or GUI
restart forced. Relaunch desktop/apps. C: free space fell to 1.1 GiB, so no more
heavy QA/build work this pass. [Evidence and limits](ui-whole-os-review.md#batch-9-task-manager-detail-and-lifecycle-checks).

## October 16 typography follow-up

User requests smaller text. Default native body now matches desktop GTK at 10pt
(previously 10.5pt); page/card/hero headings are 16/11/20pt instead of 19/12/24pt.
Launcher search is 14pt instead of 16pt. AI no longer silently raises body text
to 14.5pt or titlebar text to 13pt on wide windows. User DPI/text scaling stays
respected, and action/window-control target dimensions are not blanket-shrunk.
The earlier large dark screenshot used 200% text as a stress fixture, not default
configuration. Normal-scale captures and current evidence follow in the ledger.
All 25 compact native pages pass dark/light, plus both-theme contrast,
native/generated density, wide AI and targeted 200% text checks. Source
`f39e99b` is pushed to both remotes, both CI checks pass, signed candidate and
Ooonana WSL refresh verified. Relaunch apps for new typography; no ISO build.
[Measurements and screenshot](ui-whole-os-review.md#batch-8-smaller-native-type-no-width-triggered-ai-zoom).

## October 16 native chat details; OpenVINO deferred

User defers OpenVINO until its unfinished major update is ready. No integration
changes, runtime setup/tests or model downloads in this pass. Earlier OpenVINO
entries below remain historical. Generic native Ooonana AI stays in scope.

Native chat now has proportional controls, compact chats/conversation switching,
bounded long captions, useful empty search, default-Cancel Delete and bounded
native attachment picker. Failed/stale/closed provider callbacks stay safe and
UTF-8 attachments remain editable, never sent automatically. Actual private
GTK/i3 checks pass dark/light compact/desktop and targeted 125/200% text; existing
stream/cancel/copy/keyboard regression passes with fixture processes only.
Published with typography follow-up below; existing ISO unchanged. [Evidence and scope](ui-whole-os-review.md#batch-7-generic-native-chat-details-openvino-deferred).

## October 16 proportional controls and Settings

Source `8cc3b17` fixes oversized desktop controls without reducing type. At
normal scale, native button/entry/dropdown heights change from 42/52/46px to
32/32/33px; native helper actions fit their labels. Generated GTK theme matches
the compact sizing. Existing window-control/dock targets remain unchanged.

Settings gains narrow page navigation, bounded/selectable status values,
automatic visible keyboard focus, bounded native wallpaper/log dialogs, Copy
log, honest Bluetooth errors, motion rollback and duplicate/late-action guards.
Private actual GTK/i3 tests pass 25 normal-scale native pages in dark/light;
targeted Settings/control fixtures pass through 200% text. Geany real picker and
window controls pass. Commands that could change services/packages/wallpaper
were mocked in the interaction fixtures. No sound, models or ISO build.

Both remotes contain source. [GitHub regression](https://github.com/Ooonana/Ooonana-OS/actions/runs/38824635241)
and [GitLab smoke](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2953124816)
passed. Signed 654-package candidate generation and native Ooonana WSL update
are verified, including core/runtime health hooks, source hashes, actual GTK/CSS
imports as UID1000 and unprivileged package search. Previous generations and
rollback checkpoints stay. Relaunch desktop/apps for updated code/theme.
[Publication and coverage ledger](ui-whole-os-review.md#published-checkpoint-after-batch-6).
Broader application/display/session review remains active; physical/interactive
gates are not implied by fixture success.

## October 15 physical USB identification and frontend preparation

User connects freshly flashed disposable G: USB and authorizes erasing fault-test
data there. Read-only payload hashing matches published ISO kernel/initramfs/
rootfs/EFI loader; persistent GRUB entry is present, persistence file absent.
No formatting, raw writable access, power cut, storage fill or physical upgrade.
Same-PC USB boot requires manual stage-1 evidence before fault tests.

Native installed Ooonana WSL gained Firefox launcher/QTerminal and coherent Qt6
dependencies through real nonroot package operations; archive verification and
offscreen QTerminal 2.4.0 version passed. No browser runtime/model downloads.
Windows UI/browser helpers fail at kernel-assets initialization even after reset;
no UI tests claimed, alternate automation or old PDF-navigation bypass attempted.
Signing/promotion scope still awaits answer; key stays local, stable unchanged.
[Payload proof, boundaries and manual USB baseline](physical-usb-qa-20261015.md).

## October 15 GitLab smoke repair and guide refresh

Screenshot identifies failed pipeline 2948699262, job 17185957127, commit
2f891ed. Job trace access is restricted; matching Alpine 3.24.2 reproduction
found first launcher test exits 127 because CI omitted `findmnt`. Added
`util-linux`, explicit readiness checks, Node and C compiler so PDF harness/time
CSR tests run instead of silently skipping. Both providers now run WSL fixtures;
those fixtures mock all Windows tools and check that interop cannot drain the
calling script's stdin. No real distro import/unregister from regression tests.

Field guide refreshed to installed WSL 0.10.0/stable 0.9.9, correct local GUI
launcher, verified user-built ISO and accurately separated remaining runtime/
interactive gates. Four rendered pages checked. Bootable PDF unchanged.

Read-only cleanup recheck: temporary QA registration/VHD, raw image and tarball
are absent; logs and replacement plan retained. C: ~3.7 GiB / F: ~28.9 GiB free.
No denied-target cleanup retry. Active disks/models/history/keys preserved.
CI/tests/docs only; no packaged runtime/kernel edits or ISO remake.
Remote eccf95c checks passed: GitLab 2948761455 and GitHub 38655509434.
Follow-up pins tested Ubuntu 24.04 and verified Node24 checkout SHA in both
GitHub workflows to avoid upcoming runner/runtime drift; no package publication.
[Detailed checks and remaining work](ci-smoke-repair-20261015.md).

## October 14 installed WSL fresh replacement completed

User waived backup and explicitly authorized replacing experimental Ooonana.
Fresh 0.10.0 from verified ISO passed temporary QA, signed local 654-package
snapshot (1302 checksum entries), real nonroot install, runtime health,
GTK/WSLg and i3/dock/panel readiness. Old experiments erased without backup.
Normal VHD copy-import stalled; idle-engine reset cleared only incomplete target,
then verified VHD was registered in place at the same F: directory. Final actual
Ooonana cold user/version/package/GUI checks passed. Ubuntu/default/disk path,
Windows models, signing key, repositories and ISO unchanged.

Installed WSL now core 0.10.0; stable package channel remains 0.9.9. Native signed
snapshot at `/var/lib/ooonana/candidate-repo-0.10` needs no removable-drive boot
mount. WSL-local launcher preserves packaged helper, extends cold Xephyr wait
to 60 seconds and selects nested X11/XCB. Host installer also closes interop
stdin; adapter/source tests and ShellCheck passed. No AI weights downloaded,
audio playback or permanent audio suppression.

Cleanup was policy-blocked before execution; QA distro plus generated raw/tar
remain (~6.5 GiB), with history preserved and manual commands documented.
[Replacement details, adaptations, cleanup and launch](wsl-replacement-20261014.md).
Older dated installed-WSL status below is historical. No physical ISO remake
needed for these host-only/WSL-local changes.

## October 14 computer scan and resident RAM accounting

Accessible C:/F: metadata scan covered 1,660,467 files; both WSL native roots
reviewed. Junction/cloud reparse entries and protected paths skipped, with
local-only evidence. Confirmed ~652 MiB old QA kernel/initramfs payload and a
small byte-identical C: QA archive, but execution policy blocked removal before
the command ran. No deletion/bypass; history/models/releases/keys remain.

Reproduced disk-mode RAM refusal. Corrected conservative host accounting to
include reusable RAM already resident in one observed WSL VM, subtracting all
Linux nonreclaimable usage and another 512 MiB overhead. Virtual capacity is
not credit; invalid/ambiguous readings refuse/fall back. Both 2 GiB reserves
remain; unit/source/ShellCheck and live RAM-budget checks pass. Existing user-built
ISO resume completed static/Rufus, service, BIOS/UEFI and checksum/promotion.
No fresh construction or installed WSL migration. Candidate now at
`F:\Ooonana\ooonana-os\release-current\ooonana-full-i3.iso`, 2,895,407,104 bytes;
independent Windows SHA256 matched:
`96dc45a2f27f0cd6e0e2e4e76b78af0604b3cbe79231c3eddadd1fc85c94c86d`.
Temporary C: ISO removed; F workspace unmounted; old completed staging retired.

Legacy virtual `e1000` Tx-hang warnings triggered a host-only harness repair:
q35 probe uses PCIe `e1000e`, and health predicates reject Tx hangs/watchdogs.
Actual published-image service/fault/shutdown retest passed without those
errors; `build-diagnostics-20261014/service.va5T6eo1.log` retains evidence.
Physical Wi-Fi is not certified. Core 0.10.0 candidate; stable/installed WSL
remain 0.9.9. Latest C: ~5.1 GiB / F: ~17.1 GiB snapshot; future full-workspace
launch correctly refused capacity-plus-reserve. No bypass or ISO rebuild needed
for current host-only changes. Older dated status below is historical.
[Detailed scan, boundaries, blocked targets and accounting](computer-junk-review-20261014.md).

## October 14 disk-backed verification closure

Repeated RAM-mirror refusal resolved with explicit `--verify-on-disk PATH`.
Plain ISO temporary copy on C: DrvFS avoids pinned media, WSL VHD growth and
slow F-backed QEMU CD reads. Copy is compared byte-for-byte; both disk and RAM
retain 2 GiB reserves. Disk-mode probes use 1536 MiB VMs (~3.5 GiB host RAM
headroom), not a physical/live OS limit. Unknown files, changed mount ownership
and symlinks refuse cleanup; only the owned ISO and empty directory are removed.

Actual existing ISO copy, static/Rufus checks, all service/fault/shutdown checks
and BIOS/UEFI startup passed without guest I/O/OOM/panic errors. Temporary
2.90 GB C: copy removed; F workspace normally unmounted. Fresh helper copy and
cleanup, source/fixture guards and ShellCheck passed. No rebuild or promotion;
user-run resume remains for final checksum/promotion. Stable/installed WSL stay
0.9.9; original candidate generation unchanged. C: ~8.8 GiB after cleanup.
Prior `37f1ba4` GitHub/GitLab CI passed. Full evidence and new command:
[build verification recheck](build-verification-recheck-20261014.md).

## October 14 user build and model inventory

User's F-backed sparse-workspace build passed preflight and full-rootfs audit
(174 scripts, 524 ELF files, zero errors), then produced a 2,895,407,104-byte
staged ISO. Static hybrid/GRUB/kernel/payload checks passed, but service
verification failed on NetworkManager/BlueZ readiness. A repeat using the same
ISO reached all service/shutdown markers while reporting a guest CD-ROM timeout
and I/O error. Exact cause of the first failure is unproven; daemon binaries are
not demonstrated broken. Staged ISO remains unpromoted; October 6 release stays.

Fixed host verification to reject guest I/O/filesystem/OOM/panic errors even
with success markers, retain service serial logs and bound cold-start retries.
ISO resume verifies signed inputs, current kernel config, fingerprint and
completed provenance; mounted children refuse resume/promotion cleanup.
Workspace cleanup retries ordinary unmount within a bound, checks ownership and
retains busy/foreign mounts. F builds also require at least 1 GiB C: headroom.
Optional nonswappable RAM verification checks Windows and Linux free memory
before copying existing media. Actual staged fingerprint passed after these
host-only changes; no runtime/package edit or ISO rebuild occurred.

Source/backend regression suites passed. Actual RAM-media preparation refused
because Windows had ~1.7 GiB free with WSL active (latest snapshot ~2 GiB); full verification needs ~6.7
GiB. Unit tests cover memory budgets, read errors, mount ownership and failure
predicates; RAM-backed real-guest verification remains pending. User compacted
WSL disk; latest C: ~9.8 GiB, F: ~17.5 GiB. No assistant compaction/relocation.
Removed 467,228 KiB (~456 MiB) redundant QA Python libraries after retaining
metadata/file history and confirming a matching QA environment remains.
Models, signed generations, kernel cache, releases and keys stay.
[Evidence, cleanup targets, limits and resume command](build-verification-recheck-20261014.md).

Pinned candidate generation:
`5f8074ffabc6ed5848360cd1666d0c7f74ae9f2961656b6ade612efc192dbe8f`;
core 0.10.0, 654 packages / 612 nodes, clean source revision
`2c7a925e1d9e6d0e7b4e8723350b036885a4a795`. Both source CI pipelines passed.
Native Ubuntu retains one testing-only SmolLM2-360M store, 218,728 KiB (~214 MiB),
with ~207 MiB primary weights. No personal weights or extensionless model-cache
blobs found in scanned native paths; Windows mounts/symlinks not followed.
Ooonana WSL stays stopped and unverified, not claimed empty. Installed WSL
update/migration deferred; no assistant model/runtime download, VHD relocation
or compaction. [Inventory and policy](wsl-model-storage-20261014.md).

## October 14 F-backed build workspace

Windows ISO launcher now prepares a separate 21 GiB sparse ext4 build file on
F:, keeping Ubuntu/Ooonana distro VHD locations unchanged. Rootfs, disk images,
temporary files and future kernel work use that native filesystem, not raw
NTFS trees. Initial setup requires 29 GiB F: headroom; reuse counts physical
free space plus already allocated workspace extents, retaining an 8 GiB output
reserve. Checks run before expensive release phases. UUID/label/size, symlink,
exclusive-lock and mount checks reject foreign or damaged files; flush/unmount
failures retain workspace. Retry space accounting includes reclaimable failed
scratch, refuses mounted children, and rechecks capacity after kernel compile.

Actual 64 MiB F-backed ext4 probe passed ownership, setuid, hardlinks, symlinks
and `cp -a`. Sparse variant also passes with only 393,216 bytes allocated;
evidence: `F:\Ooonana\ooonana-os\build-storage-thin-probe-20261014.1igKczFW\result.log`.
Windows sparse helper now has null stdin, avoiding WSL interop consuming a piped
script's remaining commands. Launcher/storage/source-release/backend regressions
and signed 654-package / 612-node input-only release preflight pass. Removed
5,755,216 KiB (~5.49 GiB) inactive failed C-backed build scratch after retaining
fingerprint/completion markers and file listing under
`/var/tmp/ooonana-build-storage-cleanup-20261014.ke7Wd2xb/`. This is logical guest
space reclaimed; no VHD compaction or promise of equal Windows free space.
History, model stores, old releases, signed generations and keys remain.

Non-sparse NTFS formatting caused long zero-fill I/O on removable F: (~3.6 MB/s
observed). Stopped only this run's Ubuntu session to cancel it; sparse-file
setup replaces that slow allocation path. Removal of the owned incomplete
`F:\Ooonana\ooonana-os\build-storage\release-stage.ext4.creating` (21 GiB) was
policy-blocked; no alternate deletion/overwrite attempted. User subsequently
removed it manually and passed actual sparse-workspace setup/preflight, as
recorded above. Later user build produced unpromoted media; verification outcome
and host repairs above supersede the earlier in-progress snapshot.
No assistant ISO build, sound, installed WSL migration, stable
promotion or private-key upload.

## October 14 startup, Power and Settings

Actual GRUB EFI preview reproduced small-screen logo/menu overlap; responsive
spacing and divider repair retain boot policy. Power lock errors cannot fall
back to insecure blanking; logout/reboot/shutdown default to Cancel, duplicate
requests are blocked and failures visible. Settings now waits for command
completion, rolls back failed theme preference, preserves failed wallpaper
choice and reads memory asynchronously with stale/closed-window guards.
Private 640/1280px state/action tests, native catalog/window/dock/panel and
source generation checks pass. Removed ~125 MiB confirmed current-turn test
payloads; logs/screenshots/configs/history/releases/models kept.
[Evidence and limits](ui-structure-recheck-20261014.md). No ISO, sound, actual
host power action, installed WSL migration or stable promotion.

## October 13 centered dock and native app detail pass

Dock now measures 60px with icons centered independently of running/count
markers. Compact targets and unpinned access remain intact. Shared native
forms/tooltips/sidebar focus and icon/text spacing refined. Task Manager obeys
reduced motion and prevents multiline process commands from stretching rows.
Native catalog covers 25 windows/pages/dialogs at 1024x768 and 1280x800 with
mocked backends; separate interactive source tests cover actions/input.
Added personal cursor is this machine's default (21px, private assets); public
fallback remains 19px, now consistent in generated Xsettings. README captures
updated; old dated evidence retained. [Details and limits](frontend-detail-pass-20261013.md).
No ISO, sound, installed WSL migration or stable promotion.

## October 13 frontend micro-polish

Corrected stale Font Awesome 6 family names on the v3.24/Font Awesome 7
candidate: Solid symbols previously resolved to Brands, dropping control,
AI and status glyphs. Panel status spacing/colors now keep long Wi-Fi labels
clear of the centered AI action at 1024 and 1280 pixels. Dock focus is visible
without hovering; preview headings/captions are aligned with stronger hierarchy,
bounded previews remain focus-neutral, and screen-reader descriptions include
window/minimized counts. Native and third-party controls gain pressed feedback
without changing circle sizes, shape/input regions or window actions.

Impeccable guided one bounded refinement pass, preserving wallpaper/cursor,
icons, opaque palette and behavior. Private actual-userspace GTK/i3/Polybar
checks pass; enabled button-state text contrast exceeds 4.5:1. README screenshot
updated; older visual evidence retained. [Evidence and remaining gates](frontend-polish-20261013.md).
No ISO, audio test, installed WSL migration or stable-channel promotion.

## October 13 ISO build blockers

User's actual full-rootfs build found three audit errors with two causes:
v3.24 `rofi` contains shared data but not the launcher executable, and the
Intel DMC audit demanded a raw blob despite packaged `.zst` firmware and target
kernel ZSTD support. Both full-i3 and combined profiles now explicitly include
`rofi-x11-wayland`. Firmware audit accepts nonempty raw blobs or compressed blobs
only with the corresponding resolved target-kernel loader options; missing,
unsupported and outside-root targets still fail. Release passes its actual
cached kernel config to audit. Existing bundle dependencies remain intact.

Repaired failed staging rootfs passes all 174 script / 524 ELF checks with zero
errors; launcher reports 2.0.0. Regression fixtures cover the split package,
stale bundles and firmware capabilities. Compressed DMC is retained byte-for-byte
in the initramfs fixture. Actual UID1000 X11 menu with shipped theme, Wi-Fi
prompt, two entries and Enter selection passed; earlier auto-select/filter
probe was inconclusive, not used as evidence of a broken shipped interaction.
Proof: `/var/tmp/ooonana-build-blockers-20261013.lc6DCFza/` audit/menu logs.
Candidate metadata contains 654 packages / 612 dependency nodes, with the only
new desktop dependency `rofi-x11-wayland`. This is not a completed ISO. Rebuild
normally, without resume flags: earlier rootfs tarball predates launcher repair.
Physical C: free space remains below the 20 GiB staging recommendation; F: has
adequate space. No installed Ooonana WSL migration or stable-channel promotion.

## October 12 deep software scan

Fixed Task Manager long-uptime/unsigned-UID overflow, identity-safe task/API
termination, quick-kill safeguard bypass, bounded command-line reads, failed
state flushes, malformed i3 IPC and repository publication flush ordering.
Thirteen candidate GUI gates and real installed Linux CPU AI journey passed;
full root and private UID1000 workflows passed. Removed ~224.5 MiB duplicate owned test payloads and
overlays, retaining logs/screenshots/history. Bytecode cleanup policy-blocked;
no retry through alternate tools. Installed WSL/stable unchanged; no ISO or sound.
[Detailed evidence and assistant-owned remaining work](deep-recheck-20261012.md).

## October 12 AI, Qt and Firefox closure

- Native AI was explicitly requesting non-streaming replies. Removed that flag;
  bounded incremental UTF-8 reads now paint live text, including split Korean
  bytes. Stop terminates only owned CLI process; shared API stays running.
- Real GTK -> production CLI -> installed CPU engine passed low-memory refusal,
  visible streaming, Stop, same-engine reuse and loaded-engine crash/restart.
  SmolLM2-360M QA export, 1280 MiB cgroup cap, no swap, read-only models;
  CPU load/inference 4.459 s, HTTP cancel/reuse 0.333/0.219 s. Proof:
  `/var/tmp/ooonana-native-ai-final-20261012.KGKGpMny/run.log`.
  This is not GPU/large production-model or physical-session certification.
- New-base QTerminal 2.4.0-r0 passed composited paint, minimize/restore,
  fullscreen/restore, movement and close-dialog focus/bounds/cancel/confirmation.
  Added optional catalog entry, not boot dependency. Candidate stage: 653
  packages, 611 full-i3 dependency nodes. Qt file pickers/theme and physical
  session remain separate. Proof:
  `/var/tmp/ooonana-ai-qt-final-20261012.dwDKlZMo/qterminal-frame`.
- All thirteen isolated candidate GUI gates passed together:
  `/var/tmp/ooonana-gui-source-freeze-20261012.v8Yv713R/run.log`. Final streaming fixture
  also passed after pipe cleanup; read-error fixture confirms owned child stops:
  `/var/tmp/ooonana-ai-stream-freeze-20261012.xrpldgja`.
- Actual nonroot Firefox installation exposed missing `/var/tmp` in rootfs.
  Builder/core archive now create sticky 1777 directory; core health check
  refuses absent/unsafe permissions. Build, upgrade and refusal regressions pass.
  Firefox 157.0.1 setup/status/update passed in private Linux storage:
  `/var/tmp/ooonana-firefox-repaired-20261012.4PxGKuV4/firefox-install-update.log`.
  Proper mount/PID root and `/dev/full` fix chroot/outer-wrapper QA limitations;
  real UID1000 Documents/FUSE activation, Firefox renderer seccomp=2/no-new-privs=1,
  painted controls, minimize/restore/fullscreen/restore/move/close passed:
  `/var/tmp/ooonana-firefox-final-20261012.HgOA2mXJ/run.log`.
  Sandboxed picker is blocked by Firefox first-run Terms prompt. User delegated
  recommendation; acceptance deferred, none accepted. Private QA profile has diagnostics off; production defaults
  unchanged. No browser/Flatpak sandbox or host security policy disabled.
- CI caught standalone sandbox-helper fixture missing the new app selector.
  Added explicit Chromium selector plus Firefox uninitialized/unlocked/ready
  regression. This was test-harness scope, not a disabled production sandbox.
  New `/var/tmp` health requirement also exposed outdated shutdown-hook fixture;
  fixture now models actual sticky directory. Entire GitHub CI command suite
  passed locally: `/var/tmp/ooonana-full-ci-20261012.DYLFbvQV/run.log`.
- GitHub's nonroot factory run exposed archive extraction masking sticky modes.
  Install, replacement, configuration restore and rollback now preserve archive
  permissions explicitly. Tests use umask 077 and verify packaged 0644 files,
  custom 0640 configuration retention and sticky 1777 `/var/tmp`; health checks
  stay strict. Live-root migration fixture uses a canonical `/` alias, preventing
  host admin-helper escalation while verifying live replacement refusal.
  Entire GitHub command suite also passed as UID1000 with private HOME/XDG state:
  `/var/tmp/ooonana-nonroot-ci-final-20261012.JMr2j1Eu/run.log`. Root upgrade,
  interruption and migration fixtures passed separately:
  `/var/tmp/ooonana-root-permissions-20261012.OT6AEchs/run.log`.
- Actual candidate BusyBox/musl passed root installation, upgrade, custom 0640
  configuration retention, sticky 1777 directory and failed-health rollback.
  Nonroot BusyBox ignores permission-preservation flags; that unsupported path
  now refuses before unpack/replacement/recovery deletion instead of silently
  damaging modes. Normal administrator installation remains supported; GNU tar
  supports nonroot offline targets. CI includes portable archive-mode fixture.
  Proof: `/var/tmp/ooonana-tar-candidate-final-20261012.MPmMW4AU/{root,nonroot}.log`.
  Host Ubuntu BusyBox lacks `-T`; candidate binary was tested through its musl
  loader in a private binary-only fixture, without changing cached userspace.
- Removed only two failed private Flatpak download caches (~367 MiB), keeping
  logs and histories. Owned F: 6 GiB test-file format stalled in WSL 9p I/O;
  stopped owned formatter. Removal was tool-policy blocked; file retained,
  no alternate deletion attempted. Valid runtime/release caches remain.
- Latest physical headroom roughly C: 4.4 GiB, F: 10.8 GiB. Full image staging
  still requires 20 GiB free on C:, 8 GiB on F:. No ISO, installed WSL migration,
  stable-channel promotion, sound, physical disk mutation or key enrollment.
  PDF real Chromium viewer remains tool-policy blocked; hardware explicitly skipped.

## October 12 real candidate portal follow-up

- Real activation exposed another missing split package: `xdg-document-portal`.
  Added it to Firefox dependency closure, native factory imports and both/full-i3
  profiles. Firefox wrapper bumped to 1.0.1 so existing clients see dependency
  repair as an upgrade. GTK frontend/backend alone lacked Documents service.
- FUSE cleanup also lacked `/etc/mtab`; full rootfs now links it to
  `/proc/self/mounts`. Actual rootfs fixture and portal cleanup retest cover it.
- Added opt-in real portal probe and signed supplemental-package COW overlay.
  No full rootfs copy/rebuild, preserved candidate modification or downloads by
  GUI tests. Real Ooonana manager installed verified packages into private upper.
- UID1000 frontend/backend/Documents activation and FUSE mount, picker bounds,
  painted window buttons, Escape cancellation and opening an unchanged owned
  file passed at 1024x768. Screenshot inspected. Thin upper uses about 2.2 MiB.
  Proof: `/var/tmp/ooonana-portal-candidate-20261012.MlDoAVbo`.
- All twelve isolated candidate GUI probes passed together at 1280x800: native
  apps, AI indicators/chat, desktop interactions, notifications, controls,
  dock, panel, portals, composited Geany/Nemo/Chromium. Proof:
  `/var/tmp/ooonana-gui-portals-final-20261012.QZ9gyduI/run.log`.
- Firefox launcher/probe refusal, full-rootfs and package-factory fixtures passed.
  Refreshed signed candidate staging contains 643 packages and 611 dependency
  nodes with supported v3.24 provenance. Only candidate generation is refreshed;
  stable 0.9.9 repository/installed WSL remain untouched.
- This is not actual Firefox Flatpak download/update or sandboxed Firefox picker
  certification. New-base Qt, GUI-to-real-model journey, real PDF viewer and
  physical/session checks remain separate. Private session intentionally lacks
  system bus/audio services; Glycin sandbox warning remains a known chroot limit.
- C: ~7.4 GiB, F: ~16.8 GiB. Large rootfs/ISO staging still needs more C: space.
  No ISO, WSL migration, sound, signing enrollment or private-key upload.

## October 11 repository selection repair

- Confirmed default F: repository is signed stable core 0.9.9, with imported musl
  1.2.5-r3 and no explicit supported-base provenance. Current source is core
  0.10.0; release refusal prevents incompatible userland reuse, not a broken
  Ooonana package manager. Existing isolated candidate contains musl 1.2.6-r2 and
  explicit Alpine v3.24 provenance.
- Added explicit `--repo` / `OOONANA_RELEASE_REPO` selection to release builder;
  default stable repository and installed WSL stay unchanged. Windows wrapper
  delegates selected-repo validation instead of requiring an unrelated default.
- Fixed missing GTK portal entries in the combined factory profile as well as
  full-i3. Regression covers both profiles and CLI/environment precedence.
- Actual signed-stage refresh exposed a factory ordering bug: unsigned reindex
  retained an old signature, so the manager correctly rejected dependency checks.
  Factory now signs before validation and refuses missing-key refresh before
  touching signed staging. Build-time closure checks use the explicitly chosen
  public key, not the unrelated bundled default. Reuse, custom-key verification
  and no-write refusal regression added; client trust enrollment is unchanged.
- Refreshed all factory payloads on the same v3.24 branch, current native
  core/OpenVINO/Firefox/branding and portal closure. Real Ooonana dry-run checks
  passed for full-i3, native apps and common tools. Final inventory: 642 packages,
  623 imported packages with explicit v3.24 provenance, 610 dependency nodes.
  Initial stale-signature failure log retained; repaired signing phase passed.
- Current-source factory/release/Firefox/CLI regressions passed. Candidate-only
  atomic publication target is `F:\Ooonana\ooonana-os\build\full-i3-repo-0.10`;
  trusted signatures and archive checksums are checked before pointer promotion.
  Stable `build/full-i3-repo/CURRENT` and installed Ooonana 0.9.9 are unchanged.
- Input-only preflight passed with repaired native staging: repo/signatures,
  desktop closure, cached kernel config, firmware and source/boot/service gates.
  This is not a rebuilt final-image or hardware pass. Evidence:
  `/var/tmp/ooonana-repo-repair-20261011.iA9JyBvt`.
- F: initially ~18 GiB free, but C: only ~7 GiB after staging. Ubuntu VHD/staging
  backs onto C:; virtual WSL `df` capacity is not physical headroom. README build
  command checks 20 GiB free on C: first. No ISO, migration, sound, stable-channel
  promotion, client key enrollment or private-key upload.

## October 11 runtime setup, inference and portal follow-up

- Hardware/USB checks explicitly skipped by user. No physical target available;
  GPU, radio/audio routing, power loss, unrelated-drive safety and physical
  display/session certification are deferred, not passed. No sound or ISO build.
- Fresh OpenVINO setup completed as UID1000 in disposable storage: pinned Ubuntu
  root image/checksum, dated APT packages, hash-locked pip dependencies, current
  app installation, import readiness and real atomic generation promotion.
  Proof: `/var/tmp/ooonana-fresh-runtime-20261011.pXoMA9RG/setup.log`.
- Real CPU loading/inference/SSE exposed cancellation continuing generation after
  BrokenPipeError: GenAI swallowed the Python callback exception. API now captures
  disconnection and returns an explicit native stop signal for both chat and text
  completion. Deterministic HTTP cancellation regression added to both CIs.
- Fresh userspace plus packaged bubblewrap transport passed CPU loading/inference
  (4.85 s), real SSE, chat/completion cancellation and same-engine reuse
  (0.33/0.43 s), strict memory JSON/SSE, loaded-engine SIGKILL/restart, UID1000,
  read-only models, exact dependency versions and current installed GUI assets.
  Proof: `/var/tmp/ooonana-fresh-inference-20261011.ua0k3JRE/run.log`.
  Disposable SmolLM2-360M INT4 export was pinned to
  `a20518b267e200941f99935631a03d57a9eb74ab`; all 13 selected files verified by
  Hugging Face CLI. About 224 MB downloaded; saved production models untouched.
  Memory cap 1280 MiB, no swap allowance, two-CPU quota. This is small-model CPU
  proof, not GPU, large saved-model or new-image physical certification.
- Candidate image lacked desktop portal frontend/backend. Full-i3 and Firefox
  dependency closure now include GTK portals; i3-specific backend configuration
  and desktop/D-Bus activation environment handoff added. Firefox packaging and
  full-i3 rootfs regressions passed. Real nonroot Flatpak installation/update and
  portal/file-picker interaction remain pending until current candidate rebuilt.
- Source/candidate remains 0.10.0; installed Ooonana WSL remains 0.9.9. Migration,
  signing enrollment and private-key upload remain deferred. No denied cleanup
  retry. Windows C: ~8.35 GiB, F: ~7.97 GiB; do not treat WSL virtual free space
  as physical staging headroom. Fresh release repo/rootfs still required.


## October 9 offline installed-app and Qt follow-up

- Built/installed OpenVINO Chat 0.2.1 offline into a disposable copy-on-write overlay over cached Linux venv. `pip check`, every pinned dependency version and bundled web-asset hashes passed. Real packaged bubblewrap API now passes without PYTHONPATH/current-source override: UID1000, read-only models, strict memory JSON/SSE, cross-invocation status, crash/restart, stop/state and bridge cleanup. Preserved cache remains 0.2.0. Final fixture uses about 4.23 MiB: `/var/tmp/ooonana-current-app-cow-20261009.lYrBbA8F/run.log`. This closes current-app installation/transport gap, not full Ubuntu/APT setup or model inference.
- Existing QTerminal 1.4.0 passed painted Ooonana controls, minimize/restore/fullscreen/restore/floating move/close using current config/control code in an isolated nonroot Ubuntu/Xvfb session. Capture inspected; no sound. Host Qt/i3, without compositor: not new-base Qt/theme/portal or physical session certification. Proof: `/var/tmp/ooonana-qt-window-20261009.HZcsOdqY`.
- Third-party probe now refuses a missing expected control overlay instead of silently skipping actions; floating movement also works for initially tiled Qt clients. All eleven candidate GUI gates passed again, including composited Geany/Nemo/Chromium. Proof: `/var/tmp/ooonana-gui-installed-app-20261009.pmEp5a9o/run.log`.
- No runtime/model download, production data mutation, ISO, installed WSL migration, signing enrollment or denied cleanup retry. Full remaining gates stay below/in the closure checklist.
- Removed only three redundant cloned test venvs created during this pass (about 1.34 GiB allocated). Exact paths/metadata, no active mounts/open files and replacement COW proof checked first. Logs, original cached venv and models/history preserved; discarded clones reproducible, not recoverable as deleted files. No VHD compaction or guarantee that Windows backing-drive free space returns.

## October 9 staged runtime setup and interrupted-promotion recovery

- Found OpenVINO setup updating the working userspace in place and force setup deleting it before replacement. Setup now holds kernel writer lock, installs only in a staged copy/fresh pinned userspace, validates readiness and switches a retained generation pointer. No old-generation/model/history deletion. Space floor refuses before copying/downloading; low-RAM warning no longer counts swap as physical RAM.
- Legacy directory conversion journals before moving its old tree. Launch blocks during pending promotion; failed rename rolls back and the next setup recovers after SIGKILL. Real filesystem/lock/rename/sync fixtures passed three interruption points, normal installer/readiness/checksum failures, concurrency, space/memory warnings and unsafe metadata refusal. Inner installer/downloads are mocked: full setup/inference not certified.
- Actual nonroot bubblewrap/API transport also passed with the generation pointer and its own read-only model mount; cached userspace/venv unchanged. Proof: `/var/tmp/ooonana-transport-generation-20261009.YDaIdXIq.log`. Both CIs include setup regression. [Safety, recovery and limits](openvino-runtime-safety.md).
- Follow-up ran the complete setup fault fixture inside isolated Alpine 3.24 candidate userspace and on Ubuntu. Both passed. Fixture now owns its HOME and checks both GNU/BusyBox lock refusals plus no second installer call. GitLab smoke installs `xz` for GNU tar extraction; fixture regression guards that dependency. Alpine proof: `/var/tmp/ooonana-setup-alpine-20261009.G0NqxfxR/setup.log`.
- No real runtime installation, ISO, deferred WSL migration, sound, signing enrollment or cleanup workaround. Candidate remains 0.10.0; installed/stable 0.9.9. [Full remaining gates](remaining-closure-20261008.md).

## October 9 packaged OpenVINO transport follow-up

- Real packaged bubblewrap launcher passed as UID1000 in private network/PID/mount namespaces on Ubuntu QA host: lazy API start, status from a second invocation, strict oversized-context JSON503/SSE error, daemon survival across launcher exits, owned SIGKILL/restart and stop/state cleanup. Daemon `/proc` confirms host UID1000 and its own model mount read-only. All per-command browser-bridge FIFO directories removed. Preserved models/venv mounted read-only; no weights compiled, browser opened or download performed. This is not installed Ooonana/new-image kernel validation.
- Reused cached Ubuntu 24.04 QA userspace and pinned OpenVINO 2026.4.1/GenAI/tokenizers 2026.4.1.0. Writable overlay held only disposable mountpoints/readiness marker. Cached app is 0.2.0, so current vendored code was explicitly injected for QA; this does not validate setup installing the current app snapshot. Actual transport is bubblewrap, not proot. Full setup, inference/streaming/cancel and loaded-engine recovery remain pending.
- Added opt-in real transport runner/probe and ordinary-run/worker-refusal regression to both CIs. Final real run and targeted regressions passed; logs retained outside repository. No ISO, installed WSL migration, cleanup workaround, sound or signing enrollment.

## October 9 continuation: storage guards, generation OOM and guide

- Generation-time OpenVINO allocation failures now use typed insufficient-memory errors, including a failed grammar retry. OOM does not trigger a retry; unrelated errors keep their existing behavior. JSON/SSE, load/fallback/generation regressions, backend metrics and cgroup checks passed.
- Firefox setup/update now refuse RAM-only/temporary USB storage before any Flatpak calls. Both Firefox and OpenVINO setup refuse unknown, blank, unreadable or dangling live-mode metadata. Explicit volatile opt-in only permits known temporary modes. Existing browser launch/status and setup dry-run stay nonmutating. Fixture and reproducible package checks passed; no browser/runtime downloads.
- Docs-only guide refreshed with current Chromium/GTK/PDF/runtime evidence, candidate/stable separation and pending gates. Fixed blank page-boundary separators creating empty continuation headings; regression and all four rendered pages checked using PDF skill. Bootable PDF unchanged. Both CIs now run guide/OpenVINO package fixtures; GitLab smoke includes `strings` dependency.
- Read-only cleanup recheck confirms previous policy-blocked synthetic images remain (~617 MiB allocated); stale F: temp files remain too. No deletion workaround, compaction, history/model/config/key/release removal. Current C: ~10.30 GiB, F: ~7.97 GiB; large release rebuild/verified WSL backup still lack safe space. Windows free RAM fluctuated ~7.5 to ~5.7 GiB; model compile requires extra host margin, so no heavyweight inference attempted.
- Source/candidate stays 0.10.0, installed Ooonana WSL/stable stays 0.9.9. No ISO, WSL migration, sound or key enrollment. [Full remaining gates](remaining-closure-20261008.md).

## October 9 runtime and file-picker follow-up

- Reproduced actual Geany Open dialog at y=-44, height 862 on 1280x800. Initial GTK file-picker role now receives output-relative bounds and centering; generic alerts remain unchanged. Real nonroot file-picker focus/cancel/open and minimize/fullscreen/restore/move/close passed at 1280x800 and 1024x768. All eleven isolated GUI probes passed again; fresh inspected file-picker capture added to README.
- Actual pinned Linux OpenVINO 2026.4.1 / GenAI 2026.4.1.0, real Granite tokenizer (including Korean text), five saved-model memory estimates, strict oversized-context refusal and API SIGKILL/restart passed. Models mounted read-only, private network/PID namespace and disposable state, UID1000. This early check used existing Linux Python 3.12 venv without packaged transport; later bubblewrap follow-up above supersedes that gap, not full model inference.
- Found low-memory failures exposed as generic HTTP500. API now returns HTTP503 `insufficient_memory` or typed SSE error plus DONE; GPU-to-CPU fallback allocation failures receive the same RAM guidance. Unit JSON/SSE/health/unrelated-error/no-OOM-retry regressions and final real API probe passed; both source CIs include the regression.
- Physical inference remains pending: smallest saved weights ~4.63 GiB; host free RAM measured ~4.2 GiB before probes, while WSL reports its guest allowance. No heavyweight compile/download, ISO, WSL migration, sound or key upload. Last storage check C: ~10.4 GiB, F: ~7.97 GiB; F remains below release builder's 8 GiB minimum.
- Cleanup request identified abandoned synthetic images/stale temp files, but deletion was policy-rejected before execution. No targets removed or alternate-path retry. Logs/history/models/releases/valid generations remain. [Complete remaining list](remaining-closure-20261008.md).

## Latest remaining-work closure

- PDF cold list now verifies one metadata snapshot instead of resolving builtin packages repeatedly; extra hash-splitting AWK processes removed. Signature/checksum/index-version/missing-checksum/external-source regressions passed. Node measurements: list ~130 -> 45s, sync ~86 -> 57s; not viewer guarantees. Rebuilt actual PDF passed full boot/input/Backspace/edit/version/sync in 107s; 116 fields and final rendering checked. Guide stays earlier candidate snapshot.
- Reproduced real black Nemo overlay fills; RGBA visual selection before realize plus shape-damage redraw repaired them. All eleven isolated GUI probes passed together, including Geany/Nemo/Chromium composited frames/actions. Fresh candidate desktop/window captures inspected and README updated.
- Chromium optional shader disk cache caused sandbox syscall crash; global config/current generated helper disable only that cache. Renderer/GPU kernel state confirms seccomp filtering and privilege lock; normal GPU selection/sandbox remain. Software Xvfb/WSL kernel evidence, not image-kernel browser or physical GPU certification.
- Actual 6.18.37 disposable VM proved interrupted package upgrade/config rollback, wrong-password refusal/nonroot login, partition and full ext4/FAT file persistence fault/recovery paths. Dirty FAT refused unchanged, late handoff/corrupt-image cleanup passed, failed shutdown held through three rescue exits. Wrong installer BusyBox test seed lacked `blkid`; fixture now refuses incompatible seeds before boot. Unrelated guest USB hash unchanged; no host disk attached.
- Replaced predictable PID checksum cache with private random directory; allocation failure refuses and privilege exec cannot leak caller cache. Symlink/cleanup/handoff, scratch applet, package/migration/interruption and final real upgrade rollback checks passed; rebuilt PDF/core package include guard.
- Final PDF guard exposed missing TinyEMU `rdtime`/counter enable support. Architectural `time/timeh` reads now use the actual CLINT clock with machine/supervisor privilege checks; compiled width/permission/idempotence/refusal tests passed. No RNG bypass/native kernel rebuild. Final shipped suite passed in 87s; 116 fields and last render checked. Earlier 107s/timing observations above are historical measurements.
- Broad unit/backend/kernel/boot/package fixtures passed; small current core package inspected. Installed Ooonana/stable remain 0.9.9; candidate 0.10.0 not promoted. Disk space blocks large rebuild/backup. WSL migration remains user-deferred, signing key local, no ISO/sound. [Complete pending list](remaining-closure-20261008.md).

Entries below are historical; latest closure supersedes earlier Chromium/Nemo blockers and PDF timing results.

## PDF boot follow-up and remaining candidate gates

- Previous shipped PDF did not hard-hang in reproduction: quiet init reached its prompt after about 170 seconds while an obsolete elapsed row stayed frozen. Fixed serial handoff/status, early boot-stage output, deterministic sequential RAM seed and RAM shell/backend use. Rebuilt bootable PDF plus guide; native prompt readiness passed. Actual shipped Node VM passed boot/stable input/native/virtual Backspace/middle edit/version/sync in 207 seconds under QA load. Real 500k-instruction cap reached prompt in 83 seconds. All 116 fields/appearances/blank input and rendered pages checked; Chromium viewer interaction remains manual because local navigation was denied, with no workaround.
- Fixed QA observation hooks for lexical functions inside page-open try/catch; serial benchmarks and instruction caps now reach actual runtime bindings. Source fixture tests catch alias-only instrumentation. Native probe checks prompt, panic and bounded timeout, and reaps its owned guest. Package list remains slow (130s in loaded Node benchmark); sync took 86s. Larger PDF seed trades about 1.6 MiB for sequential startup.
- Nemo capture now passes actual packaged compositor and minimize/restore/fullscreen/restore/move/close. Earlier single-pixel readiness sampled the fullscreen glyph rather than green fill; area-based validation keeps rejecting unpainted controls. Latest capture inspected without black controls/bottom strip. No speculative production redraw change or compositor/sandbox disable.
- Service readiness, update/config safety, interrupted upgrade/retry, offline migration, native UI source and kernel policy/source checks passed again. Chromium sandbox crash remains release blocker; no newer v3.24 Chromium package found in current upstream index. Installed WSL migration stays user-deferred; no ISO, sound, key enrollment or stable promotion. [Full remaining list](supported-base-20261008.md#release-blockers--remaining-work).

## Supported-base candidate and cleanup

- Work continues on `codex/supported-base-0-10`, core 0.10.0 with coherent Alpine v3.24 imported payloads. Installed Ooonana WSL, stable main/update endpoint and valid historical generations remain 0.9.9. No Ubuntu conversion, live libc replacement or ISO build.
- Built scratch/full-i3 candidate rootfs; 639-package signed staging repository passed metadata/signature checks and 580-node desktop dependency closure. New base image loading needed explicit Glycin PNG/SVG providers because APK `install_if` is not an ordinary dependency. Native GTK/CSS/reflow, actual controls, AI fixture chat/indicators, launcher/input and Task Manager checks passed. Geany/Nemo actual window actions passed. Chromium 152 crashed in its syscall sandbox; Nemo compositor capture also needs follow-up. Release remains held, not certified by source tests.
- Added offline whole-world migration preflight, per-APK base guards, equal/lower-version ABI replacement, major approval before writes, pinned-generation resumability and retained completion records. Interrupted/failing health hooks cannot clear whole-world journal through per-package recovery. Fixtures, update interruption, package factory and kernel policy/source tests passed; no fresh physical/kernel boot certification.
- Refreshed both PDFs with candidate/stable separation and current backend; current-source embedded VM passed boot, input, native/virtual Backspace, version and package sync in 145 seconds under QA load. Blank input and all three guide pages rendered and inspected. Actual PDF viewer latency remains separate.
- Failed compressed WSL export stopped before F: filled; deleted only new incomplete 7,671,521,280-byte export. Original distro unchanged. Empty owned GUI test home removed; history/models/keys/checkpoints/logs/verified caches kept. User requested WSL migration be skipped for now; full valid backup and independent offline method still required before resuming.
- Private signing key remains local. CI candidate tags cannot replace stable Pages/R2; GitLab deployment requires explicit major-publish variable on main. [Detailed evidence and remaining gates](supported-base-20261008.md).
- Candidate checkpoint pushed to both remotes; GitHub regression and GitLab smoke passed. Stable main was not merged or deployed. Latest PDF command benchmark: bare command 3.2s, help 4.7s, version 3.1s; package list/sync still about 85s in Node VM and remain optimization work. Nemo paint check still failed with private session D-Bus; failed logs retained, speculative redraw edit reverted.

## October 8 UI and optional catalog

- Open Appearance sections, slimmer panel, focus-neutral eased dock hover/Reduce motion. Browser icon now blue globe. Original wallpaper retained; startup uses canonical panel/dock-clear fitting. Failed changes preserve saved choice.
- Added optional common CLI catalog and explicit nonroot Firefox Flatpak setup launcher, not bundled browser/runtime. No default desktop closure bloat or newer ABI library mixing. Supported-base migration remains urgent.
- Native captures inspected; README refreshed. Scoped tests/remaining physical gates: [October 8 report](ui-catalog-20261008.md). Production ISO stays user-built; private key local, enrollment deferred, no sound.

Current source includes the backend/desktop repairs below. ISO building stays with user. Audio backend stays enabled; no playback tests. Older entries record status at the time of each pass; their local/uncommitted and ISO-pending notes are superseded by this update.

## Window-frame repair and frontend checks

- Removed rectangular control-popup backgrounds using X11 bounding/input shapes around opaque circular buttons. Gaps expose the existing draggable titlebar, without translucent windows or a compositor dependency. Buttons remain 16 pixels, native controls 24 pixels; tooltips and accessible names stay intact.
- Rounded windows no longer have a bright rectangular orange perimeter clipped at corners. Frame edges blend into titlebar colors; focused title text and tiling indicators retain orange. Foreign GTK client-side dialogs keep their own headers, without forced duplicate i3 decoration. Browser initial size is 80% output width / 70% height; user resizing/fullscreen remains available.
- Fixed unflushed X11 event registration that left controls behind moved windows, and reduced configure-event coalescing from 60 to 16 milliseconds. Tests now move real clients without manually refreshing the manager. Other-window dock actions no longer mix pinned sessions; selectors use the installed opaque theme.
- Added matching browser icon for dock/launcher. Small-screen Settings cards reflow, app minimum sizes are bounded, and AI chats/tools move behind an accessible sidebar toggle. Existing native app workflows remain intact.
- Real private-profile Geany, Nemo and Chromium passed minimize/restore/fullscreen/restore/move/close with source i3 config and packaged xrender rounding policy. Captures were inspected: no rectangular popup backing or clipped orange outline. Chromium capture uses software rendering, not physical GPU validation. Initial Chromium GPU capture was blank and its cleanup timed out; fixture now uses explicit software rendering and always releases its private compositor/window manager. No GPU workaround was forced into production browser launch.
- Isolated regression checks passed popup/input geometry, native/foreign CSD headers, hover focus, dock previews/actions, AI chat/cancel/code clipboard and memory indicators, Settings reflow, launcher arrow/search/Unicode Backspace/clipboard, Task Manager filtering/sorting/live samples/cancel/owned-process termination, source native UI and full-rootfs generation. Small-screen captures fit 640x600; dock checks covered 640/1024/1280 pixels. Panel 1280-pixel rendering succeeded, but its first teardown timed out; it is not a clean matrix pass.
- Core/runtime/OpenVINO packages were rebuilt and synchronized through guarded installed-WSL transactions. Health checks and all three package verifiers passed; installed i3 config/control source hashes match current source. Custom config/checkpoints/models/history and signing keys preserved. Restart the nested GUI to load new processes; no global WSL restart performed. WSL update check reported already current. Earlier nested session loss included a recorded WSLg Weston/libwinpr crash; this frame patch does not certify WSLg stability.
- Screenshot: [rounded third-party controls](assets/ooonana-third-party-rounded.png). Detailed coverage and manual gates: [frontend recheck](frontend-recheck-20261007.md). Fresh normal ISO build remains user-owned; previous ISO does not contain these edits.

## Full backend inventory recheck

- Re-ran all 49 shell regression scripts plus CLI smoke, all 34 argument-free Python regression scripts, and the separate authenticated nonroot login VM: 85 entrypoints passed after fixing the package-factory gate below. Some wrappers repeat underlying tests; these are entrypoints, not a unique test-case count. The Windows-only PDF browser invocation remains skipped; no physical/interactive pass is inferred.
- Package-factory initially falsely reported missing Xephyr support. Actual pipeline statuses were `tar=141`, `grep=0`: early-exit `grep -q` caused SIGPIPE under `pipefail`. Archive predicates now drain output; the complete factory passed twice. GitHub regression now runs this gate.
- Re-ran complete current persistence matrices: 30 ext4 and 31 FAT32 guest cases passed, including partition/file persistence, unrelated-media isolation, power cuts, ENOSPC, explicit offline fixture recovery, corrupt/late-handoff refusal, interrupted package upgrade and three failed-shutdown rescue exits. Source-patched service VM passed endpoint/readiness/watchdog recovery, frozen BlueZ recovery, silent audio-server checks, desktop command/dependency checks, privilege dispatch and actual clean kernel power-down. Existing October 6 ISO/kernel supplied the VM base; no new production build was made.
- Signed local repository passed 678-package/552-node closure and all 1,351 declared file checksums. Source syntax passed 129 Python files, 155 shell files and two JavaScript entrypoints; extracted core runtime passed 32 Python/83 shell files. ShellCheck error-level source pass completed. These counts overlap; syntax is not functional proof.
- Native PDF runtime review found `--reuse-kernel` rejecting architecture/menu-selected flags while `--reuse-runtime` ignored current fragment requirements. Fragment now matches Linux's dependency-selected alternatives/debug-menu flags. Fresh Kconfig resolution, cached real runtime reuse and regression fixtures validate required/forbidden/duplicate settings; both CI smoke suites now run reuse regressions. Existing embedded JavaScript VM passed boot, stable input, native/virtual/middle-edit Backspace, version and package sync in 136 seconds under concurrent QA load. This does not prove Chromium latency or newly rebuild either PDF artifact/kernel.
- Post-push GitHub checks passed. New GitLab smoke failed after adding the PDF reuse regression: its Alpine bootstrap lacked GNU find, while PDF injection uses `find -printf`. BusyBox rejection reproduced locally. Added `findutils` to that check image plus a dependency regression and visible subprocess failure diagnostics; follow-up CI must validate the changed bootstrap. Deployment was skipped, not promoted on a failed check stage.
- [Backend coverage and remaining gates](backend-recheck-20261007.md) inventories every backend category, including physical/device, model/runtime installation, firmware/release and full installed-upgrade limitations. No claim of exhaustive hardware certification or zero bugs. Installed WSL/source artifacts, models/history, trust enrollment/private key remain unchanged. Logs: `/var/tmp/ooonana-full-backend-20261007.K4f5J0JB`. ISO building remains user-owned.

## Persistence and interrupted-upgrade fault pass

- Reproduced concurrent removal succeeding while an upgrade was waiting in its health hook. Package mutations now hold a kernel-released writer lock; hook-started background services do not inherit it. SIGKILL cannot run rollback traps, so replacement now persists checksum-verified old payload/config/state and a prepared/committed journal before destructive changes. Pending replacements block further mutations/file verification until explicit `ooonana recover`. Wrong-root, corrupt/incomplete/legacy journals refuse without guessed deletion; a failed restore retains its retryable checkpoint. Completed/recovered checkpoints remain private. This is package-owned recovery, not a whole-system or arbitrary-hook rollback guarantee.
- Actual localhost transfer fault reproduced GNU wget ignoring the CLI retry budget and a truncated archive poisoning the cache. GNU retries are now bounded, remote files stage and verify before promotion, and damaged older remote archive caches can be fetched again. TERM/KILL, concurrent writer, corrupt snapshot, wrong root, failed recovery/retry, interrupted download and successful retry passed using the actual CLI on a newly formatted disposable ext4 file installation.
- QEMU matrices passed with current live-init/storage source and the existing 6.18.37-3 kernel/BusyBox: ext4 and FAT32 boot media, separate persistence partitions and file-backed storage, saved/temporary isolation, abrupt guest power cuts, ENOSPC boot refusal, offline reclaim of one known fixture filler, reboot recovery, corrupt storage, late handoff faults and three rescue-shell exits during failed shutdown. The real guest CLI also installed a baseline package, lost power during an upgrade health hook, rebooted, and restored old payload/custom config. Unrelated same-label USB image hashes stayed unchanged.
- File-backed FAT crash exposed the outer dirty flag surviving power loss while persistence still attached writable. New read-only BPB gate refuses dirty/unreadable FAT before setup/attachment can remount it writable. VM refusal leaves the entire disposable USB byte-identical. Explicit offline fsck on a copied regular-file test image, followed by boot, restored the committed sentinel. No automatic repair, flag clearing, saved-overlay deletion or guarantee for unsynced writes/controller failures.
- File-backed ENOSPC follow-up passed on both ext4 and FAT32 outer media: fill the inner ext4, orderly shutdown, refuse the next persistent boot below 16 MiB free, inspect both layers offline, remove only the known disposable filler, and restore the committed sentinel after reboot. Combined matrices/follow-up completed 63 successful VM case runs, including repeated baseline creation. These are not physical power-cut certifications.
- Radio/audio control fixtures, service readiness/watchdog, metrics/API, package/update safety, installed-WSL wrapper, release repository/policy, current-source rootfs/initramfs, portable version ordering and kernel source/build/smoke-gate regressions passed. Real kernel compilation, production ISO creation and new physical boot were not performed.
- Windows reports Intel AX201 Wi-Fi up, Intel Bluetooth, Realtek audio and Iris Xe devices present; that is not a Linux functional pass. Ooonana WSL exposes virtual Ethernet and an audio endpoint reply, no physical radio/DRM devices, and uses Microsoft's WSL kernel. Pair/reconnect, device/slider changes, GPU rendering, fan/thermal readings and physical USB/controller power loss remain blocked on an actual Ooonana USB boot and identified disposable media. Hardware checklist now includes silent read-only collection commands. Frontend work remains deferred; no sound played, host disk/radio/fan settings changed, key uploaded or history/model store accessed.
- Test output logs remain under `/var/tmp/ooonana-backend-20261007.GqAehtXn`; failed-run logs also remain in their five owned fixture directories. Disposable disk/rootfs/kernel copies from this pass were removed after successful retests; original kernels/seed caches/releases/history remain. A PowerShell launch hit host memory pressure while WSL reported 6.7 GiB file cache; only owned failed-fixture cache was advised away, without dropping global caches or changing host memory settings. Fresh normal user ISO build required: `& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'`.

## GUI/backend follow-up

- Reproduced browser/document titles stealing native dock groups: Chromium titled `Music` became Music; `Task Manager`, `Processes` and `Spotlight` page titles also matched the wrong pins. Native titles now require native/legacy identity; known third-party classes keep their correct groups. Explicit OpenVINO browser-bridge titles remain supported. Actual desktop source titles `OpenVINO / Quack` and its approval-needed state now match Offline AI. This is title/identity fixture coverage, not an OpenVINO inference or native-webview launch claim.
- Reproduced a killed dock remaining absent while its supervisor/panel stayed alive. Supervisor now recovers only its exited panel/dock child, leaving healthy siblings and unrelated displays alone. Each child has a maximum of three automatic retries per 30 seconds; persistent failures cool that child's retries with a diagnostic instead of spinning or killing the healthy sibling. Spawn errors are also contained during recovery. Permanent process fixtures cover both recoveries, sibling retention through repeated failures, retry limit and owned cleanup.
- Source review found the legacy WSL updater still overwrote configs/package records directly and omitted new top-level RAM/panel helpers. Retired that raw overlay path. `update-installed-wsl.sh --repo DIR [--dry-run]` now requires built same-version core/runtime packages with executable health hooks, and OpenVINO when installed; missing packages/archives/hooks, bad archive checksums and version changes are refused before reinstall. Published generations are pinned during preflight. Native CLI retains signature policy, config preservation, per-package health/rollback and checkpoints. Personal-cursor raw overlay is also refused; existing cursor configuration is preserved. Use normal `ooonana upgrade` for version changes. A multi-package sync is a sequence of package transactions, not one all-package atomic transaction.
- Reproduced major-update policy bypass: `ooonana reinstall ooonana-core-runtime` installed 0.11.0 over 0.10.0 without approval in a disposable fixture. Repair/reinstall now require explicit `--allow-major` for the same OS version jumps as upgrade, including repairs of missing files. Dry-run reports the required approval. Regression verifies refused replacement keeps old package state and approved replacement succeeds with custom config retained.
- Actual isolated GTK/i3 checks passed native and third-party close/minimize/restore/fullscreen, unfocused targets, native action-menu dispatch, dialog decoration, hover-focus behavior and bounded dock previews at 640/1280 pixels. Native GTK/CSS, radio-unavailable UI, Music fixture and public cursor checks passed. Dock/Music captures under `F:\Ooonana\ooonana-os\qa-frontend-20261007` were visually inspected; no sound played. Closed-window preview probe returned safely; no preview crash was reproduced.
- Service readiness/watchdog, CPU/network/API metrics, update/config rollback, kernel source/build/gate, live boot/persistence file safety, current-source rootfs, WSL builder/updater, CLI, shell lint and GitLab policy checks passed. These are source/fixture regressions; no new production ISO, kernel compilation or physical boot is claimed. Previous `e710eb1` GitHub and GitLab pipelines both completed successfully.
- Built current core/runtime and OpenVINO packages in separate local staging and synchronized installed Ooonana WSL through the new guarded wrapper. Core health hooks, three package presence checks, source-byte comparison and nonroot GTK imports passed. The plain WSL import probe emitted a GDK no-seat warning; it is not a new interactive WSLg keyboard/display proof. i3, panel, environment, inittab, NetworkManager, Bluetooth and WSL config hashes stayed unchanged; custom configs and model/history stores remain. Recovery checkpoints remain under `/var/lib/ooonana/packages/backups/`. No global WSL restart, unregister/import, engine update or signing-key upload.
- Current October 6 ISO remains a verified historical build but does not contain these October 7 functional changes. User must run a fresh normal `& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'`; no resume of old staging. Physical USB display/input, Rufus/BIOS/UEFI, persistence power-loss/recovery, radios/audio/sensors/GPU/RAM/model inference remain manual. Signing enrollment remains deferred; private key stays local.

## User build, cleanup and installed WSL sync

- User's October 6 normal ISO build completed successfully: 678-package signed repository closure, runtime closure with zero errors, actual service/desktop VM smoke and clean kernel power-down, plus BIOS and UEFI boot gates. Local `release-current/ooonana-full-i3.iso` is 2,504,079,360 bytes; its actual SHA256 matches the build log and checksum file: `265afcf3d2524dbfbfeda8d1977f8d846ed8ad6a34bdd76d9dc9018ff4d9767e`. CPUID SVM warning did not prevent VM completion. This is not physical hardware/persistence power-loss proof. Personal cursor still limits this image to personal use.
- Removed 16 confirmed disposable GTK/Xvfb fixture directories (252 KiB allocated) after checking ownership/mounts/processes. Source junk scan was empty. QA screenshots/logs, Git history, archives, models, package/kernel/firmware caches and release artifacts remain. Empty Windows `tmp-test` directory remains because deletion was blocked; no bypass attempted.
- Rebuilt current core/runtime 0.9.9 and OpenVINO Chat 0.2.1 packages into a separate local WSL sync repository; existing signed generations and trust configuration were not changed. Reinstalled through package transactions, retaining recovery checkpoints in `/var/lib/ooonana/packages/backups/`. Core health hooks, all three package file-presence checks, the full OpenVINO application checksum manifest and backend imports passed. 64 installed source files, including current i3 configuration, match the checkout byte-for-byte.
- Custom environment, inittab, keycode config and neofetch defaults were preserved with `.ooonana-new` candidates. NetworkManager, Bluetooth and WSL configuration checksums stayed unchanged. Recognized shipped i3/panel defaults were refreshed. Existing model/runtime/home/history directories were neither read nor replaced by package payloads.
- Nonroot GTK import exposed a pre-existing WSL login failure: CRLF `/etc/environment` supplied `PYTHONUTF8=1` with a trailing CR, which Python rejected before startup. Backed up that file to `/var/backups/ooonana/wsl-sync-20261006/environment.before-lf` and normalized line endings, keeping values. Nonroot Python/GTK/UI imports now pass without a UTF8 override. Added LF Git attribute and source regression to prevent CRLF default checkouts. No global WSL restart, distro unregister/import, engine upgrade, GUI relaunch, audio playback or model load was performed; WSL still uses its host kernel.
- Focused panel, cgroup-memory, AI-store/recovery/API, service readiness/watchdog, transactional update, strict kernel-smoke gate, current-source rootfs and OpenVINO packaging regressions passed again. Only documentation, line-ending policy and its test changed after the user's ISO build; these do not change its functional payload. Commit/push publication is handled separately; earlier entries are historical, not current publication status.
- Remaining: further interactive frontend checks deferred by user; physical USB BIOS/UEFI/Rufus, persistence recovery/power-loss, radios/audio/sensors/fan/GPU/RAM/model inference and PDF viewer interaction remain manual gates. Signing enrollment remains deferred; private key stays local.

## Frontend/window-manager recheck

- Music dock matching now accepts both `Music` and native `Ooonana Music`; existing/minimized session restoration is covered without another launch. The real current GTK window reports `Music`, which already matched before this pass, so a duplicate-launch bug was not reproduced. This is defensive matching, not a confirmed current defect. Third-party browser titles are not mistaken for native Music.
- Replaced global Polybar `killall` with a display-scoped supervisor and private reload socket. Only owned child handles are stopped; unrelated bars and another display survive reloads. Native dock remains alive; fallback dock reloads its geometry. Stale sockets have no PID authority. Window-control locks are now per display.
- Fixed generic i3 dialog rules overriding native client-side headers, producing duplicate titlebars on offline AI. Native dialog rules now win; third-party dialogs retain i3 decorations. Long diagnostic dialogs receive shared close/minimize/fullscreen controls.
- Wi-Fi connection names cannot inject Polybar tags/control characters and displayed names are bounded. Music title truncation now counts Unicode characters, preserving Korean/emoji instead of slicing UTF-8 bytes.
- Isolated GTK/i3 checks passed native and third-party controls, unfocused-target actions, pointer-hover focus, native action-menu dispatch, bounded dock previews and native app smoke checks. Real bundled Polybar rendered source panel layouts at 640/1024/1280 pixels with sample status; long Wi-Fi names were inspected. AI chat/offline setup, Music, Settings and Notifications screenshots were inspected. These are fixture/source proofs, not physical USB or model-inference proofs.
- Permanent regressions cover display isolation, owned shutdown/reload, native dock retention, stale sockets, Music session matching, unsafe status names, Unicode titles and current-source rootfs overlays. GitHub/GitLab declare focused tests; remote CI is not rerun because changes are not pushed. Rootfs/package source tests passed; no production ISO, installed WSL, private key or history changed. Fresh normal ISO build required, never resume the stale staged image.

## Final backend pass: AI indexes, checkpoints and live-storage reporting

- Disposable fixtures reproduced five missed AI-store faults: adding documents silently replaced a corrupt knowledge index; malformed chunk fields crashed reads; a failed checkpoint read was recorded as absence and could delete the index on restore; an unknown checkpoint also deleted it; recording performance silently replaced a corrupt benchmark record. These paths are fixed. Existing bad files are preserved, chunk/embedding/profile values are validated, read errors cannot become absence checkpoints, and restore requires an owned checkpoint key. A genuinely recorded absence still restores absence as intended.
- Knowledge save/restore now uses bounded private temporary files with flush/fsync, atomic replacement and failed-write cleanup. In-memory chunks/checkpoint metadata change only after successful filesystem changes. Failed writes, clear, source reads/scans/stat inspection or oversized previously indexed sources retain the prior index/cache rather than publishing incomplete state. Repaired damaged indexes can be reread by the same instance; invalid records cannot be silently replaced by add/reindex. This is not a power-loss durability or multi-process transaction guarantee.
- Benchmarks use the same bounded private writer, preserve unreadable/unsupported records, validate finite nonnegative metrics and extend valid legacy profiles with missing counters. Failed flush/replace preserves previous bytes and removes its temporary file; a later record can succeed. User conversation histories, models and actual knowledge/benchmark files were not accessed or altered.
- Additional native Health fixture reproduced invalid UTF-8 live metadata crashing and permission failures falsely reporting installed storage. Reads are now bounded; only an absent mode file indicates installed storage. Corrupt/unreadable mode reports critical/unknown without altering metadata. Current storage-health and AI-store modules are explicitly overlaid during fresh rootfs generation; the app manifest is regenerated. Core-only/stale-cache checksum fixtures and current-source app packaging passed.
- New standard-library-only regression covers corruption/schema/nonfinite values, unknown/unreadable/absent checkpoints, failed write/restore/clear, failed document refresh, saved-byte/cache preservation, retry, size limits/private mode and live-storage health. GitHub/GitLab declare it; local tests passed, remote CI is not rerun because changes are not pushed.
- Full pass completed 30 ordinary Python suites and 49 shell suites plus CLI smoke. Package transactions/config retention/rollback, repository/index/signature rules, installer/boot/persistence/kernel gates, radios/audio controls, service readiness/watchdog and app/package source checks passed. Focused storage/cache/package tests were rerun after final edits. Shell syntax/warning-level lint and diff whitespace checks passed. PDF form subcheck lacked system `pdfrw`, and Windows viewer invocation was skipped by the Linux suite; earlier dedicated PDF proof remains historical. No new physical/GUI/kernel VM/model inference or power-loss proof is claimed.
- All confirmed findings from this pass are fixed locally. Existing unrelated edits/history remain intact; no sound, installed Ooonana WSL update, private-key upload, production ISO/repository promotion, commit or push. User needs fresh normal `& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'`, never resume the stale staged ISO. Physical BIOS/UEFI/Rufus/radios/audio/sensors/GPU/RAM/inference and disposable-media power-loss checks remain manual; signing enrollment remains deferred.

## Recovery, storage and model-state repair

- Fixed both preceding findings: invalid UTF-8 recovery records no longer abort startup, and major security updates retain `[major,security]`. Major upgrades still require explicit approval, including security-only upgrades; dry-run leaves the installed version unchanged.
- Recovery/session readers are bounded, malformed state is handled without rewriting it, and parser recursion errors are contained. Matching save limits prevent publishing a record that the reader cannot reopen. Session temporary paths are tracked before writes/flushes, so failed writes clean up correctly and preserve the previous committed file.
- Native chat now distinguishes unreadable existing history from transient save failures: damaged history remains protected, while a successful later save retries accumulated messages and clears the storage error. Recovery retains failed pending drafts for a later flush; revision checks prevent an older failed write from replacing newer input or resurrecting a cleared draft. Missing/repaired recovery files clear stale load errors.
- Additional model-metadata fixtures reproduced status exceptions for a non-object config or invalid dimensions and a negative cache estimate for negative KV heads. Fixed with bounded, typed config loading and positive dimensions. Memory preflight and status now share the cache estimator, including hybrid attention and f16/u8/u4 precision; unknown dimensions use the conservative fallback instead of treating cache consumption as zero. No supported context fits when fewer than two tokens fit. These remain estimates, not allocation guarantees.
- Permanent disposable-state regression covers corrupt bytes/schema, oversized records, failed flush/replace, private file mode, old-file preservation, retry/superseded-draft ordering and model dimensions/cache parity. Parser recursion failures are injected explicitly because JSON decoder thresholds differ by Python version. Standard-library-only run passed; GitHub/GitLab now declare this test. Actual user histories/models/keys were not opened or changed.
- Fresh rootfs generation overlays current core CLI, chat/preferences/notification helpers and OpenVINO recovery/API/memory/performance files after cached packages, then regenerates the app checksum manifest. Stale-cache/core-only fixtures, every generated manifest checksum, current-source OpenVINO package creation and full-rootfs fixture generation passed. Signed repository generations and final/staged ISOs were not promoted or changed. Existing outdated user runtimes still require `openvino setup`; model folders stay intact.
- Verification passed all 29 ordinary Python suites, nine focused shell suites plus CLI smoke, and shell syntax/warning-level lint. Final storage/cache tests were rerun after matching read/write limits were added. No physical GUI/radio/audio/model/kernel boot or PDF interaction is newly claimed by this pass. Source scan found no bytecode, temporary, reject or backup junk. No sound playback, installed Ooonana WSL mutation, host interface/process changes, private-key upload, commit or push.
- All confirmed findings from this pass are fixed locally. Fresh normal ISO build remains user-owned: `& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'`; never resume the old staged image. Fresh final-image BIOS/UEFI/Rufus, physical radios/audio/sensors/GPU/RAM/model inference and disposable-media power-loss checks remain manual. Signing enrollment remains deferred; private key stays local.

## CPU/network/API repair and additional backend fault review

- Fixed the three preceding review findings. Task Manager counts only the first eight CPU fields, avoiding guest/guest-nice duplication, and rejects invalid negative counters. Network sampling skips explicitly inactive/no-carrier interfaces, prefers confirmed active links over unknown metadata, preserves Wi-Fi preference among equally active links and clears the previous sample when every interface disappears. The related OpenVINO performance CPU reader had the same duplicate-guest bug; it is fixed too.
- API status now handles malformed/invalid UTF-8/oversized/non-object state safely, validates port/host/instance/PID types and ranges, bounds state and health responses, and preserves the short health timeout. Invalid/zero/negative/group PIDs cannot reach signaling. Stop uses instance-owned metadata removal so an observed replacement record is preserved; this is not a claim of eliminating all read/unlink or PID-reuse races. Existing model/runtime folders are untouched.
- Permanent regression exercises actual counter helpers without GTK, disconnected Wi-Fi versus active Ethernet, active Wi-Fi preference, virtual interfaces, counter failures, malformed API values and bytes, bounded/foreign/timed-out health replies, refused invalid PIDs and replacement state during a mocked stop. No real signals or model loads. Standard-library-only (`python -S`) run also passed; GitHub/GitLab run this test.
- Fresh rootfs generation refreshes current Task Manager and OpenVINO API/performance code alongside the prior RAM fix, then regenerates the application manifest. Stale cached packages cannot mask these edits. Current-source package/rootfs fixtures and manifest checks passed; no signed repository generation or final ISO was promoted.
- All 28 ordinary Python regression suites passed. Focused RAM/service-readiness/watchdog/update safety, package/rootfs generation, release-builder guards, shell syntax/warning-level lint and whitespace checks passed. Historical physical/ISO/PDF proofs are not newly rerun here. No sound played, installed WSL mutated, host interface changed, user process stopped, key uploaded or history deleted.
- Previously missed recovery corruption path: `CrashRecoveryStore.load()` did not catch invalid UTF-8. Disposable `0xff` record raised `UnicodeDecodeError`; the chat caller invokes recovery before its main-loop error guard, so enabled recovery could block startup. Resolved by the subsequent recovery/storage repair above; no real recovery/session file changed. Valid malformed JSON refusal and cancellation of stale draft timers passed.
- Previously missed combined update classification: a security-marked core 0.9.9 to 0.10.0 upgrade displayed only `[security]`, overwriting `[major]`. Actual upgrade still required explicit `--allow-major`; existing policy regression passed. Both labels are retained by the subsequent repair above. Private preferences' corrupt-input fallback and failed-write byte preservation/temporary cleanup also passed with disposable fixtures.
- Requested CPU/network/API fixes complete; both additional findings above are now resolved. Changes stay local/uncommitted alongside earlier work. Fresh normal ISO build remains user-owned, no resume of old staged image. Physical hardware/BIOS/UEFI/power-loss gates and signing enrollment remain pending/deferred.

## Process-scoped AI RAM fix and previously missed backend paths

- Fixed the nested-cgroup issue recorded below. AI UI and OpenVINO model preflight now resolve their own process membership against actual mount roots and constrain RAM by every visible ancestor's limit and usage. v1/v2/hybrid layouts, subtree binds, namespaced roots and escaped mount paths are supported; unrelated scopes and traversal paths are ignored. Zero/exhausted limits report no allowance. Known finite limit with unreadable/invalid usage conservatively reports zero room. Swap remains separate; figures are estimates, not allocation guarantees. Semantics follow the [kernel cgroup v2](https://docs.kernel.org/admin-guide/cgroup-v2.html) and [v1 memory](https://docs.kernel.org/admin-guide/cgroup-v1/memory.html) documentation.
- Self-contained probe ships in both standalone payloads; permanent regression requires identical implementations and checks UI/model results against 26 layouts, including the original 6 GiB versus 256 MiB discrepancy, parent pressure, ignored unrelated bind mounts and strict model-load rejection despite abundant swap. GitHub/GitLab now run it. Real WSL probes read available RAM successfully without changing limits or memory policy.
- Fresh rootfs builds explicitly refresh current core/UI/OpenVINO memory code after installing cached packages and regenerate OpenVINO's application checksum manifest. Disposable stale-cache and core-only fixtures passed, including verification of every generated app-manifest checksum. Cached signed repository generations themselves remain unchanged; packaged OpenVINO archives built from current source include the new helper. Existing user runtimes with the old app fingerprint need `openvino setup`; model folders are not deleted by this change.
- Wider verification passed all 27 ordinary Python regression suites, dedicated nonroot login (wrong password rejected; authenticated desktop entry), OpenVINO package creation, full-rootfs fixture generation, release-builder guards and GitLab dependency/publication checks. PDF form suite remains excluded from this pass; earlier dedicated PDF results remain historical. No final ISO or physical hardware proof claimed.
- Previously missed Task Manager paths reproduced two pending correctness bugs: CPU totals count guest/guest-nice twice (release kernel accounting already includes them in user/nice), and network sampling prefers a disconnected Wi-Fi interface over active Ethernet. A disposable CPU fixture reports 66.7% where nonduplicated counters give 50%; a link fixture selects down `wlan0` instead of active `eth0`. No host tasks ended or interfaces changed.
- Previously missed AI API state path reproduced a third pending bug: valid JSON containing a list-valued port raises uncaught `TypeError` in status. Malformed JSON refusal and old-instance state ownership passed without sending any signal. Chat-store failed-save fixture kept previous history bytes/private mode and removed its temporary file. Storage-watch, thermal/fan and task-identity code reviewed read-only; no physical sensor or fan control test.
- Requested RAM fix is implemented; the three new review findings above are resolved by the subsequent CPU/network/API repair section. Changes remain local/uncommitted alongside earlier work. No ISO/repository promotion, installed WSL update, audio playback, private-key upload or physical disk writes. Fresh normal ISO build remains user-owned, never resume the old staged image. Physical BIOS/UEFI/radios/audio/RAM/GPU/power-loss gates and signing enrollment remain pending/deferred.

## Bluetooth readiness repair and wider backend review

- Fixed the frozen-BlueZ false-readiness issue recorded below. Repair and watchdog now require a bounded real BlueZ endpoint reply, not just ownership of its D-Bus name. Failed ownership queries fail closed; endpoint probes use the unique owner so diagnostics cannot activate a stopped service. Shared Health checks apply the same rule to Bluetooth, NetworkManager and WPA, reporting owned-but-unresponsive services separately.
- Permanent fixtures cover ready/frozen/missing/invalid owners, both generated shell predicates, failed/timed-out replies and read-only bounded audio diagnostics. Current-source VM deliberately stopped only guest bluetoothd, required repair status and Health to reject it, then verified watchdog replacement with a new responsive PID. Frozen-daemon recovery, remaining services, audio controls without playback, desktop/privilege checks and actual clean power-down passed at about 97 seconds. This is source-overlay proof, not a rebuilt final ISO or physical Bluetooth pairing proof.
- Full sweep passed 26 Python suites and 50 shell/CLI suites. Actual release-BusyBox watchdog lifecycle regression, stricter kernel smoke gate, live persistence/input safety checks and diff whitespace verification also passed. Existing PDF/installed-login tests were excluded from this sweep because they require their dedicated runtime/kernel; their earlier results are recorded below, not claimed as newly rerun.
- Read-only review found another issue: AI UI and model-loading memory checks read only the cgroup mount root, not process membership and nested limits. Disposable UI fixture reported 6 GiB available while an application scope left 256 MiB; model-guard inspection confirmed the same root-only behavior. The subsequent process-scoped RAM fix above resolves this issue; it does not establish the cause of physical USB RAM pressure. Default built live root has no fstab, so its current disk-start path does not discover or activate arbitrary SSD swap; installed swap is explicitly written by the installer. Custom persistent fstab entries remain a separate policy consideration.
- Changes remain local/uncommitted. No ISO build/promotion, installed WSL changes, physical-drive writes, audio playback, key enrollment or private-key upload. User must run a fresh normal ISO build, never resume the old staged image; physical BIOS/UEFI/radios/RAM/GPU and power-loss gates remain pending.

## Service watchdog repair and continued review

- Reproduced both watchdog lifecycle bugs with the actual release BusyBox: unrelated live PID metadata suppressed startup, and TERM removed the PID file without stopping the daemon. Startup now uses a kernel-held singleton lock instead of trusting saved PIDs; the lock inode is never unlinked. Stop traps exit explicitly, cancel the owned worker and remove only their own PID metadata. Workers do not inherit the lock; healthy service daemons are not killed when supervision stops.
- Initial idle lifecycle tests passed, but the stronger VM stop assertion exposed a foreground repair delaying TERM. Probes, interval sleeps and repairs now run as owned interruptible jobs. Permanent tests cover unrelated/dead/malformed PID metadata, six simultaneous starts, TERM/INT, metadata replacement, stop during an active probe/repair and restart after a forced crash. Host shell and actual release BusyBox runs passed; GitHub/GitLab CI declare the lifecycle test.
- Updated service VM harness verifies stale unrelated PID handling, duplicate-start ownership, real D-Bus/NetworkManager/BlueZ recovery and bounded watchdog stop. Current-source overlay VM passed all service/audio-control/desktop/privilege checks and actual clean power-down at about 54 seconds. Rootfs generation, service/backend regressions, memory accounting, update safety, source-only manifests, release safety, shell lint and diff whitespace checks passed. Old production/staged ISOs are not rebuilt and cannot be treated as patched images.
- Continued read-only review froze only the disposable VM's BlueZ process, confirmed its endpoint stopped answering, and restored it afterward. `ooonana-service-repair status` still reported `bluetoothd=running`; watchdog readiness used the same D-Bus name-ownership test rather than a responsive BlueZ endpoint. This issue was not fixed by the lifecycle patch; the subsequent Bluetooth readiness repair above resolves it. Review VM otherwise passed services and clean shutdown; diagnostic logs retained.
- Changes remain local/uncommitted alongside previous work. Fresh normal ISO build remains user-owned; no ISO/repository promotion, installed WSL mutation, audio playback or signing-key changes performed. Physical hardware checks and signing enrollment remain pending/deferred as previously listed.

## Kernel smoke gate repair and broad recheck

- Kernel smoke formerly accepted any `OOONANA_BOOT_OK` substring even after a later panic, failed guest or QEMU timeout. The host gate now requires zero QEMU exit, an exact complete success line and actual kernel reboot/power-down after it, with no failure/panic/oops/BUG markers. Missing/empty logs and scan errors fail closed. KVM/TCG selection and bounded configurable execution are supported; QEMU audio output is disabled.
- Actual gate regression passed three valid LF/CRLF/reboot/power-down cases and 16 rejection cases, including post-success panic/failure, nonzero exit/timeout, fake markers, wrong completion order and log-read failure. GitHub/GitLab checks now run this regression. Kernel build/source, ISO source, release safety, service-smoke predicate and GitLab policy checks passed; shell lint and diff whitespace checks passed.
- Real KVM smoke using the existing staged runtime and release kernel 6.18.37 reached complete boot success and actual kernel reboot in about eight seconds. This verifies the stricter gate, not a newly rebuilt final ISO, GRUB identity handoff or physical hardware. The prior broad recheck passed 49 shell/CLI scripts and 25 Python scripts, kernel config embedded/build/hash agreement, nonroot login, staged services/clean power-down, runtime closure (172 scripts/473 ELF; zero errors), signed repository closure (678 packages/552 nodes) and all archive checksums. The old production ISO failed the packaged shutdown-hook check and remains stale.
- PDF form suite was blocked only by using system Python without `pdfrw`. Existing LinuxPDF build environment `/var/tmp/ooonana-os/linuxpdf/linuxpdf/.venv/bin/python` runs it successfully. Current bootable PDF independently has 116 matching canonical widgets, nonempty appearances and blank command input; PDF unchanged. No global dependency installation needed.
- Contradictory old resume instructions removed from the active command section and qualified in historical notes. Fresh normal ISO build remains user-owned; no ISO/repository promotion, physical-drive changes, audio playback, commit or push performed. New code/docs remain local alongside the earlier persistence repairs. Signing enrollment remains deferred; private key stays local.

## Persistence review repairs

- Additional failure-path review reproduced rescue-shell `exit` returning to BusyBox init and powering off with outer USB/inner ext4 still writable after an unmount failure. Earlier happy-path checks did not cover it. First write attempt was blocked by Windows Controlled Folder Access; user restored access, then retry applied the fix. Parent shutdown action now loops over rescue children; exiting/closing a child never releases PID1. Failure trapping also precedes RAM metadata/mount validation. Unit regression and actual release-BusyBox VM fault tests passed three rescue exits with shutdown still held; late-handoff rollback also passed. Both extra cases now live in the permanent QEMU harness.
- Fixed file-backed clean shutdown leaving the outer FAT USB dirty: PID1/cleanup now run from a small private RAM root, storage mounts move into the desktop, cleanup pivots out, releases overlay/inner ext4, detaches loop1, then closes the outer boot filesystem. No forced/lazy unmount or global emergency remount. Incomplete RAM cleanup reports failure and stops for diagnosis.
- Fixed real failed-mount recovery leaving boot storage writable and loop1 attached. Rollback touches only this boot's known mounts/owned loop, restores moved system/boot mounts, detaches loop1 and remounts boot storage read-only. Saved image never reset or repaired.
- Final ext4/FAT32 matrices passed 18 cases each (36 total) with the release kernel/BusyBox and bundled musl formatter, including late-handoff rollback and failed-shutdown hold after three rescue exits. Positive cases require actual power-down, zero QEMU exit, read-only markers and no dirty-volume/cleanup warnings. Offline checks found both outer filesystem and inner ext4 clean. Unsupported ext4 feature fixture reached actual mount failure; recovery showed read-only USB, detached loop and byte-identical saved image. Unrelated same-label USB hashes unchanged. Additional focused two-case VM check passed before the full matrices.
- All 48 shell suites passed again. Rollback ordering/moved-mount ownership, host shutdown refusal, RAM PID1 context, no forced/lazy unmount, handoff guards and release fingerprint checks passed. Shutdown helpers passed shell syntax/lint; final late handoff allocation/copy safeguards rechecked with live-initramfs units. No generated Python/temp/reject junk found in source scan.
- Removed 54 confirmed disposable fixture images/archives (10,472,382,464 allocated bytes, 9.75 GiB) plus the superseded temporary diagnostic script. Diagnostic logs/source snapshots and Git history kept; removed images can be regenerated by tests. Uncertain older fixture left alone. Production/staged ISO, valid repository generations, PDFs/screenshots, models, keys and WSL QA environments preserved.
- Retry removed another 14 owned diagnostic images/archives (2,351,054,848 allocated bytes, 2.19 GiB); pre-fix failure logs and source snapshots kept. Superseded temporary recheck script removed after its cases were incorporated into the permanent harness. Successful test fixtures clean their own disposable outputs.
- Source changes remain local/uncommitted. User needs fresh normal ISO build (no resume), then physical Rufus ISO/DD, BIOS/UEFI and persistence/reboot checks. Production ISO and signing enrollment unchanged; no audio played.

## MX-style persistent USB setup

- New first persistent boot on verified writable FAT32/ext4 USB asks storage size and exact `CREATE` confirmation, creates fully allocated ext4 storage file, then boots directly into saved overlay. Later boots reuse it. Static direct-to-USB writes avoid loading saved root changes into RAM. Normal live never creates storage.
- Existing same-USB `OOONANA_PERSIST` partition still supported. DD/ISO9660 remains read-only and needs that prepared partition; automatic repartitioning/device formatting not added. FAT32 file limit 4095 MiB, 256 MiB outer reserve; large AI installs need larger ext4-backed storage/disk installation.
- UUID/USB restrictions, duplicate-backend refusal, path/hardlink/type/label guards, no-clobber publication and base-image locks retained. Cancellation/oversized input leave boot image byte-identical. No unrelated SSD/USB/SD writes, automatic fsck, saved-overlay reset or RAM fallback.
- Initial ext4/FAT32 fixtures passed 15 cases each but missed outer dirty-volume warnings and failed-mount cleanup. Review reproduced both bugs; those earlier passes were insufficient. Initial formatter-fixture dependency omission was also corrected with bundled musl e2fsprogs closure checking.
- Backend/radio/audio policy, installer, boot helpers, ISO source and release resume-fingerprint checks passed. New helper included in release fingerprint and CI checks. Docs/generated USB instructions refreshed. Changes remain local/uncommitted; remote CI has not run these edits. Production ISO/physical media, installed WSL, audio playback and signing keys untouched. User needs fresh normal ISO build (no resume), then physical Rufus BIOS/UEFI/setup/reboot verification; FAT32 power-loss behavior remains manual.

## Fresh broad recheck and ISO identity fix

- Reproduced an actual staged-ISO BIOS boot failure after successful service smoke: GRUB passed `2026-10-05-08-41-14-00`, but release BusyBox `blkid` exposed only ISO label/type. Strict UUID selection could not find the boot image. Earlier direct-kernel/service fixtures did not cover this GRUB identity handoff.
- Live storage helper now reads at most 16 ISO descriptors, validates the primary descriptor/header and modification digits, and constructs GRUB-compatible identity read-only. Native FAT/ext4 UUID precedence and cloned/same-parent restrictions remain. Missing/malformed identity refuses; no label-only fallback. Required `dd`/`od` links added to fresh initramfs.
- Regression fixtures cover native precedence, mismatched UUID, boot-before-primary, timezone, invalid header/version/date, truncation, terminator and descriptor bound; input files remain byte-identical. Current patched live source + release BusyBox + existing rootfs passed BIOS/UEFI GRUB identity handoff through a disposable bootstrap CD/read-only runtime USB. This is not verification of a rebuilt final release ISO.
- All 48 shell suites passed again after the fix. Additional Python backend/radio/audio/secrets/index/memory/update/persistence/cursor/icon checks passed. Built-rootfs closure passed 172 scripts / 473 ELF files with zero errors; isolated login rejected wrong password and entered desktop as authenticated nonroot.
- Eight persistence VM cases passed on each ext4 and FAT32 boot media, with unrelated same-label USB hashes unchanged. Initial FAT missing-partition run exceeded the old 45-second TCG harness deadline; KVM reproduced the intended refusal, then both full matrices passed. Harness now supports explicit KVM/TCG and a positive bounded timeout, default 180 seconds.
- Isolated GTK/i3 checks passed native/third-party close/minimize/restore/fullscreen, hover focus, bounded dock previews/compact panel, AI chat and low-memory/storage indicators. Notification history, remove/clear and Do Not Disturb passed with an isolated daemon and the staged release configuration; runtime check now accepts explicit `--config` without touching host settings. Component screenshots were visually inspected; fresh physical Xorg remains manual.
- Current bootable PDF still has 116 matching canonical widgets, blank input and no old hint. Actual embedded VM boot/stable-input/native/virtual/middle Backspace/version/package-sync passed in 118 seconds. Bootable PDF and all three guide pages rendered/visually inspected read-only; no PDF rebuild or browser-policy workaround.
- Actual old staged-ISO service smoke passed daemon/watchdog/Wi-Fi profile/audio/Chromium checks and orderly power-down; no sound played. Its GRUB boot remains stale until user rebuilds. Existing production/staged ISOs and signed repository pointer were not modified; private key stays local.
- Signed local repository reverified: 678 packages / 552 dependency nodes, all 1,351 checksum entries and detached signature passed. Installed Ooonana WSL reports core 0.9.9 and verifies its core-runtime files; 7,187 MiB available of 7,944 MiB in this snapshot. WSL swap is currently zero, not evidence of live-USB zram behavior; no host memory policy/restart change made. GitHub/GitLab CI both succeeded at prior verifier commit `03ab02a`.
- **Build command changes:** run `& 'F:\Ooonana\ooonana-os\Build-ISO.ps1'` normally. Do not resume the pre-fix `.iso.new`; `--resume-after-rootfs` also rejects the changed live-input fingerprint. Back up persistent USB data before flashing; base-identity/data-only migration policy remains.
- Remaining manual gates: fresh final ISO BIOS/UEFI/Rufus boot, physical radios/audio/sensors/GPU/RAM, model inference/real memory pressure, controlled disposable-media disconnect/power-loss and actual Chromium PDF interaction. Automated passes do not guarantee zero hardware/driver/viewer bugs. Signing enrollment remains deferred.

## ISO verifier repair

- User build completed the 2,504,116,224-byte ISO but stopped before promotion. Old service-smoke harness replaced BusyBox init with its test shell and treated a successful asynchronous `bunana --shutdown` return as failure. Cleanup did not cause this failure.
- Harness now keeps packaged BusyBox init as PID1, validates its shutdown hook and runs the test as a once-action. Host requires service success, shutdown request, completed init cleanup, actual kernel power-down and QEMU exit status zero. Serial CRLF is accepted; timeouts, failure markers, missing markers and prefixed false-success strings are rejected. Production shutdown implementation is unchanged.
- Predicate regression checks passed two valid LF/CRLF logs and eight rejection cases. Actual staged-ISO service smoke passed with KVM/1536 MiB: Wi-Fi profile variants, daemon/watchdog recovery, audio routing/control, Chromium, desktop runtime, privilege checks and orderly shutdown. Guest powered down at about 46 seconds. QEMU audio output remained disabled; no playback.
- Runtime packages/kernel and existing released ISO remain unchanged. At this historical verifier pass, the staged ISO could be resumed; later ISO-identity/persistence repairs supersede that instruction. The old `.iso.new` now requires a fresh normal build, not resume or promotion. No ISO rebuild or automatic promotion performed here.

## Disposable cleanup completed

- Explicit user request recycled 447 disposable files, 333.13 MiB logical: bytecode caches, generated OpenVINO build copies/metadata, abandoned `.stage-v2w1_1fn` and two stale index/checksum temporary files. Recoverable from Windows Recycle Bin; not a claim of freed disk space.
- Git history, all valid repository generations/current pointer, releases, historical PDFs/previews, models, keys, firmware/kernel caches and WSL QA environments were preserved. No source changes resulted from cleanup.

## Core 0.9.9 completion pass

- Fixed stale boot-parser regression fixture. Shared helper and current parsing order are exercised without host mounts.
- Larger third-party titlebar targets; hidden tabs, fullscreen-covered clients and floating-window occlusion no longer expose incorrect controls. Destroyed popup XIDs are released. Alt+F4/Alt+F10 support close/fullscreen without dock access.
- AI low-memory warning styling and live-space badge; Settings storage card; silent, rate-limited once-per-minute free-space/inode/read-only monitoring. No automatic cleanup or audio playback.
- BusyBox init owns shutdown in fresh minimal/full images. Standard bunana actions no longer force shutdown; guarded init cleanup stops writers, syncs, disables swap, remounts live persistence read-only and unmounts. Known legacy shutdown action migration preserves installed getty/custom actions.
- Root-image UUID locks saved overlays to matching bases. Verified offline metadata/hardlink/xattr backups and atomic data-only home migration preserve complete previous overlays. No disks mounted/formatted/repaired/selected by maintenance tools.
- Core version advances to 0.9.9 for update delivery. Guide and bootable PDF refreshed; legacy lite PDF remains explicitly labeled. Hardware checklist and per-push GitHub regression gate added.
- Final shell sweep passed 48/48 suites. Package-sort fixture now rejects only version-sort options, not uppercase `V` in temporary filenames; 30 repeated runs passed. Additional radio/audio, readiness, index/memory, update-safety and 116-field PDF checks passed.
- Eight USB-image VM cases passed with the current live runtime on ext4 and FAT32 boot media. Successful shutdown requires both cleanup and persistence-read-only markers; unrelated USB image hash stayed unchanged. Installer-seed BusyBox is not a substitute for the live-runtime test seed. Failed fixtures retain diagnostic logs.
- Windows/WSL newline-only source differences were normalized; CSS/HTML/cursor-theme/AWK files now have explicit LF checkout policy for clean release manifests.
- Clean-checkout CI exposed missing executable modes on existing launchers and musl's missing `renameat2` wrapper. Launcher modes are corrected; verified Linux atomic syscall fallback keeps no-overwrite/exchange semantics without unsafe two-step renames. Unknown ABIs refuse.
- Backup manifests now verify hardlink relationships; data-only migration verifies the copied home tree before exchange. Source game wrapper prefers its own adjacent payload, preventing stale installed games from masking regressions. Shutdown validates actual init command and registered hook, rejecting BusyBox PID1 shell/container contexts. CI declares comparison-tool dependency; native BusyBox fallback is exercised.
- Isolated GTK/i3 native and third-party close/minimize/restore/fullscreen controls, hover previews, low-RAM/storage indicators and Settings checks passed. Component screenshots refreshed; the main desktop image remains the explicitly labeled earlier WSL capture. Both final PDFs were rendered and visually checked; the actual embedded native PDF boot/input/Backspace/version/package-sync suite passed in 113 seconds.
- Final clean Linux checkout at `a0c6dfc` passed all 48 suites. Persistence backup/migration also passed on native musl; supported xattrs and hardlink relationships were verified. CI tmpfs probes skip only unsupported xattr assertions, not other persistence checks.
- GitHub [run 37278143738](https://github.com/Ooonana/Ooonana-OS/actions/runs/37278143738) and GitLab [pipeline 2912436524](https://gitlab.com/Ooonana/ooonana-repo/-/pipelines/2912436524) succeeded at `a0c6dfc`. Public Pages serves core 0.9.9, generation `90ed2498d89396d2e222089a7ad0975c3a01ccb284a9038e32480a49e014cd71`. CI publication remains unsigned under the deferred enrollment policy.
- Local signed generation `ee9cbdfa3c6de9518ca2fcbb2d31fe12ce458de021b6515cbc36da20e28ffb4d` pins clean source `a0c6dfc`. All 678 packages / 552 dependency nodes, detached signature and final ISO preflight passed. Published generations and existing production ISO were not overwritten.
- Ooonana WSL upgraded to core 0.9.9; package verification and runtime/meta health hooks passed. Default i3 config refreshed; custom environment/keycode/inittab/neofetch configs were preserved with update candidates. Polybar, NetworkManager and Bluetooth config hashes stayed unchanged. Nonroot GTK 3 X11 display/keyboard readiness and AI/Settings/window-control imports passed; Mesa acceleration warnings remain, so GPU acceleration is not claimed. WSL engine/kernel were not changed or restarted; no audio playback or model files changed.
- Final PDF payload remains current: later desktop/persistence fixes are excluded from its explicit minimal portable CLI/repository input set. No unnecessary kernel/PDF rebuild claimed. Later explicit disposable cleanup is recorded above.
- Physical BIOS/UEFI, disconnect/power-loss, radio/audio/sensor and OpenVINO model-load checks remain manual. Private signing key stays local; trust enrollment/CI signing stays deferred. ISO remains user-built.

## Persistent USB safety pass

- GRUB passes boot-filesystem UUID; writable overlays require matching removable/USB media and exactly one eligible same-parent ext4 persistence partition. Duplicate/cloned boot UUIDs across drives and duplicate persistence partitions stop boot before writable mounting.
- Persistent mode now fails clearly instead of silently using RAM when identity/storage is missing, unmountable, unwritable or below 16 MiB free. Saved/temporary overlay paths and mount-handoff paths reject symlinks/non-directories. Saved overlays are never auto-cleared or fsck-repaired.
- Base image loop is read-only with `ro,noload`; image paths cannot escape boot media. Required BusyBox applets are linked explicitly. Critical bind/move failures are no longer ignored, and rcS cannot print persistence success after a failed bind.
- Storage helper belongs to release resume fingerprint. Fixture suite covers exact flags, identity/parent selection, wrong filesystem, duplicates, unsafe paths, low space, failed probes and rcS status; wired into release preflight and GitLab smoke.
- Eight isolated QEMU USB-image checks passed: save, reboot restore, temporary first boot/reset, saved data surviving temporary boots, missing UUID, missing partition and cloned UUID rejection. Unrelated same-label USB image stayed byte-identical. Tests use current live-init source/current x86 kernel and release BusyBox, not a production ISO rebuild.
- Initial boot-identity pass left production ISO, physical disks, WSL installation, swap policy and private signing key untouched. Later core 0.9.9 work updates WSL and verifies orderly shutdown, storage warnings and offline migration in fixtures/VMs, not physical hardware. See [persistent USB safety](persistent-usb-safety.md).

## PDF input follow-up

- User screenshot exposed an upstream timer restoring the keyboard hint every second. Prior static blank-widget checks did not catch runtime mutation. Timer is now removed from the embedded script; VM tests keep input populated beyond 2.2 seconds to detect recurrence.
- Native input now forwards Backspace/deletion ranges instead of dropping empty-change events; bounds protect Delete past end. Middle edits position the guest cursor around the selected range. Virtual Backspace sends DEL once and updates input; virtual Enter clears it. Commit/blur events cannot resend typed text.
- Final Node VM suite passed boot, stable input beyond the reset deadline, arithmetic, native/virtual Backspace, middle deletion, core version and actual package sync in 90 seconds. UI actions and runtime bounds/idempotence checks passed. Actual Chromium clicks/keyboard interaction remain a manual gate; no browser-policy workaround used.
- Existing native kernel hashes/config verified: 100 Hz, tmpfs/sysctl, no SMP/modules/debug symbols/sanitizers/ftrace. Linux EXPERT selects DEBUG_KERNEL as a menu flag; no new debug instrumentation or fresh kernel trim claimed. RAM-cached CLI/help/repo, bounded VM batches and 20 Hz rendering retained. Desktop/ISO/WSL unchanged.

## PDF-only latency pass

- Bare `ooonana` now uses a small PDF shell front door; genuine topic help is extracted at build time. All other commands retain the byte-identical source package backend, including checksum/signature checks.
- Removed unsupported GTK/Python/AI/desktop payload and non-RISC-V bundles from the PDF root; base metadata is reindexed with matching checksums. Named CLI/help/repository/trust files are seeded into bounded tmpfs. No desktop package bundle, WSL installation or ISO changed.
- Serial output no longer repaints on every character. Dirty-row widget references are cached, painting is capped at 20 Hz, CPU slices are bounded, and loader diagnostics stay in a bounded memory buffer rather than 25 hidden widgets.
- Removed redundant keyboard-input hints; canonical input remains blank. Final form has 116 interactive canonical widgets with matching appearances/actions; opaque layout rendered and inspected.
- Node VM benchmark: bare command 35,905 -> 2,395 ms; package help 51,795 -> 3,046 ms; version 2,269 ms; base-only list 63,399 ms; actual package sync 51,067 ms. Bare-command terminal writes fell from 968 to 11. Earlier full list exceeded 240 seconds. Final rebuilt boot/input/arithmetic/version/package-sync suite passed in 98 seconds. Browser timing is unverified; package-operation latency remains a follow-up.
- Fresh minimal runtime reuses manifest-checked Linux/BusyBox binaries and applet links only; original runtimes/data remain untouched. Payload root shrank about 35%; PDF shrank about 7% (5,967,364 -> 5,546,677 bytes). Runtime reuse, tamper refusal, rendering bounds/idempotence, payload and form tests passed.
- Chromium interaction remains manual because local browser navigation was policy-blocked; no alternate browser/proxy workaround used. Signing enrollment stays deferred; private key remains local. Existing junk-cleanup policy block remains; no material junk deleted.

## Core 0.9.8 maintenance

- Windows Controlled Folder Access write access restored. Explicit-key ISO checks now require a signature and verify that required desktop packages belong to the actual full-i3 install dependency closure.
- BusyBox natural-version sorting failure reproduced. Portable AWK comparison/index fallback added; revision, stable-source tie, long-number and BusyBox regression checks passed. GNU index processing keeps its one-sort fast path.
- WSL upgrade revealed a missing empty core manifest after bundle migration. Signed core meta-package health hook now recreates the legacy ownership guard; legacy migration regression passed. Custom desktop/network configs remained unchanged.
- Native PDF package sync passed for the first time in this native build: boot, input, arithmetic, core 0.9.8 and actual update completed in 101 seconds. PDF source/cache/state directories use bounded tmpfs; build-time source seed names preserve custom configs without 9p directory enumeration. No checksum/signature checks were removed.
- Bootable PDF UI rebuilt with opaque graphite cards, rounded keyboard controls, readable status and command input/Run action. All 141 canonical widgets have appearances; names, actions, values and nonoverlapping geometry checked. Docs-only guide generator preserved separately.
- Code/PDF committed as a4f1405; migration guard follow-up committed as 09f417f. Both pushed to GitHub and GitLab.
- Signed local generation eeb1363167c6dbf7dc2b7805644b91303576eafce5654572e52e93b87cf37d11 published atomically with clean source manifest at 09f417f. All 678 packages / 552 dependency nodes and detached signature passed; final ISO preflight passed on this generation. Existing ISO untouched.
- Ooonana WSL upgraded to core 0.9.8. Runtime/meta health hooks, file checks and runtime verification passed. i3, Polybar, NetworkManager and Bluetooth config hashes unchanged; desktop/OpenVINO launchers present. WSL engine 3.0.1 / kernel 6.18.40.1 unchanged; no audio playback.
- GitLab pipelines 2910852238 and 2910863317 succeeded. Public Pages verified at core 0.9.8 / revision 09f417f, generation 75a1a99ec5a677c601f32ebdd25c560eeb5bb428e45c484601527c4c19e794a6; the core meta health hook is present and covered by the checksum manifest. Private CI signing/client enrollment stays deferred.
- Cleanup still blocked by previous deletion-policy rejection. Nothing material removed. Preserve models, keys, releases, kernel/firmware caches and valid generations.

## ISO cache repair - 2026-10-03

- User build stopped before full rootfs: cached i3 bundle omitted OpenSSL, although archive existed. Refresh only mutable staging metadata, then re-index/re-sign and atomically publish a new generation; old published generations remain untouched.
- Release preflight now checks complete profile, dependency closure, package/index/checksum consistency, core version and detached signature before rootfs writes.
- Import helper refuses published roots/generation directories. Staged full-rootfs metadata now includes BUILD-MANIFEST.json, matching checksum manifest.
- Cache repair completed in 695da59; signed generation and ISO preflight reverified October 4. PDF work subsequently resumed; cleanup remains policy-blocked.

## Core 0.9.7 pass

- Native dock: bounded RAM-only hover previews, tooltips, running indicators, restore and right-click actions. Isolated i3 hover focus checks passed.
- Responsive wide/compact/small panel layouts and bounded music title length. Hidden top-bar shortcuts remain accessible in native windows, dock menus and Control Center.
- AI elapsed request/model-start phase and physical/cgroup-aware RAM badge; timer only during activity. GTK low-RAM fixture checks passed; no inference claimed.
- Backend: bounded endpoint readiness, one-sort index merge (10,004 fixture rows in about 35 ms), signed index checks and source-only manifests. Generated public/bytecode/egg-info outputs no longer alone mark source dirty.
- Native PDF SHMEM/tmpfs/sysctl resolved; standalone/nofork BusyBox and RAM-backed temporary mounts added. Boot/input/version/actual tmpfs mount passed; 140-field PDF structure reopened and static layout inspected. Package-sync timeout remains; interactive viewer check blocked by browser file-URL policy.
- Core code/PDF pass committed as fc3e8dc and pushed to GitHub/GitLab. Signed local generation published; WSL core upgrade/health check and ISO preflight passed. GitLab pipeline 2908742342 build jobs passed; Pages activation still pending at final check (public endpoint still served 0.9.6).
- Hardware regression checklist added. Private signing key stays local; enrollment/CI signing deferred.

## Completed foundation in core 0.9.6

- Cursor increased to **110% of previous size**, preserving original shape and hotspot proportions: personal 19 -> 21 px; public 17 -> 19 px. Actual Xcursor frames regenerated; WSL personal theme updated. Preserved native Windows frames were used, not a stretched enlargement of the previous small frame.
- Nineteen matching native SVG icons added to application entries and window headers; WSL icon cache refreshed.
- Missing BusyBox `find` link repaired in WSL/scratch base. OpenSSL included in core dependencies/cloud profiles so target clients can verify signed repository updates; failed package verification now propagates cleanly.
- Third-party titlebar close/minimize/fullscreen buttons added with focus-neutral, event-driven positioning. Isolated i3/xterm interaction checks passed.
- Installed boot now hands off to BusyBox init/getty instead of the legacy root shell. Diskless QEMU test rejected wrong password, accepted fixture password, and entered desktop launcher as UID 1000. Physical Xorg login remains untested.
- OpenVINO Chat 0.2.1: complete Linux x86_64/Python 3.12 wheel lock with hashes, pinned Ubuntu runtime image/checksum and dated APT snapshot. Fresh full-app imports and snapshot dependency resolution passed; no model inference performed.
- Native RISC-V64 Linux 6.18.37 / BusyBox 1.37.0 PDF regenerated. TinyEMU boot, keyboard input, arithmetic and core 0.9.6 version checks passed. Full package-sync check remains too slow to pass its timeout. Emulator-only RV64 clock scaling makes guest time 16x slower; not an x86 desktop/kernel change.

## Remaining gates

- Physical USB boot: BIOS/UEFI/GRUB, persistence, unrelated-drive protection and installer swap. New ISO build and real installed nonroot Xorg login. User performs ISO build.
- Existing saved USB overlays require verified offline backup and explicit data-only migration before using a rebuilt ISO; backup before flashing, because imaging can erase the persistence partition. No automatic legacy-overlay conversion or power-loss durability guarantee.
- Physical hardware checks: Wi-Fi, Bluetooth, audio routing (without playback), available RAM/zram, CPU/GPU/fans and disk/network counters. WSL/import/UI tests do not prove these.
- Real OpenVINO model loading/inference and CPU/GPU memory guards on hardware; fresh ISO dock/window/cursor/panel interaction check.
- CI signing and trusted client enrollment deferred by user's choice: private key stays local; no CI secret uploaded. Public CI/Pages deployment is distinct from Git pushes and local signed publication.
- Chromium PDF-viewer interaction verification for this native build; native package sync now passed.
- Actual WSLg accelerated rendering: GTK 3 X11/keyboard readiness passed, but Mesa reported acceleration warnings; no forced graphics backend or global software-rendering override applied.
- Optional storage review: WSL QA environments remain review-only. Disposable cleanup completed above; historical PDFs/previews, models, keys, releases and useful build caches remain intentionally preserved.

## Commands

User-owned ISO build, from PowerShell:

```powershell
& 'F:\Ooonana\ooonana-os\Build-ISO.ps1' --repo '/mnt/winf/Ooonana/ooonana-os/build/full-i3-repo-0.10'
```

Do not launch another copy while the current build runs. Shipped runtime/package
changes require a fresh normal build; documentation-only updates do not.
Do not use `--resume-after-iso` or
`--resume-after-rootfs` against the old October 5 staging. Back up persistent USB
data before flashing; existing production/staged ISOs do not contain these repairs.

Ooonana WSL desktop, from PowerShell:

```powershell
wsl -d Ooonana -u ooonana --exec start-ooonana-i3
```

## Verified foundation

Private local signing key generated; public trust key bundled. Atomic generation publication/cache, configuration preservation, health-check rollback, update policy/reboot reporting, memory preflight, actual zram reporting, event-driven dock/music, Health/Updates apps, native AI chat polish, WSL XDG handoff and unprivileged query-cache fixes passed scoped tests. Working PDF boots and accepts input. Latest desktop screenshot was captured from real nested WSL i3 without sound playback.

After reboot: local generation signature verified; Windows CRLF pointer compatibility fixed and regression-tested. Release preflight checks source/build inputs only, not fresh ISO boot or physical hardware functionality.
