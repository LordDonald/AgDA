from __future__ import annotations

import json
import time

from collections import OrderedDict
from threading import RLock
from typing import Any

from redis import Redis

from packages.contracts.question import (
    InterpretationStatus,
    QuestionInterpretation,
)

from packages.question_router.conversation import (
    ConversationContext,
)


# ============================================================
# IN-MEMORY CONVERSATION STORE
# ============================================================

class ConversationStore:
    """
    Process-local conversation store.

    Used for local development and tests.

    Only the most recent successfully interpreted analytical
    context is retained for each conversation.
    """

    def __init__(
        self,
        max_conversations: int = 500,
    ):

        if max_conversations < 1:
            raise ValueError(
                "max_conversations must be >= 1."
            )

        self.max_conversations = (
            max_conversations
        )

        self._contexts: OrderedDict[
            str,
            ConversationContext,
        ] = OrderedDict()

        self._lock = RLock()


    def get(
        self,
        conversation_id: str,
    ) -> ConversationContext | None:

        with self._lock:

            context = self._contexts.get(
                conversation_id
            )

            if context is not None:

                self._contexts.move_to_end(
                    conversation_id
                )

            return context


    def put(
        self,
        conversation_id: str,
        interpretation: QuestionInterpretation,
    ) -> None:

        if (
            interpretation.status
            != InterpretationStatus.INTERPRETED
            or interpretation.question_specification
            is None
        ):
            return

        context = ConversationContext(
            last_interpretation=
                interpretation
        )

        with self._lock:

            self._contexts[
                conversation_id
            ] = context

            self._contexts.move_to_end(
                conversation_id
            )

            while (
                len(self._contexts)
                > self.max_conversations
            ):

                self._contexts.popitem(
                    last=False
                )


    def delete(
        self,
        conversation_id: str,
    ) -> bool:

        with self._lock:

            return (
                self._contexts.pop(
                    conversation_id,
                    None,
                )
                is not None
            )


    def clear(
        self,
    ) -> None:

        with self._lock:
            self._contexts.clear()


    def count(
        self,
    ) -> int:

        with self._lock:
            return len(
                self._contexts
            )


    def close(
        self,
    ) -> None:

        self.clear()


# ============================================================
# REDIS CONVERSATION STORE
# ============================================================

class RedisConversationStore:
    """
    Shared Redis-backed conversation store.

    Conversation state:
    - is shared across API processes / replicas;
    - survives API process restarts;
    - expires automatically after the configured TTL;
    - retains only successfully interpreted analytical context.
    """

    SCHEMA_VERSION = 1

    def __init__(
        self,
        *,
        redis_url: str | None = None,
        ttl_seconds: int = 86400,
        max_conversations: int = 500,
        client: Any | None = None,
        key_prefix: str = "agda:conversation",
    ):

        if ttl_seconds < 1:
            raise ValueError(
                "ttl_seconds must be >= 1."
            )

        if max_conversations < 1:
            raise ValueError(
                "max_conversations must be >= 1."
            )

        if (
            client is None
            and not redis_url
        ):
            raise ValueError(
                "redis_url is required when "
                "a Redis client is not supplied."
            )

        self.ttl_seconds = (
            ttl_seconds
        )

        self.max_conversations = (
            max_conversations
        )

        self.key_prefix = (
            key_prefix.rstrip(":")
        )

        self.index_key = (
            f"{self.key_prefix}:index"
        )

        if client is not None:

            self._redis = client

        else:

            self._redis = Redis.from_url(
                redis_url,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
            )

        # Fail startup immediately if Redis cannot be reached.
        self._redis.ping()


    # --------------------------------------------------------
    # Keys
    # --------------------------------------------------------

    def _key(
        self,
        conversation_id: str,
    ) -> str:

        return (
            f"{self.key_prefix}:"
            f"{conversation_id}"
        )


    # --------------------------------------------------------
    # Expired index maintenance
    # --------------------------------------------------------

    def _remove_expired_index_members(
        self,
    ) -> None:

        cutoff = (
            time.time()
            - self.ttl_seconds
        )

        self._redis.zremrangebyscore(
            self.index_key,
            "-inf",
            cutoff,
        )


    # --------------------------------------------------------
    # Capacity
    # --------------------------------------------------------

    def _prune_to_capacity(
        self,
    ) -> None:

        self._remove_expired_index_members()

        current_count = int(
            self._redis.zcard(
                self.index_key
            )
        )

        overflow = (
            current_count
            - self.max_conversations
        )

        if overflow <= 0:
            return

        oldest_ids = (
            self._redis.zrange(
                self.index_key,
                0,
                overflow - 1,
            )
        )

        if not oldest_ids:
            return

        pipeline = (
            self._redis.pipeline(
                transaction=True
            )
        )

        for conversation_id in oldest_ids:

            pipeline.delete(
                self._key(
                    conversation_id
                )
            )

        pipeline.zrem(
            self.index_key,
            *oldest_ids,
        )

        pipeline.execute()


    # --------------------------------------------------------
    # Get
    # --------------------------------------------------------

    def get(
        self,
        conversation_id: str,
    ) -> ConversationContext | None:

        key = self._key(
            conversation_id
        )

        payload = (
            self._redis.get(
                key
            )
        )

        if payload is None:

            self._redis.zrem(
                self.index_key,
                conversation_id,
            )

            return None

        try:

            stored = json.loads(
                payload
            )

            if (
                stored.get(
                    "schema_version"
                )
                != self.SCHEMA_VERSION
            ):

                raise ValueError(
                    "Unsupported stored "
                    "conversation schema version."
                )

            interpretation = (
                QuestionInterpretation
                .model_validate(
                    stored[
                        "last_interpretation"
                    ]
                )
            )

        except (
            KeyError,
            TypeError,
            ValueError,
        ) as error:

            # Remove invalid/corrupt conversation state rather
            # than repeatedly failing every follow-up request.
            self.delete(
                conversation_id
            )

            raise ValueError(
                "Stored conversation context "
                "is invalid."
            ) from error

        now = time.time()

        # Sliding expiration:
        # an actively used conversation stays alive.
        pipeline = (
            self._redis.pipeline(
                transaction=True
            )
        )

        pipeline.expire(
            key,
            self.ttl_seconds,
        )

        pipeline.zadd(
            self.index_key,
            {
                conversation_id:
                    now
            },
        )

        pipeline.execute()

        return ConversationContext(
            last_interpretation=
                interpretation
        )


    # --------------------------------------------------------
    # Put
    # --------------------------------------------------------

    def put(
        self,
        conversation_id: str,
        interpretation: QuestionInterpretation,
    ) -> None:

        if (
            interpretation.status
            != InterpretationStatus.INTERPRETED
            or interpretation.question_specification
            is None
        ):
            return

        key = self._key(
            conversation_id
        )

        payload = json.dumps(
            {
                "schema_version":
                    self.SCHEMA_VERSION,

                "last_interpretation":
                    interpretation.model_dump(
                        mode="json"
                    ),
            },
            separators=(
                ",",
                ":",
            ),
        )

        now = time.time()

        pipeline = (
            self._redis.pipeline(
                transaction=True
            )
        )

        pipeline.set(
            key,
            payload,
            ex=self.ttl_seconds,
        )

        pipeline.zadd(
            self.index_key,
            {
                conversation_id:
                    now
            },
        )

        pipeline.execute()

        self._prune_to_capacity()


    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------

    def delete(
        self,
        conversation_id: str,
    ) -> bool:

        pipeline = (
            self._redis.pipeline(
                transaction=True
            )
        )

        pipeline.delete(
            self._key(
                conversation_id
            )
        )

        pipeline.zrem(
            self.index_key,
            conversation_id,
        )

        result = (
            pipeline.execute()
        )

        return bool(
            result[0]
        )


    # --------------------------------------------------------
    # Clear
    # --------------------------------------------------------

    def clear(
        self,
    ) -> None:

        keys = list(
            self._redis.scan_iter(
                match=
                    f"{self.key_prefix}:*"
            )
        )

        if keys:

            self._redis.delete(
                *keys
            )


    # --------------------------------------------------------
    # Count
    # --------------------------------------------------------

    def count(
        self,
    ) -> int:

        self._remove_expired_index_members()

        return int(
            self._redis.zcard(
                self.index_key
            )
        )


    # --------------------------------------------------------
    # Close
    # --------------------------------------------------------

    def close(
        self,
    ) -> None:
        """
        Close this client's Redis connections.

        IMPORTANT:
        This deliberately does NOT clear shared conversation
        state. API shutdown must not destroy contexts belonging
        to other replicas or future processes.
        """

        self._redis.close()