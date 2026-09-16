from __future__ import annotations

from packages.analytics.executor import (
    AnalyticsExecutor,
)

from packages.analytics.question_executor import (
    QuestionSpecificationExecutor,
)

from packages.analytics.registry import (
    MetricRegistry,
)

from packages.answering.pipeline import (
    QuestionPipeline,
)

from packages.answering.service import (
    AnswerService,
)

from packages.data_release.loader import (
    AgDAReleaseLoader,
)

from packages.question_router.router import (
    QuestionRouter,
)

from packages.answering.conversations import (
    ConversationStore,
)

from packages.question_router.conversation import (
    ContextualQuestionResolver,
)

from apps.api.app.core.settings import (
    settings,
)


# ============================================================
# AgDA APPLICATION RUNTIME
# ============================================================

class AgDARuntime:

    def __init__(self):

        self.loader = None

        self.connection = None

        self.registry = None

        self.analytics_executor = None

        self.specification_executor = None

        self.router = None

        self.pipeline = None

        self.answer_service = None

        self.release_info = None

        self.ready = False

        self.contextual_resolver = None

        self.conversation_store = None


    # --------------------------------------------------------
    # Start
    # --------------------------------------------------------

    def start(
        self,
    ) -> None:

        if self.ready:
            return


        self.loader = (
            AgDAReleaseLoader()
        )

        self.connection = (
            self.loader.open()
        )

        self.release_info = (
            self.loader.release_info()
        )


        self.registry = (
            MetricRegistry.from_connection(
                self.connection
            )
        )


        self.analytics_executor = (
            AnalyticsExecutor(
                connection=
                    self.connection,

                registry=
                    self.registry,
            )
        )


        self.specification_executor = (
            QuestionSpecificationExecutor(
                executor=
                    self.analytics_executor,

                registry=
                    self.registry,

                metric_version=
                    self.release_info[
                        "metric_version"
                    ],
            )
        )


        self.router = (
            QuestionRouter(
                connection=
                    self.connection,

                registry=
                    self.registry,

                metric_version=
                    self.release_info[
                        "metric_version"
                    ],
            )
        )

        self.contextual_resolver = (
            ContextualQuestionResolver(
                router=
                    self.router
            )
        )


        self.conversation_store = (
            ConversationStore(
                max_conversations=
                    settings.max_conversations
            )
        )

        
        self.pipeline = (
            QuestionPipeline(
                router=
                    self.router,

                specification_executor=
                    self.specification_executor,

                contextual_resolver=
                    self.contextual_resolver,
            )
        )


        self.answer_service = (
            AnswerService(
                pipeline=
                    self.pipeline,

                data_version=
                    self.release_info[
                        "data_version"
                    ],

                metric_version=
                    self.release_info[
                        "metric_version"
                    ],
            )
        )


        self.ready = True


    # --------------------------------------------------------
    # Stop
    # --------------------------------------------------------

    def stop(
        self,
    ) -> None:

        if self.loader is not None:

            self.loader.close()

        if self.conversation_store is not None:

            self.conversation_store.clear()

        
        self.connection = None

        self.ready = False


    # --------------------------------------------------------
    # Health information
    # --------------------------------------------------------

    def health(
        self,
    ) -> dict:

        return {
            "status":
                (
                    "ready"
                    if self.ready
                    else "not_ready"
                ),

            "ready":
                self.ready,

            "environment":
                settings.environment,

            "conversation_contexts":
                (
                    self.conversation_store.count()
                    if self.conversation_store
                    is not None
                    else 0
                ),

            "data_version":
                (
                    self.release_info[
                        "data_version"
                    ]
                    if self.release_info
                    else None
                ),

            "release_state":
                (
                    self.release_info[
                        "release_state"
                    ]
                    if self.release_info
                    else None
                ),

            "metric_version":
                (
                    self.release_info[
                        "metric_version"
                    ]
                    if self.release_info
                    else None
                ),

            "registered_metrics":
                (
                    self.registry.count()
                    if self.registry
                    else 0
                ),
        }


# ============================================================
# PROCESS-SCOPED RUNTIME
# ============================================================

runtime = AgDARuntime()