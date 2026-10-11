from dataclasses import dataclass
from enum import StrEnum
import re

from packages.data_sources.external_metrics import (
    ExternalMetricDefinition,
    ExternalMetricKind,
    ExternalMetricRegistry,
)


class ExternalRouteStatus(StrEnum):
    NO_MATCH = "no_match"
    ROUTED = "routed"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class ExternalQuestionRoute:
    question: str
    normalized_question: str
    status: ExternalRouteStatus
    metric_id: str | None = None
    source_id: str | None = None
    operation: str | None = None
    reason: str | None = None


def normalize_external_question(
    question: str,
) -> str:

    if (
        not isinstance(question, str)
        or not question.strip()
    ):
        raise ValueError(
            "question must be nonblank text."
        )

    normalized = question.casefold()

    normalized = re.sub(
        r"[^a-z0-9%°]+",
        " ",
        normalized,
    )

    return " ".join(
        normalized.split()
    )


def _contains_term(
    normalized_question: str,
    term: str,
) -> bool:

    normalized_term = normalize_external_question(
        term
    )

    return (
        f" {normalized_term} "
        in f" {normalized_question} "
    )


def _matching_metrics(
    normalized_question: str,
    registry: ExternalMetricRegistry,
) -> tuple[
    ExternalMetricDefinition,
    ...
]:

    matches = []

    for metric in registry.list():
        if any(
            _contains_term(
                normalized_question,
                term,
            )
            for term
            in metric.question_terms
        ):
            matches.append(
                metric
            )

    return tuple(
        matches
    )


def _market_operation(
    normalized_question: str,
) -> str:

    rank_terms = (
        "highest",
        "lowest",
        "cheapest",
        "most expensive",
        "least expensive",
        "rank",
        "ranking",
        "top",
        "bottom",
    )

    if any(
        _contains_term(
            normalized_question,
            term,
        )
        for term
        in rank_terms
    ):
        return "rank"

    return "value"


def _weather_operation(
    metric: ExternalMetricDefinition,
    normalized_question: str,
) -> str:

    if (
        metric.metric_id
        == "forecast_precipitation_mm"
    ):
        total_terms = (
            "how much rain",
            "total rain",
            "total rainfall",
            "total precipitation",
            "rain total",
            "rainfall total",
        )

        if any(
            _contains_term(
                normalized_question,
                term,
            )
            for term
            in total_terms
        ):
            return "sum"

        return "value"

    range_terms = (
        "range",
        "highest",
        "lowest",
        "maximum",
        "minimum",
        "max",
        "min",
    )

    if any(
        _contains_term(
            normalized_question,
            term,
        )
        for term
        in range_terms
    ):
        return "range"

    return "value"


class ExternalQuestionRouter:

    def __init__(
        self,
        registry: ExternalMetricRegistry,
    ) -> None:

        if not isinstance(
            registry,
            ExternalMetricRegistry,
        ):
            raise TypeError(
                "registry must be an ExternalMetricRegistry."
            )

        self.registry = registry

    def route(
        self,
        question: str,
    ) -> ExternalQuestionRoute:

        normalized = normalize_external_question(
            question
        )

        matches = _matching_metrics(
            normalized,
            self.registry,
        )

        if not matches:
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=ExternalRouteStatus.NO_MATCH,
            )

        source_ids = {
            metric.source_id
            for metric
            in matches
        }

        if (
            len(source_ids) > 1
            or len(matches) > 1
        ):
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=ExternalRouteStatus.AMBIGUOUS,
                reason=(
                    "The question refers to multiple external "
                    "metrics or sources. Ask about one external "
                    "measure at a time so AgDA does not silently "
                    "combine datasets with different provenance "
                    "and time semantics."
                ),
            )

        metric = matches[0]

        if (
            metric.kind
            == ExternalMetricKind.MARKET_PRICE
        ):
            operation = _market_operation(
                normalized
            )
        else:
            operation = _weather_operation(
                metric,
                normalized,
            )

        if (
            operation
            not in metric.supported_operations
        ):
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=ExternalRouteStatus.AMBIGUOUS,
                metric_id=metric.metric_id,
                source_id=metric.source_id,
                reason=(
                    "The requested external-data operation "
                    "is not supported for this metric."
                ),
            )

        return ExternalQuestionRoute(
            question=question,
            normalized_question=normalized,
            status=ExternalRouteStatus.ROUTED,
            metric_id=metric.metric_id,
            source_id=metric.source_id,
            operation=operation,
        )
