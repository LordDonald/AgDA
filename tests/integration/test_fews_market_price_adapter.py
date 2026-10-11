from datetime import (
    date,
)
from decimal import (
    Decimal,
)

from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
    normalize_fews_market_price,
    normalize_fews_page,
)


def main():

    raw_record = {
        "period_date":
            "2025-01-31",

        "country_code":
            "NG",

        "admin_1":
            "Abia",

        "admin_2":
            "Aba North",

        "fnid":
            "NG0000M001",

        "market":
            "Aba",

        "market_id":
            57682,

        "cpcv2":
            "R01122AC",

        "cpcv2_description":
            (
                "Maize grain (corn), "
                "other, white"
            ),

        "product":
            "Maize Grain (White)",

        "price_type":
            "Retail",

        "product_source":
            "Local",

        "unit":
            "kg",

        "currency":
            "NGN",

        "value":
            998.1,

        "dataseries":
            15312,

        "source_organization":
            "FEWS NET",

        "source_document":
            (
                "Famine Early Warning Systems "
                "Network (FEWS NET), Nigeria, "
                "Price (weekly)"
            ),

        "collection_status":
            "Published",

        "modified":
            "2026-07-21T23:02:24",

        "longitude":
            7.37063,

        "latitude":
            5.10719,
    }


    record = (
        normalize_fews_market_price(
            raw_record
        )
    )


    assert (
        record.source_id
        == FEWS_MARKET_SOURCE_ID
    )

    assert (
        record.period_date
        == date(
            2025,
            1,
            31,
        )
    )

    assert (
        record.country_code
        == "NG"
    )

    assert (
        record.admin_1
        == "Abia"
    )

    assert (
        record.admin_2
        == "Aba North"
    )

    assert (
        record.market
        == "Aba"
    )

    assert (
        record.market_id
        == 57682
    )

    assert (
        record.cpcv2
        == "R01122AC"
    )

    assert (
        record.product
        == "Maize Grain (White)"
    )

    assert (
        record.price_type
        == "Retail"
    )

    assert (
        record.unit
        == "kg"
    )

    assert (
        record.currency
        == "NGN"
    )

    assert (
        record.value
        == Decimal(
            "998.1"
        )
    )

    assert (
        record.dataseries
        == 15312
    )

    assert (
        record.source_organization
        == "FEWS NET"
    )

    assert (
        record.longitude
        == Decimal(
            "7.37063"
        )
    )

    assert (
        record.latitude
        == Decimal(
            "5.10719"
        )
    )


    # Derived FEWS statistics deliberately
    # do not belong to the canonical record.
    assert not hasattr(
        record,
        "pct_change_from_one_year_ago",
    )

    assert not hasattr(
        record,
        "two_year_average",
    )


    page = (
        normalize_fews_page(
            {
                "count":
                    902,

                "next":
                    (
                        "https://fdw.fews.net/"
                        "api/marketpricefacts/"
                        "?offset=5&page_size=5"
                    ),

                "previous":
                    None,

                # Intentionally only two rows:
                # FEWS may return fewer result
                # objects than page_size.
                "results": [
                    raw_record,
                    {
                        **raw_record,
                        "cpcv2":
                            "R01122AB",
                        "cpcv2_description":
                            (
                                "Maize grain "
                                "(corn), yellow"
                            ),
                        "product":
                            "Maize Grain (Yellow)",
                        "value":
                            968.5,
                        "dataseries":
                            15313,
                    },
                ],
            }
        )
    )


    assert len(
        page
    ) == 2

    assert (
        page[1].product
        == "Maize Grain (Yellow)"
    )

    assert (
        page[1].value
        == Decimal(
            "968.5"
        )
    )


    missing_value_detected = False

    try:

        normalize_fews_market_price(
            {
                **raw_record,
                "value":
                    None,
            }
        )

    except ValueError:

        missing_value_detected = True


    assert missing_value_detected


    print(
        "Canonical market price record: PASSED"
    )

    print(
        "FEWS market price normalization: PASSED"
    )

    print(
        "FEWS short-page handling: PASSED"
    )

    print(
        "FEWS derived-field exclusion: PASSED"
    )

    print(
        "FEWS MARKET PRICE ADAPTER TEST: PASSED"
    )


if __name__ == "__main__":

    main()
