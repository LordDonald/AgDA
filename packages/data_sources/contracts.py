from dataclasses import (
    dataclass,
)
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from enum import (
    StrEnum,
)


class SourceType(
    StrEnum,
):

    MARKET_PRICE = (
        "market_price"
    )

    WEATHER_OBSERVATION = (
        "weather_observation"
    )

    WEATHER_FORECAST = (
        "weather_forecast"
    )

    OTHER_EXTERNAL = (
        "other_external"
    )


class FreshnessStatus(
    StrEnum,
):

    FRESH = (
        "fresh"
    )

    STALE = (
        "stale"
    )

    UNKNOWN = (
        "unknown"
    )


def _require_text(
    field_name: str,
    value: str,
) -> None:

    if not value.strip():

        raise ValueError(
            f"{field_name} must not be blank."
        )


def _require_aware_datetime(
    field_name: str,
    value: datetime,
) -> None:

    if (
        value.tzinfo is None
        or value.utcoffset() is None
    ):

        raise ValueError(
            f"{field_name} must be timezone-aware."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class SourceDefinition:

    source_id: str

    display_name: str

    source_type: SourceType

    provider: str

    geographic_scope: str

    methodology_note: str

    attribution: str

    stale_after_hours: int | None

    expected_refresh_hours: int | None = None

    license_name: str | None = None

    source_url: str | None = None


    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "source_id",
            "display_name",
            "provider",
            "geographic_scope",
            "methodology_note",
            "attribution",
        ):

            _require_text(
                field_name,
                getattr(
                    self,
                    field_name,
                ),
            )


        if (
            self.stale_after_hours
            is not None
            and self.stale_after_hours
            <= 0
        ):

            raise ValueError(
                "stale_after_hours must be "
                "greater than zero."
            )


        if (
            self.expected_refresh_hours
            is not None
            and self.expected_refresh_hours
            <= 0
        ):

            raise ValueError(
                "expected_refresh_hours must be "
                "greater than zero."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class SourceSnapshot:

    source_id: str

    dataset_version: str

    observed_from: datetime

    observed_to: datetime

    refreshed_at: datetime

    retrieved_at: datetime

    record_count: int


    def __post_init__(
        self,
    ) -> None:

        _require_text(
            "source_id",
            self.source_id,
        )

        _require_text(
            "dataset_version",
            self.dataset_version,
        )


        for field_name in (
            "observed_from",
            "observed_to",
            "refreshed_at",
            "retrieved_at",
        ):

            _require_aware_datetime(
                field_name,
                getattr(
                    self,
                    field_name,
                ),
            )


        if (
            self.observed_from
            > self.observed_to
        ):

            raise ValueError(
                "observed_from must not be "
                "after observed_to."
            )


        if self.record_count < 0:

            raise ValueError(
                "record_count must be >= 0."
            )


def evaluate_freshness(
    definition: SourceDefinition,
    snapshot: SourceSnapshot,
    *,
    now: datetime | None = None,
) -> FreshnessStatus:

    if (
        definition.source_id
        != snapshot.source_id
    ):

        raise ValueError(
            "Source definition and snapshot "
            "source_id values do not match."
        )


    if (
        definition.stale_after_hours
        is None
    ):

        return (
            FreshnessStatus.UNKNOWN
        )


    effective_now = (
        now
        or datetime.now(
            timezone.utc
        )
    )

    _require_aware_datetime(
        "now",
        effective_now,
    )


    stale_after = timedelta(
        hours=
            definition
            .stale_after_hours,
    )


    if (
        effective_now
        - snapshot.refreshed_at
        > stale_after
    ):

        return (
            FreshnessStatus.STALE
        )


    return (
        FreshnessStatus.FRESH
    )
