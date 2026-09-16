from __future__ import annotations

from dataclasses import asdict
from typing import Any

from packages.analytics.executor import (
    ScalarMetricResult,
    TableMetricResult,
)

from packages.answering.pipeline import (
    QuestionPipeline,
    QuestionPipelineResult,
)

from packages.contracts.answer import (
    AgDAAnswer,
    ClarificationPayload,
    EvidencePayload,
    ReframePayload,
    VisualizationPayload,
)

from packages.question_router.conversation import (
    ConversationContext,
)


# ============================================================
# ANSWER SERVICE
# ============================================================

class AnswerService:

    def __init__(
        self,
        pipeline: QuestionPipeline,
        data_version: str,
        metric_version: str,
    ):

        self.pipeline = pipeline

        self.data_version = data_version

        self.metric_version = metric_version


    # ========================================================
    # PUBLIC API
    # ========================================================

    def answer(
        self,
        question: str,
        max_rank_items: int = 5,
        context: ConversationContext | None = None,
    ) -> AgDAAnswer:

        answer, _ = (
            self.answer_with_pipeline_result(
                question=
                    question,

                max_rank_items=
                    max_rank_items,

                context=
                    context,
            )
        )

        return answer


    def answer_with_pipeline_result(
        self,
        question: str,
        max_rank_items: int = 5,
        context: ConversationContext | None = None,
    ) -> tuple[
        AgDAAnswer,
        QuestionPipelineResult,
    ]:

        pipeline_result = (
            self.pipeline.run(
                question=
                    question,

                context=
                    context,
            )
        )


        if pipeline_result.status == "answered":

            answer = self._compose_answered(
                pipeline_result,
                max_rank_items=
                    max_rank_items,
            )


        elif (
            pipeline_result.status
            == "contextual_info"
        ):

            answer = (
                self._compose_contextual_info(
                    pipeline_result
                )
            )


        elif (
            pipeline_result.status
            == "needs_clarification"
        ):

            answer = self._compose_clarification(
                pipeline_result
            )


        elif (
            pipeline_result.status
            == "reframe_required"
        ):

            answer = self._compose_reframe(
                pipeline_result
            )


        elif (
            pipeline_result.status
            == "unsupported"
        ):

            answer = self._compose_unsupported(
                pipeline_result
            )


        else:

            raise RuntimeError(
                f"Unhandled pipeline status: "
                f"{pipeline_result.status}"
            )


        return (
            answer,
            pipeline_result,
        )


    # ========================================================
    # ANSWERED QUESTION
    # ========================================================

    def _compose_answered(
        self,
        pipeline_result: QuestionPipelineResult,
        max_rank_items: int,
    ) -> AgDAAnswer:

        result = pipeline_result.result

        if isinstance(
            result,
            ScalarMetricResult,
        ):

            return self._compose_scalar(
                pipeline_result,
                result,
            )


        if isinstance(
            result,
            TableMetricResult,
        ):

            return self._compose_table(
                pipeline_result,
                result,
                max_rank_items=max_rank_items,
            )


        raise RuntimeError(
            "Answered pipeline result has "
            "no analytical result."
        )


    # ========================================================
    # SCALAR ANSWERS
    # ========================================================

    def _compose_scalar(
        self,
        pipeline_result: QuestionPipelineResult,
        result: ScalarMetricResult,
    ) -> AgDAAnswer:

        interpretation = (
            pipeline_result.interpretation
        )


        formatted_value = self._format_value(
            result.value,
            result.unit,
        )


        context = self._geography_context(
            result.filters
        )


        crop = result.filters.get(
            "crop"
        )

        item = result.filters.get(
            "item"
        )

        climate_event = result.filters.get(
            "climate_event"
        )


        # ----------------------------------------------------
        # Metric-specific language
        # ----------------------------------------------------

        if result.metric_id == "household_crop_participation_rate":

            headline = (
                f"About {formatted_value} of households "
                f"{context} participated in crop cultivation."
            )


        elif result.metric_id == "crop_grower_share":

            headline = (
                f"About {formatted_value} of crop-growing households "
                f"{context} grew {crop}."
            )


        elif result.metric_id == "median_plot_area_ha":

            headline = (
                f"The median cultivated plot area "
                f"{context} was {formatted_value}."
            )


        elif result.metric_id in {
            "median_completed_yield",
            "median_high_confidence_yield",
        }:

            crop_text = (
                f"{crop} "
                if crop
                else ""
            )

            headline = (
                f"The median {crop_text}yield "
                f"{context} was {formatted_value} "
                "among eligible harvest records."
            )


        elif result.metric_id == "harvest_completion_rate":

            headline = (
                f"About {formatted_value} of harvested crop records "
                f"{context} were reported complete at interview."
            )


        elif result.metric_id == "crop_seller_rate":

            crop_text = (
                f" for {crop}"
                if crop
                else ""
            )

            headline = (
                f"Estimated seller participation{crop_text} "
                f"{context} was {formatted_value}."
            )


        elif result.metric_id == "median_commercialization_share":

            crop_text = (
                crop
                if crop
                else "crop"
            )

            headline = (
                f"The median share of reported {crop_text} harvest "
                f"commercialized {context} was {formatted_value}."
            )


        elif result.metric_id == "median_household_consumption_share":

            headline = (
                f"The median share of harvest consumed by households "
                f"{context} was {formatted_value}."
            )


        elif result.metric_id == "median_postharvest_loss_share":

            headline = (
                f"The median reported post-harvest loss share "
                f"{context} was {formatted_value}."
            )


        elif result.metric_id in {
            "pp_food_insecurity_count",
            "ph_food_insecurity_count",
        }:

            visit = (
                "post-planting"
                if result.metric_id
                == "pp_food_insecurity_count"
                else "post-harvest"
            )

            headline = (
                f"The weighted average {visit} food-insecurity "
                f"experience count {context} was {formatted_value} "
                "on the descriptive 0–8 scale."
            )


        elif result.metric_id == "food_insecurity_change":

            if result.value is None:

                headline = (
                    "The food-security change could not be calculated."
                )

            elif result.value < 0:

                headline = (
                    "The weighted post-harvest food-insecurity "
                    f"experience count {context} was about "
                    f"{abs(result.value):.2f} points lower "
                    "than at post-planting."
                )

            elif result.value > 0:

                headline = (
                    "The weighted post-harvest food-insecurity "
                    f"experience count {context} was about "
                    f"{result.value:.2f} points higher "
                    "than at post-planting."
                )

            else:

                headline = (
                    "The weighted food-insecurity experience count "
                    f"{context} showed no average change between visits."
                )


        elif result.metric_id == "planting_extension_access_rate":

            headline = (
                f"About {formatted_value} of households "
                f"{context} received planting-season extension advice."
            )


        elif result.metric_id == "farm_information_access_rate":

            headline = (
                f"About {formatted_value} of households "
                f"{context} sought or received farm information."
            )


        elif result.metric_id == "median_same_basis_price_change":

            item_text = (
                f" for {item}"
                if item
                else ""
            )

            headline = (
                "The median same-measurement-basis community "
                f"price change{item_text} {context} "
                f"was {formatted_value}."
            )


        elif result.metric_id == "climate_likely_share":

            event_text = (
                climate_event
                if climate_event
                else "the climate event"
            )

            headline = (
                f"{formatted_value} of sampled community assessments "
                f"{context} rated {event_text} as likely "
                "or extremely likely."
            )


        elif result.metric_id == "adaptation_no_action_share":

            headline = (
                f"{formatted_value} of eligible climate-event records "
                f"{context} reported no planned or taken "
                "adaptation action."
            )


        else:

            headline = (
                f"{result.metric_name}: "
                f"{formatted_value}."
            )


        evidence = self._scalar_evidence(
            result
        )


        evidence_text = self._evidence_sentence(
            evidence
        )


        warnings = []

        if result.caution:

            warnings.append(
                result.caution
            )


        answer_text = (
            headline
            + " "
            + evidence_text
        )


        if result.caution:

            answer_text += (
                " "
                + result.caution
            )


        visualization = VisualizationPayload(
            recommended=False
        )


        return AgDAAnswer(
            status="answered",

            question=
                pipeline_result.question,

            answer_text=
                answer_text,

            question_specification=
                (
                    interpretation
                    .question_specification
                    .model_dump(
                        mode="json"
                    )
                    if interpretation
                    .question_specification
                    else None
                ),

            result={
                "value":
                    result.value,

                "unit":
                    result.unit,
            },

            evidence=
                evidence,

            visualization=
                visualization,

            clarification=
                None,

            reframe=
                None,

            warnings=
                warnings,

            data_version=
                self.data_version,

            metric_version=
                self.metric_version,
        )


    # ========================================================
    # TABLE / RANK ANSWERS
    # ========================================================

    def _compose_table(
        self,
        pipeline_result: QuestionPipelineResult,
        result: TableMetricResult,
        max_rank_items: int,
    ) -> AgDAAnswer:

        warnings = []
        
        comparison_caution = None

        max_rank_items = max(
            1,
            min(
                int(max_rank_items),
                10,
            ),
        )


        visible_rows = (
            result.rows[
                :max_rank_items
            ]
        )


        if not visible_rows:

            answer_text = (
                "The available data do not contain enough "
                "supporting observations for this comparison."
            )

        else:

            context = self._geography_context(
                result.filters
            )


            entries = []


            for row in visible_rows:

                group_value = row[
                    result.group_by
                ]

                value_text = self._format_value(
                    row.get(
                        "value"
                    ),
                    result.unit,
                )

                grade = row.get(
                    "evidence_grade",
                    "Unclassified"
                )

                records = row.get(
                    "records",
                    0
                )


                entries.append(
                    f"{group_value}: {value_text} "
                    f"({grade}; {records:,} records)"
                )


            if result.metric_id == "crop_grower_share":

                dimension_name = self._dimension_name(
                    result.group_by
                )
            
                intro = (
                    f"Among {dimension_name} meeting the evidence threshold "
                    f"{context}, the leading grower shares were"
                )


            elif (
                result.metric_id
                == "median_completed_yield"
                and result.group_by
                == "planting_extension"
            ):

                intro = (
                    "Among eligible completed-harvest records, "
                    "the observed median yields by reported "
                    "planting-season extension status were"
                )

                comparison_caution = (
                    "This is an unadjusted descriptive comparison. "
                    "Crop mix and other factors may differ between "
                    "households reporting extension and those not "
                    "reporting extension, so the observed difference "
                    "should not be interpreted as a causal effect "
                    "of extension."
                )

                warnings.append(
                    comparison_caution
                )


            elif result.metric_id in {
                "median_completed_yield",
                "median_high_confidence_yield",
            }:

                intro = (
                    "Among crops meeting the evidence threshold "
                    f"{context}, the highest observed median yields were"
                )


            elif result.metric_id == "crop_seller_rate":

                intro = (
                    "Among crops meeting the evidence threshold "
                    f"{context}, seller participation was highest for"
                )


            elif result.metric_id == "climate_likely_share":

                intro = (
                    f"Among assessed climate events {context}, "
                    "the highest shares rated likely or extremely likely were"
                )


            else:

                dimension_name = self._dimension_name(
                    result.group_by
                )

                intro = (
                    f"Among {dimension_name} meeting the evidence threshold "
                    f"{context}, the leading results were"
                )


            answer_text = (
                intro
                + ": "
                + "; ".join(
                    entries
                )
                + "."
            )


            if result.caution:

                answer_text += (
                    " "
                    + result.caution
                )
                

            if comparison_caution:

                answer_text += (
                    " "
                    + comparison_caution
                )


        if result.caution:

            warnings.append(
                result.caution
            )


        visualization = VisualizationPayload(
            recommended=
                bool(
                    visible_rows
                ),

            visual_type=(
                "horizontal_bar"
                if visible_rows
                else None
            ),

            title=(
                result.metric_name
                if visible_rows
                else None
            ),

            dimension=(
                result.group_by
                if visible_rows
                else None
            ),

            metric_id=(
                result.metric_id
                if visible_rows
                else None
            ),

            unit=(
                result.unit
                if visible_rows
                else None
            ),

            max_items=(
                len(
                    visible_rows
                )
                if visible_rows
                else None
            ),

            data=(
                visible_rows
                if visible_rows
                else None
            ),
        )


        specification = (
            pipeline_result
            .interpretation
            .question_specification
        )


        return AgDAAnswer(
            status="answered",

            question=
                pipeline_result.question,

            answer_text=
                answer_text,

            question_specification=(
                specification.model_dump(
                    mode="json"
                )
                if specification
                else None
            ),

            result=visible_rows,

            evidence=None,

            visualization=
                visualization,

            clarification=None,

            reframe=None,

            warnings=
                warnings,

            data_version=
                self.data_version,

            metric_version=
                self.metric_version,
        )


    # ========================================================
    # CONTEXTUAL / METHODOLOGICAL INFORMATION
    # ========================================================

    def _compose_contextual_info(
        self,
        pipeline_result:
            QuestionPipelineResult,
    ) -> AgDAAnswer:

        interpretation = (
            pipeline_result.interpretation
        )


        answer_text = (
            interpretation.reason
            or (
                "The previous result should be "
                "interpreted using its stated "
                "methodological limitations."
            )
        )


        return AgDAAnswer(
            status=
                "answered",

            question=
                pipeline_result.question,

            answer_text=
                answer_text,

            question_specification=
                None,

            result=
                None,

            evidence=
                None,

            visualization=
                None,

            clarification=
                None,

            reframe=
                None,

            warnings=
                [],

            data_version=
                self.data_version,

            metric_version=
                self.metric_version,
        )
    
    # ========================================================
    # CLARIFICATION
    # ========================================================

    def _compose_clarification(
        self,
        pipeline_result: QuestionPipelineResult,
    ) -> AgDAAnswer:

        interpretation = (
            pipeline_result.interpretation
        )


        crop = None

        if (
            "crop"
            in interpretation.entities
            and interpretation.entities[
                "crop"
            ]
        ):

            crop = (
                interpretation.entities[
                    "crop"
                ][0]
            )


        normalized = (
            interpretation
            .normalized_question
        )


        asks_state_comparison = any(
            phrase in normalized
            for phrase in [
                "which state",
                "what state",
                "best state",
                "strongest state",
            ]
        )


        options = []


        if crop and asks_state_comparison:

            options = [
                "observed yield",
                "how commonly the crop is grown",
                "seller participation",
                "commercialization share",
            ]


            prompt = (
                f"I can compare states for {crop} in several ways. "
                "Do you mean strongest by "
                + ", ".join(
                    options[:-1]
                )
                + f", or {options[-1]}?"
            )


        elif crop:

            options = [
                "observed yield",
                "how commonly the crop is grown",
                "seller participation",
                "commercialization share",
            ]


            prompt = (
                f"What aspect of {crop} performance "
                "do you want to compare: "
                + ", ".join(
                    options[:-1]
                )
                + f", or {options[-1]}?"
            )


        else:

            prompt = (
                interpretation.reason
                or
                "I can answer this in several ways. "
                "Which outcome or measure would you like me to compare?"
            )


        clarification = (
            ClarificationPayload(
                clarification_required=True,

                prompt=
                    prompt,

                options=
                    options,

                resolved_entities=
                    interpretation.entities,

                candidate_metrics=
                    interpretation.metric_candidates,
            )
        )


        return AgDAAnswer(
            status=
                "needs_clarification",

            question=
                pipeline_result.question,

            answer_text=
                prompt,

            question_specification=
                None,

            result=
                None,

            evidence=
                None,

            visualization=
                None,

            clarification=
                clarification,

            reframe=
                None,

            warnings=
                [],

            data_version=
                self.data_version,

            metric_version=
                None,
        )


    # ========================================================
    # REFRAME
    # ========================================================

    def _compose_reframe(
        self,
        pipeline_result: QuestionPipelineResult,
    ) -> AgDAAnswer:

        interpretation = (
            pipeline_result.interpretation
        )


        support_flags = (
            interpretation.support_flags
        )


        request_type = (
            support_flags[0]
            if support_flags
            else "unsupported_interpretation"
        )


        reason = (
            interpretation.reason
            or
            "The question cannot be answered as phrased."
        )


        alternative = (
            interpretation
            .suggested_reframe
        )


        answer_text = reason


        if alternative:

            answer_text += (
                " A supported alternative is to "
                + alternative[0].lower()
                + alternative[1:]
            )


        reframe = ReframePayload(
            original_request_type=
                request_type,

            reason=
                reason,

            supported_alternative=
                alternative,
        )


        return AgDAAnswer(
            status=
                "reframe_required",

            question=
                pipeline_result.question,

            answer_text=
                answer_text,

            question_specification=
                None,

            result=
                None,

            evidence=
                None,

            visualization=
                None,

            clarification=
                None,

            reframe=
                reframe,

            warnings=
                [],

            data_version=
                self.data_version,

            metric_version=
                None,
        )


    # ========================================================
    # UNSUPPORTED
    # ========================================================

    def _compose_unsupported(
        self,
        pipeline_result: QuestionPipelineResult,
    ) -> AgDAAnswer:

        reason = (
            pipeline_result
            .interpretation
            .reason
            or
            "The available data do not support "
            "this question reliably."
        )


        return AgDAAnswer(
            status=
                "unsupported",

            question=
                pipeline_result.question,

            answer_text=
                reason,

            question_specification=
                None,

            result=
                None,

            evidence=
                None,

            visualization=
                None,

            clarification=
                None,

            reframe=
                None,

            warnings=
                [],

            data_version=
                self.data_version,

            metric_version=
                None,
        )


    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _format_value(
        value: float | int | None,
        unit: str | None,
    ) -> str:

        if value is None:

            return "Unavailable"


        if unit == "proportion":

            return (
                f"{value * 100:.1f}%"
            )


        if unit == "%":

            return (
                f"{value:.1f}%"
            )


        if unit == "kg/ha":

            return (
                f"{value:,.1f} kg/ha"
            )


        if unit == "ha":

            return (
                f"{value:,.3f} ha"
            )


        if unit == "0-8 experiences":

            return (
                f"{value:.2f}"
            )


        if unit == "experience-count change":

            return (
                f"{value:+.2f}"
            )


        return (
            f"{value:,.2f}"
        )


    @staticmethod
    def _geography_context(
        filters: dict[str, Any],
    ) -> str:

        state = filters.get(
            "state"
        )

        zone = filters.get(
            "zone"
        )

        sector = filters.get(
            "sector"
        )


        if state:

            return (
                f"in {state}"
            )


        if zone:

            return (
                f"in the {zone}"
            )


        if sector:

            return (
                f"among {sector} households"
            )


        return (
            "in the analytical sample"
        )


    @staticmethod
    def _scalar_evidence(
        result: ScalarMetricResult,
    ) -> EvidencePayload:

        evidence = result.evidence


        return EvidencePayload(
            evidence_grade=
                evidence.evidence_grade,

            records=
                evidence.records,

            households=
                evidence.households,

            clusters=
                evidence.clusters,

            value_available=
                evidence.value_available,

            denominator_households=
                evidence.denominator_households,

            minimum_evidence_threshold=
                evidence.minimum_records,

            claim_type=
                result.claim_type,

            causal_interpretation_allowed=
                result.causal_interpretation_allowed,

            methodological_caution=
                result.caution,
        )


    @staticmethod
    def _evidence_sentence(
        evidence: EvidencePayload,
    ) -> str:

        if evidence.households is not None:

            return (
                f"Evidence: {evidence.evidence_grade}, "
                f"based on {evidence.records:,} records "
                f"from {evidence.households:,} households."
            )


        if evidence.clusters is not None:

            return (
                f"Evidence: {evidence.evidence_grade}, "
                f"based on {evidence.records:,} records "
                f"across {evidence.clusters:,} sampled communities."
            )


        return (
            f"Evidence: {evidence.evidence_grade}, "
            f"based on {evidence.records:,} records."
        )


    @staticmethod
    def _dimension_name(
        group_by: str,
    ) -> str:

        mapping = {
            "crop":
                "crops",

            "state":
                "states",

            "zone":
                "zones",

            "sector":
                "groups",

            "item":
                "food items",

            "climate_event":
                "climate events",
        }


        return mapping.get(
            group_by,
            "groups",
        )