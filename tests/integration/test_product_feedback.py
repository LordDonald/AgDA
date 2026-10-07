from __future__ import annotations

from pydantic import ValidationError

from apps.api.app.core import (
    product_feedback,
)

from packages.contracts.feedback import (
    FeedbackRequest,
)


def test_feedback_contract() -> None:

    helpful = FeedbackRequest(
        request_id=
            "req_feedback_test_001",

        rating=
            "helpful",
    )

    assert helpful.reason_code is None


    negative = FeedbackRequest(
        request_id=
            "req_feedback_test_002",

        rating=
            "not_helpful",

        reason_code=
            "unclear",
    )

    assert (
        negative.reason_code
        == "unclear"
    )


    try:

        FeedbackRequest(
            request_id=
                "req_feedback_test_003",

            rating=
                "helpful",

            reason_code=
                "incorrect",
        )

    except ValidationError:

        pass

    else:

        raise AssertionError(
            "Helpful feedback must reject "
            "a negative reason code."
        )


def test_feedback_upsert() -> None:

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


        def fetchone(self):

            return (1,)


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
        product_feedback
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

        captured["kwargs"] = kwargs

        return FakeConnection()


    product_feedback.psycopg.connect = (
        fake_connect
    )


    try:

        product_feedback.save_feedback(
            database_url=
                "postgresql://example.invalid/test",

            request_id=
                "req_feedback_test_004",

            rating=
                "not_helpful",

            reason_code=
                "insufficient_evidence",
        )

    finally:

        product_feedback.psycopg.connect = (
            original_connect
        )


    assert (
        captured["database_url"]
        == "postgresql://example.invalid/test"
    )

    assert (
        captured["kwargs"][
            "connect_timeout"
        ]
        == 5
    )

    assert (
        "INSERT INTO product_feedback"
        in captured["sql"]
    )

    assert (
        "ON CONFLICT"
        in captured["sql"]
    )

    assert (
        "DO UPDATE"
        in captured["sql"]
    )

    assert captured["params"] == (
        "req_feedback_test_004",
        "not_helpful",
        "insufficient_evidence",
        "req_feedback_test_004",
    )


    serialized = str(
        captured["params"]
    )

    assert "question" not in serialized
    assert "conversation" not in serialized
    assert "answer_text" not in serialized


if __name__ == "__main__":

    test_feedback_contract()

    print(
        "Product feedback contract: PASSED"
    )


    test_feedback_upsert()

    print(
        "Product feedback upsert: PASSED"
    )


    print(
        "PRODUCT FEEDBACK TEST: PASSED"
    )
