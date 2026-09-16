from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil

import pandas as pd


# ============================================================
# PROJECT / RELEASE PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_DATA_DIR = (
    PROJECT_ROOT
    / "03_data"
)

INVENTORY_DIR = (
    SOURCE_DATA_DIR
    / "inventory"
)

PROCESSED_SOURCE_DIR = (
    SOURCE_DATA_DIR
    / "processed"
)

ANALYTICAL_VIEW_SOURCE_DIR = (
    SOURCE_DATA_DIR
    / "analytics"
    / "metric_views"
)

QA_CONFIG_SOURCE_DIR = (
    INVENTORY_DIR
    / "question_answering"
)


DATA_VERSION = "wave5_v1"
METRIC_VERSION = "1.0.0"

RELEASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "releases"
    / DATA_VERSION
)

PROCESSED_RELEASE_DIR = (
    RELEASE_DIR
    / "processed"
)

VIEW_RELEASE_DIR = (
    RELEASE_DIR
    / "views"
)

ENTITY_RELEASE_DIR = (
    RELEASE_DIR
    / "entities"
)

METRIC_RELEASE_DIR = (
    RELEASE_DIR
    / "metrics"
)

METADATA_RELEASE_DIR = (
    RELEASE_DIR
    / "metadata"
)


for folder in [
    PROCESSED_RELEASE_DIR,
    VIEW_RELEASE_DIR,
    ENTITY_RELEASE_DIR,
    METRIC_RELEASE_DIR,
    METADATA_RELEASE_DIR,
]:
    folder.mkdir(
        parents=True,
        exist_ok=True
    )


# ============================================================
# HELPERS
# ============================================================

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def find_file(
    root: Path,
    filename: str
) -> Path:

    matches = list(
        root.rglob(filename)
    )

    if len(matches) == 0:
        raise FileNotFoundError(
            f"Could not locate {filename} under {root}"
        )

    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple files found for {filename}: {matches}"
        )

    return matches[0]


def publish_csv_as_parquet(
    source_path: Path,
    target_path: Path
) -> dict:

    dataframe = pd.read_csv(
        source_path,
        low_memory=False
    )

    dataframe.to_parquet(
        target_path,
        index=False,
        engine="pyarrow"
    )

    reloaded = pd.read_parquet(
        target_path,
        engine="pyarrow"
    )

    if dataframe.shape != reloaded.shape:
        raise RuntimeError(
            f"Shape mismatch after Parquet publish: "
            f"{source_path.name}"
        )

    return {
        "rows": dataframe.shape[0],
        "columns": dataframe.shape[1],
        "source_file": source_path.name,
        "published_file": target_path.name,
    }


def copy_metadata_file(
    source_path: Path,
    target_dir: Path
) -> Path:

    target_path = (
        target_dir
        / source_path.name
    )

    shutil.copy2(
        source_path,
        target_path
    )

    return target_path


# ============================================================
# LOAD MANIFESTS
# ============================================================

processed_manifest = pd.read_csv(
    INVENTORY_DIR
    / "processed_data_manifest.csv"
)

analytical_view_manifest = pd.read_csv(
    INVENTORY_DIR
    / "analytical_view_manifest.csv"
)


# ============================================================
# 1. PUBLISH 10 PROCESSED TABLES
# ============================================================

processed_publish_records = []

for row in processed_manifest.itertuples():

    source_path = find_file(
        PROCESSED_SOURCE_DIR,
        row.data_file
    )

    target_path = (
        PROCESSED_RELEASE_DIR
        / f"{row.table_name}.parquet"
    )

    publish_info = (
        publish_csv_as_parquet(
            source_path,
            target_path
        )
    )

    publish_info.update({
        "table_name":
            row.table_name,

        "expected_rows":
            int(row.rows),

        "row_count_valid":
            publish_info["rows"]
            == int(row.rows)
    })

    processed_publish_records.append(
        publish_info
    )


processed_release_manifest = pd.DataFrame(
    processed_publish_records
)


# ============================================================
# 2. PUBLISH 7 ANALYTICAL VIEWS
# ============================================================

view_publish_records = []

for row in analytical_view_manifest.itertuples():

    source_path = (
        ANALYTICAL_VIEW_SOURCE_DIR
        / row.file_name
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Analytical view source missing: {source_path}"
        )

    target_path = (
        VIEW_RELEASE_DIR
        / f"{row.view_name}.parquet"
    )

    publish_info = (
        publish_csv_as_parquet(
            source_path,
            target_path
        )
    )

    publish_info.update({
        "view_name":
            row.view_name,

        "expected_rows":
            int(row.rows),

        "row_count_valid":
            publish_info["rows"]
            == int(row.rows)
    })

    view_publish_records.append(
        publish_info
    )


view_release_manifest = pd.DataFrame(
    view_publish_records
)


# ============================================================
# 3. PUBLISH ENTITY CATALOGS
# ============================================================

entity_files = {
    "state_entity_catalog.csv":
        "state_entity_catalog.parquet",

    "zone_entity_catalog.csv":
        "zone_entity_catalog.parquet",

    "crop_entity_catalog.csv":
        "crop_entity_catalog.parquet",

    "item_entity_catalog.csv":
        "item_entity_catalog.parquet",

    "climate_event_catalog.csv":
        "climate_event_catalog.parquet",
}


entity_publish_records = []

for source_name, target_name in (
    entity_files.items()
):

    source_path = (
        QA_CONFIG_SOURCE_DIR
        / source_name
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Entity catalog missing: {source_path}"
        )

    target_path = (
        ENTITY_RELEASE_DIR
        / target_name
    )

    publish_info = (
        publish_csv_as_parquet(
            source_path,
            target_path
        )
    )

    publish_info.update({
        "entity_catalog":
            source_name
    })

    entity_publish_records.append(
        publish_info
    )


entity_release_manifest = pd.DataFrame(
    entity_publish_records
)


# ============================================================
# 4. PUBLISH METRIC CONFIGURATION
# ============================================================

metric_files = [
    "analytical_metric_catalog.csv",
    "analytical_metric_registry.csv",
    "analytical_answer_policy.csv",
]


metric_publish_records = []

for filename in metric_files:

    source_path = (
        INVENTORY_DIR
        / filename
    )

    target_path = (
        METRIC_RELEASE_DIR
        / filename.replace(
            ".csv",
            ".parquet"
        )
    )

    publish_info = (
        publish_csv_as_parquet(
            source_path,
            target_path
        )
    )

    publish_info.update({
        "metric_artifact":
            filename
    })

    metric_publish_records.append(
        publish_info
    )


metric_release_manifest = pd.DataFrame(
    metric_publish_records
)


# ============================================================
# 5. COPY METADATA / METHODOLOGY ARTIFACTS
# ============================================================

metadata_files = [
    "processed_data_manifest.csv",
    "processed_relationship_map.csv",
    "analytical_view_manifest.csv",
    "context_coverage_summary.csv",
    "community_cluster_crosswalk_wave5.csv",
    "question_spec_schema.csv",
    "03_data_preparation_closeout.csv",
    "04_analytical_metrics_closeout.csv",
    "05_question_answering_layer_closeout.csv",
    "06_application_architecture_closeout.csv",
]


copied_metadata_paths = []

for filename in metadata_files:

    source_path = (
        INVENTORY_DIR
        / filename
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"Metadata artifact missing: {source_path}"
        )

    copied_metadata_paths.append(
        copy_metadata_file(
            source_path,
            METADATA_RELEASE_DIR
        )
    )


# Copy question-answering regression artifacts
for filename in [
    "question_answering_regression_cases.json",
    "question_answering_regression_results.csv",
]:

    source_path = (
        QA_CONFIG_SOURCE_DIR
        / filename
    )

    if not source_path.exists():
        raise FileNotFoundError(
            f"QA artifact missing: {source_path}"
        )

    copied_metadata_paths.append(
        copy_metadata_file(
            source_path,
            METADATA_RELEASE_DIR
        )
    )


# ============================================================
# 6. RELEASE QA
# ============================================================

qa_results = {
    "data_version":
        DATA_VERSION,

    "metric_version":
        METRIC_VERSION,

    "processed_tables_expected":
        10,

    "processed_tables_published":
        len(
            processed_release_manifest
        ),

    "processed_row_counts_valid":
        bool(
            processed_release_manifest[
                "row_count_valid"
            ].all()
        ),

    "analytical_views_expected":
        7,

    "analytical_views_published":
        len(
            view_release_manifest
        ),

    "view_row_counts_valid":
        bool(
            view_release_manifest[
                "row_count_valid"
            ].all()
        ),

    "entity_catalogs_expected":
        5,

    "entity_catalogs_published":
        len(
            entity_release_manifest
        ),

    "metric_artifacts_expected":
        3,

    "metric_artifacts_published":
        len(
            metric_release_manifest
        ),
}


qa_results[
    "release_content_valid"
] = bool(
    qa_results[
        "processed_tables_published"
    ] == 10
    and
    qa_results[
        "processed_row_counts_valid"
    ]
    and
    qa_results[
        "analytical_views_published"
    ] == 7
    and
    qa_results[
        "view_row_counts_valid"
    ]
    and
    qa_results[
        "entity_catalogs_published"
    ] == 5
    and
    qa_results[
        "metric_artifacts_published"
    ] == 3
)


qa_results_path = (
    RELEASE_DIR
    / "qa_results.json"
)

with qa_results_path.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        qa_results,
        file,
        indent=2
    )


# ============================================================
# 7. RELEASE MANIFEST
# ============================================================

release_manifest = {
    "project":
        "AgDA",

    "data_version":
        DATA_VERSION,

    "survey_wave":
        "Wave 5",

    "release_state":
        "candidate",

    "created_at_utc":
        datetime.now(
            timezone.utc
        ).isoformat(),

    "storage_format":
        "parquet",

    "query_engine":
        "duckdb",

    "metric_version":
        METRIC_VERSION,

    "processed_table_count":
        len(
            processed_release_manifest
        ),

    "analytical_view_count":
        len(
            view_release_manifest
        ),

    "entity_catalog_count":
        len(
            entity_release_manifest
        ),

    "metric_artifact_count":
        len(
            metric_release_manifest
        ),

    "release_content_valid":
        qa_results[
            "release_content_valid"
        ],

    "application_default":
        False,
}


release_manifest_path = (
    RELEASE_DIR
    / "release_manifest.json"
)

with release_manifest_path.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        release_manifest,
        file,
        indent=2
    )


# ============================================================
# 8. CHECKSUMS
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


checksums = pd.DataFrame(
    checksum_records
)

checksums.to_csv(
    RELEASE_DIR
    / "checksums.csv",
    index=False
)


# ============================================================
# 9. FINAL OUTPUT
# ============================================================

print(
    "\n========================================"
)

print(
    f"AgDA RELEASE: {DATA_VERSION}"
)

print(
    "========================================"
)

print(
    "Processed tables:",
    len(
        processed_release_manifest
    )
)

print(
    "Analytical views:",
    len(
        view_release_manifest
    )
)

print(
    "Entity catalogs:",
    len(
        entity_release_manifest
    )
)

print(
    "Metric artifacts:",
    len(
        metric_release_manifest
    )
)

print(
    "Files checksummed:",
    len(
        checksums
    )
)

print(
    "Release content valid:",
    qa_results[
        "release_content_valid"
    ]
)

print(
    "Release state:",
    release_manifest[
        "release_state"
    ]
)

print(
    "\nRelease directory:"
)

print(
    RELEASE_DIR
)