from __future__ import annotations

import psycopg


_UPSERT_FEEDBACK_SQL = """
INSERT INTO product_feedback (
    request_id,
    rating,
    reason_code
)
SELECT
    %s,
    %s,
    %s
WHERE EXISTS (
    SELECT 1
    FROM product_events
    WHERE request_id = %s
      AND event_name = 'agda_question'
)
ON CONFLICT (
    request_id
)
DO UPDATE SET
    rating =
        EXCLUDED.rating,
    reason_code =
        EXCLUDED.reason_code,
    updated_at =
        NOW()
RETURNING id
"""


def save_feedback(
    *,
    database_url: str,
    request_id: str,
    rating: str,
    reason_code: str | None,
) -> None:
    """
    Persist explicit user feedback.

    Unlike passive telemetry, feedback is
    an explicit user action, so failures are
    allowed to propagate to the API route.
    """

    values = (
        request_id,
        rating,
        reason_code,
        request_id,
    )

    with psycopg.connect(
        database_url,
        connect_timeout=5,
    ) as connection:

        with connection.cursor() as cursor:

            cursor.execute(
                _UPSERT_FEEDBACK_SQL,
                values,
            )

            saved_row = (
                cursor.fetchone()
            )

            if saved_row is None:

                raise LookupError(
                    "Feedback request ID "
                    "does not match a recorded "
                    "AgDA answer."
                )
