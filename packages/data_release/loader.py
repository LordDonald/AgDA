from __future__ import annotations

from pathlib import Path
import hashlib
import json

import duckdb
import pandas as pd


# ============================================================
# PROJECT PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RELEASES_DIR = (
    PROJECT_ROOT
    / "data"
    / "releases"
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


def quote_identifier(
    identifier: str
) -> str:
    """
    Safely quote a DuckDB identifier.
    """

    return (
        '"'
        + identifier.replace(
            '"',
            '""'
        )
        + '"'
    )


# ============================================================
# RELEASE LOADER
# ============================================================

class AgDAReleaseLoader:

    def __init__(
        self,
        data_version: str | None = None
    ):

        self.requested_data_version = (
            data_version
        )

        self.data_version = None
        self.release_dir = None
        self.manifest = None
        self.connection = None


    # --------------------------------------------------------
    # Resolve release
    # --------------------------------------------------------

    def resolve_release(
        self
    ) -> Path:

        if self.requested_data_version:

            data_version = (
                self.requested_data_version
            )

        else:

            if not STABLE_POINTER_PATH.exists():

                raise FileNotFoundError(
                    "Stable-release pointer does not exist."
                )

            stable_pointer = load_json(
                STABLE_POINTER_PATH
            )

            if (
                stable_pointer.get(
                    "release_state"
                )
                != "stable"
            ):

                raise RuntimeError(
                    "Stable-release pointer does not "
                    "reference a stable release."
                )

            data_version = (
                stable_pointer[
                    "data_version"
                ]
            )


        release_dir = (
            RELEASES_DIR
            / data_version
        )


        if not release_dir.exists():

            raise FileNotFoundError(
                f"Release directory not found: "
                f"{release_dir}"
            )


        self.data_version = (
            data_version
        )

        self.release_dir = (
            release_dir
        )

        return release_dir


    # --------------------------------------------------------
    # Validate release manifest
    # --------------------------------------------------------

    def validate_manifest(
        self
    ) -> dict:

        if self.release_dir is None:

            self.resolve_release()


        manifest_path = (
            self.release_dir
            / "release_manifest.json"
        )


        if not manifest_path.exists():

            raise FileNotFoundError(
                "release_manifest.json is missing."
            )


        manifest = load_json(
            manifest_path
        )


        if (
            manifest.get(
                "data_version"
            )
            != self.data_version
        ):

            raise RuntimeError(
                "Manifest data version does not "
                "match resolved release."
            )


        if (
            manifest.get(
                "release_state"
            )
            != "stable"
        ):

            raise RuntimeError(
                f"Release {self.data_version} "
                "is not stable."
            )


        if (
            manifest.get(
                "application_default"
            )
            is not True
            and
            self.requested_data_version
            is None
        ):

            raise RuntimeError(
                "Default stable release is not "
                "marked application_default."
            )


        if not manifest.get(
            "release_content_valid",
            False
        ):

            raise RuntimeError(
                "Release manifest indicates "
                "invalid release content."
            )


        self.manifest = manifest

        return manifest


    # --------------------------------------------------------
    # Validate final release checksums
    # --------------------------------------------------------

    def validate_checksums(
        self
    ) -> bool:

        if self.release_dir is None:

            self.resolve_release()


        checksums_path = (
            self.release_dir
            / "checksums.csv"
        )


        if not checksums_path.exists():

            raise FileNotFoundError(
                "checksums.csv is missing."
            )


        checksums = pd.read_csv(
            checksums_path
        )


        for row in checksums.itertuples():

            path = (
                self.release_dir
                / row.relative_path
            )


            if not path.exists():

                raise RuntimeError(
                    f"Release artifact missing: "
                    f"{row.relative_path}"
                )


            if (
                path.stat().st_size
                != int(
                    row.size_bytes
                )
            ):

                raise RuntimeError(
                    f"Release artifact size mismatch: "
                    f"{row.relative_path}"
                )


            actual_hash = (
                sha256_file(
                    path
                )
            )


            if actual_hash != row.sha256:

                raise RuntimeError(
                    f"Release checksum mismatch: "
                    f"{row.relative_path}"
                )


        return True


    # --------------------------------------------------------
    # Open DuckDB
    # --------------------------------------------------------

    def open(
        self
    ) -> duckdb.DuckDBPyConnection:

        self.resolve_release()

        self.validate_manifest()

        self.validate_checksums()


        self.connection = (
            duckdb.connect(
                database=":memory:"
            )
        )


        self._register_release_views()


        return self.connection


    # --------------------------------------------------------
    # Register release Parquet datasets
    # --------------------------------------------------------

    def _register_release_views(
        self
    ) -> None:

        if self.connection is None:

            raise RuntimeError(
                "DuckDB connection is not open."
            )


        parquet_groups = {
            "processed":
                self.release_dir
                / "processed",

            "views":
                self.release_dir
                / "views",

            "entities":
                self.release_dir
                / "entities",

            "metrics":
                self.release_dir
                / "metrics",
        }


        for group_name, directory in (
            parquet_groups.items()
        ):

            if not directory.exists():

                raise FileNotFoundError(
                    f"Release directory missing: "
                    f"{directory}"
                )


            for parquet_path in sorted(
                directory.glob(
                    "*.parquet"
                )
            ):

                object_name = (
                    parquet_path.stem
                )

                quoted_name = (
                    quote_identifier(
                        object_name
                    )
                )


                parquet_sql_path = (
                    parquet_path
                    .resolve()
                    .as_posix()
                    .replace(
                        "'",
                        "''"
                    )
                )
                
                
                self.connection.execute(
                    f"""
                    CREATE OR REPLACE VIEW
                    {quoted_name}
                    AS
                    SELECT *
                    FROM read_parquet(
                    '{parquet_sql_path}'
                    )
                    """
                )


    # --------------------------------------------------------
    # Introspection
    # --------------------------------------------------------

    def list_registered_objects(
        self
    ) -> pd.DataFrame:

        if self.connection is None:

            raise RuntimeError(
                "Release is not open."
            )


        return self.connection.execute(
            """
            SELECT
                table_name
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchdf()


    # --------------------------------------------------------
    # Release information
    # --------------------------------------------------------

    def release_info(
        self
    ) -> dict:

        if self.manifest is None:

            self.validate_manifest()


        return {
            "data_version":
                self.data_version,

            "release_state":
                self.manifest[
                    "release_state"
                ],

            "metric_version":
                self.manifest[
                    "metric_version"
                ],

            "processed_tables":
                self.manifest[
                    "processed_table_count"
                ],

            "analytical_views":
                self.manifest[
                    "analytical_view_count"
                ],

            "entity_catalogs":
                self.manifest[
                    "entity_catalog_count"
                ],

            "metric_artifacts":
                self.manifest[
                    "metric_artifact_count"
                ],
        }


    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    def close(
        self
    ) -> None:

        if self.connection is not None:

            self.connection.close()

            self.connection = None


# ============================================================
# CONVENIENCE FUNCTION
# ============================================================

def open_stable_release():

    loader = AgDAReleaseLoader()

    connection = loader.open()

    return loader, connection