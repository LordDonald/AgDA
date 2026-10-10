from datetime import (
    date,
    datetime,
)
from decimal import (
    Decimal,
    InvalidOperation,
)
from typing import (
    Any,
)

from packages.data_sources.market_prices import (
    MarketPriceRecord,
)


FEWS_MARKET_SOURCE_ID = (
    "fews_net_market_prices_ng"
)


def _optional_text(
    value: Any,
) -> str | None:

    if value is None:

        return None

    cleaned = str(
        value
    ).strip()

    return (
        cleaned
        if cleaned
        else None
    )


def _required_text(
    field_name: str,
    value: Any,
) -> str:

    cleaned = (
        _optional_text(
            value
        )
    )

    if cleaned is None:

        raise ValueError(
            f"Missing required FEWS field: "
            f"{field_name}"
        )

    return cleaned


def _optional_int(
    field_name: str,
    value: Any,
) -> int | None:

    if value in (
        None,
        "",
    ):

        return None

    try:

        return int(
            value
        )

    except (
        TypeError,
        ValueError,
    ) as error:

        raise ValueError(
            f"Invalid integer FEWS field: "
            f"{field_name}"
        ) from error


def _decimal(
    field_name: str,
    value: Any,
    *,
    required: bool,
) -> Decimal | None:

    if value in (
        None,
        "",
    ):

        if required:

            raise ValueError(
                f"Missing required FEWS field: "
                f"{field_name}"
            )

        return None

    try:

        return Decimal(
            str(
                value
            )
        )

    except (
        InvalidOperation,
        ValueError,
    ) as error:

        raise ValueError(
            f"Invalid decimal FEWS field: "
            f"{field_name}"
        ) from error


def _parse_date(
    field_name: str,
    value: Any,
) -> date:

    text = (
        _required_text(
            field_name,
            value,
        )
    )

    try:

        return date.fromisoformat(
            text[:10]
        )

    except ValueError as error:

        raise ValueError(
            f"Invalid date FEWS field: "
            f"{field_name}"
        ) from error


def _parse_datetime(
    field_name: str,
    value: Any,
) -> datetime | None:

    text = (
        _optional_text(
            value
        )
    )

    if text is None:

        return None

    normalized = (
        text.replace(
            "Z",
            "+00:00",
        )
    )

    try:

        return datetime.fromisoformat(
            normalized
        )

    except ValueError as error:

        raise ValueError(
            f"Invalid datetime FEWS field: "
            f"{field_name}"
        ) from error


def normalize_fews_market_price(
    payload: dict[
        str,
        Any,
    ],
) -> MarketPriceRecord:

    country_code = (
        _required_text(
            "country_code",
            payload.get(
                "country_code"
            ),
        )
        .upper()
    )


    return MarketPriceRecord(
        source_id=
            FEWS_MARKET_SOURCE_ID,

        period_date=
            _parse_date(
                "period_date",
                payload.get(
                    "period_date"
                ),
            ),

        country_code=
            country_code,

        admin_1=
            _optional_text(
                payload.get(
                    "admin_1"
                )
            ),

        admin_2=
            _optional_text(
                payload.get(
                    "admin_2"
                )
            ),

        fnid=
            _optional_text(
                payload.get(
                    "fnid"
                )
            ),

        market=
            _required_text(
                "market",
                payload.get(
                    "market"
                ),
            ),

        market_id=
            _optional_int(
                "market_id",
                payload.get(
                    "market_id"
                ),
            ),

        cpcv2=
            _required_text(
                "cpcv2",
                payload.get(
                    "cpcv2"
                ),
            ),

        cpcv2_description=
            _optional_text(
                payload.get(
                    "cpcv2_description"
                )
            ),

        product=
            _required_text(
                "product",
                payload.get(
                    "product"
                ),
            ),

        price_type=
            _required_text(
                "price_type",
                payload.get(
                    "price_type"
                ),
            ),

        product_source=
            _optional_text(
                payload.get(
                    "product_source"
                )
            ),

        unit=
            _required_text(
                "unit",
                payload.get(
                    "unit"
                ),
            ),

        currency=
            _required_text(
                "currency",
                payload.get(
                    "currency"
                ),
            )
            .upper(),

        value=
            _decimal(
                "value",
                payload.get(
                    "value"
                ),
                required=True,
            ),

        dataseries=
            _optional_int(
                "dataseries",
                payload.get(
                    "dataseries"
                ),
            ),

        source_organization=
            _required_text(
                "source_organization",
                payload.get(
                    "source_organization"
                ),
            ),

        source_document=
            _optional_text(
                payload.get(
                    "source_document"
                )
            ),

        collection_status=
            _optional_text(
                payload.get(
                    "collection_status"
                )
            ),

        source_modified_at=
            _parse_datetime(
                "modified",
                payload.get(
                    "modified"
                ),
            ),

        longitude=
            _decimal(
                "longitude",
                payload.get(
                    "longitude"
                ),
                required=False,
            ),

        latitude=
            _decimal(
                "latitude",
                payload.get(
                    "latitude"
                ),
                required=False,
            ),
    )


def normalize_fews_page(
    payload: dict[
        str,
        Any,
    ],
) -> tuple[
    MarketPriceRecord,
    ...
]:

    results = (
        payload.get(
            "results"
        )
    )

    if not isinstance(
        results,
        list,
    ):

        raise ValueError(
            "FEWS response results must "
            "be a list."
        )


    return tuple(
        normalize_fews_market_price(
            record
        )
        for record in results
    )
