from __future__ import annotations

import time

import fakeredis

from packages.answering.conversations import (
    RedisConversationStore,
)

from packages.contracts.question import (
    InterpretationStatus,
    Operation,
    QuestionInterpretation,
    QuestionSpecification,
)


def make_interpretation(
    crop: str = "RICE",
) -> QuestionInterpretation:

    filters = {
        "state": "Kaduna",
        "crop": crop,
    }

    specification = QuestionSpecification(
        metric_id=
            "crop_grower_share",

        operation=
            Operation.VALUE,

        filters=
            filters,

        group_by=
            None,

        ascending=
            False,

        top_n=
            None,

        minimum_records=
            None,

        metric_version=
            "1.0.0",
    )

    return QuestionInterpretation(
        question=
            f"What about {crop.lower()}?",

        normalized_question=
            f"what about {crop.lower()}?",

        status=
            InterpretationStatus.INTERPRETED,

        metric_id=
            "crop_grower_share",

        operation=
            Operation.VALUE,

        group_by=
            None,

        filters=
            filters,

        entities={
            "state": [
                "Kaduna"
            ],

            "crop": [
                crop
            ],
        },

        metric_candidates=[
            "crop_grower_share"
        ],

        question_specification=
            specification,
    )


def test_shared_state() -> None:

    server = (
        fakeredis.FakeServer()
    )

    client_a = (
        fakeredis.FakeRedis(
            server=server,
            decode_responses=True,
        )
    )

    client_b = (
        fakeredis.FakeRedis(
            server=server,
            decode_responses=True,
        )
    )

    store_a = RedisConversationStore(
        client=
            client_a,

        ttl_seconds=
            60,

        max_conversations=
            10,
    )

    store_b = RedisConversationStore(
        client=
            client_b,

        ttl_seconds=
            60,

        max_conversations=
            10,
    )

    interpretation = (
        make_interpretation(
            "RICE"
        )
    )

    store_a.put(
        "shared-conversation",
        interpretation,
    )

    context = store_b.get(
        "shared-conversation"
    )

    assert context is not None

    assert (
        context.last_interpretation
        .question_specification
        .filters[
            "crop"
        ]
        == "RICE"
    )

    assert (
        store_b.count()
        == 1
    )

    ttl = client_b.ttl(
        "agda:conversation:"
        "shared-conversation"
    )

    assert 0 < ttl <= 60

    # Closing one API process/client must NOT
    # delete shared conversation state.
    store_a.close()

    context_after_close = (
        store_b.get(
            "shared-conversation"
        )
    )

    assert (
        context_after_close
        is not None
    )

    store_b.clear()

    assert (
        store_b.count()
        == 0
    )

    store_b.close()


def test_non_interpreted_is_not_stored() -> None:

    client = (
        fakeredis.FakeRedis(
            decode_responses=True,
        )
    )

    store = RedisConversationStore(
        client=
            client,

        ttl_seconds=
            60,

        max_conversations=
            10,
    )

    unsupported = (
        QuestionInterpretation(
            question=
                "Is rice profitable?",

            normalized_question=
                "is rice profitable?",

            status=
                InterpretationStatus
                .UNSUPPORTED,
        )
    )

    store.put(
        "unsupported-conversation",
        unsupported,
    )

    assert (
        store.get(
            "unsupported-conversation"
        )
        is None
    )

    assert (
        store.count()
        == 0
    )

    store.close()


def test_capacity_eviction() -> None:

    client = (
        fakeredis.FakeRedis(
            decode_responses=True,
        )
    )

    store = RedisConversationStore(
        client=
            client,

        ttl_seconds=
            60,

        max_conversations=
            2,
    )

    store.put(
        "conversation-1",
        make_interpretation(
            "RICE"
        ),
    )

    time.sleep(
        0.01
    )

    store.put(
        "conversation-2",
        make_interpretation(
            "MAIZE"
        ),
    )

    time.sleep(
        0.01
    )

    store.put(
        "conversation-3",
        make_interpretation(
            "SOYA BEANS"
        ),
    )

    assert (
        store.count()
        == 2
    )

    assert (
        store.get(
            "conversation-1"
        )
        is None
    )

    assert (
        store.get(
            "conversation-2"
        )
        is not None
    )

    assert (
        store.get(
            "conversation-3"
        )
        is not None
    )

    store.clear()
    store.close()


def test_delete() -> None:

    client = (
        fakeredis.FakeRedis(
            decode_responses=True,
        )
    )

    store = RedisConversationStore(
        client=
            client,

        ttl_seconds=
            60,

        max_conversations=
            10,
    )

    store.put(
        "delete-me",
        make_interpretation(),
    )

    assert (
        store.delete(
            "delete-me"
        )
        is True
    )

    assert (
        store.get(
            "delete-me"
        )
        is None
    )

    assert (
        store.delete(
            "delete-me"
        )
        is False
    )

    store.close()


if __name__ == "__main__":

    test_shared_state()

    print(
        "Shared Redis state: PASSED"
    )

    test_non_interpreted_is_not_stored()

    print(
        "Unsupported-state guard: PASSED"
    )

    test_capacity_eviction()

    print(
        "Capacity eviction: PASSED"
    )

    test_delete()

    print(
        "Delete behavior: PASSED"
    )

    print(
        "REDIS CONVERSATION STORE: PASSED"
    )