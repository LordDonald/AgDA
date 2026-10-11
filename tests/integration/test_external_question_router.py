import unittest

from packages.data_sources.external_metrics import (
    build_external_metric_registry,
)
from packages.data_sources.external_router import (
    ExternalQuestionRouter,
    ExternalRouteStatus,
)


class ExternalQuestionRouterTests(
    unittest.TestCase
):

    def setUp(self):
        self.router = ExternalQuestionRouter(
            build_external_metric_registry()
        )

    def test_market_price_routes_to_fews(
        self,
    ):
        route = self.router.route(
            "What is the maize price?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.metric_id,
            "market_price_ngn_per_kg",
        )
        self.assertEqual(
            route.source_id,
            "fews_net_market_prices_ng",
        )
        self.assertEqual(
            route.operation,
            "value",
        )

    def test_market_price_rank_is_detected(
        self,
    ):
        route = self.router.route(
            "Which market has the highest maize price?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.operation,
            "rank",
        )

    def test_temperature_routes_to_weather(
        self,
    ):
        route = self.router.route(
            "What is the forecast temperature?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.metric_id,
            "forecast_temperature_2m_c",
        )
        self.assertEqual(
            route.source_id,
            "open_meteo_forecast",
        )
        self.assertEqual(
            route.operation,
            "value",
        )

    def test_temperature_range_is_detected(
        self,
    ):
        route = self.router.route(
            "What is the temperature range?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.operation,
            "range",
        )

    def test_rain_routes_to_precipitation(
        self,
    ):
        route = self.router.route(
            "Will it rain?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.metric_id,
            "forecast_precipitation_mm",
        )
        self.assertEqual(
            route.operation,
            "value",
        )

    def test_total_rain_uses_sum_operation(
        self,
    ):
        route = self.router.route(
            "How much rain is forecast?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.ROUTED,
        )
        self.assertEqual(
            route.operation,
            "sum",
        )

    def test_wave5_question_falls_through(
        self,
    ):
        route = self.router.route(
            "Which states have the lowest maize yields?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.NO_MATCH,
        )
        self.assertIsNone(
            route.metric_id
        )

    def test_two_weather_metrics_are_ambiguous(
        self,
    ):
        route = self.router.route(
            "What are the temperature and humidity?"
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.AMBIGUOUS,
        )

        self.assertIn(
            "one external measure",
            route.reason,
        )

    def test_cross_source_question_is_ambiguous(
        self,
    ):
        route = self.router.route(
            "Compare maize price with rainfall."
        )

        self.assertEqual(
            route.status,
            ExternalRouteStatus.AMBIGUOUS,
        )

    def test_blank_question_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            self.router.route(
                "   "
            )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
