#!/usr/bin/env python3
"""Read-only UUID fallback fixtures; no mount, real disk, or release build."""
import os
from pathlib import Path
import subprocess
import tempfile

helper = Path(__file__).resolve().parents[1] / "scripts/lib/live-boot-storage.sh"
expected = "2026-10-05-08-41-14-00"
script = '''
. "$1"
blkid_value() {
  case "$1" in
    TYPE) printf '%s\\n' "$FIXTURE_TYPE" ;;
    UUID) [ -n "$FIXTURE_UUID" ] && printf '%s\\n' "$FIXTURE_UUID" ;;
    *) return 1 ;;
  esac
}
live_uuid_matches "$3" "$2"
'''

def descriptor(kind=1, version=1, magic=b"CD001", date=b"2026100508411400"):
    data = bytearray(2048)
    data[:7] = bytes([kind]) + magic + bytes([version])
    data[813:829] = date
    return bytes(data)

with tempfile.TemporaryDirectory(prefix="ooonana-iso-uuid-") as directory:
    path = Path(directory) / "fixture.iso"
    before = b"\0" * (16 * 2048)
    fixtures = [
        ("primary", before + descriptor(), True),
        ("boot-then-primary", before + descriptor(kind=0) + descriptor(), True),
        ("nonzero-zone", before + descriptor()[:829] + b"\x24" + descriptor()[830:], True),
        ("wrong-magic", before + descriptor(magic=b"CD002"), False),
        ("wrong-version", before + descriptor(version=2), False),
        ("terminator", before + descriptor(kind=255) + descriptor(), False),
        ("bounded", before + descriptor(kind=0) * 16 + descriptor(), False),
        ("short", before + descriptor()[:820], False),
        ("blank-date", before + descriptor(date=b"0000000000000000"), False),
        ("spaces", before + descriptor(date=b"                "), False),
        ("nondigit", before + descriptor(date=b"20261005084114xx"), False),
        ("nul-date", before + descriptor(date=b"\0" * 16), False),
    ]
    def check(data, wanted, fs="iso9660", uuid="", match=expected):
        path.write_bytes(data)
        result = subprocess.run(
            ["sh", "-eu", "-c", script, "fixture", str(helper), str(path), match],
            env={**os.environ, "FIXTURE_TYPE": fs, "FIXTURE_UUID": uuid},
            capture_output=True, timeout=10,
        )
        assert (result.returncode == 0) == wanted, result.stderr.decode(errors="replace")
        assert path.read_bytes() == data, "UUID probe modified boot media"
    for name, data, wanted in fixtures:
        try:
            check(data, wanted)
        except AssertionError as error:
            raise AssertionError(name) from error
    check(before + descriptor(), False, fs="ext4")
    check(before + descriptor(), False, match="2026-10-05-08-41-15-00")
    check(before + descriptor(), False, uuid="different-uuid")
    check(b"native UUID needs no descriptor", True, fs="ext4", uuid=expected)
    path.write_bytes(before + descriptor())
    clone = path.with_name("clone.iso")
    clone.write_bytes(path.read_bytes())
    clone_script = script.replace('live_uuid_matches "$3" "$2"', '''
boot_media_candidate() { return 0; }
parent_disk_name() { case "$1" in */clone.iso) echo second ;; *) echo first ;; esac; }
live_boot_parent_for_uuid "$3" "$2" "$4"
''')
    result = subprocess.run(
        ["sh", "-eu", "-c", clone_script, "fixture", str(helper), str(path), expected, str(clone)],
        env={**os.environ, "FIXTURE_TYPE": "iso9660", "FIXTURE_UUID": ""},
        capture_output=True, timeout=10,
    )
    assert result.returncode == 2, "Cloned ISO UUID on separate parents was accepted"
    assert path.read_bytes() == clone.read_bytes() == before + descriptor()

print("ok iso-boot-uuid: bounded read-only ISO fallback, malformed/cloned refusal, native UUID precedence")
