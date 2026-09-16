from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from packages.contracts.question import (
    InterpretationStatus,
    Operation,
    QuestionInterpretation,
    QuestionSpecification,
)

from packages.question_router.router import (
    QuestionRouter,
    normalize_question_text,
)


# ============================================================
# CONVERSATION CONTEXT
# ============================================================

@dataclass(frozen=True)
class ConversationContext:

    last_interpretation: QuestionInterpretation


# ============================================================
# CONTEXTUAL LANGUAGE
# ============================================================

FOLLOW_UP_PREFIXES = (
    "what about",
    "how about",
    "and what about",
    "and how about",
    "same for",
    "show me",
    "show",
)


METRIC_SWITCH_PATTERNS = {
    "median_completed_yield": [
        "observed yield",
        "yield instead",
        "yields instead",
        "show yield",
        "show yields",
    ],

    "crop_grower_share": [
        "grower share",
        "crop prevalence",
        "how commonly",
        "commonly grown",
    ],

    "crop_seller_rate": [
        "seller participation",
        "seller rate",
        "selling instead",
    ],

    "median_commercialization_share": [
        "commercialization",
        "commercialisation",
        "commercialization share",
        "commercialisation share",
        "sales share",
        "share sold",
    ],

    "median_postharvest_loss_share": [
        "postharvest loss",
        "post harvest loss",
        "loss share",
    ],

    "median_household_consumption_share": [
        "consumption share",
        "household consumption",
        "consumed instead",
    ],
}


# ============================================================
# CONTEXTUAL QUESTION RESOLVER
# ============================================================

class ContextualQuestionResolver:

    def __init__(
        self,
        router: QuestionRouter,
    ):

        self.router = router


    # --------------------------------------------------------
    # Public resolution
    # --------------------------------------------------------

    def resolve(
        self,
        question: str,
        context: ConversationContext | None,
    ) -> QuestionInterpretation | None:

        if context is None:

            return None


        previous = (
            context.last_interpretation
        )


        if (
            previous.status
            != InterpretationStatus.INTERPRETED
            or previous.question_specification
            is None
        ):

            return None


        normalized = (
            normalize_question_text(
                question
            )
        )

        # ----------------------------------------------------
        # Methodological / meta follow-ups
        #
        # These questions ask about the interpretation of the
        # previous result rather than requesting a new metric.
        #
        # Example:
        # "Is that an actual weather forecast?"
        # ----------------------------------------------------

        previous_specification = (
            previous.question_specification
        )


        forecast_methodology_follow_up = (
            previous_specification
            is not None
            and
            previous_specification.metric_id
            == "climate_likely_share"
            and
            any(
                phrase in normalized
                for phrase in (
                    "actual weather forecast",
                    "weather forecast",
                    "meteorological forecast",
                    "is that a forecast",
                    "is this a forecast",
                )
            )
        )


        if forecast_methodology_follow_up:

            definition = (
                self.router.registry.get(
                    previous_specification.metric_id
                )
            )


            caution = (
                definition.caution
                or (
                    "This metric represents community "
                    "expectations of climate risk, not "
                    "a meteorological forecast."
                )
            )


            return QuestionInterpretation(
                question=
                    question,

                normalized_question=
                    normalized,

                status=
                    InterpretationStatus
                    .CONTEXTUAL_INFO,

                metric_id=
                    None,

                operation=
                    None,

                group_by=
                    None,

                filters=
                    {},

                entities=
                    previous.entities,

                metric_candidates=
                    [],

                support_flags=[
                    "methodological_follow_up"
                ],

                reason=(
                    "No. "
                    + caution
                ),

                suggested_reframe=
                    None,

                question_specification=
                    None,
            )


        new_entities = (
            self.router.detect_entities(
                question
            )
        )


        metric_switch = (
            self._detect_metric_switch(
                normalized
            )
        )
        
        # ----------------------------------------------------
        # Standalone interpretation
        #
        # A conversational follow-up can introduce a new
        # analytical metric while relying on prior entities.
        #
        # Example:
        # "How much of it do farmers usually sell?"
        #
        # Standalone routing can identify commercialization,
        # while conversation context supplies RICE + Kaduna.
        # ----------------------------------------------------

        standalone_interpretation = (
            self.router.interpret(
                question
            )
        )


        standalone_specification = (
            standalone_interpretation
            .question_specification
            if (
                standalone_interpretation.status
                == InterpretationStatus.INTERPRETED
                and
                standalone_interpretation
                .question_specification
                is not None
            )
            else None
        )


        if not self._looks_like_follow_up(
            normalized,
            new_entities,
            metric_switch,
        ):

            return None


        previous_spec = (
            previous.question_specification
        )


        direct_entity_follow_up = (
            self._is_entity_follow_up(
                normalized
            )
        )

        comparison_reference_follow_up = (
            "compare them"
            in normalized
            or
            "compare those"
            in normalized
            or
            "compare the two"
            in normalized
        )

        effective_metric_switch = (
            None
            if comparison_reference_follow_up
            else metric_switch
        )
        
        standalone_metric_id = (
            standalone_specification.metric_id
            if standalone_specification
            is not None
            else None
        )

        
        metric_id = (
            effective_metric_switch
            or (
                None
                if (
                    direct_entity_follow_up
                    or
                    comparison_reference_follow_up
                )
                else standalone_metric_id
            )
            or previous_spec.metric_id
        )


        if not self.router.registry.contains(
            metric_id
        ):

            return None


        filters = dict(
            previous_spec.filters
        )


        # ----------------------------------------------------
        # Apply only entity dimensions that are analytically
        # valid for the resolved target metric.
        #
        # A word such as "maize" may resolve both to the crop
        # MAIZE and to community-price items such as shelled
        # maize. Those item entities must not leak into crop,
        # production or commercialization metrics.
        # ----------------------------------------------------

        allowed_entity_dimensions = {
            "state",
            "zone",
        }


        if (
            metric_id
            == "median_same_basis_price_change"
        ):

            allowed_entity_dimensions.add(
                "item"
            )

        else:

            allowed_entity_dimensions.add(
                "crop"
            )


        if metric_id in {
            "climate_likely_share",
            "adaptation_no_action_share",
        }:

            allowed_entity_dimensions.add(
                "climate_event"
            )


        for dimension in (
            allowed_entity_dimensions
        ):

            if dimension not in new_entities:

                continue


            values = (
                new_entities[
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

        filters = {
            key: value
            for key, value
            in filters.items()
            if key
            in allowed_entity_dimensions
                }
        
        operation = (
            previous_spec.operation
        )

        group_by = (
            previous_spec.group_by
        )

        top_n = (
            previous_spec.top_n
        )

        ascending = (
            previous_spec.ascending
        )


        # ----------------------------------------------------
        # Standalone analytical structure
        #
        # Use it when the follow-up introduces a genuinely
        # new analytical structure.
        #
        # Example:
        # "Which of those states gets the best rice yields?"
        # → rank states by yield.
        #
        # Do NOT use it for:
        # "What about rice?"
        # because that is an entity substitution.
        # ----------------------------------------------------

        if (
            effective_metric_switch is None
            and standalone_specification
            is not None
            and not direct_entity_follow_up
            and not comparison_reference_follow_up
        ):

            operation = (
                standalone_specification
                .operation
            )

            group_by = (
                standalone_specification
                .group_by
            )

            top_n = (
                standalone_specification
                .top_n
            )

            ascending = (
                standalone_specification
                .ascending
            )


        # ----------------------------------------------------
        # Direct entity substitution
        #
        # Previous:
        # rank crops in Kaduna
        #
        # Follow-up:
        # "What about rice?"
        #
        # Result:
        # RICE value in Kaduna.
        #
        # Also supports:
        # rank states → "What about Kaduna?"
        # ----------------------------------------------------

        if (
            direct_entity_follow_up
            and effective_metric_switch is None
            and group_by is not None
            and group_by in new_entities
        ):

            operation = (
                Operation.VALUE
            )

            group_by = None

            top_n = None


        # ----------------------------------------------------
        # Explicit metric switch
        #
        # Preserve the previous analytical comparison
        # structure.
        #
        # Example:
        # rank RICE yield by state
        # → "Show seller participation instead"
        # → rank RICE seller participation by state.
        # ----------------------------------------------------

        if effective_metric_switch is not None:

            operation = (
                previous_spec.operation
            )

            group_by = (
                previous_spec.group_by
            )

            top_n = (
                previous_spec.top_n
            )

            ascending = (
                previous_spec.ascending
            )


        # ----------------------------------------------------
        # Merge entity memory
        # ----------------------------------------------------

        entities = {
            key: list(value)
            for key, value
            in previous.entities.items()
        }


        for key, value in (
            new_entities.items()
        ):

            entities[
                key
            ] = list(
                value
            )


        # ----------------------------------------------------
        # Build validated specification
        # ----------------------------------------------------

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
                    ascending,

                top_n=
                    top_n,

                minimum_records=
                    previous_spec.minimum_records,

                metric_version=
                    previous_spec.metric_version,
            )
        )


        return QuestionInterpretation(
            question=
                question,

            normalized_question=
                normalized,

            status=
                InterpretationStatus.INTERPRETED,

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

            metric_candidates=[
                metric_id
            ],

            support_flags=[],

            reason=None,

            suggested_reframe=None,

            question_specification=
                specification,
        )


    # ========================================================
    # FOLLOW-UP DETECTION
    # ========================================================

    @staticmethod
    def _looks_like_follow_up(
        normalized: str,
        entities:
            dict[
                str,
                list[str]
            ],
        metric_switch:
            str | None,
    ) -> bool:

        # ----------------------------------------------------
        # Explicit comparative-reference continuations
        #
        # These phrases depend on an existing comparison
        # established by the previous turn.
        # ----------------------------------------------------

        if any(
            phrase in normalized
            for phrase in (
                "compare them",
                "compare those",
                "compare the two",
            )
        ):

            return True

        if any(
            normalized.startswith(
                prefix
            )
            for prefix
            in FOLLOW_UP_PREFIXES
        ):

            return True


        if "instead" in normalized:

            return True


        if metric_switch is not None:

            return True


        # Short entity-only continuation:
        #
        # "Kaduna?"
        # "Maize?"
        #
        word_count = len(
            normalized.split()
        )


        if (
            entities
            and word_count <= 4
        ):

            return True

        # ----------------------------------------------------
        # Safe referential continuations
        # ----------------------------------------------------

        if (
            "of it"
            in normalized
            or
            "those states"
            in normalized
        ):

            return True
            

        return False


    @staticmethod
    def _is_entity_follow_up(
        normalized: str,
    ) -> bool:

        return (
            normalized.startswith(
                "what about"
            )
            or normalized.startswith(
                "how about"
            )
            or normalized.startswith(
                "and what about"
            )
            or normalized.startswith(
                "and how about"
            )
        )


    # ========================================================
    # METRIC SWITCH DETECTION
    # ========================================================

    @staticmethod
    def _detect_metric_switch(
        normalized: str,
    ) -> str | None:

        matches = []


        for (
            metric_id,
            phrases
        ) in (
            METRIC_SWITCH_PATTERNS.items()
        ):

            for phrase in phrases:

                normalized_phrase = (
                    normalize_question_text(
                        phrase
                    )
                )


                if (
                    normalized_phrase
                    in normalized
                ):

                    matches.append(
                        metric_id
                    )

                    break


        matches = list(
            dict.fromkeys(
                matches
            )
        )


        if len(matches) == 1:

            return matches[0]


        return None