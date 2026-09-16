from __future__ import annotations

from collections import OrderedDict
from threading import RLock

from packages.contracts.question import (
    InterpretationStatus,
    QuestionInterpretation,
)

from packages.question_router.conversation import (
    ConversationContext,
)


class ConversationStore:
    """
    Small process-local conversation store for the MVP.

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
            ConversationContext
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