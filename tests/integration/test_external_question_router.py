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

    def test_wave5_shared_vocabulary_stays_with_core(self):
        questions = (
            "What is the median maize price change?",
            "Which states had the highest price increase?",
            "Which communities are worried about high temperature?",
            "What climate risk has the highest temperature concern?",
            "What share of communities take no action on climate and rain?",
            "What is the community maize price?",
            "Show Wave5 temperature expectations.",
            "What is the Wave 5 price change in Abia in 2025?",
            "Compare maize yield and price change.",
            "How much did the price of maize change?",
            "What is the percentage change in maize price?",
            "How likely is very high temperature in Abia?",
            "What are the climate temperature expectations?",
        )
        for question in questions:
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertEqual(route.status, ExternalRouteStatus.NO_MATCH)
                self.assertIsNone(route.metric_id)
                self.assertIsNone(route.reason)

    def test_wave5_external_mixtures_require_reframing(self):
        questions = (
            "Compare maize yields and market price.",
            "Compare Wave5 yield with FEWS price.",
            "Compare community climate risk with forecast temperature.",
            "Compare price change with Open-Meteo rainfall.",
            "What is FEWS maize price change?",
            "Does rainfall affect crop yield?",
            "Compare Wave 5 with FEWS.",
            "Show Wave5 maize price and rainfall.",
            "What is the external forecast for household food insecurity?",
        )
        for question in questions:
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertEqual(route.status, ExternalRouteStatus.AMBIGUOUS)
                self.assertIn("Wave 5", route.reason)
                self.assertIn("remain separate", route.reason)

    def test_explicit_commodity_location_time_and_unit_are_not_ignored(self):
        questions = (
            "What is the rice price?",
            "What is the yellow maize price?",
            "Which market has the highest sorghum price?",
            "What is the maize price in Aba?",
            "What is the Aba maize price?",
            "What is the maize price in Nigeria?",
            "What is the maize price on 2025-01-31?",
            "What is the maize price today?",
            "What is the current maize price?",
            "Which market has the highest maize price in dollars?",
            "What is the maize price per bag?",
            "What is the maize price in Celsius?",
            "What is the Open-Meteo maize price?",
            "Will it rain from FEWS NET?",
            "What is the forecast temperature in kg?",
            "What is relative humidity in Celsius?",
            "Will it rain for maize?",
            "Will it rain tomorrow?",
            "Will it rain in Lagos?",
            "What is the temperature at 2026-10-12T12:00:00Z?",
            "What is the temperature at noon?",
            "What is the temperature range next week?",
            "What is total rain for October?",
            "Show the humidity for latitude 5 longitude 7.",
            "What is the average temperature?",
            "Show the top 2 market price ranking.",
        )
        for question in questions:
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertEqual(route.status, ExternalRouteStatus.AMBIGUOUS)
                self.assertIn("/v1/external-queries", route.reason)
                self.assertIsNotNone(route.metric_id)

    def test_unqualified_saved_snapshot_questions_remain_supported(self):
        questions = (
            "Which market has the lowest white maize price?",
            "Show the most expensive maize market price.",
            "What is the cost per kg?",
            "What is the price from FEWS NET?",
            "Show the saved forecast temperature range.",
            "What is the maximum relative humidity?",
            "How much rain is forecast across the saved window?",
            "What is the total precipitation in the saved snapshot?",
            "Show the range of forecast temperature values.",
            "Show the total forecast precipitation values.",
            "Will it rain?",
        )
        for question in questions:
            with self.subTest(question=question):
                self.assertEqual(
                    self.router.route(question).status,
                    ExternalRouteStatus.ROUTED,
                )

    def test_conflicting_directions_and_operations_require_reframing(self):
        questions = (
            "Which markets have the highest and lowest maize price?",
            "Show the most expensive and least expensive maize price.",
            "Show the top and bottom market price.",
            "Which market price is highest and cheapest?",
            "Show the maize price value and rank.",
            "What is the forecast temperature value and range?",
            "What is the total and range of forecast precipitation?",
            "Will it rain and how much rain is forecast?",
            "Is rain expected and what is total rain?",
        )
        for question in questions:
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertEqual(route.status, ExternalRouteStatus.AMBIGUOUS)
                self.assertIn("one operation at a time", route.reason)

    def test_minimum_and_maximum_weather_values_are_one_range(self):
        for question in (
            "What are the minimum and maximum forecast temperature?",
            "What are the highest and lowest relative humidity?",
        ):
            with self.subTest(question=question):
                route = self.router.route(question)
                self.assertEqual(route.status, ExternalRouteStatus.ROUTED)
                self.assertEqual(route.operation, "range")


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
