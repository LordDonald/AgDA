from __future__ import annotations

from dataclasses import dataclass
import json

import duckdb
import pandas as pd


# ============================================================
# METRIC DEFINITION
# ============================================================

@dataclass(frozen=True)
class MetricDefinition:

    metric_id: str

    table_name: str

    aggregation: str

    value_column: str | None

    indicator_column: str | None

    evidence_filters: dict | None

    default_minimum_records: int | None

    unit: str | None

    display_name: str | None

    question_family: str | None

    claim_type: str | None

    causal_interpretation_allowed: bool

    headline_safe: bool

    caution: str | None


# ============================================================
# HELPERS
# ============================================================

def _optional_string(
    value
) -> str | None:

    if value is None:
        return None

    if pd.isna(value):
        return None

    text = str(value).strip()

    if text.lower() in {
        "",
        "none",
        "null",
        "nan",
    }:
        return None

    return text


def _parse_json_object(
    value
) -> dict | None:

    text = _optional_string(
        value
    )

    if text is None:
        return None

    parsed = json.loads(
        text
    )

    if parsed is None:
        return None

    if not isinstance(
        parsed,
        dict
    ):
        raise ValueError(
            "Expected JSON object for evidence_filters."
        )

    return parsed


def _as_bool(
    value
) -> bool:

    if isinstance(
        value,
        bool
    ):
        return value

    return (
        str(value)
        .strip()
        .casefold()
        in {
            "true",
            "1",
            "yes",
        }
    )


# ============================================================
# METRIC REGISTRY
# ============================================================

class MetricRegistry:

    def __init__(
        self,
        definitions: dict[
            str,
            MetricDefinition
        ],
    ):

        self._definitions = (
            definitions
        )


    # --------------------------------------------------------
    # Build registry from stable DuckDB release
    # --------------------------------------------------------

    @classmethod
    def from_connection(
        cls,
        connection:
            duckdb.DuckDBPyConnection,
    ) -> "MetricRegistry":

        registry_df = (
            connection.execute(
                """
                SELECT *
                FROM analytical_metric_registry
                """
            ).fetchdf()
        )

        catalog_df = (
            connection.execute(
                """
                SELECT *
                FROM analytical_metric_catalog
                """
            ).fetchdf()
        )

        policy_df = (
            connection.execute(
                """
                SELECT *
                FROM analytical_answer_policy
                """
            ).fetchdf()
        )


        # ----------------------------------------------
        # Validate unique metric IDs
        # ----------------------------------------------

        for name, dataframe in [
            (
                "analytical_metric_registry",
                registry_df
            ),
            (
                "analytical_metric_catalog",
                catalog_df
            ),
            (
                "analytical_answer_policy",
                policy_df
            ),
        ]:

            if (
                dataframe[
                    "metric_id"
                ].duplicated().any()
            ):

                raise RuntimeError(
                    f"Duplicate metric IDs in {name}."
                )


        registry_ids = set(
            registry_df[
                "metric_id"
            ]
        )

        catalog_ids = set(
            catalog_df[
                "metric_id"
            ]
        )

        policy_ids = set(
            policy_df[
                "metric_id"
            ]
        )


        if not (
            registry_ids
            == catalog_ids
            == policy_ids
        ):

            raise RuntimeError(
                "Metric registry, catalog and "
                "answer-policy IDs do not match."
            )


        # ----------------------------------------------
        # Join authoritative metric metadata
        # ----------------------------------------------

        combined = (
            registry_df
            .merge(
                catalog_df[
                    [
                        "metric_id",
                        "display_name",
                        "question_family",
                    ]
                ],
                on="metric_id",
                how="left",
                validate="one_to_one",
            )
            .merge(
                policy_df[
                    [
                        "metric_id",
                        "claim_type",
                        "causal_interpretation_allowed",
                        "headline_safe",
                        "caution",
                    ]
                ],
                on="metric_id",
                how="left",
                validate="one_to_one",
            )
        )


        definitions = {}


        for row in (
            combined.itertuples(
                index=False
            )
        ):

            minimum_records = (
                None
                if pd.isna(
                    row.default_minimum_records
                )
                else int(
                    row.default_minimum_records
                )
            )


            definition = (
                MetricDefinition(
                    metric_id=
                        row.metric_id,

                    table_name=
                        row.table_name,

                    aggregation=
                        row.aggregation,

                    value_column=
                        _optional_string(
                            row.value_column
                        ),

                    indicator_column=
                        _optional_string(
                            row.indicator_column
                        ),

                    evidence_filters=
                        _parse_json_object(
                            row.evidence_filters
                        ),

                    default_minimum_records=
                        minimum_records,

                    unit=
                        _optional_string(
                            row.unit
                        ),

                    display_name=
                        _optional_string(
                            row.display_name
                        ),

                    question_family=
                        _optional_string(
                            row.question_family
                        ),

                    claim_type=
                        _optional_string(
                            row.claim_type
                        ),

                    causal_interpretation_allowed=
                        _as_bool(
                            row.causal_interpretation_allowed
                        ),

                    headline_safe=
                        _as_bool(
                            row.headline_safe
                        ),

                    caution=
                        _optional_string(
                            row.caution
                        ),
                )
            )


            definitions[
                definition.metric_id
            ] = definition


        return cls(
            definitions
        )


    # --------------------------------------------------------
    # Registry access
    # --------------------------------------------------------

    def get(
        self,
        metric_id: str
    ) -> MetricDefinition:

        if (
            metric_id
            not in self._definitions
        ):

            raise KeyError(
                f"Unknown metric_id: "
                f"{metric_id}"
            )

        return self._definitions[
            metric_id
        ]


    def contains(
        self,
        metric_id: str
    ) -> bool:

        return (
            metric_id
            in self._definitions
        )


    def list_metric_ids(
        self
    ) -> list[str]:

        return sorted(
            self._definitions.keys()
        )


    def count(
        self
    ) -> int:

        return len(
            self._definitions
        )


    def to_dataframe(
        self
    ) -> pd.DataFrame:

        return pd.DataFrame(
            [
                definition.__dict__
                for definition
                in self._definitions.values()
            ]
        ).sort_values(
            "metric_id"
        ).reset_index(
            drop=True
        )