from dataclasses import dataclass
from enum import StrEnum
import re

from packages.data_sources.external_metrics import (
    ExternalMetricDefinition,
    ExternalMetricKind,
    ExternalMetricRegistry,
)
from packages.question_router.config import METRIC_LANGUAGE


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


def _has_any_term(question: str, terms: tuple[str, ...]) -> bool:
    return any(_contains_term(question, term) for term in terms)


def _core_boundary(
    question: str,
    matches: tuple[ExternalMetricDefinition, ...],
) -> ExternalRouteStatus | None:
    """Keep shared vocabulary from taking questions away from Wave 5.

    Core phrases remain owned by the existing Wave 5 interpreter. An explicit
    external source or an additional external measure makes a mixed request,
    which must be reframed rather than silently answering one part.
    """
    core_metrics = {
        metric_id
        for metric_id, language in METRIC_LANGUAGE.items()
        if _has_any_term(question, tuple(language["phrases"]))
    }
    kinds = {metric.kind for metric in matches}
    if ExternalMetricKind.MARKET_PRICE in kinds and _has_any_term(
        question,
        ("change", "changes", "changed", "increase", "increased",
         "decrease", "decreased", "rose", "fell"),
    ):
        core_metrics.add("median_same_basis_price_change")
    climate_expectation = _has_any_term(question, ("climate", "expectations"))
    climate_event_risk = (
        _has_any_term(
            question,
            ("high temperature", "high temperatures", "extreme heat",
             "late rain", "late rains", "late onset of rain"),
        )
        and _has_any_term(
            question,
            ("risk", "risky", "likely", "likelihood", "chance",
             "expected", "expect", "occur", "occurrence"),
        )
    )
    if ExternalMetricKind.WEATHER_FORECAST in kinds and (
        climate_expectation or climate_event_risk
    ):
        core_metrics.add("climate_likely_share")
    core_marker = _has_any_term(
        question,
        ("wave5", "wave 5", "survey", "surveyed", "household",
         "households", "community", "communities"),
    )
    external_marker = _has_any_term(
        question,
        ("fews", "open meteo", "ecmwf", "forecast", "forecasts",
         "external data", "external source", "external sources"),
    )
    core_measure = _has_any_term(
        question,
        ("yield", "yields", "productivity", "hectares", "acreage",
         "extension", "commercialization", "commercialised",
         "commercialized", "consumption", "sellers", "participation",
         "adaptation", "food insecurity", "postharvest loss"),
    )
    if not (core_metrics or core_marker or core_measure):
        return None
    if external_marker:
        return ExternalRouteStatus.AMBIGUOUS
    if not matches:
        return ExternalRouteStatus.NO_MATCH
    overlap_kinds = set()
    if "median_same_basis_price_change" in core_metrics:
        overlap_kinds.add(ExternalMetricKind.MARKET_PRICE)
    if core_metrics & {"climate_likely_share", "adaptation_no_action_share"}:
        overlap_kinds.add(ExternalMetricKind.WEATHER_FORECAST)
    if overlap_kinds and all(metric.kind in overlap_kinds for metric in matches):
        return ExternalRouteStatus.NO_MATCH
    if core_marker and not core_metrics and not core_measure and len(matches) == 1:
        return ExternalRouteStatus.NO_MATCH
    return ExternalRouteStatus.AMBIGUOUS


# Natural-language routing intentionally supports only unqualified questions
# about the saved snapshot. Precise filters belong to /v1/external-queries.
# Reject unrecognized qualifiers instead of guessing or silently dropping them.
_UNQUALIFIED_WORDS = frozenset("""
    a an the what which where how much many is are was were be been has have had
    does do did will would can could please show list give tell me us of to and
    with by in at on for from across within over all data saved local snapshot
    snapshots window available values value source records period it
""".split())
_MARKET_WORDS = frozenset("""
    observed historical retail market markets maize white grain price prices
    cost per kg kilogram kilograms naira ngn highest lowest cheapest most
    expensive least rank ranking top bottom fews net
""".split())
_WEATHER_WORDS = frozenset("""
    hourly forecast forecasts expected expect predicted prediction predictions
    open meteo ecmwf weather
""".split())
_MEASURE_WORDS = {
    "forecast_temperature_2m_c": frozenset("""
        temperature hot cold degree degrees celsius range maximum minimum max
        min highest lowest
    """.split()),
    "forecast_relative_humidity_2m_pct": frozenset("""
        humidity humid relative percent percentage % range maximum minimum max
        min highest lowest
    """.split()),
    "forecast_precipitation_mm": frozenset("""
        rain rainfall precipitation total mm millimetres millimeters
    """.split()),
}


def _has_unsupported_qualifier(
    question: str,
    metric: ExternalMetricDefinition,
) -> bool:
    if metric.kind == ExternalMetricKind.MARKET_PRICE:
        words = _UNQUALIFIED_WORDS | _MARKET_WORDS
    else:
        words = _UNQUALIFIED_WORDS | _WEATHER_WORDS | _MEASURE_WORDS.get(
            metric.metric_id, frozenset()
        )
    return any(word not in words for word in question.split())


def _has_conflicting_operations(
    question: str,
    metric: ExternalMetricDefinition,
) -> bool:
    if metric.kind == ExternalMetricKind.MARKET_PRICE:
        ascending = _has_any_term(
            question, ("lowest", "cheapest", "least expensive", "bottom")
        )
        descending = _has_any_term(
            question, ("highest", "most expensive", "top")
        )
        if ascending and descending:
            return True
    explicit_operations = sum(
        _has_any_term(question, terms)
        for terms in (("value",), ("rank", "ranking"),
                      ("range",), ("sum", "total"))
    )
    if explicit_operations > 1 and _contains_term(question, "and"):
        return True
    if metric.metric_id == "forecast_precipitation_mm":
        return _weather_operation(metric, question) == "sum" and _has_any_term(
            question,
            ("will it rain", "is rain expected", "is rainfall expected",
             "is precipitation expected"),
        )
    return False


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

        boundary = _core_boundary(normalized, matches)
        if boundary is not None:
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=boundary,
                reason=(
                    "This question combines Wave 5 survey analysis with "
                    "external data. Ask about one dataset at a time; their "
                    "provenance and time semantics must remain separate."
                    if boundary == ExternalRouteStatus.AMBIGUOUS
                    else None
                ),
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

        if _has_conflicting_operations(normalized, metric):
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=ExternalRouteStatus.AMBIGUOUS,
                metric_id=metric.metric_id,
                source_id=metric.source_id,
                reason=(
                    "This question requests more than one external operation or "
                    "ranking direction. Ask for one operation at a time, and "
                    "choose either highest or lowest for a market ranking."
                ),
            )

        if _has_unsupported_qualifier(normalized, metric):
            return ExternalQuestionRoute(
                question=question,
                normalized_question=normalized,
                status=ExternalRouteStatus.AMBIGUOUS,
                metric_id=metric.metric_id,
                source_id=metric.source_id,
                reason=(
                    "This question includes a qualifier that the saved-snapshot "
                    "question route cannot apply safely. Use the external query "
                    "endpoint with explicit commodity, location, or time filters "
                    "(/v1/external-queries), or ask about the full saved snapshot. "
                    "No requested restriction has been silently ignored."
                ),
            )

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
