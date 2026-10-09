from dataclasses import (
    dataclass,
)
from datetime import (
    datetime,
)

from packages.data_sources.contracts import (
    FreshnessStatus,
    SourceDefinition,
    SourceSnapshot,
    evaluate_freshness,
)


@dataclass(
    frozen=True,
    slots=True,
)
class SourceState:

    definition: SourceDefinition

    snapshot: SourceSnapshot | None

    freshness: FreshnessStatus


class SourceRegistry:

    def __init__(
        self,
    ) -> None:

        self._definitions: dict[
            str,
            SourceDefinition,
        ] = {}

        self._snapshots: dict[
            str,
            SourceSnapshot,
        ] = {}


    def register(
        self,
        definition: SourceDefinition,
    ) -> None:

        source_id = (
            definition.source_id
        )

        if source_id in self._definitions:

            raise ValueError(
                f"External source already registered: "
                f"{source_id}"
            )


        self._definitions[
            source_id
        ] = definition


    def contains(
        self,
        source_id: str,
    ) -> bool:

        return (
            source_id
            in self._definitions
        )


    def get_definition(
        self,
        source_id: str,
    ) -> SourceDefinition:

        try:

            return self._definitions[
                source_id
            ]

        except KeyError as error:

            raise KeyError(
                f"Unknown external source: "
                f"{source_id}"
            ) from error


    def list_definitions(
        self,
    ) -> tuple[
        SourceDefinition,
        ...
    ]:

        return tuple(
            self._definitions[
                source_id
            ]
            for source_id
            in sorted(
                self._definitions
            )
        )


    def record_snapshot(
        self,
        snapshot: SourceSnapshot,
    ) -> None:

        self.get_definition(
            snapshot.source_id
        )

        self._snapshots[
            snapshot.source_id
        ] = snapshot


    def get_snapshot(
        self,
        source_id: str,
    ) -> SourceSnapshot | None:

        self.get_definition(
            source_id
        )

        return self._snapshots.get(
            source_id
        )


    def get_state(
        self,
        source_id: str,
        *,
        now: datetime | None = None,
    ) -> SourceState:

        definition = (
            self.get_definition(
                source_id
            )
        )

        snapshot = (
            self.get_snapshot(
                source_id
            )
        )


        if snapshot is None:

            freshness = (
                FreshnessStatus.UNKNOWN
            )

        else:

            freshness = (
                evaluate_freshness(
                    definition,
                    snapshot,
                    now=now,
                )
            )


        return SourceState(
            definition=
                definition,

            snapshot=
                snapshot,

            freshness=
                freshness,
        )


    def list_states(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[
        SourceState,
        ...
    ]:

        return tuple(
            self.get_state(
                source_id,
                now=now,
            )
            for source_id
            in sorted(
                self._definitions
            )
        )
