from __future__ import annotations

from apps.api.app.core import (
    product_analytics,
)


def sample_payload() -> dict:

    return {
        "event":
            "agda_question",

        "timestamp":
            "2026-10-06T12:00:00+00:00",

        "request_id":
            "req_persistence_test_001",

        "environment":
            "staging",

        "status":
            "answered",

        "metric_id":
            "crop_grower_share",

        "operation":
            "rank",

        "group_by":
            "crop",

        "was_follow_up":
            False,

        "question_length":
            42,

        "result_count":
            3,

        "evidence_grade":
            None,

        "visualization_recommended":
            True,

        "processing_duration_ms":
            123.45,

        "data_version":
            "wave5_v1",

        "metric_version":
            "1.0.0",
    }


def test_persistence_insert() -> None:

    captured = {}


    class FakeCursor:

        def __enter__(self):

            return self


        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):

            return False


        def execute(
            self,
            sql,
            params,
        ):

            captured["sql"] = sql
            captured["params"] = params


    class FakeConnection:

        def __enter__(self):

            return self


        def __exit__(
            self,
            exc_type,
            exc_value,
            traceback,
        ):

            return False


        def cursor(self):

            return FakeCursor()


    original_connect = (
        product_analytics
        .psycopg
        .connect
    )


    def fake_connect(
        database_url,
        **kwargs,
    ):

        captured["database_url"] = (
            database_url
        )

        captured["connect_kwargs"] = (
            kwargs
        )

        return FakeConnection()


    product_analytics.psycopg.connect = (
        fake_connect
    )


    try:

        product_analytics.persist_question_event(
            database_url=
                "postgresql://example.invalid/test",

            payload=
                sample_payload(),
        )

    finally:

        product_analytics.psycopg.connect = (
            original_connect
        )


    assert (
        captured["database_url"]
        == "postgresql://example.invalid/test"
    )

    assert (
        captured["connect_kwargs"][
            "connect_timeout"
        ]
        == 5
    )

    assert (
        "INSERT INTO product_events"
        in captured["sql"]
    )

    assert (
        "ON CONFLICT"
        in captured["sql"]
    )

    assert (
        len(
            captured["params"]
        )
        == 15
    )

    # Environment isolation is provided by
    # separate staging/production databases.
    assert (
        "staging"
        not in captured["params"]
    )


def test_persistence_disabled() -> None:

    original_connect = (
        product_analytics
        .psycopg
        .connect
    )


    def fail_if_called(
        *args,
        **kwargs,
    ):

        raise AssertionError(
            "Database should not be contacted."
        )


    product_analytics.psycopg.connect = (
        fail_if_called
    )


    try:

        product_analytics.persist_question_event(
            database_url=None,
            payload=sample_payload(),
        )

    finally:

        product_analytics.psycopg.connect = (
            original_connect
        )


def test_persistence_fail_open() -> None:

    original_connect = (
        product_analytics
        .psycopg
        .connect
    )


    def failing_connect(
        *args,
        **kwargs,
    ):

        raise RuntimeError(
            "Synthetic database failure"
        )


    product_analytics.psycopg.connect = (
        failing_connect
    )


    try:

        product_analytics.persist_question_event(
            database_url=
                "postgresql://example.invalid/test",

            payload=
                sample_payload(),
        )

    finally:

        product_analytics.psycopg.connect = (
            original_connect
        )


if __name__ == "__main__":

    test_persistence_insert()

    print(
        "Product analytics durable insert: PASSED"
    )


    test_persistence_disabled()

    print(
        "Product analytics disabled mode: PASSED"
    )


    test_persistence_fail_open()

    print(
        "Product analytics fail-open behavior: PASSED"
    )


    print(
        "PRODUCT ANALYTICS PERSISTENCE TEST: PASSED"
    )
