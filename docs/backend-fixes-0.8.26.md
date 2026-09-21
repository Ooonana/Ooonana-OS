# Backend fixes in core 0.8.26

Wi-Fi fixes preserve SSID whitespace and Unicode identity through scan parsing,
grouping, hidden-network entry and profile naming. Wi-Fi-only repair no longer
unblocks Bluetooth or cellular radios; Bluetooth-only repair leaves Wi-Fi alone.

PSK, WEP and enterprise passwords are passed to the privileged credential helper
through stdin, then saved using NetworkManager's D-Bus Update method. Profiles
retain system-owned secrets for reconnect. No password appears in process
arguments or a temporary activation file. The helper preserves D-Bus value types,
SSID bytes, IP configuration and non-secret security settings. It is intended for
the fresh profiles created by the Wi-Fi connection workflow.

API contract: [NetworkManager Settings.Connection](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Settings.Connection.html).

Other corrections:

- Package removal checks all installed dependents.
- Upgrades and dependency installation recheck package conflicts.
- Reinstall validates replacement before removing installed data.
- Upgrade/reinstall snapshots affected files and metadata, restoring them when
  extraction or installation fails. Hook side effects outside package-owned
  payload are not covered; power-loss/SIGKILL recovery is not implemented.
- Kernel dry runs preserve existing outputs; cache checks include kernel version.
- Live init mounts proc before reading custom rootfs command-line options.
- AI streaming accepts usage-only events and propagates generation errors.
- Audio startup and restart target processes belonging to current user.
- First-boot setup marks completion only after password setting succeeds.
- Packaged settings launcher now matches source guard.

Validation: 42 shell suites passed, including new backend regressions for the
nine audit failures, rollback after failed upgrade/reinstall hooks, radio scope,
audio ownership, setup completion ordering, and real GLib D-Bus variant encoding
against a simulated service. ShellCheck error-level checks passed for changed
runtime/build shell scripts. These tests do not establish hardware connectivity.

An additional WSL NetworkManager integration check saved a fixture password using
the actual helper, read it back from NetworkManager, verified exact spaced Unicode
SSID and disabled autoconnect, then deleted the temporary profile. No router
association or radio changes were requested.

Remaining release work: build a fresh ISO and run its QEMU verification; boot
physical USB and check Wi-Fi association/reconnect, Bluetooth/audio, install and
persistence. Actual OpenVINO model inference and external chat interoperability
remain hardware/runtime checks. Linux Wi-Fi Aware currently only reports NAN
capability; a working Linux NAN datapath requires additional implementation.
