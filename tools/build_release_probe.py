"""Build a standalone source-identity probe from an exact clean release checkout.

The manifest hashes actual checkout bytes, preserving the checkout's intentional
Git newline handling. Generated probes use only Python or Node standard libraries.
Write its output outside the release checkout, then execute it from the deployed
API root (or deployed web root for --scope web).
"""

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


class ProbeBuildError(Exception):
    """A controlled error that never includes file contents or command output."""


def require(condition, message):
    if not condition:
        raise ProbeBuildError(message)


def git(checkout, *arguments):
    result = subprocess.run(["git", "-C", str(checkout), *arguments],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    require(result.returncode == 0, "Git could not verify the release checkout.")
    return result.stdout


def verify_checkout(checkout, revision):
    require(git(checkout, "rev-parse", "HEAD").decode().strip() == revision,
            "Release checkout HEAD does not match the required revision.")
    require(not git(checkout, "status", "--porcelain", "--untracked-files=all").strip(),
            "Release checkout must be clean, including untracked files.")
    # Git status may hide local edits behind assume-unchanged/skip-worktree flags.
    entries = git(checkout, "ls-files", "-v", "-z").split(b"\0")
    require(all(entry.startswith(b"H ") for entry in entries if entry),
            "Release checkout must not hide tracked changes with index flags.")


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def is_within(path, parent):
    return path == parent or parent in path.parents


def build_probe(checkout, revision, output, scope="api", language="python"):
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)), "A full lowercase 40-character Git revision is required.")
    require(scope in ("api", "web"), "Scope must be api or web.")
    require(language in ("python", "node"), "Language must be python or node.")
    checkout = Path(checkout).resolve()
    output = Path(output).resolve()
    require(checkout.is_dir(), "Release checkout directory is missing.")
    root = Path(git(checkout, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    require(checkout == root, "Checkout must name the repository root.")
    require(not is_within(output, checkout), "Probe output must be outside the release checkout.")
    require(output.parent.is_dir(), "Probe output directory must already exist.")
    verify_checkout(checkout, revision)
    paths = git(checkout, "ls-files", "-z").decode("utf-8").split("\0")
    manifest = {}
    for relative in paths:
        if not relative:
            continue
        if scope == "web":
            if not relative.startswith("apps/web/"):
                continue
            deployed_path = relative[len("apps/web/"):]
        else:
            if not (relative.startswith(("packages/", "apps/api/", "data/releases/"))
                    or relative in ("pyproject.toml", "requirements.txt", "requirements-production.txt")):
                continue
            deployed_path = relative
        parts = PurePosixPath(deployed_path).parts
        require(parts and not PurePosixPath(deployed_path).is_absolute()
                and not any(part in (".", "..") for part in parts)
                and not any(ord(character) < 32 for character in deployed_path),
                "Tracked source paths must be safe relative paths.")
        path = checkout.joinpath(*PurePosixPath(relative).parts)
        require(path.is_file() and not path.is_symlink() and is_within(path.resolve(), checkout),
                "Tracked source must be a regular file within the checkout.")
        manifest[deployed_path] = digest(path)
    require(bool(manifest), "No tracked files matched the requested source scope.")
    # Detect normal working-tree changes while collecting the manifest.
    verify_checkout(checkout, revision)
    template = PROBE_SOURCE if language == "python" else NODE_PROBE_SOURCE
    literal = repr if language == "python" else json.dumps
    source = template.replace("@@REVISION@@", literal(revision)).replace("@@MANIFEST@@", literal(dict(sorted(manifest.items()))))
    output.write_text(source, encoding="utf-8", newline="\n")
    return len(manifest)


PROBE_SOURCE = '''"""Generated exact-release source verifier; no network or database access."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys

REVISION = @@REVISION@@
MANIFEST = @@MANIFEST@@


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError("Explicit target environment is required.")


def emit(environment, count, mismatches, *, status):
    print(json.dumps({"revision": REVISION, "environment": environment,
                      "file_count": count, "mismatch_paths": mismatches,
                      "status": status}, separators=(",", ":")), flush=True)


def main(argv=None):
    parser = SafeParser(description=__doc__)
    parser.add_argument("--expected-environment", required=True, choices=("staging", "production"))
    try:
        args = parser.parse_args(argv)
    except ValueError:
        emit(None, 0, [], status="environment_refused")
        return 2
    expected = args.expected_environment
    configured = [os.environ[name] for name in ("AGDA_ENV", "RAILWAY_ENVIRONMENT_NAME")
                  if os.environ.get(name)]
    if not configured or any(value != expected for value in configured):
        # Check environment before resolving cwd or reading any deployed source.
        emit(expected, 0, [], status="environment_refused")
        return 2
    root = Path.cwd().resolve()
    mismatches = []
    for relative, expected_hash in MANIFEST.items():
        path = root.joinpath(*PurePosixPath(relative).parts)
        try:
            resolved = path.resolve()
            if path.is_symlink() or not path.is_file() or root not in resolved.parents:
                mismatches.append(relative)
                continue
            with path.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != expected_hash:
                mismatches.append(relative)
        except (OSError, RuntimeError):
            mismatches.append(relative)
    emit(expected, len(MANIFEST), mismatches, status="failed" if mismatches else "passed")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
'''


NODE_PROBE_SOURCE = '''// Generated exact-release source verifier; no network or database access.
"use strict";
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const REVISION = @@REVISION@@;
const MANIFEST = @@MANIFEST@@;

function emit(environment, count, mismatches, status) {
    process.stdout.write(JSON.stringify({revision: REVISION, environment,
        file_count: count, mismatch_paths: mismatches, status}) + "\\n");
}

function main(argv) {
    // Supports `node - --expected-environment staging` when source arrives on stdin.
    if (argv.length !== 2 || argv[0] !== "--expected-environment" ||
        !["staging", "production"].includes(argv[1])) {
        emit(null, 0, [], "environment_refused");
        return 2;
    }
    const expected = argv[1];
    const configured = [process.env.AGDA_ENV, process.env.RAILWAY_ENVIRONMENT_NAME].filter(Boolean);
    if (!configured.length || configured.some(value => value !== expected)) {
        // Validate environment before resolving cwd or reading any deployed source.
        emit(expected, 0, [], "environment_refused");
        return 2;
    }
    const root = fs.realpathSync(process.cwd());
    const mismatches = [];
    for (const [relative, expectedHash] of Object.entries(MANIFEST)) {
        const filename = path.join(root, ...relative.split("/"));
        let descriptor;
        try {
            const resolved = fs.realpathSync(filename);
            const within = path.relative(root, resolved);
            if (!fs.lstatSync(filename).isFile() || !within || path.isAbsolute(within) ||
                within === ".." || within.startsWith(".." + path.sep)) {
                mismatches.push(relative);
                continue;
            }
            descriptor = fs.openSync(filename, "r");
            const hash = crypto.createHash("sha256");
            const buffer = Buffer.alloc(65536);
            let size;
            while ((size = fs.readSync(descriptor, buffer, 0, buffer.length, null)) > 0) {
                hash.update(buffer.subarray(0, size));
            }
            if (hash.digest("hex") !== expectedHash) mismatches.push(relative);
        } catch {
            mismatches.push(relative);
        } finally {
            if (descriptor !== undefined) fs.closeSync(descriptor);
        }
    }
    emit(expected, Object.keys(MANIFEST).length, mismatches, mismatches.length ? "failed" : "passed");
    return mismatches.length ? 1 : 0;
}

process.exitCode = main(process.argv.slice(2));
'''


class SafeParser(argparse.ArgumentParser):
    def error(self, message):
        raise ProbeBuildError("Required arguments: --checkout, --revision, --output; optional --scope api or web and --language python or node.")


def main(argv=None):
    try:
        parser = SafeParser(description=__doc__)
        parser.add_argument("--checkout", required=True, help="Exact clean release repository root.")
        parser.add_argument("--revision", required=True, help="Expected full lowercase Git SHA.")
        parser.add_argument("--output", required=True, help="Generated verifier path outside the source checkout.")
        parser.add_argument("--scope", choices=("api", "web"), default="api")
        parser.add_argument("--language", choices=("python", "node"), default="python")
        args = parser.parse_args(argv)
        count = build_probe(args.checkout, args.revision, args.output, args.scope, args.language)
    except ProbeBuildError as error:
        print(json.dumps({"status": "failed", "reason": str(error)}, separators=(",", ":")))
        return 1
    except Exception:
        print(json.dumps({"status": "failed", "reason": "Could not build source verifier."}, separators=(",", ":")))
        return 1
    print(json.dumps({"status": "built", "revision": args.revision, "scope": args.scope, "language": args.language,
                      "file_count": count}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
