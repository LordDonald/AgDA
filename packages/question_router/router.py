from __future__ import annotations

import re
from typing import Any

import duckdb

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.contracts.question import (
    InterpretationStatus,
    Operation,
    QuestionInterpretation,
    QuestionSpecification,
)

from packages.question_router.config import (
    CLIMATE_ALIAS_ADDITIONS,
    GROUP_PATTERNS,
    METRIC_LANGUAGE,
    RANKING_TERMS,
    UNSUPPORTED_LANGUAGE,
)


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_question_text(
    question: Any,
) -> str:

    if question is None:

        return ""


    text = (
        str(question)
        .strip()
        .casefold()
    )


    text = (
        text
        .replace(
            "’",
            "'"
        )
        .replace(
            "‘",
            "'"
        )
    )


    text = re.sub(
        r"[^a-z0-9%+/<>\-']+",
        " ",
        text,
    )


    text = text.replace(
        "-",
        " "
    )


    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def clean_survey_label(
    value: Any,
) -> str | None:

    if value is None:

        return None


    return re.sub(
        r"^\d+\.\s*",
        "",
        str(value).strip(),
    )


# ============================================================
# ENTITY ALIASES
# ============================================================

def generate_entity_aliases(
    value: Any,
) -> set[str]:

    if value is None:

        return set()


    original = str(
        value
    ).strip()


    aliases = {
        normalize_question_text(
            original
        )
    }


    without_parentheses = (
        re.sub(
            r"\([^)]*\)",
            " ",
            original,
        )
    )


    aliases.add(
        normalize_question_text(
            without_parentheses
        )
    )


    for part in re.findall(
        r"\(([^)]*)\)",
        original,
    ):

        aliases.add(
            normalize_question_text(
                part
            )
        )


    for part in re.split(
        r"[/,()]",
        original,
    ):

        cleaned = (
            normalize_question_text(
                part
            )
        )

        if cleaned:

            aliases.add(
                cleaned
            )


    return {
        alias
        for alias
        in aliases
        if alias
    }


def phrase_in_question(
    alias: str,
    normalized_question: str,
) -> bool:

    pattern = (
        r"(?<!\w)"
        + re.escape(
            alias
        )
        + r"(?!\w)"
    )


    return bool(
        re.search(
            pattern,
            normalized_question,
        )
    )


# ============================================================
# QUESTION ROUTER
# ============================================================

class QuestionRouter:

    def __init__(
        self,
        connection:
            duckdb.DuckDBPyConnection,

        registry:
            MetricRegistry,

        metric_version: str,
    ):

        self.connection = connection

        self.registry = registry

        self.metric_version = (
            metric_version
        )

        self.entity_alias_indexes = (
            self._build_entity_indexes()
        )


    # ========================================================
    # ENTITY CATALOGS
    # ========================================================

    def _build_entity_indexes(
        self,
    ) -> dict[
        str,
        dict[
            str,
            set[str]
        ]
    ]:

        state_df = (
            self.connection.execute(
                """
                SELECT *
                FROM state_entity_catalog
                """
            ).fetchdf()
        )


        zone_df = (
            self.connection.execute(
                """
                SELECT *
                FROM zone_entity_catalog
                """
            ).fetchdf()
        )


        crop_df = (
            self.connection.execute(
                """
                SELECT *
                FROM crop_entity_catalog
                """
            ).fetchdf()
        )


        item_df = (
            self.connection.execute(
                """
                SELECT *
                FROM item_entity_catalog
                """
            ).fetchdf()
        )


        climate_df = (
            self.connection.execute(
                """
                SELECT *
                FROM climate_event_catalog
                """
            ).fetchdf()
        )


        indexes = {
            "state":
                self._build_alias_index(
                    state_df,
                    self._canonical_column(
                        state_df,
                        [
                            "state_name",
                            "state_label",
                        ],
                    ),
                ),

            "zone":
                self._build_alias_index(
                    zone_df,
                    self._canonical_column(
                        zone_df,
                        [
                            "zone_name",
                            "zone_label",
                        ],
                    ),
                ),

            "crop":
                self._build_alias_index(
                    crop_df,
                    "crop_name",
                ),

            "item":
                self._build_alias_index(
                    item_df,
                    "item_name",
                ),

            "climate_event":
                self._build_alias_index(
                    climate_df,
                    "climate_event",
                ),
        }


        for alias, canonical in (
            CLIMATE_ALIAS_ADDITIONS.items()
        ):

            normalized_alias = (
                normalize_question_text(
                    alias
                )
            )


            indexes[
                "climate_event"
            ].setdefault(
                normalized_alias,
                set(),
            ).add(
                canonical
            )


        return indexes


    @staticmethod
    def _canonical_column(
        dataframe,
        candidates:
            list[str],
    ) -> str:

        for column in candidates:

            if column in dataframe.columns:

                return column


        raise KeyError(
            f"No canonical entity column "
            f"found among: {candidates}"
        )


    @staticmethod
    def _build_alias_index(
        dataframe,
        canonical_column: str,
    ) -> dict[
        str,
        set[str]
    ]:

        index = {}


        for canonical_value in (
            dataframe[
                canonical_column
            ]
            .dropna()
            .unique()
        ):

            cleaned_canonical = (
                clean_survey_label(
                    canonical_value
                )
            )


            for alias in (
                generate_entity_aliases(
                    cleaned_canonical
                )
            ):

                index.setdefault(
                    alias,
                    set(),
                ).add(
                    cleaned_canonical
                )


        return index


    # ========================================================
    # ENTITY DETECTION
    # ========================================================

    def detect_entities(
        self,
        question: str,
    ) -> dict[
        str,
        list[str]
    ]:

        normalized = (
            normalize_question_text(
                question
            )
        )


        detected = {}


        for entity_type, alias_index in (
            self.entity_alias_indexes.items()
        ):

            matches = []


            aliases = sorted(
                alias_index.keys(),
                key=len,
                reverse=True,
            )


            for alias in aliases:

                if phrase_in_question(
                    alias,
                    normalized,
                ):

                    matches.extend(
                        sorted(
                            alias_index[
                                alias
                            ]
                        )
                    )


            unique_matches = (
                list(
                    dict.fromkeys(
                        matches
                    )
                )
            )


            if unique_matches:

                detected[
                    entity_type
                ] = unique_matches


        return detected


    # ========================================================
    # SAFETY / SUPPORT FLAGS
    # ========================================================

    def detect_support_flags(
        self,
        question: str,
    ) -> list[str]:

        normalized = (
            normalize_question_text(
                question
            )
        )


        flags = []


        for category, phrases in (
            UNSUPPORTED_LANGUAGE.items()
        ):

            for phrase in phrases:

                if phrase_in_question(
                    normalize_question_text(
                        phrase
                    ),
                    normalized,
                ):

                    flags.append(
                        category
                    )

                    break


        return list(
            dict.fromkeys(
                flags
            )
        )


    # ========================================================
    # METRIC SCORING
    # ========================================================

    def score_metric_intents(
        self,
        question: str,
    ) -> list[
        dict[str, Any]
    ]:

        normalized = (
            normalize_question_text(
                question
            )
        )


        scored = []


        for metric_id, language in (
            METRIC_LANGUAGE.items()
        ):

            if not self.registry.contains(
                metric_id
            ):

                continue


            score = 0

            matched_phrases = []

            matched_keywords = []


            for phrase in language.get(
                "phrases",
                []
            ):

                normalized_phrase = (
                    normalize_question_text(
                        phrase
                    )
                )


                if phrase_in_question(
                    normalized_phrase,
                    normalized,
                ):

                    score += 4

                    matched_phrases.append(
                        phrase
                    )


            for keyword in language.get(
                "keywords",
                []
            ):

                normalized_keyword = (
                    normalize_question_text(
                        keyword
                    )
                )


                if phrase_in_question(
                    normalized_keyword,
                    normalized,
                ):

                    score += 1

                    matched_keywords.append(
                        keyword
                    )


            if score > 0:

                scored.append({
                    "metric_id":
                        metric_id,

                    "score":
                        score,

                    "matched_phrases":
                        matched_phrases,

                    "matched_keywords":
                        matched_keywords,
                })


        return sorted(
            scored,
            key=lambda item: (
                -item["score"],
                item["metric_id"],
            ),
        )


    # ========================================================
    # METRIC SELECTION
    # ========================================================

    def choose_metric_candidate(
        self,
        question: str,
        entities:
            dict[
                str,
                list[str]
            ],
    ) -> dict[str, Any]:

        normalized = (
            normalize_question_text(
                question
            )
        )


        # ----------------------------------------------
        # Climate adaptation
        # ----------------------------------------------

        adaptation_patterns = [
            "no adaptation action",
            "no action on climate",
            "taking no action",
            "do nothing about climate",
            "no action",
        ]


        if any(
            phrase_in_question(
                normalize_question_text(
                    pattern
                ),
                normalized,
            )
            for pattern
            in adaptation_patterns
        ):

            return {
                "metric_id":
                    "adaptation_no_action_share",

                "status":
                    "metric_detected",

                "candidates": [
                    "adaptation_no_action_share"
                ],
            }


        # ----------------------------------------------
        # Entity-aware climate risk
        # ----------------------------------------------

        climate_risk_terms = [
            "risk",
            "risky",
            "likely",
            "likelihood",
            "chance",
            "expected",
            "expect",
            "occur",
            "occurrence",
        ]


        if (
            "climate_event"
            in entities
            and any(
                phrase_in_question(
                    normalize_question_text(
                        term
                    ),
                    normalized,
                )
                for term
                in climate_risk_terms
            )
        ):

            return {
                "metric_id":
                    "climate_likely_share",

                "status":
                    "metric_detected",

                "candidates": [
                    "climate_likely_share"
                ],
            }


        # ----------------------------------------------
        # "How much ... sell?"
        # ----------------------------------------------

        if (
            "how much"
            in normalized
            and re.search(
                r"\b(sell|sold|selling)\b",
                normalized,
            )
        ):

            return {
                "metric_id":
                    "median_commercialization_share",

                "status":
                    "metric_detected",

                "candidates": [
                    "median_commercialization_share"
                ],
            }


        # ----------------------------------------------
        # Seller participation
        # ----------------------------------------------

        seller_patterns = [
            r"\bhow many farmers sell\b",
            r"\bwhat percentage of farmers sell\b",
            r"\bwhat share of farmers sell\b",
            r"\bseller rate\b",
            r"\bseller participation\b",
            r"\bmarket participation\b",
        ]


        if any(
            re.search(
                pattern,
                normalized,
            )
            for pattern
            in seller_patterns
        ):

            return {
                "metric_id":
                    "crop_seller_rate",

                "status":
                    "metric_detected",

                "candidates": [
                    "crop_seller_rate"
                ],
            }


        # ----------------------------------------------
        # Yield/productivity
        # ----------------------------------------------

        if re.search(
            r"\b(yield|yields|productivity)\b",
            normalized,
        ):

            if any(
                phrase in normalized
                for phrase in [
                    "high confidence",
                    "reliable yield",
                    "gps measured",
                    "strongest yield evidence",
                ]
            ):

                metric_id = (
                    "median_high_confidence_yield"
                )

            else:

                metric_id = (
                    "median_completed_yield"
                )


            return {
                "metric_id":
                    metric_id,

                "status":
                    "metric_detected",

                "candidates": [
                    metric_id
                ],
            }


        # ----------------------------------------------
        # General scoring
        # ----------------------------------------------

        scores = (
            self.score_metric_intents(
                question
            )
        )


        if not scores:

            return {
                "metric_id":
                    None,

                "status":
                    "no_metric_detected",

                "candidates":
                    [],
            }


        top_score = (
            scores[0]["score"]
        )


        top_candidates = [
            item["metric_id"]
            for item
            in scores
            if item["score"]
            == top_score
        ]


        if len(top_candidates) > 1:

            return {
                "metric_id":
                    None,

                "status":
                    "ambiguous_metric",

                "candidates":
                    top_candidates,
            }


        return {
            "metric_id":
                top_candidates[0],

            "status":
                "metric_detected",

            "candidates": [
                item["metric_id"]
                for item
                in scores[:5]
            ],
        }


    # ========================================================
    # OPERATION / GROUP
    # ========================================================

    def detect_operation_and_group(
        self,
        question: str,
    ) -> dict[str, Any]:

        normalized = (
            normalize_question_text(
                question
            )
        )


        group_by = None
        
        extension_yield_comparison_language = (
            (
                "extension"
                in normalized
                or
                "extension advice"
                in normalized
            )
            and
            any(
                phrase in normalized
                for phrase in (
                    "yield",
                    "yields",
                    "productivity",
                )
            )
            and
            any(
                phrase in normalized
                for phrase in (
                    "better",
                    "higher",
                    "compare",
                    "difference",
                )
            )
        )


        for dimension, patterns in (
            GROUP_PATTERNS.items()
        ):

            if any(
                phrase_in_question(
                    normalize_question_text(
                        pattern
                    ),
                    normalized,
                )
                for pattern
                in patterns
            ):

                group_by = dimension

                break


        operation = (
            Operation.VALUE
        )


        # --------------------------------------------------------
        # Natural-language ranking / grouping cues
        # --------------------------------------------------------
    
        crop_prevalence_language = any(
            phrase in normalized
            for phrase in (
                "mostly growing",
                "grow most",
                "grown most",
                "most commonly grown",
                "commonly grown",
            )
        )
    
    
        geographic_ranking_language = (
            normalized.startswith(
                "where "
            )
            or
            "which state"
            in normalized
            or
            "which states"
            in normalized
            or
            "those states"
            in normalized
            or
            "by state"
            in normalized
        )
    
    
        climate_event_ranking_language = (
            any(
                phrase in normalized
                for phrase in (
                    "climate threat",
                    "climate risk",
                    "climate event",
                )
            )
            and
            any(
                phrase in normalized
                for phrase in (
                    "highest",
                    "biggest",
                    "most",
                    "top",
                )
            )
        )
    
    
        # --------------------------------------------------------
        # Choose the comparison dimension.
        #
        # Explicit geographic/climate language has precedence
        # over the generic crop-prevalence fallback.
        # --------------------------------------------------------
    
        if extension_yield_comparison_language:

            group_by = (
                "planting_extension"
            )


        elif climate_event_ranking_language:

            group_by = (
                "climate_event"
            )
    
    
        elif geographic_ranking_language:
    
            group_by = (
                "state"
            )
    
    
        elif (
            crop_prevalence_language
            and group_by is None
        ):
    
            group_by = (
                "crop"
            )
    
    
        # --------------------------------------------------------
        # Choose the operation.
        # --------------------------------------------------------
    
        if extension_yield_comparison_language:

            operation = (
                Operation.GROUP
            )
            
        
        elif (
            crop_prevalence_language
            or geographic_ranking_language
            or climate_event_ranking_language
            or any(
                term in normalized
                for term
                in RANKING_TERMS
            )
        ):
    
            operation = (
                Operation.RANK
            )
    
    
        elif group_by is not None:
    
            operation = (
                Operation.GROUP
            )
            
        return {
            "operation":
                operation,
    
            "group_by":
                group_by,
        }


    # ========================================================
    # FULL INTERPRETATION
    # ========================================================

    def interpret(
        self,
        question: str,
    ) -> QuestionInterpretation:

        normalized = (
            normalize_question_text(
                question
            )
        )


        entities = (
            self.detect_entities(
                question
            )
        )


        support_flags = (
            self.detect_support_flags(
                question
            )
        )


        # ----------------------------------------------
        # Unsupported: profitability
        # ----------------------------------------------

        if (
            "profitability"
            in support_flags
        ):

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .UNSUPPORTED,

                entities=
                    entities,

                support_flags=
                    support_flags,

                reason=(
                    "Profitability cannot be calculated "
                    "reliably because complete production-cost "
                    "and margin data are unavailable."
                ),
            )


        # ----------------------------------------------
        # Causal reframe
        # ----------------------------------------------

        if "causal" in support_flags:

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .REFRAME_REQUIRED,

                entities=
                    entities,

                support_flags=
                    support_flags,

                reason=(
                    "The available survey supports "
                    "descriptive and associational "
                    "comparisons, not causal claims."
                ),

                suggested_reframe=(
                    "Compare the observed outcome "
                    "across the relevant groups "
                    "without claiming that one caused "
                    "the other."
                ),
            )


        # ----------------------------------------------
        # Prescriptive reframe
        # ----------------------------------------------

        if (
            "recommendation"
            in support_flags
        ):

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .REFRAME_REQUIRED,

                entities=
                    entities,

                support_flags=
                    support_flags,

                reason=(
                    "The survey can provide an evidence "
                    "profile but cannot by itself determine "
                    "what an individual farmer should plant."
                ),

                suggested_reframe=(
                    "Summarize crop prevalence, observed "
                    "yield, commercialization, price context "
                    "and climate conditions for the requested "
                    "geography."
                ),
            )


        metric_detection = (
            self.choose_metric_candidate(
                question,
                entities,
            )
        )


        operation_info = (
            self.detect_operation_and_group(
                question
            )
        )


        if (
            metric_detection[
                "status"
            ]
            == "no_metric_detected"
        ):

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .NEEDS_CLARIFICATION,

                entities=
                    entities,

                support_flags=
                    support_flags,

                metric_candidates=
                    [],

                reason=(
                    "No supported analytical metric "
                    "was identified."
                ),
            )


        if (
            metric_detection[
                "status"
            ]
            == "ambiguous_metric"
        ):

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .NEEDS_CLARIFICATION,

                entities=
                    entities,

                support_flags=
                    support_flags,

                metric_candidates=
                    metric_detection[
                        "candidates"
                    ],

                reason=(
                    "More than one analytical metric "
                    "fits the wording."
                ),
            )


        metric_id = (
            metric_detection[
                "metric_id"
            ]
        )


        operation = (
            operation_info[
                "operation"
            ]
        )


        group_by = (
            operation_info[
                "group_by"
            ]
        )


        filters = {}


        # ----------------------------------------------
        # Geography
        # ----------------------------------------------

        for dimension in [
            "state",
            "zone",
        ]:

            if dimension in entities:

                values = (
                    entities[
                        dimension
                    ]
                )


                filters[
                    dimension
                ] = (
                    values[0]
                    if len(values) == 1
                    else values
                )


        # ----------------------------------------------
        # Price metric uses item entity
        # ----------------------------------------------

        if (
            metric_id
            == "median_same_basis_price_change"
        ):

            if "item" in entities:

                values = (
                    entities[
                        "item"
                    ]
                )


                filters[
                    "item"
                ] = (
                    values[0]
                    if len(values) == 1
                    else values
                )


        # ----------------------------------------------
        # Production/commercialization uses crop
        # ----------------------------------------------

        else:

            if (
                "crop"
                in entities
                and group_by != "crop"
            ):

                values = (
                    entities[
                        "crop"
                    ]
                )


                filters[
                    "crop"
                ] = (
                    values[0]
                    if len(values) == 1
                    else values
                )


        # ----------------------------------------------
        # Climate event
        # ----------------------------------------------

        if (
            metric_id
            in {
                "climate_likely_share",
                "adaptation_no_action_share",
            }
            and
            "climate_event"
            in entities
            and group_by
            != "climate_event"
        ):

            values = (
                entities[
                    "climate_event"
                ]
            )


            filters[
                "climate_event"
            ] = (
                values[0]
                if len(values) == 1
                else values
            )


        # ----------------------------------------------
        # Helpful default grouping
        # ----------------------------------------------

        if (
            operation
            == Operation.RANK
            and group_by is None
        ):

            if metric_id in {
                "crop_grower_share",
                "median_completed_yield",
                "median_high_confidence_yield",
                "crop_seller_rate",
                "median_commercialization_share",
                "median_household_consumption_share",
                "median_postharvest_loss_share",
            }:

                group_by = "crop"


            elif (
                metric_id
                == "climate_likely_share"
            ):

                group_by = (
                    "climate_event"
                )


        if (
            operation
            == Operation.RANK
            and group_by is None
        ):

            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .NEEDS_CLARIFICATION,

                metric_id=
                    metric_id,

                entities=
                    entities,

                metric_candidates=
                    metric_detection[
                        "candidates"
                    ],

                support_flags=
                    support_flags,

                reason=(
                    "A ranking was requested, "
                    "but the dimension to rank "
                    "could not be determined."
                ),
            )


        specification = (
            QuestionSpecification(
                metric_id=
                    metric_id,

                operation=
                    operation,

                filters=
                    filters,

                group_by=
                    group_by,

                ascending=
                    any(
                        term
                        in normalized.split()
                        for term in [
                            "lowest",
                            "least",
                            "worst",
                            "weakest",
                        ]
                    ),

                top_n=(
                    10
                    if operation
                    == Operation.RANK
                    else None
                ),

                minimum_records=
                    None,

                metric_version=
                    self.metric_version,
            )
        )


        return QuestionInterpretation(
            question=
                question,

            normalized_question=
                normalized,

            status=
                InterpretationStatus
                .INTERPRETED,

            metric_id=
                metric_id,

            operation=
                operation,

            group_by=
                group_by,

            filters=
                filters,

            entities=
                entities,

            metric_candidates=
                metric_detection[
                    "candidates"
                ],

            support_flags=
                support_flags,

            question_specification=
                specification,
        )