#!/usr/bin/env python3
"""Cold builtin queries retain checksum/signature/version and source behavior."""
import hashlib
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

root = Path(__file__).resolve().parents[1]
cli = root / "packages/ooonana/usr/bin/ooonana"
spec = importlib.util.spec_from_file_location("indexer", root / "scripts/index-repo-fast.py")
indexer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(indexer)

with tempfile.TemporaryDirectory(prefix="ooonana-query-") as temporary:
    work = Path(temporary)
    repo, state, sources, cache = (work / name for name in ("repo", "state", "sources", "cache"))
    for directory in (repo, state / "installed", sources, cache):
        directory.mkdir(parents=True)
    for ident, version in (("alpha", "1.2"), ("beta", "2.0")):
        (repo / f"{ident}.pkg").write_text(
            f'OOONANA_PKG_ID="{ident}"\nOOONANA_PKG_VERSION="{version}"\n'
            f'OOONANA_PKG_SUMMARY="{ident} fixture"\nOOONANA_PKG_KIND="bundle"\n'
        )
    (state / "installed/alpha.pkg").write_bytes((repo / "alpha.pkg").read_bytes())
    env = dict(os.environ, OOONANA_ROOT=str(work / "target"), OOONANA_REPO_DIR=str(repo),
               OOONANA_STATE_DIR=str(state), OOONANA_SOURCES_DIR=str(sources),
               OOONANA_CACHE_DIR=str(cache), TMPDIR=str(work))

    def query(*args, error=None):
        result = subprocess.run(["sh", str(cli), *args], env=env, capture_output=True, text=True)
        if error:
            assert result.returncode != 0 and error in result.stderr, result
        else:
            assert result.returncode == 0, result.stderr
        return result.stdout

    indexer.index(repo)
    cold = query("list")
    assert [line.split(None, 3) for line in cold.splitlines()] == [
        ["alpha", "1.2", "installed", "alpha fixture"],
        ["beta", "2.0", "available", "beta fixture"],
    ], repr(cold)
    assert not (cache / "index.tsv").exists(), "Read-only list warmed shared index"
    assert not list(work.glob("ooonana-checksums.*")), "Per-query cache leaked"

    original = (repo / "beta.pkg").read_bytes()
    (repo / "beta.pkg").write_bytes(original + b"# tampered\n")
    query("list", error="metadata checksum mismatch")
    (repo / "beta.pkg").write_bytes(original)
    original_sums = (repo / "SHA256SUMS").read_bytes()
    (repo / "SHA256SUMS").write_bytes(original_sums.replace(b"\n", b"\r\n"))
    assert query("list") == cold, "CRLF checksum manifest unsupported"
    (repo / "SHA256SUMS").write_bytes(b"")
    query("list", error="missing checksum: alpha.pkg")
    (repo / "SHA256SUMS").unlink()
    assert query("list") == cold, "Legacy unsigned metadata unsupported"
    (repo / "SHA256SUMS").write_bytes(original_sums)
    original_index = (repo / "index.tsv").read_bytes()
    (repo / "index.tsv").write_bytes(original_index + b"# tampered\n")
    query("list", error="metadata checksum mismatch")
    (repo / "index.tsv").write_bytes(original_index.replace(b"beta\t2.0", b"beta\t9.0"))
    sums = (repo / "SHA256SUMS").read_text().splitlines()
    digest = hashlib.sha256((repo / "index.tsv").read_bytes()).hexdigest()
    (repo / "SHA256SUMS").write_text("\n".join(
        f"{digest}  index.tsv" if line.endswith("  index.tsv") else line for line in sums
    ) + "\n")
    query("list", error="repo index version mismatch: beta")

    key, public = work / "fixture.pem", work / "fixture.pub"
    subprocess.run(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                    "-out", str(key)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    indexer.index(repo, key)
    public.write_bytes((repo / "repo.pub").read_bytes())
    env["OOONANA_BUILTIN_REPO_KEY"] = str(public)
    env["OOONANA_REQUIRE_SIGNED_REPOS"] = "1"
    assert query("list") == cold
    env.pop("OOONANA_BUILTIN_REPO_KEY")
    env["OOONANA_TRUST_REPO_EMBEDDED_KEY"] = "1"
    assert query("list") == cold, "Explicit embedded-key trust lost"
    env.pop("OOONANA_TRUST_REPO_EMBEDDED_KEY")
    env["OOONANA_BUILTIN_REPO_KEY"] = str(public)
    (repo / "SHA256SUMS.sig").write_bytes(b"broken signature")
    query("list", error="repo signature mismatch")
    indexer.index(repo, key)

    # External sources still use normal highest-version selection.
    other = work / "other"
    other.mkdir()
    (other / "beta.pkg").write_text((repo / "beta.pkg").read_text().replace('"2.0"', '"3.0"'))
    indexer.index(other, key)
    (sources / "extra.repo").write_text(
        f'OOONANA_REPO_NAME="extra"\nOOONANA_REPO_URI="{other}"\nOOONANA_REPO_KEY="{public}"\n'
    )
    assert "3.0" in query("list")
    query("update")
    assert "3.0" in query("list")
    assert not list(work.glob("ooonana-checksums.*"))

    # A predictable pre-created PID symlink must neither receive metadata nor
    # be removed by cleanup. This wrapper execs the CLI with the same PID.
    victim = work / "unrelated"
    victim.mkdir(mode=0o755)
    victim.joinpath("keep").write_text("user data")
    attack = work / "pid-symlink"
    result = subprocess.run(["sh", "-c", '''
printf '%s\\n' "${TMPDIR}/ooonana-checksums.$$" >"$2"
ln -s "$3" "${TMPDIR}/ooonana-checksums.$$"
exec sh "$1" list
''', "sh", str(cli), str(attack), str(victim)], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert [entry.name for entry in victim.iterdir()] == ["keep"], "Query followed pre-existing cache symlink"
    assert victim.stat().st_mode & 0o777 == 0o755
    assert victim.joinpath("keep").read_text() == "user data"
    assert Path(attack.read_text().strip()).is_symlink(), "Cleanup removed unrelated pre-existing entry"
    failed = subprocess.run(["sh", str(cli), "list"], env=dict(env, TMPDIR=str(work / "absent")),
                            capture_output=True, text=True)
    assert failed.returncode != 0 and "cannot create private query cache" in failed.stderr

    # Privilege handoff execs out of the caller. Allocate only afterwards, so
    # exec does not leak a directory whose EXIT trap never gets to run.
    helpers, admin_tmp = work / "helpers", work / "admin-tmp"
    helpers.mkdir()
    admin_tmp.mkdir()
    for name, contents in (("id", "#!/bin/sh\nprintf '1000\\n'\n"),
                           ("ooonana-run-admin", "#!/bin/sh\nprintf 'handoff' >\"$ADMIN_TRACE\"\n")):
        helpers.joinpath(name).write_text(contents)
        helpers.joinpath(name).chmod(0o755)
    result = subprocess.run(["sh", str(cli), "upgrade"],
        env=dict(env, OOONANA_ROOT="/", PATH=str(helpers) + ":" + env["PATH"],
                 TMPDIR=str(admin_tmp), ADMIN_TRACE=str(work / "admin-trace")), capture_output=True, text=True)
    assert result.returncode == 0 and work.joinpath("admin-trace").read_text() == "handoff", result.stderr
    assert not list(admin_tmp.iterdir()), "Cache allocated before privilege exec"

print("ok cli-query-fast: cold/warm/external queries; checksum/signature/version refusal; cleanup")
