from __future__ import annotations

from pathlib import Path
import hashlib
import json

import duckdb
import pandas as pd


# ============================================================
# RELEASE LOCATION
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_VERSION = "wave5_v1"

RELEASE_DIR = (
    PROJECT_ROOT
    / "data"
    / "releases"
    / DATA_VERSION
)

PROCESSED_DIR = (
    RELEASE_DIR
    / "processed"
)

VIEWS_DIR = (
    RELEASE_DIR
    / "views"
)

ENTITIES_DIR = (
    RELEASE_DIR
    / "entities"
)

METRICS_DIR = (
    RELEASE_DIR
    / "metrics"
)

METADATA_DIR = (
    RELEASE_DIR
    / "metadata"
)

MANIFEST_PATH = (
    RELEASE_DIR
    / "release_manifest.json"
)

QA_PATH = (
    RELEASE_DIR
    / "qa_results.json"
)

CHECKSUM_PATH = (
    RELEASE_DIR
    / "checksums.csv"
)


# ============================================================
# HELPERS
# ============================================================

def sha256_file(path: Path) -> str:

    digest = hashlib.sha256()

    with path.open("rb") as file:

        for chunk in iter(
            lambda: file.read(
                1024 * 1024
            ),
            b""
        ):

            digest.update(
                chunk
            )

    return digest.hexdigest()


def load_json(path: Path) -> dict:

    with path.open(
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(
            file
        )


# ============================================================
# 1. REQUIRED RELEASE FILES
# ============================================================

required_root_files = [
    MANIFEST_PATH,
    QA_PATH,
    CHECKSUM_PATH,
]

required_directories = [
    PROCESSED_DIR,
    VIEWS_DIR,
    ENTITIES_DIR,
    METRICS_DIR,
    METADATA_DIR,
]


root_files_exist = all(
    path.exists()
    for path in required_root_files
)

directories_exist = all(
    path.exists()
    and path.is_dir()
    for path in required_directories
)


# ============================================================
# 2. LOAD RELEASE CONTROL FILES
# ============================================================

manifest = load_json(
    MANIFEST_PATH
)

publisher_qa = load_json(
    QA_PATH
)

checksums = pd.read_csv(
    CHECKSUM_PATH
)


# ============================================================
# 3. VERIFY CHECKSUMS
# ============================================================

checksum_validation_records = []


for row in checksums.itertuples():

    path = (
        RELEASE_DIR
        / row.relative_path
    )

    exists = path.exists()

    actual_sha256 = (
        sha256_file(path)
        if exists
        else None
    )

    checksum_valid = (
        exists
        and actual_sha256
        == row.sha256
    )

    size_valid = (
        exists
        and path.stat().st_size
        == int(row.size_bytes)
    )


    checksum_validation_records.append({
        "relative_path":
            row.relative_path,

        "exists":
            exists,

        "checksum_valid":
            checksum_valid,

        "size_valid":
            size_valid
    })


checksum_validation = pd.DataFrame(
    checksum_validation_records
)


all_checksums_valid = bool(
    (
        checksum_validation[
            "exists"
        ]
        &
        checksum_validation[
            "checksum_valid"
        ]
        &
        checksum_validation[
            "size_valid"
        ]
    ).all()
)


# ============================================================
# 4. COUNT PUBLISHED PARQUET FILES
# ============================================================

processed_files = sorted(
    PROCESSED_DIR.glob(
        "*.parquet"
    )
)

view_files = sorted(
    VIEWS_DIR.glob(
        "*.parquet"
    )
)

entity_files = sorted(
    ENTITIES_DIR.glob(
        "*.parquet"
    )
)

metric_files = sorted(
    METRICS_DIR.glob(
        "*.parquet"
    )
)


# ============================================================
# 5. LOAD EXPECTED ROW COUNTS
# ============================================================

processed_manifest = pd.read_csv(
    METADATA_DIR
    / "processed_data_manifest.csv"
)

view_manifest = pd.read_csv(
    METADATA_DIR
    / "analytical_view_manifest.csv"
)


expected_processed_rows = {
    row.table_name:
        int(row.rows)

    for row
    in processed_manifest.itertuples()
}


expected_view_rows = {
    row.view_name:
        int(row.rows)

    for row
    in view_manifest.itertuples()
}


# ============================================================
# 6. DUCKDB READABILITY + ROW COUNT VALIDATION
# ============================================================

connection = duckdb.connect(
    database=":memory:"
)


parquet_validation_records = []


# ------------------------------------------------------------
# Processed tables
# ------------------------------------------------------------

for path in processed_files:

    table_name = (
        path.stem
    )

    row_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        """,
        [str(path)]
    ).fetchone()[0]


    expected_rows = (
        expected_processed_rows.get(
            table_name
        )
    )


    parquet_validation_records.append({
        "artifact_type":
            "processed",

        "name":
            table_name,

        "rows":
            row_count,

        "expected_rows":
            expected_rows,

        "row_count_valid":
            (
                expected_rows is not None
                and row_count
                == expected_rows
            ),

        "duckdb_readable":
            True
    })


# ------------------------------------------------------------
# Analytical views
# ------------------------------------------------------------

for path in view_files:

    view_name = (
        path.stem
    )

    row_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        """,
        [str(path)]
    ).fetchone()[0]


    expected_rows = (
        expected_view_rows.get(
            view_name
        )
    )


    parquet_validation_records.append({
        "artifact_type":
            "view",

        "name":
            view_name,

        "rows":
            row_count,

        "expected_rows":
            expected_rows,

        "row_count_valid":
            (
                expected_rows is not None
                and row_count
                == expected_rows
            ),

        "duckdb_readable":
            True
    })


parquet_validation = pd.DataFrame(
    parquet_validation_records
)


# ============================================================
# 7. ENTITY CATALOG VALIDATION
# ============================================================

entity_expected_counts = {
    "state_entity_catalog":
        37,

    "zone_entity_catalog":
        6,

    "crop_entity_catalog":
        52,

    "item_entity_catalog":
        111,

    "climate_event_catalog":
        4,
}


entity_validation_records = []


for path in entity_files:

    name = path.stem

    rows = connection.execute(
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        """,
        [str(path)]
    ).fetchone()[0]


    expected = (
        entity_expected_counts.get(
            name
        )
    )


    entity_validation_records.append({
        "entity_catalog":
            name,

        "rows":
            rows,

        "expected_rows":
            expected,

        "valid":
            (
                expected is not None
                and rows == expected
            )
    })


entity_validation = pd.DataFrame(
    entity_validation_records
)


# ============================================================
# 8. METRIC CONFIGURATION VALIDATION
# ============================================================

metric_catalog_path = (
    METRICS_DIR
    / "analytical_metric_catalog.parquet"
)

metric_registry_path = (
    METRICS_DIR
    / "analytical_metric_registry.parquet"
)

answer_policy_path = (
    METRICS_DIR
    / "analytical_answer_policy.parquet"
)


metric_catalog_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM read_parquet(?)
    """,
    [str(metric_catalog_path)]
).fetchone()[0]


metric_registry_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM read_parquet(?)
    """,
    [str(metric_registry_path)]
).fetchone()[0]


answer_policy_count = connection.execute(
    """
    SELECT COUNT(*)
    FROM read_parquet(?)
    """,
    [str(answer_policy_path)]
).fetchone()[0]


metric_configuration_valid = bool(
    metric_catalog_count == 18
    and metric_registry_count == 18
    and answer_policy_count == 18
)


# ============================================================
# 9. KEY BENCHMARK QUERIES THROUGH DUCKDB
# ============================================================

production_path = (
    PROCESSED_DIR
    / "field_crop_production_wave5.parquet"
)

commercialization_path = (
    PROCESSED_DIR
    / "crop_commercialization_wave5.parquet"
)

food_security_path = (
    PROCESSED_DIR
    / "food_security_wave5.parquet"
)

climate_path = (
    PROCESSED_DIR
    / "climate_context_wave5.parquet"
)


# ------------------------------------------------------------
# Completed-harvest median yield
# ------------------------------------------------------------

completed_yield_median = (
    connection.execute(
        """
        SELECT MEDIAN(
            observed_yield_kg_per_ha
        )
        FROM read_parquet(?)
        WHERE completed_yield_eligible = TRUE
        """,
        [str(production_path)]
    ).fetchone()[0]
)


# ------------------------------------------------------------
# High-confidence yield
# ------------------------------------------------------------

high_confidence_yield_median = (
    connection.execute(
        """
        SELECT MEDIAN(
            observed_yield_kg_per_ha
        )
        FROM read_parquet(?)
        WHERE high_confidence_yield = TRUE
        """,
        [str(production_path)]
    ).fetchone()[0]
)


# ------------------------------------------------------------
# Maize commercialization share
# ------------------------------------------------------------

maize_commercialization_median = (
    connection.execute(
        """
        SELECT MEDIAN(
            commercialization_share_pct
        )
        FROM read_parquet(?)
        WHERE UPPER(crop_name) = 'MAIZE'
        """,
        [str(commercialization_path)]
    ).fetchone()[0]
)


# ------------------------------------------------------------
# Food-security mean change
#
# This is intentionally an unweighted structural check.
# The production metric engine will reproduce the weighted
# benchmark separately.
# ------------------------------------------------------------

food_security_rows = (
    connection.execute(
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        """,
        [str(food_security_path)]
    ).fetchone()[0]
)


# ------------------------------------------------------------
# Climate record count
# ------------------------------------------------------------

climate_rows = (
    connection.execute(
        """
        SELECT COUNT(*)
        FROM read_parquet(?)
        """,
        [str(climate_path)]
    ).fetchone()[0]
)


benchmark_validation = {
    "completed_yield_median":
        completed_yield_median,

    "completed_yield_valid":
        abs(
            completed_yield_median
            - 1616.445947
        ) < 0.01,

    "high_confidence_yield_median":
        high_confidence_yield_median,

    "high_confidence_yield_valid":
        abs(
            high_confidence_yield_median
            - 2209.940107
        ) < 0.01,

    "maize_commercialization_median":
        maize_commercialization_median,

    "maize_commercialization_valid":
        abs(
            maize_commercialization_median
            - 25.0
        ) < 0.000001,

    "food_security_rows":
        food_security_rows,

    "food_security_rows_valid":
        food_security_rows
        == 4715,

    "climate_rows":
        climate_rows,

    "climate_rows_valid":
        climate_rows
        == 2032,
}


all_benchmarks_valid = all(
    value
    for key, value
    in benchmark_validation.items()
    if key.endswith(
        "_valid"
    )
)


# ============================================================
# 10. OVERALL INDEPENDENT VALIDATION
# ============================================================

validation_summary = {
    "data_version":
        DATA_VERSION,

    "release_state":
        manifest.get(
            "release_state"
        ),

    "root_files_exist":
        root_files_exist,

    "directories_exist":
        directories_exist,

    "publisher_release_content_valid":
        bool(
            publisher_qa.get(
                "release_content_valid"
            )
        ),

    "checksums_expected":
        len(checksums),

    "checksums_valid":
        all_checksums_valid,

    "processed_files":
        len(
            processed_files
        ),

    "processed_expected":
        10,

    "views_files":
        len(
            view_files
        ),

    "views_expected":
        7,

    "entity_files":
        len(
            entity_files
        ),

    "entities_expected":
        5,

    "metric_files":
        len(
            metric_files
        ),

    "metrics_expected":
        3,

    "parquet_row_counts_valid":
        bool(
            parquet_validation[
                "row_count_valid"
            ].all()
        ),

    "entity_counts_valid":
        bool(
            entity_validation[
                "valid"
            ].all()
        ),

    "metric_configuration_valid":
        metric_configuration_valid,

    "duckdb_readability_valid":
        bool(
            parquet_validation[
                "duckdb_readable"
            ].all()
        ),

    "benchmarks_valid":
        all_benchmarks_valid,
}


validation_summary[
    "independent_validation_passed"
] = bool(
    validation_summary[
        "root_files_exist"
    ]
    and
    validation_summary[
        "directories_exist"
    ]
    and
    validation_summary[
        "publisher_release_content_valid"
    ]
    and
    validation_summary[
        "checksums_valid"
    ]
    and
    validation_summary[
        "processed_files"
    ] == 10
    and
    validation_summary[
        "views_files"
    ] == 7
    and
    validation_summary[
        "entity_files"
    ] == 5
    and
    validation_summary[
        "metric_files"
    ] == 3
    and
    validation_summary[
        "parquet_row_counts_valid"
    ]
    and
    validation_summary[
        "entity_counts_valid"
    ]
    and
    validation_summary[
        "metric_configuration_valid"
    ]
    and
    validation_summary[
        "duckdb_readability_valid"
    ]
    and
    validation_summary[
        "benchmarks_valid"
    ]
)


# ============================================================
# 11. WRITE VALIDATION ARTIFACT
# ============================================================

independent_validation_path = (
    RELEASE_DIR
    / "independent_validation.json"
)


with independent_validation_path.open(
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        {
            "summary":
                validation_summary,

            "benchmarks":
                benchmark_validation,
        },
        file,
        indent=2
    )


# ============================================================
# 12. OUTPUT
# ============================================================

print(
    "\n========================================"
)

print(
    f"INDEPENDENT VALIDATION: {DATA_VERSION}"
)

print(
    "========================================"
)

for key, value in (
    validation_summary.items()
):

    print(
        f"{key}: {value}"
    )


print(
    "\nBENCHMARKS"
)

for key, value in (
    benchmark_validation.items()
):

    print(
        f"{key}: {value}"
    )


print(
    "\nIndependent validation file:"
)

print(
    independent_validation_path
)


connection.close()