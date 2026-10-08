#!/usr/bin/env python3
"""Keep manifest tooling dependencies inside the deploy image, not runner helper."""
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
source = (root / ".gitlab-ci.yml").read_text()
deploy = source.split("\ndeploy-package-repo:\n", 1)[1]
bootstrap = deploy.split("\n  script:\n", 1)[0]
installed = set(re.search(r"apk add --no-cache ([^\n]+)", bootstrap)[1].split())
assert {"git", "python3", "openssl", "bash"} <= installed
assert "git rev-parse --verify HEAD" in bootstrap
assert source.index("git rev-parse --verify HEAD") < source.index("bash scripts/build-package-repo.sh")
assert "publish-repo-generation.py" in deploy
smoke = source.split("\nci-smoke:\n", 1)[1].split("\ndeploy-package-repo:\n", 1)[0]
if "test-pdf-runtime-reuse.py" in smoke:
    smoke_packages = set(re.search(r"apk add --no-cache ([^\n]+)", smoke)[1].split())
    assert "findutils" in smoke_packages, "PDF runtime injection needs GNU find -printf"
if "test-cli-query-fast.py" in smoke:
    smoke_packages = set(re.search(r"apk add --no-cache ([^\n]+)", smoke)[1].split())
    assert "openssl" in smoke_packages, "Signed query fixtures require OpenSSL CLI"
print("ok gitlab-ci dependencies and atomic publication")
