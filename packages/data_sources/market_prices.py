from dataclasses import (
    dataclass,
)
from datetime import (
    date,
    datetime,
)
from decimal import (
    Decimal,
)


def _require_market_text(
    field_name: str,
    value: str,
) -> None:

    if not value.strip():

        raise ValueError(
            f"{field_name} must not be blank."
        )


@dataclass(
    frozen=True,
    slots=True,
)
class MarketPriceRecord:

    source_id: str

    period_date: date

    country_code: str

    admin_1: str | None

    admin_2: str | None

    fnid: str | None

    market: str

    market_id: int | None

    cpcv2: str

    cpcv2_description: str | None

    product: str

    price_type: str

    product_source: str | None

    unit: str

    currency: str

    value: Decimal

    dataseries: int | None

    source_organization: str

    source_document: str | None

    collection_status: str | None

    source_modified_at: datetime | None

    longitude: Decimal | None

    latitude: Decimal | None


    def __post_init__(
        self,
    ) -> None:

        for field_name in (
            "source_id",
            "country_code",
            "market",
            "cpcv2",
            "product",
            "price_type",
            "unit",
            "currency",
            "source_organization",
        ):

            _require_market_text(
                field_name,
                getattr(
                    self,
                    field_name,
                ),
            )


        if len(
            self.country_code
        ) != 2:

            raise ValueError(
                "country_code must contain "
                "a two-letter ISO code."
            )


        if self.value < 0:

            raise ValueError(
                "Market price value must "
                "not be negative."
            )
