import unittest

from packages.data_sources.external_metrics import (
    ExternalMetricDefinition,
    ExternalMetricKind,
    ExternalMetricRegistry,
    build_external_metric_registry,
)


class ExternalMetricRegistryTests(
    unittest.TestCase
):

    def test_default_registry_contains_four_metrics(
        self,
    ):
        registry = build_external_metric_registry()

        self.assertEqual(
            registry.count(),
            4,
        )

        self.assertEqual(
            {
                definition.metric_id
                for definition
                in registry.list()
            },
            {
                "market_price_ngn_per_kg",
                "forecast_temperature_2m_c",
                "forecast_relative_humidity_2m_pct",
                "forecast_precipitation_mm",
            },
        )

    def test_market_price_metric_is_fews_only(
        self,
    ):
        metric = (
            build_external_metric_registry()
            .get(
                "market_price_ngn_per_kg"
            )
        )

        self.assertEqual(
            metric.kind,
            ExternalMetricKind.MARKET_PRICE,
        )

        self.assertEqual(
            metric.source_id,
            "fews_net_market_prices_ng",
        )

        self.assertEqual(
            metric.unit,
            "NGN/kg",
        )

    def test_weather_metrics_are_open_meteo_only(
        self,
    ):
        registry = (
            build_external_metric_registry()
        )

        weather_ids = (
            "forecast_temperature_2m_c",
            "forecast_relative_humidity_2m_pct",
            "forecast_precipitation_mm",
        )

        for metric_id in weather_ids:
            with self.subTest(
                metric_id=metric_id
            ):
                metric = registry.get(
                    metric_id
                )

                self.assertEqual(
                    metric.kind,
                    ExternalMetricKind.WEATHER_FORECAST,
                )

                self.assertEqual(
                    metric.source_id,
                    "open_meteo_forecast",
                )

    def test_registry_rejects_duplicate_metric_ids(
        self,
    ):
        definition = ExternalMetricDefinition(
            metric_id="test_metric",
            source_id="test_source",
            kind=ExternalMetricKind.MARKET_PRICE,
            display_name="Test metric",
            unit="unit",
            supported_operations=("value",),
            question_terms=("test",),
            time_semantics="Test time semantics.",
            caution="Test caution.",
        )

        with self.assertRaises(
            ValueError
        ):
            ExternalMetricRegistry(
                (
                    definition,
                    definition,
                )
            )

    def test_definition_requires_operations_and_terms(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            ExternalMetricDefinition(
                metric_id="test_metric",
                source_id="test_source",
                kind=ExternalMetricKind.MARKET_PRICE,
                display_name="Test metric",
                unit="unit",
                supported_operations=(),
                question_terms=("test",),
                time_semantics="Time semantics.",
                caution="Caution.",
            )

        with self.assertRaises(
            ValueError
        ):
            ExternalMetricDefinition(
                metric_id="test_metric",
                source_id="test_source",
                kind=ExternalMetricKind.MARKET_PRICE,
                display_name="Test metric",
                unit="unit",
                supported_operations=("value",),
                question_terms=(),
                time_semantics="Time semantics.",
                caution="Caution.",
            )

    def test_unknown_metric_is_rejected(
        self,
    ):
        registry = build_external_metric_registry()

        self.assertFalse(
            registry.contains(
                "wave5_metric"
            )
        )

        with self.assertRaises(
            KeyError
        ):
            registry.get(
                "wave5_metric"
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
