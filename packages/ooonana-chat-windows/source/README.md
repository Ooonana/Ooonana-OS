# OoonanaChat Windows source

`OoonanaChat Setup 1.0.0.exe` is intentionally ignored by Git.

Build the optional local package with:

```sh
OOONANA_OONANA_CHAT_WINDOWS_SOURCE='/path/OoonanaChat Setup 1.0.0.exe' \
  bash scripts/build-ooonana-chat-windows-package.sh --out-dir /path/to/repo
```

The package launches through `ooonana wine`. It is a Windows compatibility
path, not a native Linux port.
