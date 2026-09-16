from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import re
import duckdb
import pandas as pd

from packages.analytics.registry import (
    MetricDefinition,
    MetricRegistry,
)


# ============================================================
# CONSTANTS
# ============================================================

MAX_TOP_N = 50

SUPPORTED_OPERATIONS = {
    "value",
    "group",
    "rank",
}

FILTER_ALIASES = {
    "zone": [
        "zone_label",
        "zone",
    ],

    "state": [
        "state_label",
        "state",
    ],

    "lga": [
        "lga",
    ],

    "sector": [
        "sector_label",
        "sector",
    ],

    "crop": [
        "crop_name",
    ],

    "item": [
        "item_name",
    ],

    "climate_event": [
        "climate_event",
    ],

    "visit": [
        "visit",
    ],

    "planting_extension": [
        "received_planting_extension",
    ],
}


# ============================================================
# RESULT MODELS
# ============================================================

@dataclass(frozen=True)
class EvidenceSummary:

    records: int

    households: int | None

    clusters: int | None

    value_available: int | None

    minimum_records: int

    evidence_grade: str

    denominator_households: int | None = None


@dataclass(frozen=True)
class ScalarMetricResult:

    metric_id: str

    metric_name: str | None

    operation: str

    value: float | int | None

    unit: str | None

    filters: dict[str, Any]

    evidence: EvidenceSummary

    claim_type: str | None

    causal_interpretation_allowed: bool

    caution: str | None


@dataclass(frozen=True)
class TableMetricResult:

    metric_id: str

    metric_name: str | None

    operation: str

    group_by: str

    unit: str | None

    filters: dict[str, Any]

    rows: list[dict[str, Any]]

    minimum_records: int

    claim_type: str | None

    causal_interpretation_allowed: bool

    caution: str | None


# ============================================================
# HELPERS
# ============================================================

def _quote_identifier(
    identifier: str,
) -> str:

    return (
        '"'
        + identifier.replace(
            '"',
            '""'
        )
        + '"'
    )

def _clean_group_value(
    dimension: str,
    value,
):
    if value is None:
        return None
        
    if dimension == "planting_extension":

        if pd.isna(value):

            return (
                "Unknown extension status"
            )


        return (
            "Received planting extension"
            if bool(value)
            else "No planting extension"
        )

    if dimension in {
        "state",
        "zone",
        "sector",
    }:
        return re.sub(
            r"^\d+\.\s*",
            "",
            str(value).strip(),
        )

    return value
    
def grade_evidence(
    records: int,
    minimum_records: int,
) -> str:

    if records <= 0:
        return "Insufficient"

    if records < minimum_records:
        return "Limited"

    if records < (
        2 * minimum_records
    ):
        return "Adequate"

    return "Strong"


# ============================================================
# ANALYTICS EXECUTOR
# ============================================================

class AnalyticsExecutor:

    def __init__(
        self,
        connection:
            duckdb.DuckDBPyConnection,

        registry:
            MetricRegistry,
    ):

        self.connection = connection

        self.registry = registry

        self._prepare_runtime_views()


    # ========================================================
    # RUNTIME VIEW PREPARATION
    # ========================================================

    def _prepare_runtime_views(
        self,
    ) -> None:
        """
        Create runtime-only analytical views that were
        intentionally not materialized into the release.

        Also creates analysis-ready enriched views used
        for human-friendly geography filtering.
        """

        self._validate_geography_lookups()

        self._create_geography_lookups()

        self._create_special_metric_views()

        self._create_analysis_views()


    # --------------------------------------------------------
    # Validate geography code -> label relationships
    # --------------------------------------------------------

    def _validate_geography_lookups(
        self,
    ) -> None:

        checks = {
            "state":
                "state_label",

            "zone":
                "zone_label",

            "sector":
                "sector_label",
        }


        for code_column, label_column in (
            checks.items()
        ):

            conflicting = (
                self.connection.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM (
                        SELECT
                            {_quote_identifier(code_column)}
                        FROM households_wave5
                        GROUP BY
                            {_quote_identifier(code_column)}
                        HAVING COUNT(
                            DISTINCT
                            {_quote_identifier(label_column)}
                        ) > 1
                    )
                    """
                ).fetchone()[0]
            )


            if conflicting != 0:

                raise RuntimeError(
                    f"Conflicting {code_column} "
                    f"to {label_column} mappings."
                )


        cluster_conflicts = (
            self.connection.execute(
                """
                SELECT COUNT(*)
                FROM (
                    SELECT
                        cluster_id
                    FROM community_prices_wave5
                    GROUP BY cluster_id
                    HAVING
                        COUNT(DISTINCT zone) > 1
                        OR COUNT(DISTINCT state) > 1
                        OR COUNT(DISTINCT sector) > 1
                )
                """
            ).fetchone()[0]
        )


        if cluster_conflicts != 0:

            raise RuntimeError(
                "Community-price cluster geography "
                "contains conflicting mappings."
            )


    # --------------------------------------------------------
    # Geography lookup views
    # --------------------------------------------------------

    def _create_geography_lookups(
        self,
    ) -> None:

        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            __state_lookup
            AS
            SELECT
                state,
                ANY_VALUE(state_label)
                    AS state_label
            FROM households_wave5
            GROUP BY state
            """
        )


        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            __zone_lookup
            AS
            SELECT
                zone,
                ANY_VALUE(zone_label)
                    AS zone_label
            FROM households_wave5
            GROUP BY zone
            """
        )


        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            __sector_lookup
            AS
            SELECT
                sector,
                ANY_VALUE(sector_label)
                    AS sector_label
            FROM households_wave5
            GROUP BY sector
            """
        )


        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            __cluster_geography
            AS
            SELECT
                cluster_id,
                ANY_VALUE(zone)
                    AS zone,
                ANY_VALUE(state)
                    AS state,
                ANY_VALUE(sector)
                    AS sector
            FROM community_prices_wave5
            GROUP BY cluster_id
            """
        )


    # --------------------------------------------------------
    # Runtime-only metric views
    # --------------------------------------------------------

    def _create_special_metric_views(
        self,
    ) -> None:

        # Household crop participation
        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            households_metric_view
            AS
            SELECT
                *,
                CASE
                    WHEN ag1 IS NULL
                        THEN NULL
                    WHEN ag1 = 1
                        THEN 1
                    ELSE 0
                END
                AS crop_growing_household
            FROM households_wave5
            """
        )


        # Cultivated plots only
        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            cultivated_plot_metric_view
            AS
            SELECT *
            FROM plots_wave5
            WHERE cultivated_flag = TRUE
            """
        )


        # One household/crop record for grower-share metrics
        self.connection.execute(
            """
            CREATE OR REPLACE TEMP VIEW
            crop_grower_metric_view
            AS
            SELECT DISTINCT
                c.hhid,
                c.cropcode,
                c.crop_name,
                h.wt_cross_wave5,
                h.zone,
                h.zone_label,
                h.state,
                h.state_label,
                h.lga,
                h.sector,
                h.sector_label
            FROM crop_planting_wave5 AS c
            INNER JOIN households_wave5 AS h
                ON c.hhid = h.hhid
            """
        )


    # --------------------------------------------------------
    # Generic analysis-ready views
    # --------------------------------------------------------

    def _create_analysis_views(
        self,
    ) -> None:

        metric_tables = {
            self.registry.get(
                metric_id
            ).table_name

            for metric_id
            in self.registry.list_metric_ids()
        }


        for table_name in sorted(
            metric_tables
        ):

            analysis_name = (
                self._analysis_view_name(
                    table_name
                )
            )


            # ----------------------------------------------
            # Community-price change needs cluster geography
            # ----------------------------------------------

            if (
                table_name
                == "community_price_change_wave5"
            ):

                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TEMP VIEW
                    {_quote_identifier(analysis_name)}
                    AS
                    SELECT
                        b.*,
                        cg.zone,
                        zl.zone_label,
                        cg.state,
                        sl.state_label,
                        cg.sector,
                        secl.sector_label
                    FROM
                        community_price_change_wave5
                        AS b

                    LEFT JOIN __cluster_geography
                        AS cg
                        ON b.cluster_id
                        = cg.cluster_id

                    LEFT JOIN __zone_lookup
                        AS zl
                        ON cg.zone = zl.zone

                    LEFT JOIN __state_lookup
                        AS sl
                        ON cg.state = sl.state

                    LEFT JOIN __sector_lookup
                        AS secl
                        ON cg.sector
                        = secl.sector
                    """
                )

                continue


            columns = set(
                self._get_columns(
                    table_name
                )
            )


            # ----------------------------------------------
            # HH-linked table
            # ----------------------------------------------

            if "hhid" in columns:

                household_fields = [
                    "wt_cross_wave5",
                    "zone",
                    "zone_label",
                    "state",
                    "state_label",
                    "lga",
                    "sector",
                    "sector_label",
                ]


                missing_fields = [
                    field
                    for field
                    in household_fields
                    if field not in columns
                ]


                additions = ",\n".join(
                    (
                        f"h.{_quote_identifier(field)} "
                        f"AS {_quote_identifier(field)}"
                    )
                    for field
                    in missing_fields
                )


                if additions:

                    additions = (
                        ",\n"
                        + additions
                    )


                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TEMP VIEW
                    {_quote_identifier(analysis_name)}
                    AS
                    SELECT
                        b.*
                        {additions}
                    FROM
                        {_quote_identifier(table_name)}
                        AS b

                    LEFT JOIN households_wave5
                        AS h
                        ON b.hhid = h.hhid
                    """
                )

                continue


            # ----------------------------------------------
            # Non-HH table: start with original table
            # ----------------------------------------------

            self.connection.execute(
                f"""
                CREATE OR REPLACE TEMP VIEW
                {_quote_identifier(analysis_name)}
                AS
                SELECT *
                FROM {_quote_identifier(table_name)}
                """
            )


            # Climate/context tables can contain geography
            # codes without readable labels. Add them where
            # required.
            current_columns = set(
                self._get_columns(
                    analysis_name
                )
            )


            needs_zone_label = (
                "zone"
                in current_columns
                and
                "zone_label"
                not in current_columns
            )

            needs_state_label = (
                "state"
                in current_columns
                and
                "state_label"
                not in current_columns
            )

            needs_sector_label = (
                "sector"
                in current_columns
                and
                "sector_label"
                not in current_columns
            )


            if any([
                needs_zone_label,
                needs_state_label,
                needs_sector_label,
            ]):

                previous_view = (
                    analysis_name
                    + "__base"
                )


                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TEMP VIEW
                    {_quote_identifier(previous_view)}
                    AS
                    SELECT *
                    FROM {_quote_identifier(table_name)}
                    """
                )


                additions = []

                joins = []


                if needs_zone_label:

                    additions.append(
                        "zl.zone_label AS zone_label"
                    )

                    joins.append(
                        """
                        LEFT JOIN __zone_lookup AS zl
                            ON b.zone = zl.zone
                        """
                    )


                if needs_state_label:

                    additions.append(
                        "sl.state_label AS state_label"
                    )

                    joins.append(
                        """
                        LEFT JOIN __state_lookup AS sl
                            ON b.state = sl.state
                        """
                    )


                if needs_sector_label:

                    additions.append(
                        "secl.sector_label AS sector_label"
                    )

                    joins.append(
                        """
                        LEFT JOIN __sector_lookup AS secl
                            ON b.sector = secl.sector
                        """
                    )


                addition_sql = (
                    ",\n"
                    + ",\n".join(
                        additions
                    )
                )


                join_sql = "\n".join(
                    joins
                )


                self.connection.execute(
                    f"""
                    CREATE OR REPLACE TEMP VIEW
                    {_quote_identifier(analysis_name)}
                    AS
                    SELECT
                        b.*
                        {addition_sql}
                    FROM
                        {_quote_identifier(previous_view)}
                        AS b

                    {join_sql}
                    """
                )


    # ========================================================
    # PUBLIC EXECUTION
    # ========================================================

    def execute(
        self,
        metric_id: str,
        operation: str = "value",
        filters:
            dict[str, Any]
            | None = None,
        group_by:
            str
            | None = None,
        ascending: bool = False,
        top_n:
            int
            | None = None,
        minimum_records:
            int
            | None = None,
    ) -> (
        ScalarMetricResult
        | TableMetricResult
    ):

        if operation not in (
            SUPPORTED_OPERATIONS
        ):

            raise ValueError(
                f"Unsupported operation: "
                f"{operation}"
            )


        definition = (
            self.registry.get(
                metric_id
            )
        )


        effective_minimum = (
            self._effective_minimum_records(
                definition,
                minimum_records
            )
        )


        filters = (
            filters
            or {}
        )


        # ----------------------------------------------
        # Special crop-grower-share metric
        # ----------------------------------------------

        if metric_id == "crop_grower_share":

            return (
                self._execute_crop_grower_share(
                    definition=
                        definition,

                    operation=
                        operation,

                    filters=
                        filters,

                    group_by=
                        group_by,

                    ascending=
                        ascending,

                    top_n=
                        top_n,

                    minimum_records=
                        effective_minimum,
                )
            )


        # ----------------------------------------------
        # Standard metrics
        # ----------------------------------------------

        if operation == "value":

            return (
                self._execute_scalar(
                    definition=
                        definition,

                    filters=
                        filters,

                    minimum_records=
                        effective_minimum,
                )
            )


        if group_by is None:

            raise ValueError(
                f"{operation} operation "
                "requires group_by."
            )


        return (
            self._execute_table(
                definition=
                    definition,

                operation=
                    operation,

                filters=
                    filters,

                group_by=
                    group_by,

                ascending=
                    ascending,

                top_n=
                    top_n,

                minimum_records=
                    effective_minimum,
            )
        )


    # ========================================================
    # STANDARD SCALAR EXECUTION
    # ========================================================

    def _execute_scalar(
        self,
        definition:
            MetricDefinition,
        filters:
            dict[str, Any],
        minimum_records: int,
    ) -> ScalarMetricResult:

        view_name = (
            self._metric_source_view(
                definition=
                    definition,
        
                filters=
                    filters,
            )
        )


        where_sql, parameters = (
            self._build_where_clause(
                view_name,
                filters,
                definition.evidence_filters,
            )
        )


        metric_expression = (
            self._metric_expression(
                definition
            )
        )


        columns = set(
            self._get_columns(
                view_name
            )
        )


        household_expression = (
            "COUNT(DISTINCT hhid)"
            if "hhid" in columns
            else "NULL"
        )


        cluster_expression = (
            "COUNT(DISTINCT cluster_id)"
            if "cluster_id"
            in columns
            else "NULL"
        )


        value_column = (
            definition.value_column
            or
            definition.indicator_column
        )


        value_available_expression = (
            (
                "COUNT("
                + _quote_identifier(
                    value_column
                )
                + ")"
            )
            if value_column
            in columns
            else "NULL"
        )


        row = (
            self.connection.execute(
                f"""
                SELECT
                    {metric_expression}
                        AS value,

                    COUNT(*)
                        AS records,

                    {household_expression}
                        AS households,

                    {cluster_expression}
                        AS clusters,

                    {value_available_expression}
                        AS value_available

                FROM
                    {_quote_identifier(view_name)}

                {where_sql}
                """,
                parameters,
            ).fetchone()
        )


        value = row[0]

        records = int(
            row[1]
        )


        households = (
            None
            if row[2] is None
            else int(row[2])
        )


        clusters = (
            None
            if row[3] is None
            else int(row[3])
        )


        value_available = (
            None
            if row[4] is None
            else int(row[4])
        )


        evidence = EvidenceSummary(
            records=
                records,

            households=
                households,

            clusters=
                clusters,

            value_available=
                value_available,

            minimum_records=
                minimum_records,

            evidence_grade=
                grade_evidence(
                    records,
                    minimum_records,
                ),
        )


        return ScalarMetricResult(
            metric_id=
                definition.metric_id,

            metric_name=
                definition.display_name,

            operation=
                "value",

            value=
                (
                    None
                    if value is None
                    else float(value)
                ),

            unit=
                definition.unit,

            filters=
                filters,

            evidence=
                evidence,

            claim_type=
                definition.claim_type,

            causal_interpretation_allowed=
                definition
                .causal_interpretation_allowed,

            caution=
                definition.caution,
        )


    # ========================================================
    # STANDARD GROUP / RANK
    # ========================================================

    def _execute_table(
        self,
        definition:
            MetricDefinition,
        operation: str,
        filters:
            dict[str, Any],
        group_by: str,
        ascending: bool,
        top_n:
            int
            | None,
        minimum_records: int,
    ) -> TableMetricResult:

        view_name = (
            self._metric_source_view(
                definition=
                    definition,
        
                filters=
                    filters,
        
                group_by=
                    group_by,
            )
        )


        group_column = (
            self._resolve_dimension_column(
                view_name,
                group_by,
            )
        )


        where_sql, parameters = (
            self._build_where_clause(
                view_name,
                filters,
                definition.evidence_filters,
            )
        )


        metric_expression = (
            self._metric_expression(
                definition
            )
        )


        columns = set(
            self._get_columns(
                view_name
            )
        )


        household_expression = (
            "COUNT(DISTINCT hhid)"
            if "hhid" in columns
            else "NULL"
        )


        cluster_expression = (
            "COUNT(DISTINCT cluster_id)"
            if "cluster_id"
            in columns
            else "NULL"
        )


        value_column = (
            definition.value_column
            or
            definition.indicator_column
        )


        value_available_expression = (
            (
                "COUNT("
                + _quote_identifier(
                    value_column
                )
                + ")"
            )
            if value_column
            in columns
            else "NULL"
        )


        order_direction = (
            "ASC"
            if ascending
            else "DESC"
        )


        limit_sql = ""

        if (
            operation == "rank"
            and top_n is not None
        ):

            if top_n < 1:

                raise ValueError(
                    "top_n must be >= 1."
                )


            effective_top_n = min(
                int(top_n),
                MAX_TOP_N,
            )

            limit_sql = (
                f"LIMIT {effective_top_n}"
            )


        dataframe = (
            self.connection.execute(
                f"""
                SELECT
                    {_quote_identifier(group_column)}
                        AS group_value,

                    {metric_expression}
                        AS value,

                    COUNT(*)
                        AS records,

                    {household_expression}
                        AS households,

                    {cluster_expression}
                        AS clusters,

                    {value_available_expression}
                        AS value_available

                FROM
                    {_quote_identifier(view_name)}

                {where_sql}

                GROUP BY
                    {_quote_identifier(group_column)}

                HAVING
                    COUNT(*) >= ?

                ORDER BY
                    value {order_direction},
                    group_value ASC

                {limit_sql}
                """,
                [
                    *parameters,
                    minimum_records,
                ],
            ).fetchdf()
        )


        rows = []


        for index, row in (
            dataframe.iterrows()
        ):

            record = {
                group_by:
                    _clean_group_value(
                        group_by,
                        row[
                            "group_value"
                        ],
                    ),

                "value":
                    (
                        None
                        if pd.isna(
                            row["value"]
                        )
                        else float(
                            row["value"]
                        )
                    ),

                "records":
                    int(
                        row["records"]
                    ),

                "households":
                    (
                        None
                        if pd.isna(
                            row["households"]
                        )
                        else int(
                            row["households"]
                        )
                    ),

                "clusters":
                    (
                        None
                        if pd.isna(
                            row["clusters"]
                        )
                        else int(
                            row["clusters"]
                        )
                    ),

                "value_available":
                    (
                        None
                        if pd.isna(
                            row[
                                "value_available"
                            ]
                        )
                        else int(
                            row[
                                "value_available"
                            ]
                        )
                    ),

                "evidence_grade":
                    grade_evidence(
                        int(
                            row["records"]
                        ),
                        minimum_records,
                    ),
            }


            if operation == "rank":

                record[
                    "rank"
                ] = (
                    index + 1
                )


            rows.append(
                record
            )


        return TableMetricResult(
            metric_id=
                definition.metric_id,

            metric_name=
                definition.display_name,

            operation=
                operation,

            group_by=
                group_by,

            unit=
                definition.unit,

            filters=
                filters,

            rows=
                rows,

            minimum_records=
                minimum_records,

            claim_type=
                definition.claim_type,

            causal_interpretation_allowed=
                definition
                .causal_interpretation_allowed,

            caution=
                definition.caution,
        )


    # ========================================================
    # CUSTOM CROP-GROWER SHARE
    # ========================================================

    def _execute_crop_grower_share(
        self,
        definition:
            MetricDefinition,
        operation: str,
        filters:
            dict[str, Any],
        group_by:
            str
            | None,
        ascending: bool,
        top_n:
            int
            | None,
        minimum_records: int,
    ) -> (
        ScalarMetricResult
        | TableMetricResult
    ):

        crop_filter = (
            filters.get(
                "crop"
            )
        )


        geography_filters = {
            key: value
            for key, value
            in filters.items()
            if key != "crop"
        }


        denominator_where, denominator_params = (
            self._build_where_clause(
                "households_metric_view",
                geography_filters,
                {
                    "crop_growing_household":
                        1
                },
            )
        )


        grower_where, grower_params = (
            self._build_where_clause(
                "crop_grower_metric_view",
                filters,
                None,
            )
        )


        # ----------------------------------------------------
        # Scalar crop grower share
        # ----------------------------------------------------

        if operation == "value":

            if crop_filter is None:

                raise ValueError(
                    "crop_grower_share value "
                    "operation requires a crop filter."
                )


            row = (
                self.connection.execute(
                    f"""
                    WITH denominator AS (
                        SELECT
                            hhid,
                            wt_cross_wave5
                        FROM households_metric_view
                        {denominator_where}
                    ),

                    growers AS (
                        SELECT DISTINCT
                            hhid
                        FROM crop_grower_metric_view
                        {grower_where}
                    )

                    SELECT
                        SUM(
                            CASE
                                WHEN g.hhid IS NOT NULL
                                THEN d.wt_cross_wave5
                                ELSE 0
                            END
                        )
                        /
                        NULLIF(
                            SUM(
                                d.wt_cross_wave5
                            ),
                            0
                        )
                            AS value,

                        COUNT(
                            DISTINCT g.hhid
                        )
                            AS grower_households,

                        COUNT(
                            DISTINCT d.hhid
                        )
                            AS denominator_households

                    FROM denominator AS d

                    LEFT JOIN growers AS g
                        ON d.hhid = g.hhid
                    """,
                    [
                        *denominator_params,
                        *grower_params,
                    ],
                ).fetchone()
            )


            value = row[0]

            grower_households = int(
                row[1]
            )

            denominator_households = (
                int(
                    row[2]
                )
            )


            evidence = EvidenceSummary(
                records=
                    grower_households,

                households=
                    grower_households,

                clusters=
                    None,

                value_available=
                    denominator_households,

                minimum_records=
                    minimum_records,

                evidence_grade=
                    grade_evidence(
                        grower_households,
                        minimum_records,
                    ),

                denominator_households=
                    denominator_households,
            )


            return ScalarMetricResult(
                metric_id=
                    definition.metric_id,

                metric_name=
                    definition.display_name,

                operation=
                    "value",

                value=
                    (
                        None
                        if value is None
                        else float(value)
                    ),

                unit=
                    definition.unit,

                filters=
                    filters,

                evidence=
                    evidence,

                claim_type=
                    definition.claim_type,

                causal_interpretation_allowed=
                    definition
                    .causal_interpretation_allowed,

                caution=
                    definition.caution,
            )


        # ----------------------------------------------------
        # Geographic group/rank for one requested crop
        # ----------------------------------------------------

        if group_by in {
            "state",
            "zone",
            "sector",
        }:

            if crop_filter is None:

                raise ValueError(
                    "Geographic crop_grower_share "
                    "group/rank requires a crop filter."
                )


            denominator_group_column = (
                self._resolve_dimension_column(
                    "households_metric_view",
                    group_by,
                )
            )


            grower_group_column = (
                self._resolve_dimension_column(
                    "crop_grower_metric_view",
                    group_by,
                )
            )


            order_direction = (
                "ASC"
                if ascending
                else "DESC"
            )


            limit_sql = ""


            if (
                operation == "rank"
                and top_n is not None
            ):

                if top_n < 1:

                    raise ValueError(
                        "top_n must be >= 1."
                    )


                limit_sql = (
                    f"LIMIT "
                    f"{min(int(top_n), MAX_TOP_N)}"
                )


            dataframe = (
                self.connection.execute(
                    f"""
                    WITH denominator AS (
                        SELECT
                            hhid,
                            wt_cross_wave5,

                            {_quote_identifier(
                                denominator_group_column
                            )}
                                AS group_value

                        FROM households_metric_view

                        {denominator_where}
                    ),

                    growers AS (
                        SELECT DISTINCT
                            hhid,

                            {_quote_identifier(
                                grower_group_column
                            )}
                                AS group_value

                        FROM crop_grower_metric_view

                        {grower_where}
                    ),

                    denominator_summary AS (
                        SELECT
                            group_value,

                            COUNT(
                                DISTINCT hhid
                            )
                                AS denominator_households,

                            SUM(
                                wt_cross_wave5
                            )
                                AS denominator_weight

                        FROM denominator

                        WHERE
                            group_value
                            IS NOT NULL

                        GROUP BY
                            group_value
                    ),

                    grower_summary AS (
                        SELECT
                            d.group_value,

                            COUNT(
                                DISTINCT g.hhid
                            )
                                AS records,

                            SUM(
                                d.wt_cross_wave5
                            )
                                AS grower_weight

                        FROM denominator AS d

                        INNER JOIN growers AS g
                            ON d.hhid = g.hhid
                            AND d.group_value
                                = g.group_value

                        WHERE
                            d.group_value
                            IS NOT NULL

                        GROUP BY
                            d.group_value
                    )

                    SELECT
                        g.group_value,

                        g.grower_weight
                        /
                        NULLIF(
                            d.denominator_weight,
                            0
                        )
                            AS value,

                        g.records,

                        g.records
                            AS households,

                        d.denominator_households,

                        d.denominator_households
                            AS value_available

                    FROM grower_summary AS g

                    INNER JOIN denominator_summary
                        AS d
                        ON g.group_value
                        = d.group_value

                    WHERE
                        g.records >= ?

                    ORDER BY
                        value {order_direction},
                        g.group_value ASC

                    {limit_sql}
                    """,
                    [
                        *denominator_params,
                        *grower_params,
                        minimum_records,
                    ],
                ).fetchdf()
            )


            rows = []


            for index, row in (
                dataframe.iterrows()
            ):

                record = {
                    group_by:
                        _clean_group_value(
                            group_by,
                            row[
                                "group_value"
                            ],
                        ),

                    "value":
                        float(
                            row["value"]
                        ),

                    "records":
                        int(
                            row["records"]
                        ),

                    "households":
                        int(
                            row["households"]
                        ),

                    "clusters":
                        None,

                    "denominator_households":
                        int(
                            row[
                                "denominator_households"
                            ]
                        ),

                    "value_available":
                        int(
                            row[
                                "value_available"
                            ]
                        ),

                    "evidence_grade":
                        grade_evidence(
                            int(
                                row["records"]
                            ),
                            minimum_records,
                        ),
                }


                if operation == "rank":

                    record[
                        "rank"
                    ] = (
                        index + 1
                    )


                rows.append(
                    record
                )


            return TableMetricResult(
                metric_id=
                    definition.metric_id,

                metric_name=
                    definition.display_name,

                operation=
                    operation,

                group_by=
                    group_by,

                unit=
                    definition.unit,

                filters=
                    filters,

                rows=
                    rows,

                minimum_records=
                    minimum_records,

                claim_type=
                    definition.claim_type,

                causal_interpretation_allowed=
                    definition
                    .causal_interpretation_allowed,

                caution=
                    definition.caution,
            )
        
        # ----------------------------------------------------
        # Group/rank must be by crop
        # ----------------------------------------------------

        if group_by != "crop":

            raise ValueError(
                "crop_grower_share group/rank "
                "currently requires group_by='crop'."
            )


        grower_geo_where, grower_geo_params = (
            self._build_where_clause(
                "crop_grower_metric_view",
                geography_filters,
                None,
            )
        )


        order_direction = (
            "ASC"
            if ascending
            else "DESC"
        )


        limit_sql = ""

        if (
            operation == "rank"
            and top_n is not None
        ):

            if top_n < 1:

                raise ValueError(
                    "top_n must be >= 1."
                )


            limit_sql = (
                f"LIMIT "
                f"{min(int(top_n), MAX_TOP_N)}"
            )


        dataframe = (
            self.connection.execute(
                f"""
                WITH denominator AS (
                    SELECT
                        hhid,
                        wt_cross_wave5
                    FROM households_metric_view
                    {denominator_where}
                ),

                denominator_total AS (
                    SELECT
                        COUNT(DISTINCT hhid)
                            AS denominator_households,

                        SUM(wt_cross_wave5)
                            AS denominator_weight
                    FROM denominator
                ),

                growers AS (
                    SELECT DISTINCT
                        g.hhid,
                        g.crop_name
                    FROM crop_grower_metric_view
                        AS g
                    {grower_geo_where}
                ),

                crop_summary AS (
                    SELECT
                        g.crop_name
                            AS crop,

                        COUNT(DISTINCT g.hhid)
                            AS records,

                        SUM(d.wt_cross_wave5)
                            AS grower_weight

                    FROM growers AS g

                    INNER JOIN denominator AS d
                        ON g.hhid = d.hhid

                    GROUP BY
                        g.crop_name
                )

                SELECT
                    c.crop,

                    c.grower_weight
                    /
                    NULLIF(
                        dt.denominator_weight,
                        0
                    )
                        AS value,

                    c.records,

                    c.records
                        AS households,

                    dt.denominator_households,

                    dt.denominator_households
                        AS value_available

                FROM crop_summary AS c

                CROSS JOIN denominator_total
                    AS dt

                WHERE
                    c.records >= ?

                ORDER BY
                    value {order_direction},
                    crop ASC

                {limit_sql}
                """,
                [
                    *denominator_params,
                    *grower_geo_params,
                    minimum_records,
                ],
            ).fetchdf()
        )


        rows = []


        for index, row in (
            dataframe.iterrows()
        ):

            record = {
                "crop":
                    row["crop"],

                "value":
                    float(
                        row["value"]
                    ),

                "records":
                    int(
                        row["records"]
                    ),

                "households":
                    int(
                        row["households"]
                    ),

                "clusters":
                    None,

                "denominator_households":
                    int(
                        row[
                            "denominator_households"
                        ]
                    ),

                "value_available":
                    int(
                        row[
                            "value_available"
                        ]
                    ),

                "evidence_grade":
                    grade_evidence(
                        int(
                            row["records"]
                        ),
                        minimum_records,
                    ),
            }


            if operation == "rank":

                record[
                    "rank"
                ] = (
                    index + 1
                )


            rows.append(
                record
            )


        return TableMetricResult(
            metric_id=
                definition.metric_id,

            metric_name=
                definition.display_name,

            operation=
                operation,

            group_by=
                "crop",

            unit=
                definition.unit,

            filters=
                filters,

            rows=
                rows,

            minimum_records=
                minimum_records,

            claim_type=
                definition.claim_type,

            causal_interpretation_allowed=
                definition
                .causal_interpretation_allowed,

            caution=
                definition.caution,
        )


    # ========================================================
    # SQL / FILTER HELPERS
    # ========================================================

    def _metric_expression(
        self,
        definition:
            MetricDefinition,
    ) -> str:

        aggregation = (
            definition.aggregation
        )


        if aggregation == "median":

            column = _quote_identifier(
                definition.value_column
            )

            return (
                f"MEDIAN("
                f"TRY_CAST({column} AS DOUBLE)"
                f")"
            )


        if aggregation == "mean":

            column = _quote_identifier(
                definition.value_column
            )

            return (
                f"AVG("
                f"TRY_CAST({column} AS DOUBLE)"
                f")"
            )


        if aggregation == "weighted_mean":

            value_column = (
                _quote_identifier(
                    definition.value_column
                )
            )

            weight_column = (
                _quote_identifier(
                    "wt_cross_wave5"
                )
            )

            return f"""
                SUM(
                    CASE
                        WHEN
                            {value_column}
                                IS NOT NULL
                            AND {weight_column}
                                IS NOT NULL
                            AND {weight_column} > 0
                        THEN
                            TRY_CAST(
                                {value_column}
                                AS DOUBLE
                            )
                            *
                            TRY_CAST(
                                {weight_column}
                                AS DOUBLE
                            )
                    END
                )
                /
                NULLIF(
                    SUM(
                        CASE
                            WHEN
                                {value_column}
                                    IS NOT NULL
                                AND {weight_column}
                                    IS NOT NULL
                                AND {weight_column} > 0
                            THEN
                                TRY_CAST(
                                    {weight_column}
                                    AS DOUBLE
                                )
                        END
                    ),
                    0
                )
            """


        if aggregation == "proportion":

            column = _quote_identifier(
                definition.indicator_column
            )

            return (
                f"AVG("
                f"TRY_CAST({column} AS DOUBLE)"
                f")"
            )


        if aggregation == "weighted_proportion":

            indicator_column = (
                _quote_identifier(
                    definition.indicator_column
                )
            )

            weight_column = (
                _quote_identifier(
                    "wt_cross_wave5"
                )
            )

            return f"""
                SUM(
                    CASE
                        WHEN
                            {indicator_column}
                                IS NOT NULL
                            AND {weight_column}
                                IS NOT NULL
                            AND {weight_column} > 0
                        THEN
                            TRY_CAST(
                                {indicator_column}
                                AS DOUBLE
                            )
                            *
                            TRY_CAST(
                                {weight_column}
                                AS DOUBLE
                            )
                    END
                )
                /
                NULLIF(
                    SUM(
                        CASE
                            WHEN
                                {indicator_column}
                                    IS NOT NULL
                                AND {weight_column}
                                    IS NOT NULL
                                AND {weight_column} > 0
                            THEN
                                TRY_CAST(
                                    {weight_column}
                                    AS DOUBLE
                                )
                        END
                    ),
                    0
                )
            """


        raise ValueError(
            f"Unsupported aggregation: "
            f"{aggregation}"
        )


    def _build_where_clause(
        self,
        view_name: str,
        filters:
            dict[str, Any]
            | None,
        evidence_filters:
            dict[str, Any]
            | None,
    ) -> tuple[str, list[Any]]:

        predicates = []

        parameters = []


        for filter_set in [
            filters or {},
            evidence_filters or {},
        ]:

            for dimension, values in (
                filter_set.items()
            ):

                column = (
                    self._resolve_dimension_column(
                        view_name,
                        dimension,
                    )
                )


                if not isinstance(
                    values,
                    (
                        list,
                        tuple,
                        set,
                    )
                ):

                    values = [
                        values
                    ]


                values = [
                    value
                    for value
                    in values
                    if value is not None
                ]


                if not values:
                    continue


                value_predicates = []


                for value in values:

                    quoted_column = (
                        _quote_identifier(
                            column
                        )
                    )


                    if isinstance(
                        value,
                        str
                    ):

                        value_predicates.append(
                            f"""
                            LOWER(
                                TRIM(
                                    REGEXP_REPLACE(
                                        CAST(
                                            {quoted_column}
                                            AS VARCHAR
                                        ),
                                        '^[0-9]+\\.\\s*',
                                        ''
                                    )
                                )
                            )
                            =
                            LOWER(
                                TRIM(
                                    REGEXP_REPLACE(
                                        CAST(? AS VARCHAR),
                                        '^[0-9]+\\.\\s*',
                                        ''
                                    )
                                )
                            )
                            """
                        )

                    else:

                        value_predicates.append(
                            f"{quoted_column} = ?"
                        )


                    parameters.append(
                        value
                    )


                predicates.append(
                    "("
                    + " OR ".join(
                        value_predicates
                    )
                    + ")"
                )


        if not predicates:

            return "", []


        return (
            "WHERE "
            + " AND ".join(
                predicates
            ),
            parameters,
        )


    def _resolve_dimension_column(
        self,
        view_name: str,
        dimension: str,
    ) -> str:

        columns = set(
            self._get_columns(
                view_name
            )
        )


        # Friendly alias takes priority
        if dimension in FILTER_ALIASES:

            for candidate in (
                FILTER_ALIASES[
                    dimension
                ]
            ):

                if candidate in columns:

                    return candidate


        # Exact server-controlled field
        if dimension in columns:

            return dimension


        raise KeyError(
            f"Dimension '{dimension}' "
            f"is not available in "
            f"{view_name}."
        )


    def _get_columns(
        self,
        object_name: str,
    ) -> list[str]:

        dataframe = (
            self.connection.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE
                    table_schema = 'main'
                    AND table_name = ?
                ORDER BY ordinal_position
                """,
                [object_name],
            ).fetchdf()
        )


        if dataframe.empty:

            raise KeyError(
                f"DuckDB object not found: "
                f"{object_name}"
            )


        return dataframe[
            "column_name"
        ].tolist()

        
    def _metric_source_view(
        self,
        definition: MetricDefinition,
        filters: dict[str, Any] | None = None,
        group_by: str | None = None,
    ) -> str:
        """
        Resolve the analytical source for a registered metric.
    
        Most metrics use their normal analysis-ready base table.
    
        Median completed-harvest yield may use the existing
        production_extension_view when the analytical request
        explicitly compares or filters by planting-extension
        status.
        """
    
        filters = (
            filters
            or {}
        )
    
    
        if (
            definition.metric_id
            == "median_completed_yield"
            and (
                group_by
                == "planting_extension"
                or
                "planting_extension"
                in filters
            )
        ):
    
            return (
                "production_extension_view"
            )
    
    
        return (
            self._analysis_view_name(
                definition.table_name
            )
        )


    @staticmethod
    def _analysis_view_name(
        table_name: str,
    ) -> str:

        return (
            "__analysis_"
            + table_name
        )


    @staticmethod
    def _effective_minimum_records(
        definition:
            MetricDefinition,
        requested:
            int
            | None,
    ) -> int:

        protected = (
            definition
            .default_minimum_records
            or 1
        )


        if requested is None:

            return protected


        if requested < 1:

            raise ValueError(
                "minimum_records must be >= 1."
            )


        # Caller may strengthen but never weaken
        # protected metric evidence policy.
        return max(
            protected,
            int(requested),
        )