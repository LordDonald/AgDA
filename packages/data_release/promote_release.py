from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd


# ============================================================
# PROJECT / RELEASE PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_VERSION = "wave5_v1"

RELEASES_DIR = (
    PROJECT_ROOT
    / "data"
    / "releases"
)

RELEASE_DIR = (
    RELEASES_DIR
    / DATA_VERSION
)

MANIFEST_PATH = (
    RELEASE_DIR
    / "release_manifest.json"
)

INDEPENDENT_VALIDATION_PATH = (
    RELEASE_DIR
    / "independent_validation.json"
)

CHECKSUM_PATH = (
    RELEASE_DIR
    / "checksums.csv"
)

PROMOTION_RECORD_PATH = (
    RELEASE_DIR
    / "promotion_record.json"
)

STABLE_POINTER_PATH = (
    RELEASES_DIR
    / "stable_release.json"
)


# ============================================================
# HELPERS
# ============================================================

def load_json(path: Path) -> dict:

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def write_json(
    path: Path,
    payload: dict
) -> None:

    with path.open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            payload,
            file,
            indent=2
        )


def sha256_file(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:

        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b""
        ):

            digest.update(chunk)

    return digest.hexdigest()


# ============================================================
# 1. PRE-PROMOTION VALIDATION
# ============================================================

if not RELEASE_DIR.exists():

    raise FileNotFoundError(
        f"Release does not exist: {RELEASE_DIR}"
    )


if not MANIFEST_PATH.exists():

    raise FileNotFoundError(
        f"Manifest missing: {MANIFEST_PATH}"
    )


if not INDEPENDENT_VALIDATION_PATH.exists():

    raise FileNotFoundError(
        "Independent validation must exist before promotion."
    )


manifest = load_json(
    MANIFEST_PATH
)

independent_validation = load_json(
    INDEPENDENT_VALIDATION_PATH
)


validation_summary = (
    independent_validation[
        "summary"
    ]
)


if manifest.get(
    "release_state"
) != "candidate":

    raise RuntimeError(
        "Only a candidate release may be promoted."
    )


if not validation_summary.get(
    "independent_validation_passed",
    False
):

    raise RuntimeError(
        "Independent validation did not pass. "
        "Release cannot be promoted."
    )


if manifest.get(
    "data_version"
) != DATA_VERSION:

    raise RuntimeError(
        "Manifest data version does not match "
        "the requested promotion version."
    )


print(
    "Pre-promotion validation: PASSED"
)


# ============================================================
# 2. UPDATE RELEASE MANIFEST
# ============================================================

promoted_at = (
    datetime.now(
        timezone.utc
    ).isoformat()
)


manifest[
    "release_state"
] = "stable"

manifest[
    "application_default"
] = True

manifest[
    "promoted_at_utc"
] = promoted_at

manifest[
    "promotion_validation"
] = "independent_validation_passed"


write_json(
    MANIFEST_PATH,
    manifest
)


# ============================================================
# 3. CREATE PROMOTION RECORD
# ============================================================

promotion_record = {
    "project":
        "AgDA",

    "data_version":
        DATA_VERSION,

    "previous_state":
        "candidate",

    "new_state":
        "stable",

    "promoted_at_utc":
        promoted_at,

    "independent_validation_file":
        "independent_validation.json",

    "independent_validation_passed":
        True,

    "application_default":
        True,
}


write_json(
    PROMOTION_RECORD_PATH,
    promotion_record
)


# ============================================================
# 4. REGENERATE FINAL STABLE CHECKSUMS
#
# checksums.csv is intentionally excluded from hashing itself.
# ============================================================

checksum_records = []


for path in sorted(
    RELEASE_DIR.rglob("*")
):

    if not path.is_file():
        continue

    if path.name == "checksums.csv":
        continue


    checksum_records.append({
        "relative_path":
            path.relative_to(
                RELEASE_DIR
            ).as_posix(),

        "sha256":
            sha256_file(
                path
            ),

        "size_bytes":
            path.stat().st_size
    })


final_checksums = pd.DataFrame(
    checksum_records
)


final_checksums.to_csv(
    CHECKSUM_PATH,
    index=False
)


# ============================================================
# 5. VERIFY FINAL CHECKSUMS
# ============================================================

verification_records = []


for row in (
    final_checksums.itertuples()
):

    path = (
        RELEASE_DIR
        / row.relative_path
    )

    actual_hash = sha256_file(
        path
    )

    verification_records.append({
        "relative_path":
            row.relative_path,

        "exists":
            path.exists(),

        "checksum_valid":
            actual_hash
            == row.sha256,

        "size_valid":
            path.stat().st_size
            == int(
                row.size_bytes
            )
    })


checksum_verification = pd.DataFrame(
    verification_records
)


final_checksums_valid = bool(
    (
        checksum_verification[
            "exists"
        ]
        &
        checksum_verification[
            "checksum_valid"
        ]
        &
        checksum_verification[
            "size_valid"
        ]
    ).all()
)


if not final_checksums_valid:

    raise RuntimeError(
        "Final stable checksum verification failed."
    )


# ============================================================
# 6. CREATE STABLE-RELEASE POINTER
# ============================================================

stable_pointer = {
    "project":
        "AgDA",

    "data_version":
        DATA_VERSION,

    "release_state":
        "stable",

    "release_path":
        f"data/releases/{DATA_VERSION}",

    "metric_version":
        manifest.get(
            "metric_version"
        ),

    "promoted_at_utc":
        promoted_at,
}


write_json(
    STABLE_POINTER_PATH,
    stable_pointer
)


# ============================================================
# 7. FINAL PROMOTION VALIDATION
# ============================================================

final_manifest = load_json(
    MANIFEST_PATH
)


promotion_valid = bool(
    final_manifest.get(
        "release_state"
    ) == "stable"

    and

    final_manifest.get(
        "application_default"
    ) is True

    and

    final_checksums_valid

    and

    STABLE_POINTER_PATH.exists()
)


if not promotion_valid:

    raise RuntimeError(
        "Release promotion final validation failed."
    )


# ============================================================
# 8. OUTPUT
# ============================================================

print(
    "\n========================================"
)

print(
    f"AgDA RELEASE PROMOTION: {DATA_VERSION}"
)

print(
    "========================================"
)

print(
    "Release state:",
    final_manifest[
        "release_state"
    ]
)

print(
    "Application default:",
    final_manifest[
        "application_default"
    ]
)

print(
    "Independent validation:",
    validation_summary[
        "independent_validation_passed"
    ]
)

print(
    "Final files checksummed:",
    len(
        final_checksums
    )
)

print(
    "Final checksums valid:",
    final_checksums_valid
)

print(
    "Stable pointer created:",
    STABLE_POINTER_PATH.exists()
)

print(
    "Promotion valid:",
    promotion_valid
)

print(
    "\nStable release pointer:"
)

print(
    STABLE_POINTER_PATH
)