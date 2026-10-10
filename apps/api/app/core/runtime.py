from __future__ import annotations

import logging

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


from packages.data_sources import (
    SourceRegistry,
    build_source_health_summary,
    build_source_manifest,
)

from packages.data_sources.fews_ingestion import (
    FewsIngestionError,
    build_fews_source_definition,
    restore_fews_market_prices,
)
from packages.data_sources.providers.fews_market_prices import (
    FEWS_MARKET_SOURCE_ID,
)
from packages.data_sources.snapshot_store import (
    FewsSnapshotStore,
    SnapshotStoreError,
    effective_fews_query,
)

from packages.question_router.router import (
    QuestionRouter,
)

from packages.answering.conversations import (
    ConversationStore,
    RedisConversationStore,
)

from packages.question_router.conversation import (
    ContextualQuestionResolver,
)

from apps.api.app.core.settings import (
    settings,
)


logger = logging.getLogger(__name__)


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


        self.source_registry = (
            SourceRegistry()
        )

        self.fews_snapshot_restore_status = "disabled"
        self._fews_snapshot_query = None
        self._fews_snapshot_for_query = None


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

        if (
            settings.conversation_backend
            == "redis"
        ):

            self.conversation_store = (
                RedisConversationStore(
                    redis_url=
                        settings.redis_url,

                    ttl_seconds=
                        settings
                        .conversation_ttl_seconds,

                    max_conversations=
                        settings.max_conversations,

                    key_prefix=
                        (
                            "agda:"
                            f"{settings.environment}:"
                            "conversation"
                        ),

                )
            )

        else:

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

        # Optional local provenance is separate from Wave 5 readiness.
        self.reload_fews_snapshot()


    # --------------------------------------------------------
    # Stop
    # --------------------------------------------------------

    def stop(
        self,
    ) -> None:

        if self.loader is not None:

            self.loader.close()

        if self.conversation_store is not None:

            self.conversation_store.close()


        self.conversation_store = None

        self.connection = None

        self.ready = False


    # --------------------------------------------------------
    # External source information
    # --------------------------------------------------------

    def reload_fews_snapshot(self) -> None:
        """Restore optional local FEWS provenance without contacting the provider."""
        if settings.fews_snapshot_path is None:
            self.fews_snapshot_restore_status = "disabled"
            return

        try:
            if not self.source_registry.contains(FEWS_MARKET_SOURCE_ID):
                self.source_registry.register(build_fews_source_definition(
                    stale_after_hours=settings.fews_stale_after_hours,
                ))
            stored = restore_fews_market_prices(
                store=FewsSnapshotStore(settings.fews_snapshot_path),
                registry=self.source_registry,
                stale_after_hours=settings.fews_stale_after_hours,
            )
            if stored is None:
                self.fews_snapshot_restore_status = "missing"
                return
            current = self.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID)
            if current == stored.result.snapshot:
                self._fews_snapshot_query = effective_fews_query(stored.query)
                self._fews_snapshot_for_query = current
            self.fews_snapshot_restore_status = "loaded"
        except (FewsIngestionError, SnapshotStoreError, OSError, ValueError):
            self.fews_snapshot_restore_status = "error"
            # Do not expose filesystem paths or provider/storage error details.
            logger.warning("FEWS snapshot restore failed; retaining existing source state.")

    def external_source_manifest(
        self,
    ) -> tuple[
        dict,
        ...
    ]:

        manifest = build_source_manifest(self.source_registry)
        if self._fews_snapshot_query is not None:
            current = self.source_registry.get_snapshot(FEWS_MARKET_SOURCE_ID)
            if current == self._fews_snapshot_for_query:
                for source in manifest:
                    if source["source_id"] == FEWS_MARKET_SOURCE_ID:
                        source["query"] = dict(self._fews_snapshot_query)
        return manifest


    def external_source_health(
        self,
    ) -> dict:

        summary = build_source_health_summary(self.source_registry)
        summary["snapshot_restore_status"] = self.fews_snapshot_restore_status
        return summary


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


            "external_sources":
                self.external_source_health(),
        }


# ============================================================
# PROCESS-SCOPED RUNTIME
# ============================================================

runtime = AgDARuntime()
